"""Jobsite Defense — level data: declarative JSON loading and geometry.

Phase 6: Decoupled JSON loading with multi-path routing support,
strict validation (LevelError), and path-relative resolution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.settings import CELL_SIZE, GRID_COLS, GRID_ROWS
from src.settings import POWERUP_COLORS as POWERUP_COLORS  # re-export

if TYPE_CHECKING:
    from src.enemy import Enemy
    from src.wave import WaveSpec


LEVELS_DIR = Path(__file__).resolve().parent.parent / "levels"


class LevelError(Exception):
    """Raised when level JSON cannot be found, parsed, or fails validation."""


# ---------------------------------------------------------------------------
# Path & Level Data Containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PathData:
    """A single creep navigational route defined in grid and pixel coordinates.

    Attributes:
        waypoints: Ordered grid coordinates ``(col, row)`` including off-screen spawn/exit.
        pixels: Pre-computed pixel center coordinates ``(x, y)`` for each waypoint.
    """

    waypoints: tuple[tuple[int, int], ...]
    pixels: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class LevelData:
    """Fully parsed level specification with multi-path geometry and power-ups."""

    name: str
    paths: dict[str, PathData]
    road_cells: frozenset[tuple[int, int]]
    powerup_tiles: dict[tuple[int, int], tuple[str, float]]
    waves: list[WaveSpec]

    @property
    def primary_path(self) -> PathData:
        """Return the 'main' path or the first defined path."""
        if "main" in self.paths:
            return self.paths["main"]
        if self.paths:
            return next(iter(self.paths.values()))
        raise LevelError(f"Level '{self.name}' defines no paths.")

    @property
    def waypoints(self) -> tuple[tuple[int, int], ...]:
        """Convenience accessor for primary path waypoints."""
        return self.primary_path.waypoints

    @property
    def waypoint_pixels(self) -> tuple[tuple[float, float], ...]:
        """Convenience accessor for primary path pixel coordinates."""
        return self.primary_path.pixels


# ---------------------------------------------------------------------------
# Path & Raster Helpers
# ---------------------------------------------------------------------------


def _build_road(wps: tuple[tuple[int, int], ...]) -> frozenset[tuple[int, int]]:
    """Rasterise waypoints into a frozenset of on-grid (col, row) cells.

    Off-screen cells (col < 0 or col >= GRID_COLS) are excluded because
    they cannot be drawn or built on.

    Args:
        wps: Ordered axis-aligned waypoints.

    Returns:
        Immutable set of on-grid road cells.

    Raises:
        ValueError: If any segment is diagonal.
    """
    cells: set[tuple[int, int]] = set()
    for i in range(len(wps) - 1):
        c1, r1 = wps[i]
        c2, r2 = wps[i + 1]
        if r1 == r2:
            lo, hi = (c1, c2) if c1 <= c2 else (c2, c1)
            for c in range(lo, hi + 1):
                cells.add((c, r1))
        elif c1 == c2:
            lo, hi = (r1, r2) if r1 <= r2 else (r2, r1)
            for r in range(lo, hi + 1):
                cells.add((c1, r))
        else:
            raise ValueError(
                f"Diagonal segment ({c1},{r1})→({c2},{r2}) is not supported."
            )
    return frozenset(
        (c, r) for (c, r) in cells if 0 <= c < GRID_COLS and 0 <= r < GRID_ROWS
    )


def _waypoint_pixels(
    wps: tuple[tuple[int, int], ...],
) -> tuple[tuple[float, float], ...]:
    """Convert (col, row) waypoints to pixel-centre ``(x, y)`` float pairs.

    Returns immutable primitive tuples rather than ``pygame.Vector2``
    objects to prevent accidental shared-state mutation.
    """
    half = CELL_SIZE / 2.0
    return tuple((col * CELL_SIZE + half, row * CELL_SIZE + half) for col, row in wps)


# ---------------------------------------------------------------------------
# Level File Resolution & Loader
# ---------------------------------------------------------------------------


def _resolve_level_path(filepath: str | Path) -> Path:
    """Resolve a level filepath using ``__file__`` based relative pathing to ``levels/``."""
    p = Path(filepath)
    if p.is_file():
        return p

    # Check relative to LEVELS_DIR
    in_levels = LEVELS_DIR / p.name
    if in_levels.is_file():
        return in_levels

    # Check with added .json extension
    if not p.name.endswith(".json"):
        with_json = LEVELS_DIR / f"{p.name}.json"
        if with_json.is_file():
            return with_json

    return p


def load_level(filepath: str | Path) -> LevelData:
    """Parse a declarative level JSON file and construct dynamic geometry.

    Args:
        filepath: Filesystem path or name of the JSON level specification.

    Returns:
        A fully initialized, validated, immutable ``LevelData`` container.

    Raises:
        LevelError: If the file cannot be read, JSON is malformed, any path
                    has < 2 points, or any power-up tile overlaps a road cell.
    """
    from src.enemy import HOABoardMember, OshaInspector, RainCloud, Rotted2x4
    from src.wave import WaveSpec

    enemy_registry: dict[str, type[Enemy]] = {
        "rotted2x4": Rotted2x4,
        "hoaboardmember": HOABoardMember,
        "raincloud": RainCloud,
        "oshainspector": OshaInspector,
    }

    resolved_path = _resolve_level_path(filepath)
    if not resolved_path.is_file():
        raise LevelError(f"Level file not found: {filepath} (resolved: {resolved_path})")

    try:
        content = resolved_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as e:
        raise LevelError(f"Failed to read or parse level JSON '{resolved_path}': {e}") from e

    name: str = data.get("name", "Unnamed Level")

    # Parse paths
    raw_paths: dict[str, list[list[int]]] = {}
    if "paths" in data and isinstance(data["paths"], dict):
        raw_paths = data["paths"]
    elif "waypoints" in data and isinstance(data["waypoints"], list):
        raw_paths = {"main": data["waypoints"]}
    else:
        raise LevelError(f"Level '{name}' defines no valid 'paths' or 'waypoints'.")

    paths: dict[str, PathData] = {}
    all_road_cells: set[tuple[int, int]] = set()

    for path_name, raw_wps in raw_paths.items():
        if len(raw_wps) < 2:
            raise LevelError(
                f"Path '{path_name}' in level '{name}' has less than 2 points ({len(raw_wps)}). "
                "Each path must have at least 2 points."
            )
        try:
            wps: tuple[tuple[int, int], ...] = tuple((int(pt[0]), int(pt[1])) for pt in raw_wps)
            road = _build_road(wps)
        except ValueError as ve:
            raise LevelError(f"Invalid path '{path_name}' in level '{name}': {ve}") from ve

        pixels = _waypoint_pixels(wps)
        paths[path_name] = PathData(waypoints=wps, pixels=pixels)
        all_road_cells.update(road)

    road_cells = frozenset(all_road_cells)

    # Parse powerups: {"4,0": ["attack_speed", 1.25]}
    raw_powerups = data.get("powerups", {})
    powerup_tiles: dict[tuple[int, int], tuple[str, float]] = {}
    for key, val in raw_powerups.items():
        try:
            parts = [int(p.strip()) for p in key.split(",")]
            cell = (parts[0], parts[1])
            powerup_tiles[cell] = (str(val[0]), float(val[1]))
        except Exception as e:
            raise LevelError(f"Malformed power-up entry '{key}': {val}") from e

    # Validation: Power-ups must not overlap road cells
    overlap = frozenset(powerup_tiles) & road_cells
    if overlap:
        raise LevelError(
            f"Power-up tile(s) overlap road cells in level '{name}': {sorted(overlap)}"
        )

    # Parse waves
    raw_waves = data.get("waves", [])
    waves: list[WaveSpec] = []
    for w in raw_waves:
        enemy_raw = w.get("enemy")
        if enemy_raw is None:
            raise LevelError(f"Wave specification in level '{name}' missing 'enemy' field")
        enemy_str = str(enemy_raw).lower().replace(" ", "").replace("_", "")
        if enemy_str not in enemy_registry:
            raise LevelError(f"Unknown enemy '{enemy_raw}' in wave definition for level '{name}'")
        enemy_cls = enemy_registry[enemy_str]

        path_name = str(w.get("path", "main"))
        if path_name not in paths:
            raise LevelError(f"Wave references undefined path '{path_name}' in level '{name}'")

        waves.append(
            WaveSpec(
                enemy=enemy_cls,
                count=int(w.get("count", 1)),
                interval=float(w.get("interval", 1.0)),
                path=path_name,
            )
        )

    return LevelData(
        name=name,
        paths=paths,
        road_cells=road_cells,
        powerup_tiles=powerup_tiles,
        waves=waves,
    )


POWERUP_LABELS: dict[str, str] = {
    "attack_speed": "SPD",
    "damage": "DMG",
    "range": "RNG",
}
