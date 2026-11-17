"""Jobsite Defense — global constants and configuration.

Phase 2 additions
-----------------
* Title bumped to Phase 2.
* Tower base stats added (Nail Gunner).

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

WINDOW_TITLE: str = "Jobsite Defense — Phase 2"
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

ENEMY_MAX_HEALTH: float = 100.0
"""Default starting health for a Rotted 2×4 enemy."""

# ---------------------------------------------------------------------------
# Tower — Nail Gunner base stats
# ---------------------------------------------------------------------------

NAIL_GUNNER_COST: int = 500
"""Purchase cost in project budget dollars."""

NAIL_GUNNER_RANGE: float = 120.0
"""Base attack range in pixels (2 cells)."""

NAIL_GUNNER_COOLDOWN: float = 0.8
"""Seconds between successive shots."""

NAIL_GUNNER_DAMAGE: float = 25.0
"""Hit-scan damage per nail."""

# ---------------------------------------------------------------------------
# Power-up colour map
# ---------------------------------------------------------------------------

POWERUP_COLORS: dict[str, tuple[int, int, int]] = {
    "attack_speed": COLOR_YETI_COOLER,
    "damage":       COLOR_COMPRESSOR,
    "range":        COLOR_EXTENSION_CORD,
}
"""Colour lookup for power-up tile rendering."""
