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

WINDOW_TITLE: str = "Jobsite Defense — Phase 4"
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

COLOR_HOA: tuple[int, int, int] = (190, 70, 200)
"""Purple circle for HOA Board Member swarm enemy."""

COLOR_HOA_OUTLINE: tuple[int, int, int] = (120, 35, 130)
"""Darker outline ring for the HOA Board Member."""

COLOR_OSHA: tuple[int, int, int] = (240, 200, 30)
"""Safety-yellow circle for the OSHA Inspector Boss."""

COLOR_OSHA_OUTLINE: tuple[int, int, int] = (160, 130, 15)
"""Darker outline for the OSHA Inspector Boss."""

COLOR_RAIN_CLOUD: tuple[int, int, int] = (160, 175, 195)
"""Overcast blue-grey for flying RainCloud hazard."""

COLOR_RAIN_CLOUD_OUTLINE: tuple[int, int, int] = (110, 125, 145)
"""Outline for flying RainCloud."""

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
# Enemy Archetypes — Phase 4
# ---------------------------------------------------------------------------

OSHA_INSPECTOR_HEALTH: float = 2500.0
"""Hit points for OSHA Inspector Boss."""

OSHA_INSPECTOR_SPEED: float = 40.0
"""Pixels per second for OSHA Inspector Boss."""

OSHA_INSPECTOR_BOUNTY: int = 100
"""Dollars awarded on destroying the OSHA Inspector."""

OSHA_INSPECTOR_PATIENCE: int = 20
"""Client patience lost if OSHA Inspector reaches the end."""

OSHA_AURA_RADIUS: float = 2.5 * CELL_SIZE  # 150 px
"""Radius of the Stop-Work Order disabling aura."""

RAIN_CLOUD_HEALTH: float = 60.0
"""Hit points for flying RainCloud hazard."""

RAIN_CLOUD_SPEED: float = 80.0
"""Pixels per second for flying RainCloud hazard."""

RAIN_CLOUD_BOUNTY: int = 20
"""Dollars awarded on dispersing a RainCloud."""

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

NAIL_GUNNER_TIER2_COST: int = 300
"""Upgrade cost for Tier 2: Pneumatic Overdrive."""

NAIL_GUNNER_TIER3_COST: int = 800
"""Upgrade cost for Tier 3: The Scaffold."""

# ---------------------------------------------------------------------------
# Tower — Concrete Pump base stats
# ---------------------------------------------------------------------------

CONCRETE_PUMP_COST: int = 750
"""Purchase cost in project budget dollars."""

CONCRETE_PUMP_RANGE: float = 150.0
"""Base attack range in pixels (2.5 cells)."""

CONCRETE_PUMP_COOLDOWN: float = 2.5
"""Seconds between glob launches."""

CONCRETE_PUMP_DAMAGE: float = 5.0
"""Splash damage per glob detonation."""

CONCRETE_GLOB_SPEED: float = 250.0
"""Flight speed of the concrete glob in pixels per second."""

CONCRETE_SPLASH_RADIUS: float = 1.5 * CELL_SIZE  # 90 px
"""Detonation splash radius in pixels (1.5 grid cells)."""

CONCRETE_PUMP_TIER2_COST: int = 450
"""Upgrade cost for Tier 2: Quick-Dry."""

CONCRETE_PUMP_TIER3_COST: int = 1000
"""Upgrade cost for Tier 3: Cement Truck."""

# ---------------------------------------------------------------------------
# Tower — Tarp Cannon base stats
# ---------------------------------------------------------------------------

TARP_CANNON_COST: int = 400
"""Purchase cost in project budget dollars."""

TARP_CANNON_RANGE: float = 160.0
"""Base attack range in pixels."""

TARP_CANNON_COOLDOWN: float = 0.3
"""Seconds between successive shots."""

TARP_CANNON_DAMAGE: float = 10.0
"""Impact damage per homing tarp net."""

TARP_CANNON_TIER2_COST: int = 500
"""Upgrade cost for Tier 2: Sticky Resin."""

TARP_CANNON_TIER3_COST: int = 1200
"""Upgrade cost for Tier 3: EMP Net."""

# ---------------------------------------------------------------------------
# Power-up colour map
# ---------------------------------------------------------------------------

POWERUP_COLORS: dict[str, tuple[int, int, int]] = {
    "attack_speed": COLOR_YETI_COOLER,
    "damage":       COLOR_COMPRESSOR,
    "range":        COLOR_EXTENSION_CORD,
}
"""Colour lookup for power-up tile rendering."""
