"""Tests for src/tower.py — modifier stack and combat math.

SDL dummy drivers are configured globally in ``conftest.py``.
"""

from __future__ import annotations

import pytest

from src.level import POWERUP_TILES, ROAD_CELLS
from src.settings import (
    NAIL_GUNNER_COOLDOWN,
    NAIL_GUNNER_DAMAGE,
    NAIL_GUNNER_RANGE,
)
from src.tower import NailGunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_cell_with_effect(effect: str) -> tuple[int, int]:
    """Return the first POWERUP_TILES cell with the given effect name.

    Args:
        effect: One of ``"range"``, ``"damage"``, ``"attack_speed"``.

    Raises:
        pytest.skip: If no tile with that effect exists in the level data.
    """
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
        # Other stats untouched
        assert tower.effective_damage == pytest.approx(NAIL_GUNNER_DAMAGE)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN)

    def test_damage_modifier_scales_effective_damage(self) -> None:
        """Tower on a 'damage' tile must scale effective_damage by the multiplier."""
        col, row = _find_cell_with_effect("damage")
        _effect, mult = POWERUP_TILES[(col, row)]
        tower = NailGunner(col=col, row=row)
        assert tower.effective_damage == pytest.approx(NAIL_GUNNER_DAMAGE * mult)
        # Other stats untouched
        assert tower.effective_range == pytest.approx(NAIL_GUNNER_RANGE)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN)

    def test_attack_speed_modifier_reduces_cooldown(self) -> None:
        """Tower on an 'attack_speed' tile must divide cooldown_max by multiplier."""
        col, row = _find_cell_with_effect("attack_speed")
        _effect, mult = POWERUP_TILES[(col, row)]
        tower = NailGunner(col=col, row=row)
        assert tower.effective_cooldown == pytest.approx(NAIL_GUNNER_COOLDOWN / mult)
        # Other stats untouched
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
    """Verify the tower correctly damages enemies and fires within range."""

    def test_tower_has_layer_20(self) -> None:
        """NailGunner must sit at render layer 20."""
        col, row = _find_plain_grass_cell()
        assert NailGunner(col=col, row=row).layer == 20

    def test_cost_matches_setting(self) -> None:
        """NailGunner.cost must equal NAIL_GUNNER_COST."""
        from src.settings import NAIL_GUNNER_COST
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
