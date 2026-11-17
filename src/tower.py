"""Jobsite Defense — tower definitions.

Phase 2: Nail Gunner
--------------------
The Nail Gunner is the basic single-target tower.  It scans the active
enemy list each frame, picks the closest enemy within range, and
instantly deals hit-scan damage (no projectile travel time yet).

Visual language
---------------
* Body: dark grey filled square covering most of the cell.
* Barrel indicator: a small rotating orange triangle whose tip points at
  the last locked-on enemy (or spins idly when no target is in range).
* Shot FX: a bright yellow line is drawn from the tower centre to the
  hit enemy for one frame (``_shot_flash`` timer).
* Range ring: a faint circle drawn only when the tower is selected
  (``selected`` flag, toggled by the UI layer).

Modifier stack
--------------
When the grid cell the tower occupies is a power-up tile (from
``POWERUP_TILES``), the tower's effective stats are scaled at construction
time and whenever a stat is recalculated:

    effective_range  = base_range  × range_multiplier
    effective_damage = base_damage × damage_multiplier

``attack_speed`` multipliers are reserved for future implementation
(cooldown reduction).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.grid import cell_rect
from src.level import POWERUP_TILES
from src.protocols import Clickable, Entity
from src.settings import (
    CELL_SIZE,
    NAIL_GUNNER_COOLDOWN,
    NAIL_GUNNER_COST,
    NAIL_GUNNER_DAMAGE,
    NAIL_GUNNER_RANGE,
)

if TYPE_CHECKING:
    from src.enemy import Enemy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COLOR_TOWER_BODY: tuple[int, int, int] = (60, 60, 65)
_COLOR_BARREL: tuple[int, int, int] = (230, 130, 30)   # orange triangle
_COLOR_SHOT: tuple[int, int, int] = (255, 240, 50)      # yellow nail flash
_COLOR_RANGE_RING: tuple[int, int, int] = (200, 200, 200)
_SHOT_FLASH_DURATION: float = 0.07   # seconds the nail line is visible
_IDLE_SPIN_RATE: float = 60.0        # degrees per second when no target


# ---------------------------------------------------------------------------
# NailGunner
# ---------------------------------------------------------------------------

@dataclass
class NailGunner:
    """Single-target hit-scan tower.  Satisfies ``Entity`` and ``Clickable``.

    Attributes:
        col: Grid column the tower occupies.
        row: Grid row the tower occupies.
        center: Pixel centre of the cell (computed from col/row).
        cost: Purchase cost (dollars).
        base_range: Un-modified attack range in pixels.
        base_damage: Un-modified damage per shot.
        cooldown_max: Seconds between shots.
        effective_range: Actual range after power-up multiplier.
        effective_damage: Actual damage after power-up multiplier.
        _cooldown_remaining: Seconds until next shot is allowed.
        _barrel_angle: Current barrel rotation in degrees (0° = right).
        _shot_target: Pixel position of last hit (for the flash line).
        _shot_flash: Remaining seconds for the flash-line FX.
        selected: Whether a UI element has this tower selected.
        layer: Render/update layer — towers sit at layer 20.
    """

    col: int
    row: int
    center: pygame.Vector2 = field(init=False)
    cost: int = NAIL_GUNNER_COST
    base_range: float = NAIL_GUNNER_RANGE
    base_damage: float = NAIL_GUNNER_DAMAGE
    cooldown_max: float = NAIL_GUNNER_COOLDOWN
    effective_range: float = field(init=False)
    effective_damage: float = field(init=False)
    _cooldown_remaining: float = field(default=0.0, init=False)
    _barrel_angle: float = field(default=0.0, init=False)
    _shot_target: pygame.Vector2 | None = field(default=None, init=False)
    _shot_flash: float = field(default=0.0, init=False)
    selected: bool = field(default=False, init=False)
    layer: int = field(default=20, init=False)

    def __post_init__(self) -> None:
        """Compute derived fields and apply any power-up modifier."""
        half = CELL_SIZE // 2
        self.center = pygame.Vector2(
            self.col * CELL_SIZE + half,
            self.row * CELL_SIZE + half,
        )
        self._apply_modifiers()

    def _apply_modifiers(self) -> None:
        """Read the cell's power-up tile (if any) and scale effective stats."""
        self.effective_range = self.base_range
        self.effective_damage = self.base_damage

        tile = POWERUP_TILES.get((self.col, self.row))
        if tile is None:
            return

        effect, multiplier = tile
        if effect == "range":
            self.effective_range = self.base_range * multiplier
        elif effect == "damage":
            self.effective_damage = self.base_damage * multiplier
        # attack_speed: future — would reduce cooldown_max

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Scan for targets, fire if ready, tick animations.

        This method must be called with the live enemy list each frame.
        Because ``Entity.update`` only takes ``dt``, the entity list is
        injected via :meth:`update_with_enemies` from the game loop.

        Args:
            dt: Clamped delta-time in seconds.
        """
        # Tick cooldown
        if self._cooldown_remaining > 0.0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        # Tick shot flash
        if self._shot_flash > 0.0:
            self._shot_flash -= dt
            if self._shot_flash <= 0.0:
                self._shot_target = None

        # Idle barrel spin when nothing targeted this frame
        self._barrel_angle = (self._barrel_angle + _IDLE_SPIN_RATE * dt) % 360.0

    def update_with_enemies(self, dt: float, enemies: list[Enemy]) -> None:
        """Full update: tick timers AND attempt to fire at nearest enemy.

        Called by the game loop in place of the bare ``update(dt)`` so
        the tower has access to the live enemy list without storing a
        global reference.

        Args:
            dt: Clamped delta-time in seconds.
            enemies: All currently alive ``Enemy`` instances.
        """
        self.update(dt)

        if self._cooldown_remaining > 0.0:
            return

        target = self._nearest_enemy(enemies)
        if target is None:
            return

        # Fire — hit-scan: apply damage immediately.
        target.take_damage(self.effective_damage)
        self._cooldown_remaining = self.cooldown_max
        self._shot_target = pygame.Vector2(target.pos)
        self._shot_flash = _SHOT_FLASH_DURATION

        # Aim barrel at target.
        delta = target.pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

    def _nearest_enemy(self, enemies: list[Enemy]) -> Enemy | None:
        """Return the closest alive enemy within effective_range, or None.

        Args:
            enemies: All currently alive ``Enemy`` instances.
        """
        best: Enemy | None = None
        best_dist = self.effective_range

        for enemy in enemies:
            if not enemy.alive:
                continue
            d = self.center.distance_to(enemy.pos)
            if d <= best_dist:
                best_dist = d
                best = enemy

        return best

    def draw(self, surface: pygame.Surface) -> None:
        """Render the tower body, rotating barrel triangle, and shot FX.

        Args:
            surface: The main display surface.
        """
        rect = cell_rect(self.col, self.row)
        body_rect = rect.inflate(-12, -12)   # slight inset from grid border
        pygame.draw.rect(surface, _COLOR_TOWER_BODY, body_rect, border_radius=4)

        # Optional range ring when selected
        if self.selected:
            pygame.draw.circle(
                surface,
                _COLOR_RANGE_RING,
                (int(self.center.x), int(self.center.y)),
                int(self.effective_range),
                width=1,
            )

        # Rotating barrel triangle (orange)
        self._draw_barrel(surface)

        # Shot flash — a bright yellow line to the hit location
        if self._shot_flash > 0.0 and self._shot_target is not None:
            pygame.draw.line(
                surface,
                _COLOR_SHOT,
                (int(self.center.x), int(self.center.y)),
                (int(self._shot_target.x), int(self._shot_target.y)),
                2,
            )

    def _draw_barrel(self, surface: pygame.Surface) -> None:
        """Draw a small equilateral triangle pointing in ``_barrel_angle``.

        Args:
            surface: The main display surface.
        """
        angle_rad = math.radians(self._barrel_angle)
        tip_len = 20.0
        half_base = 7.0
        perp = angle_rad + math.pi / 2.0

        tip = pygame.Vector2(
            self.center.x + math.cos(angle_rad) * tip_len,
            self.center.y + math.sin(angle_rad) * tip_len,
        )
        base_mid = pygame.Vector2(
            self.center.x - math.cos(angle_rad) * 6,
            self.center.y - math.sin(angle_rad) * 6,
        )
        bl = pygame.Vector2(
            base_mid.x + math.cos(perp) * half_base,
            base_mid.y + math.sin(perp) * half_base,
        )
        br = pygame.Vector2(
            base_mid.x - math.cos(perp) * half_base,
            base_mid.y - math.sin(perp) * half_base,
        )
        pygame.draw.polygon(
            surface,
            _COLOR_BARREL,
            [(int(tip.x), int(tip.y)), (int(bl.x), int(bl.y)), (int(br.x), int(br.y))],
        )

    # ------------------------------------------------------------------
    # Clickable protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Toggle selection when the tower cell is left-clicked.

        Args:
            event: Raw pygame event.

        Returns:
            ``True`` if the event was consumed.
        """
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and cell_rect(self.col, self.row).collidepoint(event.pos)
        ):
            self.selected = not self.selected
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self.selected:
            self.selected = False
            return True
        return False


# Type narrowing assertions for the Protocol checker.
def _assert_protocols() -> None:  # pragma: no cover
    ng: NailGunner = NailGunner(col=0, row=0)
    _e: Entity = ng
    _c: Clickable = ng
