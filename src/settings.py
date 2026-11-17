"""Jobsite Defense — global constants and configuration.

All tunable values live here so the rest of the codebase can import a
single module and stay in sync.  Nothing in this module has side effects.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Window & grid
# ---------------------------------------------------------------------------

CELL_SIZE: int = 60
"""Side length of a single grid cell in pixels."""

GRID_COLS: int = 16
"""Number of columns in the grid."""

GRID_ROWS: int = 12
"""Number of rows in the grid."""

WINDOW_WIDTH: int = CELL_SIZE * GRID_COLS   # 960
"""Window width in pixels (derived from grid)."""

WINDOW_HEIGHT: int = CELL_SIZE * GRID_ROWS  # 720
"""Window height in pixels (derived from grid)."""

TARGET_FPS: int = 60
"""Frame-rate cap for the game loop."""

WINDOW_TITLE: str = "Jobsite Defense — Phase 1"
"""Caption shown in the window title bar."""

# ---------------------------------------------------------------------------
# Colors  (R, G, B)
# ---------------------------------------------------------------------------

COLOR_GRASS: tuple[int, int, int] = (58, 107, 53)
"""Background fill — dark construction-site green."""

COLOR_ROAD: tuple[int, int, int] = (90, 90, 90)
"""Asphalt grey for road cells."""

COLOR_GRID_LINE: tuple[int, int, int] = (40, 40, 40)
"""Thin grid overlay lines."""

COLOR_ENEMY: tuple[int, int, int] = (210, 50, 50)
"""Red circle for the test enemy (Rotted 2×4)."""

COLOR_ENEMY_OUTLINE: tuple[int, int, int] = (140, 30, 30)
"""Darker outline ring for the enemy circle."""

COLOR_YETI_COOLER: tuple[int, int, int] = (100, 180, 255)
"""Blue tint for the Yeti Cooler attack-speed tile."""

COLOR_COMPRESSOR: tuple[int, int, int] = (255, 180, 60)
"""Orange tint for the Heavy Air Compressor damage tile."""

COLOR_EXTENSION_CORD: tuple[int, int, int] = (60, 220, 120)
"""Green tint for the Extension Cord range tile."""

# ---------------------------------------------------------------------------
# Enemy defaults
# ---------------------------------------------------------------------------

ENEMY_RADIUS: int = 14
"""Radius of the enemy circle in pixels."""

ENEMY_SPEED: float = 120.0
"""Default enemy speed in pixels per second."""

# ---------------------------------------------------------------------------
# Road layout — frozenset of (col, row)
#
# The path snakes across the grid:
#   Enter from the left at row 1, go right, turn down, go left, turn
#   down again, go right, and exit off the right edge.
# ---------------------------------------------------------------------------

WAYPOINTS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (6, 1),
    (6, 4),
    (2, 4),
    (2, 7),
    (9, 7),
    (9, 4),
    (13, 4),
    (13, 10),
    (15, 10),
)
"""Ordered waypoints the enemy follows, as (col, row)."""


def _build_road(waypoints: tuple[tuple[int, int], ...]) -> frozenset[tuple[int, int]]:
    """Generate the full set of road cells by walking between waypoints.

    Waypoints must be axis-aligned (share a row **or** a column).

    Args:
        waypoints: Ordered sequence of (col, row) turning points.

    Returns:
        A frozenset of every (col, row) on the road.
    """
    cells: set[tuple[int, int]] = set()
    for i in range(len(waypoints) - 1):
        c1, r1 = waypoints[i]
        c2, r2 = waypoints[i + 1]
        if r1 == r2:
            # Horizontal segment
            lo, hi = sorted((c1, c2))
            for c in range(lo, hi + 1):
                cells.add((c, r1))
        elif c1 == c2:
            # Vertical segment
            lo, hi = sorted((r1, r2))
            for r in range(lo, hi + 1):
                cells.add((c1, r))
        else:
            raise ValueError(
                f"Diagonal waypoint segment ({c1},{r1})→({c2},{r2}) is not supported."
            )
    return frozenset(cells)


ROAD_CELLS: frozenset[tuple[int, int]] = _build_road(WAYPOINTS)
"""Immutable set of all (col, row) cells that form the road."""

# ---------------------------------------------------------------------------
# Power-up tiles — {(col, row): (effect_name, multiplier)}
# ---------------------------------------------------------------------------

POWERUP_TILES: dict[tuple[int, int], tuple[str, float]] = {
    (4, 0):  ("attack_speed", 1.25),   # Yeti Cooler — near first horizontal
    (8, 3):  ("range", 1.25),          # Extension Cord — near middle turn
    (11, 6): ("damage", 1.50),         # Heavy Air Compressor — near lower path
    (1, 6):  ("attack_speed", 1.25),   # Yeti Cooler — left side
    (14, 9): ("range", 1.25),          # Extension Cord — near exit
}
"""Static power-up tile placements for the Phase 1 test level."""

# Mapping from effect name → display color
POWERUP_COLORS: dict[str, tuple[int, int, int]] = {
    "attack_speed": COLOR_YETI_COOLER,
    "damage": COLOR_COMPRESSOR,
    "range": COLOR_EXTENSION_CORD,
}
"""Color lookup for power-up tile rendering."""
