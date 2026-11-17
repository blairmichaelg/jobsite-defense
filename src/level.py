"""Jobsite Defense — level data: waypoints, road cells, and power-up tiles.

All geometry for Level 1 lives here.  ``settings.py`` retains only
visual/engine constants so there is a clean boundary between *what the
level looks like* and *how the engine renders it*.

Phase 2 change
--------------
``WAYPOINT_PIXELS`` is now a ``tuple[tuple[float, float], ...]`` of plain
primitive pairs rather than ``pygame.Vector2`` objects.  Storing mutable
objects in a module-level constant is a hazard: any caller that did
``pos = WAYPOINT_PIXELS[0]`` would hold a **reference** to the shared
object, not a copy.  Plain ``(float, float)`` tuples are immutable by
definition — callers construct a fresh ``Vector2`` when they need one.

Design rules
------------
* Spawn waypoint is one cell **left** of the grid (col = -1) so the
  enemy enters from off-screen.
* Exit waypoint is one cell **right** of the grid (col = GRID_COLS) so
  the enemy disappears cleanly off the right edge.
* Every intermediate turning-point is strictly axis-aligned with its
  neighbours; ``_build_road`` will raise on diagonal segments.
* Power-up tiles must not overlap any road cell; ``POWERUP_TILES`` is
  validated at import time.
"""

from __future__ import annotations

from src.settings import CELL_SIZE, GRID_COLS
from src.settings import POWERUP_COLORS as POWERUP_COLORS  # re-export

# ---------------------------------------------------------------------------
# Waypoints  (col, row) — ordered path the enemy follows
# ---------------------------------------------------------------------------
#
# Layout sketch (16-col × 12-row grid, one cell = 60 px):
#
#    col  -1  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16
#  row
#   1   →  ·  ·  ·  ·  ·  ·  ·  ↓                              ·
#   4                           ·  ←  ·  ·  ·  ·  ↑            ·
#   4                   ↓  ·  ·                   ↑            ·
#   7              ·  ·  ↑  →  ·  ·  ·  ·  ·  ↓               ·
#   7                                            ↓               ·
#  10                                       ↓  ·  →  ·  ·  ·  ·  →
#
# Clean snake path with off-screen entry (-1,1) and exit (16,10).

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
"""Ordered (col, row) turning-points; first and last are off-screen."""


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


ROAD_CELLS: frozenset[tuple[int, int]] = _build_road(WAYPOINTS)
"""Immutable on-grid road cells derived from WAYPOINTS."""


def _waypoint_pixels(
    wps: tuple[tuple[int, int], ...],
) -> tuple[tuple[float, float], ...]:
    """Convert (col, row) waypoints to pixel-centre ``(x, y)`` float pairs.

    Returns immutable primitive tuples rather than ``pygame.Vector2``
    objects to prevent accidental shared-state mutation.  Callers that
    need a ``Vector2`` for arithmetic should write::

        pos = pygame.Vector2(WAYPOINT_PIXELS[i])

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


WAYPOINT_PIXELS: tuple[tuple[float, float], ...] = _waypoint_pixels(WAYPOINTS)
"""Pre-computed pixel centres for every waypoint as immutable ``(x, y)`` pairs."""

# ---------------------------------------------------------------------------
# Power-up tiles — {(col, row): (effect_name, multiplier)}
# ---------------------------------------------------------------------------

POWERUP_TILES: dict[tuple[int, int], tuple[str, float]] = {
    (4,  0):  ("attack_speed", 1.25),   # Yeti Cooler    — row 0, clear of road
    (8,  3):  ("range",        1.25),   # Extension Cord — between turns
    (11, 6):  ("damage",       1.50),   # Air Compressor — lower mid
    (1,  6):  ("attack_speed", 1.25),   # Yeti Cooler    — left flank
    (14, 9):  ("range",        1.25),   # Extension Cord — near exit
}
"""Level-1 power-up placements.  Validated at import time against ROAD_CELLS."""

# Runtime guard: power-ups must not sit on the road.
_overlap = frozenset(POWERUP_TILES) & ROAD_CELLS
if _overlap:
    raise RuntimeError(
        f"Power-up tile(s) overlap road cells — fix level data: {sorted(_overlap)}"
    )

# Labels rendered on each tile for visual identification.
POWERUP_LABELS: dict[str, str] = {
    "attack_speed": "SPD",
    "damage":       "DMG",
    "range":        "RNG",
}
"""Short display labels for power-up effects."""

# POWERUP_COLORS is imported above and re-exported implicitly for render.py.
