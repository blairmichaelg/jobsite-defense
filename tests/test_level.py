"""Tests for src/level.py — road geometry and power-up placement."""

from __future__ import annotations

import os

# Ensure pygame can initialise in a headless CI environment.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.level import (
    POWERUP_TILES,
    ROAD_CELLS,
    WAYPOINT_PIXELS,
    WAYPOINTS,
    _build_road,
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
        """Every road cell must share at least one edge with another road cell.

        A cell is a neighbour of another if it differs by exactly 1 in
        exactly one axis.  An isolated cell would indicate a gap in the path.
        """
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
        assert not overlap, (
            f"Power-up tile(s) overlap road: {sorted(overlap)}"
        )

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
# Waypoint pixels
# ---------------------------------------------------------------------------


class TestWaypointPixels:
    """Validate pre-computed pixel waypoints."""

    def test_pixel_count_matches_waypoints(self) -> None:
        """WAYPOINT_PIXELS must have the same length as WAYPOINTS."""
        assert len(WAYPOINT_PIXELS) == len(WAYPOINTS)

    def test_pixel_values_match_formula(self) -> None:
        """Each pixel waypoint must equal col*CELL_SIZE + half, row*CELL_SIZE + half."""
        half = CELL_SIZE // 2
        for (col, row), px in zip(WAYPOINTS, WAYPOINT_PIXELS):
            expected_x = col * CELL_SIZE + half
            expected_y = row * CELL_SIZE + half
            assert abs(px.x - expected_x) < 0.01, f"x mismatch at ({col},{row})"
            assert abs(px.y - expected_y) < 0.01, f"y mismatch at ({col},{row})"
