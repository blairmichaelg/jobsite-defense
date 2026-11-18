"""Tests for src/level.py — road geometry and power-up placement.

SDL dummy drivers are configured globally in ``conftest.py``; no
``os.environ`` setup is needed here.
"""

from __future__ import annotations

import pygame
import pytest

from src.enemy import HOABoardMember, OshaInspector, RainCloud, Rotted2x4
from src.level import (
    POWERUP_TILES,
    ROAD_CELLS,
    WAYPOINT_PIXELS,
    WAYPOINTS,
    LevelData,
    _build_road,
    load_level,
)
from src.settings import CELL_SIZE, GRID_COLS, GRID_ROWS

# ---------------------------------------------------------------------------
# Road geometry
# ---------------------------------------------------------------------------


class TestRoadCells:
    """Validate the rasterised road is geometrically sound."""

    def test_road_is_non_empty(self) -> None:
        """ROAD_CELLS must contain at least one cell."""
        assert len(ROAD_CELLS) > 0

    def test_all_cells_within_grid(self) -> None:
        """Every road cell must lie inside the visible grid."""
        for col, row in ROAD_CELLS:
            assert 0 <= col < GRID_COLS, f"col {col} out of range"
            assert 0 <= row < GRID_ROWS, f"row {row} out of range"

    def test_road_cells_are_contiguous(self) -> None:
        """Every road cell must share at least one edge with another road cell."""
        for col, row in ROAD_CELLS:
            neighbours = {
                (col - 1, row),
                (col + 1, row),
                (col, row - 1),
                (col, row + 1),
            }
            assert neighbours & ROAD_CELLS, (
                f"Road cell ({col},{row}) has no adjacent road neighbours — path gap!"
            )

    def test_diagonal_waypoints_raise(self) -> None:
        """_build_road must raise ValueError for a diagonal waypoint pair."""
        bad_waypoints: tuple[tuple[int, int], ...] = ((0, 0), (3, 3))
        with pytest.raises(ValueError, match="Diagonal segment"):
            _build_road(bad_waypoints)

    def test_spawn_and_exit_excluded(self) -> None:
        """Off-screen spawn (-1, 1) and exit (16, 10) must not be in ROAD_CELLS."""
        spawn_col, spawn_row = WAYPOINTS[0]
        exit_col, exit_row = WAYPOINTS[-1]
        assert (spawn_col, spawn_row) not in ROAD_CELLS, "Spawn cell is off-screen"
        assert (exit_col, exit_row) not in ROAD_CELLS, "Exit cell is off-screen"


# ---------------------------------------------------------------------------
# Power-up tiles
# ---------------------------------------------------------------------------


class TestPowerupTiles:
    """Validate power-up placement constraints."""

    def test_powerups_do_not_overlap_road(self) -> None:
        """No power-up tile may sit on a road cell."""
        overlap = frozenset(POWERUP_TILES) & ROAD_CELLS
        assert not overlap, f"Power-up tile(s) overlap road: {sorted(overlap)}"

    def test_powerups_within_grid(self) -> None:
        """Every power-up tile must be inside the visible grid."""
        for col, row in POWERUP_TILES:
            assert 0 <= col < GRID_COLS, f"Power-up col {col} out of range"
            assert 0 <= row < GRID_ROWS, f"Power-up row {row} out of range"

    def test_known_effects(self) -> None:
        """Every power-up must use a recognised effect name."""
        valid = {"attack_speed", "damage", "range"}
        for key, (effect, _) in POWERUP_TILES.items():
            assert effect in valid, f"Unknown effect '{effect}' at {key}"


# ---------------------------------------------------------------------------
# Waypoint pixels — now tuple[tuple[float, float], ...]
# ---------------------------------------------------------------------------


class TestWaypointPixels:
    """Validate pre-computed pixel waypoints (primitive float pairs)."""

    def test_pixel_count_matches_waypoints(self) -> None:
        """WAYPOINT_PIXELS must have the same length as WAYPOINTS."""
        assert len(WAYPOINT_PIXELS) == len(WAYPOINTS)

    def test_pixel_values_match_formula(self) -> None:
        """Each pixel pair must equal col*CELL_SIZE + half, row*CELL_SIZE + half."""
        half = CELL_SIZE / 2.0
        for (col, row), (px, py) in zip(WAYPOINTS, WAYPOINT_PIXELS, strict=False):
            expected_x = col * CELL_SIZE + half
            expected_y = row * CELL_SIZE + half
            assert abs(px - expected_x) < 0.01, f"x mismatch at ({col},{row})"
            assert abs(py - expected_y) < 0.01, f"y mismatch at ({col},{row})"

    def test_pixels_are_plain_tuples(self) -> None:
        """WAYPOINT_PIXELS entries must be plain tuples, not Vector2 objects."""
        for entry in WAYPOINT_PIXELS:
            assert isinstance(entry, tuple), (
                f"Expected tuple, got {type(entry).__name__}: {entry!r}"
            )
            assert not isinstance(entry, pygame.Vector2), (
                "WAYPOINT_PIXELS must not store mutable Vector2 objects"
            )

    def test_vector2_construction_from_pixels(self) -> None:
        """Constructing a Vector2 from each pixel pair must work correctly."""
        for (col, row), px in zip(WAYPOINTS, WAYPOINT_PIXELS, strict=False):
            v = pygame.Vector2(*px)
            half = CELL_SIZE / 2.0
            assert abs(v.x - (col * CELL_SIZE + half)) < 0.01
            assert abs(v.y - (row * CELL_SIZE + half)) < 0.01


# ---------------------------------------------------------------------------
# JSON Level Loader
# ---------------------------------------------------------------------------


class TestJsonLevelLoader:
    """Validate parsing of external JSON level definitions."""

    def test_load_level_1_file(self) -> None:
        """load_level successfully parses levels/level_1.json."""
        lvl = load_level("levels/level_1.json")
        assert isinstance(lvl, LevelData)
        assert lvl.name == "The Foundation"
        assert lvl.waypoints == ((-1, 1), (6, 1), (6, 8), (16, 8))
        assert len(lvl.waypoint_pixels) == 4
        assert len(lvl.road_cells) > 0
        assert (4, 0) in lvl.powerup_tiles
        assert lvl.powerup_tiles[(4, 0)] == ("attack_speed", 1.25)
        assert len(lvl.waves) == 1
        wave = lvl.waves[0]
        assert wave.enemy is Rotted2x4
        assert wave.count == 10
        assert wave.interval == 1.0

    def test_load_custom_level_json(self, tmp_path: pytest.TempPathFactory) -> None:
        """load_level correctly decodes multiple wave specs and powerup entries."""
        import json

        custom_data = {
            "name": "Custom Blueprint",
            "waypoints": [[-1, 5], [10, 5], [10, 10], [16, 10]],
            "powerups": {
                "2, 2": ["damage", 1.5],
                "5, 8": ["range", 1.2],
            },
            "waves": [
                {"enemy": "Rotted2x4", "count": 5, "interval": 0.5},
                {"enemy": "HOABoardMember", "count": 8, "interval": 0.3},
                {"enemy": "RainCloud", "count": 3, "interval": 2.0},
                {"enemy": "OshaInspector", "count": 1, "interval": 1.0},
            ],
        }

        path = tmp_path / "custom_level.json"  # type: ignore[operator]
        path.write_text(json.dumps(custom_data), encoding="utf-8")

        lvl = load_level(str(path))
        assert lvl.name == "Custom Blueprint"
        assert lvl.waypoints == ((-1, 5), (10, 5), (10, 10), (16, 10))
        assert lvl.powerup_tiles[(2, 2)] == ("damage", 1.5)
        assert lvl.powerup_tiles[(5, 8)] == ("range", 1.2)
        assert len(lvl.waves) == 4
        assert lvl.waves[0].enemy is Rotted2x4
        assert lvl.waves[1].enemy is HOABoardMember
        assert lvl.waves[2].enemy is RainCloud
        assert lvl.waves[3].enemy is OshaInspector
