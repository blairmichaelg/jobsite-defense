"""Jobsite Defense — tower definitions.

Phase 2.5 changes
-----------------
* ``update(dt, world)`` now reads ``world.enemies`` directly — the
  ``update_with_enemies`` helper method is gone.
* ``attack_speed`` modifier is implemented:
  ``effective_cooldown = cooldown_max / attack_speed_multiplier``.
* ``_range_sq`` pre-computed in ``__post_init__``; ``_nearest_enemy``
  uses ``distance_squared_to()`` to avoid sqrt on every candidate.
* When a killing blow is dealt, ``world.request_earn(world.kill_bounty)``
  queues the bounty; the main loop pays it out via ``world.flush_earnings``.

Modifier stack (complete)
-------------------------
    effective_range    = base_range    × range_multiplier
    effective_damage   = base_damage   × damage_multiplier
    effective_cooldown = cooldown_max  / attack_speed_multiplier
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
        cooldown_max: Base seconds between shots (before modifiers).
        effective_range: Actual range after power-up multiplier.
        effective_damage: Actual damage after power-up multiplier.
        effective_cooldown: Actual cooldown after attack_speed modifier.
        _range_sq: ``effective_range ** 2`` — avoids sqrt in hot path.
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
    effective_cooldown: float = field(init=False)
    _range_sq: float = field(init=False)
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
        """Read the cell's power-up tile (if any) and scale effective stats.

        Modifier rules
        --------------
        * ``"range"``        → ``effective_range    = base_range    × mult``
        * ``"damage"``       → ``effective_damage   = base_damage   × mult``
        * ``"attack_speed"`` → ``effective_cooldown = cooldown_max  / mult``
          (higher mult = faster fire rate = shorter cooldown)
        """
        self.effective_range = self.base_range
        self.effective_damage = self.base_damage
        self.effective_cooldown = self.cooldown_max

        tile = POWERUP_TILES.get((self.col, self.row))
        if tile is not None:
            effect, multiplier = tile
            if effect == "range":
                self.effective_range = self.base_range * multiplier
            elif effect == "damage":
                self.effective_damage = self.base_damage * multiplier
            elif effect == "attack_speed":
                # More speed → shorter cooldown
                self.effective_cooldown = self.cooldown_max / multiplier

        # Pre-compute squared range to avoid sqrt in _nearest_enemy.
        self._range_sq = self.effective_range ** 2

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: Any) -> None:  # noqa: ANN401
        """Tick timers, scan world.enemies, and fire if the cooldown allows.

        Args:
            dt: Clamped delta-time in seconds.
            world: Shared ``World`` context; reads ``world.enemies`` and
                calls ``world.request_earn`` on kill.
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

        if self._cooldown_remaining > 0.0:
            return

        # Resolve world to get enemies list (TYPE_CHECKING import avoids cycle)
        from src.world import World as _World  # local import — no circular dep at runtime
        if not isinstance(world, _World):
            return

        target = self._nearest_enemy(world.enemies)
        if target is None:
            return

        # Remember health before damage to detect kill
        was_alive = target.alive
        target.take_damage(self.effective_damage)
        self._cooldown_remaining = self.effective_cooldown
        self._shot_target = pygame.Vector2(target.pos)
        self._shot_flash = _SHOT_FLASH_DURATION

        # Queue bounty if this shot killed the enemy
        if was_alive and not target.alive:
            world.request_earn(world.kill_bounty)

        # Aim barrel at target.
        delta = target.pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

    def _nearest_enemy(self, enemies: list[Enemy]) -> Enemy | None:
        """Return the closest alive enemy within effective_range, or None.

        Uses pre-computed ``_range_sq`` and ``distance_squared_to()`` to
        avoid a square root per candidate — measurably faster on the
        target CPU when many enemies are present.

        Args:
            enemies: All ``Enemy`` instances (alive or dead).
        """
        best: Enemy | None = None
        best_dist_sq = self._range_sq

        for enemy in enemies:
            if not enemy.alive:
                continue
            d_sq = self.center.distance_squared_to(enemy.pos)
            if d_sq <= best_dist_sq:
                best_dist_sq = d_sq
                best = enemy

        return best

    def draw(self, surface: pygame.Surface) -> None:
        """Render the tower body, rotating barrel triangle, and shot FX.

        Args:
            surface: The main display surface.
        """
        rect = cell_rect(self.col, self.row)
        body_rect = rect.inflate(-12, -12)
        pygame.draw.rect(surface, _COLOR_TOWER_BODY, body_rect, border_radius=4)

        if self.selected:
            pygame.draw.circle(
                surface,
                _COLOR_RANGE_RING,
                (int(self.center.x), int(self.center.y)),
                int(self.effective_range),
                width=1,
            )

        self._draw_barrel(surface)

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
