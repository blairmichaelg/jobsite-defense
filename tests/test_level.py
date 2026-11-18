"""Tests for src/level.py — declarative JSON loading, validation, and multi-path routing.

SDL dummy drivers are configured globally in ``conftest.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pygame
import pytest

from src.level import (
    LevelData,
    LevelError,
    PathData,
    _build_road,
    _waypoint_pixels,
    load_level,
)
from src.settings import CELL_SIZE

# ---------------------------------------------------------------------------
# Road geometry helper
# ---------------------------------------------------------------------------


class TestRoadGeometry:
    """Validate road building and rasterization helpers."""

    def test_diagonal_waypoints_raise(self) -> None:
        """_build_road must raise ValueError for a diagonal waypoint pair."""
        bad_waypoints: tuple[tuple[int, int], ...] = ((0, 0), (3, 3))
        with pytest.raises(ValueError, match="Diagonal segment"):
            _build_road(bad_waypoints)

    def test_road_raster_horizontal_and_vertical(self) -> None:
        """_build_road produces contiguous sets of on-grid cells."""
        wps: tuple[tuple[int, int], ...] = ((-1, 2), (4, 2), (4, 5))
        road = _build_road(wps)
        # On-grid: cols 0..4 in row 2, and rows 2..5 in col 4
        assert (0, 2) in road
        assert (4, 2) in road
        assert (4, 5) in road
        assert (-1, 2) not in road  # off-screen excluded


class TestWaypointPixels:
    """Validate pre-computed pixel waypoints."""

    def test_pixels_are_plain_tuples(self) -> None:
        """Waypoint pixels must be tuples, not mutable Vector2 objects."""
        wps = ((-1, 1), (6, 1))
        pixels = _waypoint_pixels(wps)
        assert len(pixels) == 2
        for entry in pixels:
            assert isinstance(entry, tuple)
            assert not isinstance(entry, pygame.Vector2)

    def test_pixel_coordinate_formula(self) -> None:
        """Pixel coordinates must point to the center of each cell."""
        wps = ((2, 3),)
        pixels = _waypoint_pixels(wps)
        half = CELL_SIZE / 2.0
        assert abs(pixels[0][0] - (2 * CELL_SIZE + half)) < 0.01
        assert abs(pixels[0][1] - (3 * CELL_SIZE + half)) < 0.01


# ---------------------------------------------------------------------------
# JSON Level Loader & Validation
# ---------------------------------------------------------------------------


class TestJsonLevelLoader:
    """Validate parsing, validation rules, and error conditions in load_level."""

    def test_load_level_1_file(self) -> None:
        """load_level successfully parses level_1.json via relative resolution."""
        lvl = load_level("level_1.json")
        assert isinstance(lvl, LevelData)
        assert lvl.name == "The Foundation"
        assert "main" in lvl.paths
        assert len(lvl.paths["main"].waypoints) >= 2
        assert len(lvl.road_cells) > 0
        assert (4, 0) in lvl.powerup_tiles
        assert lvl.powerup_tiles[(4, 0)] == ("attack_speed", 1.25)
        assert len(lvl.waves) == 5

    def test_load_level_2_multi_path(self) -> None:
        """load_level successfully parses level_2.json with main and flank paths."""
        lvl = load_level("level_2.json")
        assert isinstance(lvl, LevelData)
        assert lvl.name == "The Subcontract"
        assert "main" in lvl.paths
        assert "flank" in lvl.paths
        assert isinstance(lvl.paths["main"], PathData)
        assert isinstance(lvl.paths["flank"], PathData)
        assert len(lvl.paths["main"].waypoints) >= 2
        assert len(lvl.paths["flank"].waypoints) >= 2

        # Flank creep wave uses flank route
        flank_waves = [w for w in lvl.waves if w.path == "flank"]
        assert len(flank_waves) >= 1

    def test_path_with_less_than_two_points_raises_level_error(
        self, tmp_path: Path
    ) -> None:
        """Paths with < 2 points must raise LevelError."""
        bad_data = {
            "name": "Single Point",
            "paths": {"main": [[0, 0]]},
        }
        f = tmp_path / "bad_path.json"
        f.write_text(json.dumps(bad_data), encoding="utf-8")

        with pytest.raises(LevelError, match="less than 2 points"):
            load_level(f)

    def test_powerup_overlapping_road_raises_level_error(
        self, tmp_path: Path
    ) -> None:
        """Power-up placed on top of a road cell must raise LevelError."""
        overlap_data = {
            "name": "Overlap Level",
            "paths": {"main": [[-1, 1], [5, 1]]},
            "powerups": {"2, 1": ["damage", 1.5]},  # (2, 1) is on the road
        }
        f = tmp_path / "overlap.json"
        f.write_text(json.dumps(overlap_data), encoding="utf-8")

        with pytest.raises(LevelError, match="overlap road cells"):
            load_level(f)

    def test_malformed_json_raises_level_error(self, tmp_path: Path) -> None:
        """Invalid JSON syntax must raise LevelError."""
        f = tmp_path / "corrupt.json"
        f.write_text("{ unquoted_bad_json: 123", encoding="utf-8")

        with pytest.raises(LevelError, match="Failed to read or parse"):
            load_level(f)

    def test_nonexistent_file_raises_level_error(self) -> None:
        """Nonexistent level file must raise LevelError."""
        with pytest.raises(LevelError, match="Level file not found"):
            load_level("definitely_nonexistent_level_12345.json")
