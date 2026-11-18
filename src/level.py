"""Jobsite Defense — level data: waypoints, road cells, and power-up tiles.

Phase 5 additions
-----------------
* JSON Level Loader: ``load_level(filepath: str) -> LevelData`` parses declarative
  level files, computes road rasters, waypoint pixels, power-up maps, and typed waves.
* ``LevelData`` dataclass holding all environment specifications.
* Retains default module-level constants (``WAYPOINTS``, ``ROAD_CELLS``,
  ``WAYPOINT_PIXELS``, ``POWERUP_TILES``) for backwards compatibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.settings import CELL_SIZE, GRID_COLS
from src.settings import POWERUP_COLORS as POWERUP_COLORS  # re-export

if TYPE_CHECKING:
    from src.enemy import Enemy
    from src.wave import WaveSpec


# ---------------------------------------------------------------------------
# LevelData Container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LevelData:
    """Parsed level specifications and pre-calculated geometry."""

    name: str
    waypoints: tuple[tuple[int, int], ...]
    waypoint_pixels: tuple[tuple[float, float], ...]
    road_cells: frozenset[tuple[int, int]]
    powerup_tiles: dict[tuple[int, int], tuple[str, float]]
    waves: list[WaveSpec]


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
        (c, r) for (c, r) in cells if 0 <= c < GRID_COLS
    )


def _waypoint_pixels(
    wps: tuple[tuple[int, int], ...],
) -> tuple[tuple[float, float], ...]:
    """Convert (col, row) waypoints to pixel-centre ``(x, y)`` float pairs.

    Returns immutable primitive tuples rather than ``pygame.Vector2``
    objects to prevent accidental shared-state mutation.

    Args:
        wps: Grid-coordinate waypoints including off-screen entries.

    Returns:
        Tuple of ``(px_x, px_y)`` float pairs, one per waypoint.
    """
    half = CELL_SIZE / 2.0
    return tuple(
        (col * CELL_SIZE + half, row * CELL_SIZE + half)
        for col, row in wps
    )


# ---------------------------------------------------------------------------
# JSON Level Loader
# ---------------------------------------------------------------------------

def load_level(filepath: str) -> LevelData:
    """Parse a declarative level JSON file and construct dynamic geometry.

    Args:
        filepath: Filesystem path to the JSON level specification.

    Returns:
        A fully initialized, immutable ``LevelData`` container.
    """
    from src.enemy import HOABoardMember, OshaInspector, RainCloud, Rotted2x4
    from src.wave import WaveSpec

    enemy_registry: dict[str, type[Enemy]] = {
        "rotted2x4": Rotted2x4,
        "hoaboardmember": HOABoardMember,
        "raincloud": RainCloud,
        "oshainspector": OshaInspector,
    }

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    name: str = data.get("name", "Unnamed Level")

    # Parse waypoints
    raw_wps = data.get("waypoints", [])
    wps: tuple[tuple[int, int], ...] = tuple((int(pt[0]), int(pt[1])) for pt in raw_wps)
    road_cells = _build_road(wps)
    waypoint_pixels = _waypoint_pixels(wps)

    # Parse powerups: {"4,0": ["attack_speed", 1.25]}
    raw_powerups = data.get("powerups", {})
    powerup_tiles: dict[tuple[int, int], tuple[str, float]] = {}
    for key, val in raw_powerups.items():
        parts = [int(p.strip()) for p in key.split(",")]
        powerup_tiles[(parts[0], parts[1])] = (str(val[0]), float(val[1]))

    # Parse waves
    raw_waves = data.get("waves", [])
    waves: list[WaveSpec] = []
    for w in raw_waves:
        enemy_str = str(w.get("enemy", "Rotted2x4")).lower().replace(" ", "").replace("_", "")
        enemy_cls = enemy_registry.get(enemy_str, Rotted2x4)
        waves.append(
            WaveSpec(
                enemy=enemy_cls,
                count=int(w.get("count", 1)),
                interval=float(w.get("interval", 1.0)),
            )
        )

    return LevelData(
        name=name,
        waypoints=wps,
        waypoint_pixels=waypoint_pixels,
        road_cells=road_cells,
        powerup_tiles=powerup_tiles,
        waves=waves,
    )


# ---------------------------------------------------------------------------
# Default Campaign Level 1 (Backwards Compatibility)
# ---------------------------------------------------------------------------

WAYPOINTS: tuple[tuple[int, int], ...] = (
    (-1, 1),   # spawn — off-screen left
    (6,  1),   # turn south
    (6,  4),   # turn west
    (2,  4),   # turn south
    (2,  7),   # turn east
    (9,  7),   # turn north
    (9,  4),   # turn east
    (13, 4),   # turn south
    (13, 10),  # turn east
    (16, 10),  # exit — off-screen right
)

ROAD_CELLS: frozenset[tuple[int, int]] = _build_road(WAYPOINTS)
WAYPOINT_PIXELS: tuple[tuple[float, float], ...] = _waypoint_pixels(WAYPOINTS)

POWERUP_TILES: dict[tuple[int, int], tuple[str, float]] = {
    (4,  0):  ("attack_speed", 1.25),
    (8,  3):  ("range",        1.25),
    (11, 6):  ("damage",       1.50),
    (1,  6):  ("attack_speed", 1.25),
    (14, 9):  ("range",        1.25),
}

_overlap = frozenset(POWERUP_TILES) & ROAD_CELLS
if _overlap:
    raise RuntimeError(
        f"Power-up tile(s) overlap road cells — fix level data: {sorted(_overlap)}"
    )

POWERUP_LABELS: dict[str, str] = {
    "attack_speed": "SPD",
    "damage":       "DMG",
    "range":        "RNG",
}
