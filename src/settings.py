"""Jobsite Defense — global constants and configuration.

Phase 1.5 changes
-----------------
* Level geometry (``WAYPOINTS``, ``ROAD_CELLS``, ``POWERUP_TILES``) has
  been moved to :mod:`src.level`.  ``settings.py`` now contains only
  visual and engine constants with no side effects.
* ``POWERUP_COLORS`` is kept here as the canonical colour map; it is
  re-exported by :mod:`src.level` for convenience.

Nothing in this module has side effects.
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
"""Window width in pixels."""

WINDOW_HEIGHT: int = CELL_SIZE * GRID_ROWS  # 720
"""Window height in pixels."""

TARGET_FPS: int = 60
"""Frame-rate cap for the game loop."""

WINDOW_TITLE: str = "Jobsite Defense — Phase 1.5"
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
# Power-up colour map
# ---------------------------------------------------------------------------

POWERUP_COLORS: dict[str, tuple[int, int, int]] = {
    "attack_speed": COLOR_YETI_COOLER,
    "damage":       COLOR_COMPRESSOR,
    "range":        COLOR_EXTENSION_CORD,
}
"""Colour lookup for power-up tile rendering."""
