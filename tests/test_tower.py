"""Tests for src/tower.py & src/projectile.py — modifier stack, combat, upgrades, and prediction.

SDL dummy drivers are configured globally in ``conftest.py``.
"""

from __future__ import annotations

import pygame
import pytest

from src.economy import Economy
from src.enemy import Enemy, RainCloud, Rotted2x4, SpeedModifier
from src.level import load_level
from src.projectile import ConcreteGlob, TarpProjectile
from src.settings import (
    CONCRETE_GLOB_SPEED,
    CONCRETE_PUMP_COOLDOWN,
    CONCRETE_PUMP_COST,
    CONCRETE_PUMP_DAMAGE,
    CONCRETE_PUMP_RANGE,
    CONCRETE_PUMP_TIER2_COST,
    CONCRETE_PUMP_TIER3_COST,
    CONCRETE_SPLASH_RADIUS,
    NAIL_GUNNER_COOLDOWN,
    NAIL_GUNNER_COST,
    NAIL_GUNNER_DAMAGE,
    NAIL_GUNNER_RANGE,
    NAIL_GUNNER_TIER2_COST,
    NAIL_GUNNER_TIER3_COST,
)
from src.tower import ConcretePump, NailGunner, TarpCannon, Tower
from src.world import World

_DEFAULT_LEVEL = load_level("level_1.json")
POWERUP_TILES = _DEFAULT_LEVEL.powerup_tiles
ROAD_CELLS = _DEFAULT_LEVEL.road_cells

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
# Combat & Base Tower
# ---------------------------------------------------------------------------


class TestCombat:
    """Verify NailGunner hitscan firing and rewards."""

    def test_tower_base_class(self) -> None:
        """NailGunner and ConcretePump are instances of Tower."""
        col, row = _find_plain_grass_cell()
        assert isinstance(NailGunner(col=col, row=row), Tower)
        assert isinstance(ConcretePump(col=col, row=row), Tower)

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

    def test_disabled_tower_does_not_fire(self) -> None:
        """Tower with is_disabled=True returns immediately without shooting."""
        col, row = _find_plain_grass_cell()
        tower = NailGunner(col=col, row=row)
        tower.is_disabled = True
        enemy = Enemy(
            pos=pygame.Vector2(tower.center.x + 20, tower.center.y),
            health=10.0,
        )
        world = World(enemies=[enemy], economy=Economy())

        tower.update(0.1, world)
        assert enemy.alive is True  # Unharmed because tower was disabled


# ---------------------------------------------------------------------------
# Tower Upgrades
# ---------------------------------------------------------------------------


class TestTowerUpgrades:
    """Verify NailGunner and ConcretePump upgrade trees."""

    def test_nail_gunner_tier_2_upgrade(self) -> None:
        """Tier 2 Pneumatic Overdrive halves base cooldown and increments invested."""
        col, row = _find_plain_grass_cell()
        tower = NailGunner(col=col, row=row)
        assert tower.invested == NAIL_GUNNER_COST
        assert tower.upgrade_level == 1
        assert tower.next_upgrade_cost == NAIL_GUNNER_TIER2_COST
        assert tower.next_upgrade_name == "Pneumatic Overdrive"

        tower.upgrade()

        assert tower.upgrade_level == 2
        assert tower.cooldown_max == pytest.approx(NAIL_GUNNER_COOLDOWN / 2.0)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN / 2.0)
        assert tower.invested == NAIL_GUNNER_COST + NAIL_GUNNER_TIER2_COST

    def test_nail_gunner_tier_3_upgrade(self) -> None:
        """Tier 3 The Scaffold doubles range and enables air targeting."""
        col, row = _find_plain_grass_cell()
        tower = NailGunner(col=col, row=row)
        tower.upgrade()  # to tier 2
        assert tower.can_target_air is False

        assert tower.next_upgrade_cost == NAIL_GUNNER_TIER3_COST
        assert tower.next_upgrade_name == "The Scaffold"

        tower.upgrade()  # to tier 3

        assert tower.upgrade_level == 3
        assert tower.base_range == pytest.approx(NAIL_GUNNER_RANGE * 2.0)
        assert tower.effective_range == pytest.approx(NAIL_GUNNER_RANGE * 2.0)
        assert tower.can_target_air is True
        assert tower.invested == (
            NAIL_GUNNER_COST + NAIL_GUNNER_TIER2_COST + NAIL_GUNNER_TIER3_COST
        )
        assert tower.next_upgrade_cost is None

    def test_air_targeting_restriction(self) -> None:
        """Ground towers cannot target RainCloud; Tier 3 Scaffold NailGunner can."""
        col, row = _find_plain_grass_cell()
        t_ground = NailGunner(col=col, row=row)
        t_scaffold = NailGunner(col=col, row=row)
        t_scaffold.upgrade()
        t_scaffold.upgrade()  # Tier 3

        cloud = RainCloud(pos=pygame.Vector2(t_ground.center.x + 30, t_ground.center.y))

        # Ground tower finds no target
        assert t_ground._nearest_enemy([cloud]) is None  # noqa: SLF001

        # Scaffold tower targets cloud
        assert t_scaffold._nearest_enemy([cloud]) is cloud  # noqa: SLF001

    def test_concrete_pump_upgrades(self) -> None:
        """Tier 2 increases slow debuff to 0.2x; Tier 3 doubles splash radius."""
        col, row = _find_plain_grass_cell()
        pump = ConcretePump(col=col, row=row)
        assert pump.slow_multiplier == 0.5
        assert pump.splash_radius == CONCRETE_SPLASH_RADIUS

        # Upgrade to Tier 2
        pump.upgrade()
        assert pump.upgrade_level == 2
        assert pump.slow_multiplier == 0.2
        assert pump.invested == CONCRETE_PUMP_COST + CONCRETE_PUMP_TIER2_COST

        # Upgrade to Tier 3
        pump.upgrade()
        assert pump.upgrade_level == 3
        assert pump.splash_radius == pytest.approx(CONCRETE_SPLASH_RADIUS * 2.0)
        assert pump.invested == (
            CONCRETE_PUMP_COST + CONCRETE_PUMP_TIER2_COST + CONCRETE_PUMP_TIER3_COST
        )


# ---------------------------------------------------------------------------
# Concrete Pump & Projectiles
# ---------------------------------------------------------------------------


class TestConcretePumpAndGlob:
    """Verify ConcretePump target leading and ConcreteGlob splash damage."""

    def test_concrete_pump_base_stats(self) -> None:
        """ConcretePump base stats match settings."""
        col, row = _find_plain_grass_cell()
        pump = ConcretePump(col=col, row=row)
        assert pump.cost == CONCRETE_PUMP_COST
        assert pump.base_range == CONCRETE_PUMP_RANGE
        assert pump.cooldown_max == CONCRETE_PUMP_COOLDOWN
        assert pump.base_damage == CONCRETE_PUMP_DAMAGE
        assert pump.layer == 20

    def test_concrete_pump_leads_target(self) -> None:
        """ConcretePump predicts target position based on flight time with 3-pass iteration."""
        col, row = _find_plain_grass_cell()
        pump = ConcretePump(col=col, row=row)
        # Enemy moving horizontally at 100 px/s
        enemy = Rotted2x4(
            pos=pygame.Vector2(pump.center.x + 100, pump.center.y),
            speed=100.0,
        )
        world = World(enemies=[enemy])

        aim = pygame.Vector2(enemy.pos)
        for _ in range(3):
            flight = pump.center.distance_to(aim) / CONCRETE_GLOB_SPEED
            aim = enemy.predict_pos(flight)
        expected_lead = aim

        pump.update(0.1, world)

        assert len(world.projectiles) == 1
        glob = world.projectiles[0]
        assert isinstance(glob, ConcreteGlob)
        assert glob.target_pos == expected_lead

    def test_concrete_glob_detonates_and_slows_in_splash(self) -> None:
        """ConcreteGlob splash damages and applies SpeedModifier to all enemies in radius."""
        target = pygame.Vector2(200, 200)
        glob = ConcreteGlob(
            pos=pygame.Vector2(195, 200),
            target_pos=target,
            speed=200.0,
            damage=5.0,
        )

        e1 = Rotted2x4(pos=pygame.Vector2(220, 200), health=50.0)
        e2 = Rotted2x4(pos=pygame.Vector2(400, 400), health=50.0)

        world = World(enemies=[e1, e2], projectiles=[glob])

        glob.update(0.1, world)

        assert glob.alive is False
        assert e1.health == 45.0
        assert "speed" in e1.modifiers
        speed_mod = e1.modifiers["speed"]
        assert isinstance(speed_mod, SpeedModifier)
        assert speed_mod.multiplier == 0.5
        assert speed_mod.duration == 3.0
        assert e2.health == 50.0


# ---------------------------------------------------------------------------
# TarpCannon and TarpProjectile
# ---------------------------------------------------------------------------


class TestTarpCannonAndProjectile:
    """Validate TarpCannon anti-air prioritization and TarpProjectile homing mechanics."""

    def test_tarp_cannon_initial_stats(self) -> None:
        """TarpCannon initializes with cost 400, cooldown 0.3s, range 160, and damage 10."""
        cannon = TarpCannon(col=2, row=2)
        assert cannon.cost == 400
        assert cannon.invested == 400
        assert cannon.cooldown_max == 0.3
        assert cannon.base_range == 160.0
        assert cannon.base_damage == 10.0
        assert cannon.can_target_air is True

    def test_tarp_cannon_prioritizes_flying_enemies(self) -> None:
        """TarpCannon targets flying enemies (RainCloud) over closer ground enemies."""
        cannon = TarpCannon(col=4, row=4)
        cannon.center = pygame.Vector2(200, 200)

        # Ground enemy is closer (50px away)
        ground_creep = Rotted2x4(pos=pygame.Vector2(250, 200))
        # Flying enemy is further but within range (100px away < 160px)
        air_creep = RainCloud(pos=pygame.Vector2(300, 200))

        world = World(enemies=[ground_creep, air_creep])
        target = cannon._nearest_enemy(world.enemies)

        assert target is air_creep

    def test_tarp_cannon_falls_back_to_ground_targets(self) -> None:
        """TarpCannon targets ground enemies when no flying enemies are present."""
        cannon = TarpCannon(col=4, row=4)
        cannon.center = pygame.Vector2(200, 200)

        ground_creep = Rotted2x4(pos=pygame.Vector2(250, 200))
        world = World(enemies=[ground_creep])

        target = cannon._nearest_enemy(world.enemies)
        assert target is ground_creep

    def test_tarp_cannon_fires_tarp_projectile(self) -> None:
        """Updating TarpCannon when target in range spawns a TarpProjectile."""
        cannon = TarpCannon(col=4, row=4)
        cannon.center = pygame.Vector2(200, 200)
        cloud = RainCloud(pos=pygame.Vector2(260, 200))
        world = World(enemies=[cloud])

        cannon.update(0.1, world)

        assert len(world.projectiles) == 1
        tarp = world.projectiles[0]
        assert isinstance(tarp, TarpProjectile)
        assert tarp.target is cloud

    def test_tarp_projectile_homes_and_damages(self) -> None:
        """TarpProjectile moves toward target, hits, and deals damage."""
        cloud = RainCloud(pos=pygame.Vector2(220, 200), health=60.0)
        proj = TarpProjectile(
            pos=pygame.Vector2(200, 200),
            target=cloud,
            speed=400.0,
            damage=10.0,
        )
        world = World(enemies=[cloud], projectiles=[proj])

        # At speed 400, dt 0.1 travels 40px, reaching distance 20px easily
        proj.update(0.1, world)

        assert proj.alive is False
        assert cloud.health == 50.0

    def test_tarp_projectile_awards_bounty_on_kill(self) -> None:
        """Killing an enemy with a TarpProjectile grants its bounty to the world."""
        cloud = RainCloud(pos=pygame.Vector2(205, 200), health=5.0)
        proj = TarpProjectile(
            pos=pygame.Vector2(200, 200),
            target=cloud,
            speed=400.0,
            damage=10.0,
        )
        economy = Economy(project_budget=100)
        world = World(enemies=[cloud], projectiles=[proj], economy=economy)

        proj.update(0.1, world)
        world.flush_earnings()

        assert proj.alive is False
        assert cloud.alive is False
        assert world.economy.project_budget == 100 + cloud.bounty

    def test_tarp_cannon_upgrades(self) -> None:
        """TarpCannon upgrades through Tier 2 (Sticky Resin) and Tier 3 (EMP Net)."""
        cannon = TarpCannon(col=2, row=2)
        assert cannon.upgrade_level == 1
        assert cannon.next_upgrade_name == "Sticky Resin"
        assert cannon.next_upgrade_cost == 500

        cannon.upgrade()
        assert cannon.upgrade_level == 2
        assert cannon.invested == 900  # 400 + 500
        assert cannon.next_upgrade_name == "EMP Net"
        assert cannon.next_upgrade_cost == 1200

        cannon.upgrade()
        assert cannon.upgrade_level == 3
        assert cannon.invested == 2100  # 900 + 1200
        assert cannon.next_upgrade_name is None
        assert cannon.next_upgrade_cost is None

    def test_tarp_cannon_tier2_applies_slow_to_flyers(self) -> None:
        """Tier 2 TarpCannon projectile applies 0.3x speed modifier to flying targets."""
        cannon = TarpCannon(col=4, row=4)
        cannon.center = pygame.Vector2(200, 200)
        cannon.upgrade_level = 2

        cloud = RainCloud(pos=pygame.Vector2(220, 200), health=60.0)
        world = World(enemies=[cloud])

        cannon.update(0.1, world)
        assert len(world.projectiles) == 1
        proj = world.projectiles[0]
        assert isinstance(proj, TarpProjectile)
        assert proj.slow_multiplier == 0.3

        # Projectile hits cloud
        proj.update(0.1, world)
        assert proj.alive is False
        assert "speed" in cloud.modifiers
        cloud_mod = cloud.modifiers["speed"]
        assert isinstance(cloud_mod, SpeedModifier)
        assert cloud_mod.multiplier == 0.3

    def test_tarp_cannon_tier3_applies_stun_to_targets(self) -> None:
        """Tier 3 TarpCannon projectile applies 1.5s stun to targets."""
        cannon = TarpCannon(col=4, row=4)
        cannon.center = pygame.Vector2(200, 200)
        cannon.upgrade_level = 3

        creep = Rotted2x4(pos=pygame.Vector2(220, 200), health=60.0)
        world = World(enemies=[creep])

        cannon.update(0.1, world)
        assert len(world.projectiles) == 1
        proj = world.projectiles[0]
        assert isinstance(proj, TarpProjectile)
        assert proj.stun_duration == 1.5

        proj.update(0.1, world)
        assert proj.alive is False
        assert "stun" in creep.modifiers
        assert creep.modifiers["stun"].duration == 1.5

    def test_tarp_projectile_retargets_when_original_target_dies(self) -> None:
        """If original target dies mid-flight, TarpProjectile retargets closest living enemy."""
        original = Rotted2x4(pos=pygame.Vector2(250, 200), health=10.0)
        second = Rotted2x4(pos=pygame.Vector2(260, 200), health=50.0)

        proj = TarpProjectile(
            pos=pygame.Vector2(200, 200),
            target=original,
            speed=200.0,
            damage=10.0,
        )
        world = World(enemies=[original, second], projectiles=[proj])

        # Kill original target before projectile arrives
        original.alive = False

        # Next update triggers retargeting to 'second'
        proj.update(0.1, world)
        assert proj.alive is True
        assert proj.target is second

    def test_tarp_projectile_dies_if_no_enemies_left_to_retarget(self) -> None:
        """If all enemies are dead, TarpProjectile marks alive=False."""
        original = Rotted2x4(pos=pygame.Vector2(250, 200), health=10.0)
        proj = TarpProjectile(
            pos=pygame.Vector2(200, 200),
            target=original,
            speed=200.0,
            damage=10.0,
        )
        world = World(enemies=[original], projectiles=[proj])

        original.alive = False
        proj.update(0.1, world)
        assert proj.alive is False
        assert proj.target is None
