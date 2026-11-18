"""Tests for src/tower.py & src/projectile.py — modifier stack, combat, and AoE globs.

SDL dummy drivers are configured globally in ``conftest.py``.
"""

from __future__ import annotations

import pygame
import pytest

from src.economy import Economy
from src.enemy import Enemy, Rotted2x4
from src.level import POWERUP_TILES, ROAD_CELLS
from src.projectile import ConcreteGlob
from src.settings import (
    CONCRETE_PUMP_COOLDOWN,
    CONCRETE_PUMP_COST,
    CONCRETE_PUMP_DAMAGE,
    CONCRETE_PUMP_RANGE,
    NAIL_GUNNER_COOLDOWN,
    NAIL_GUNNER_COST,
    NAIL_GUNNER_DAMAGE,
    NAIL_GUNNER_RANGE,
)
from src.tower import ConcretePump, NailGunner
from src.world import World

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_cell_with_effect(effect: str) -> tuple[int, int]:
    """Return the first POWERUP_TILES cell with the given effect name."""
    for (col, row), (eff, _mult) in POWERUP_TILES.items():
        if eff == effect:
            return (col, row)
    pytest.skip(f"No '{effect}' power-up tile defined in level data")


def _find_plain_grass_cell() -> tuple[int, int]:
    """Return a cell that is neither road nor power-up."""
    from src.settings import GRID_COLS, GRID_ROWS

    for col in range(GRID_COLS):
        for row in range(GRID_ROWS):
            if (col, row) not in ROAD_CELLS and (col, row) not in POWERUP_TILES:
                return (col, row)
    pytest.skip("No plain grass cell available")


# ---------------------------------------------------------------------------
# Modifier stack
# ---------------------------------------------------------------------------


class TestModifiers:
    """Verify all three power-up effects apply correctly to NailGunner."""

    def test_no_modifier_on_plain_grass(self) -> None:
        """Tower on plain grass must have exact base stats."""
        col, row = _find_plain_grass_cell()
        tower = NailGunner(col=col, row=row)
        assert tower.effective_range == pytest.approx(NAIL_GUNNER_RANGE)
        assert tower.effective_damage == pytest.approx(NAIL_GUNNER_DAMAGE)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN)

    def test_range_modifier_scales_effective_range(self) -> None:
        """Tower on a 'range' tile must scale effective_range by the multiplier."""
        col, row = _find_cell_with_effect("range")
        _effect, mult = POWERUP_TILES[(col, row)]
        tower = NailGunner(col=col, row=row)
        assert tower.effective_range == pytest.approx(NAIL_GUNNER_RANGE * mult)
        assert tower.effective_damage == pytest.approx(NAIL_GUNNER_DAMAGE)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN)

    def test_damage_modifier_scales_effective_damage(self) -> None:
        """Tower on a 'damage' tile must scale effective_damage by the multiplier."""
        col, row = _find_cell_with_effect("damage")
        _effect, mult = POWERUP_TILES[(col, row)]
        tower = NailGunner(col=col, row=row)
        assert tower.effective_damage == pytest.approx(NAIL_GUNNER_DAMAGE * mult)
        assert tower.effective_range == pytest.approx(NAIL_GUNNER_RANGE)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN)

    def test_attack_speed_modifier_reduces_cooldown(self) -> None:
        """Tower on an 'attack_speed' tile must divide cooldown_max by multiplier."""
        col, row = _find_cell_with_effect("attack_speed")
        _effect, mult = POWERUP_TILES[(col, row)]
        tower = NailGunner(col=col, row=row)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN / mult)
        assert tower.effective_range == pytest.approx(NAIL_GUNNER_RANGE)
        assert tower.effective_damage == pytest.approx(NAIL_GUNNER_DAMAGE)

    def test_range_sq_matches_effective_range_squared(self) -> None:
        """_range_sq must equal effective_range ** 2 for all modifier types."""
        for (col, row) in list(POWERUP_TILES.keys()) + [_find_plain_grass_cell()]:
            if (col, row) in ROAD_CELLS:
                continue
            tower = NailGunner(col=col, row=row)
            assert tower._range_sq == pytest.approx(tower.effective_range ** 2), (  # noqa: SLF001
                f"_range_sq mismatch at ({col},{row})"
            )

    def test_attack_speed_faster_than_base(self) -> None:
        """effective_cooldown on attack_speed tile must be shorter than base."""
        col, row = _find_cell_with_effect("attack_speed")
        tower = NailGunner(col=col, row=row)
        assert tower.effective_cooldown < NAIL_GUNNER_COOLDOWN


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------


class TestCombat:
    """Verify NailGunner hitscan firing and rewards."""

    def test_tower_has_layer_20(self) -> None:
        """NailGunner must sit at render layer 20."""
        col, row = _find_plain_grass_cell()
        assert NailGunner(col=col, row=row).layer == 20

    def test_cost_matches_setting(self) -> None:
        """NailGunner.cost must equal NAIL_GUNNER_COST."""
        col, row = _find_plain_grass_cell()
        assert NailGunner(col=col, row=row).cost == NAIL_GUNNER_COST

    def test_center_computed_from_cell(self) -> None:
        """Tower centre must be the pixel centre of its grid cell."""
        from src.settings import CELL_SIZE

        col, row = _find_plain_grass_cell()
        tower = NailGunner(col=col, row=row)
        half = CELL_SIZE // 2
        assert tower.center.x == col * CELL_SIZE + half
        assert tower.center.y == row * CELL_SIZE + half

    def test_nail_gunner_shoots_and_awards_bounty(self) -> None:
        """NailGunner kills low-HP enemy in range and queues enemy bounty."""
        col, row = _find_plain_grass_cell()
        tower = NailGunner(col=col, row=row)
        enemy = Enemy(
            pos=pygame.Vector2(tower.center.x + 20, tower.center.y),
            health=10.0,
            bounty=15,
        )
        world = World(enemies=[enemy], economy=Economy())

        tower.update(0.1, world)

        assert enemy.alive is False
        assert world._pending_earn == 15  # noqa: SLF001


# ---------------------------------------------------------------------------
# Concrete Pump & Projectiles
# ---------------------------------------------------------------------------


class TestConcretePumpAndGlob:
    """Verify ConcretePump artillery and ConcreteGlob splash damage."""

    def test_concrete_pump_base_stats(self) -> None:
        """ConcretePump base stats match settings."""
        col, row = _find_plain_grass_cell()
        pump = ConcretePump(col=col, row=row)
        assert pump.cost == CONCRETE_PUMP_COST
        assert pump.base_range == CONCRETE_PUMP_RANGE
        assert pump.cooldown_max == CONCRETE_PUMP_COOLDOWN
        assert pump.base_damage == CONCRETE_PUMP_DAMAGE
        assert pump.layer == 20

    def test_concrete_pump_spawns_projectile(self) -> None:
        """ConcretePump spawns a ConcreteGlob in world.projectiles when firing."""
        col, row = _find_plain_grass_cell()
        pump = ConcretePump(col=col, row=row)
        enemy = Rotted2x4(pos=pygame.Vector2(pump.center.x + 30, pump.center.y))
        world = World(enemies=[enemy])

        pump.update(0.1, world)

        assert len(world.projectiles) == 1
        glob = world.projectiles[0]
        assert isinstance(glob, ConcreteGlob)
        assert glob.target_pos == enemy.pos
        assert pump._cooldown_remaining > 0.0  # noqa: SLF001

    def test_concrete_glob_detonates_and_slows_in_splash(self) -> None:
        """ConcreteGlob splash damages and applies SpeedModifier to all enemies in radius."""
        target = pygame.Vector2(200, 200)
        glob = ConcreteGlob(
            pos=pygame.Vector2(195, 200),
            target_pos=target,
            speed=200.0,
            damage=5.0,
        )

        # Enemy inside 90px splash radius
        e1 = Rotted2x4(pos=pygame.Vector2(220, 200), health=50.0)
        # Enemy outside splash radius
        e2 = Rotted2x4(pos=pygame.Vector2(400, 400), health=50.0)

        world = World(enemies=[e1, e2], projectiles=[glob])

        # Step 0.1s: glob covers 20px, easily reaching target (5px away)
        glob.update(0.1, world)

        assert glob.alive is False
        assert e1.health == 45.0  # 50 - 5 damage
        assert "speed" in e1.modifiers
        assert e1.modifiers["speed"].multiplier == 0.5
        assert e1.modifiers["speed"].duration == 3.0

        # Outside enemy unaffected
        assert e2.health == 50.0
        assert "speed" not in e2.modifiers
