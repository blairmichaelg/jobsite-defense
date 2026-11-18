"""Jobsite Defense — tower definitions.

Phase 3 changes
---------------
* Added ``ConcretePump``: AoE slowdown artillery tower launching ``ConcreteGlob``
  projectiles ($750, 2.5s cooldown, 150px range).
* Real typing on ``update(dt, world: World)`` — removed function-level import
  and runtime isinstance gate.
* Kill bounty in ``NailGunner`` uses ``target.bounty`` for archetype-specific payouts.
* Both towers satisfy ``Entity`` and ``Clickable``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.grid import cell_rect
from src.level import POWERUP_TILES
from src.projectile import ConcreteGlob
from src.protocols import Clickable, Entity
from src.settings import (
    CELL_SIZE,
    CONCRETE_PUMP_COOLDOWN,
    CONCRETE_PUMP_COST,
    CONCRETE_PUMP_DAMAGE,
    CONCRETE_PUMP_RANGE,
    NAIL_GUNNER_COOLDOWN,
    NAIL_GUNNER_COST,
    NAIL_GUNNER_DAMAGE,
    NAIL_GUNNER_RANGE,
)

if TYPE_CHECKING:
    from src.enemy import Enemy
    from src.world import World

# ---------------------------------------------------------------------------
# Colors & Visuals
# ---------------------------------------------------------------------------

_COLOR_TOWER_BODY: tuple[int, int, int] = (60, 60, 65)
_COLOR_CONCRETE_BODY: tuple[int, int, int] = (75, 75, 70)
_COLOR_BARREL: tuple[int, int, int] = (230, 130, 30)         # orange nail gunner tip
_COLOR_CONCRETE_NOZZLE: tuple[int, int, int] = (180, 180, 175) # metallic pipe nozzle
_COLOR_SHOT: tuple[int, int, int] = (255, 240, 50)            # yellow nail flash
_COLOR_RANGE_RING: tuple[int, int, int] = (200, 200, 200)
_SHOT_FLASH_DURATION: float = 0.07   # seconds nail flash line is visible
_IDLE_SPIN_RATE: float = 60.0        # degrees per second when idle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nearest_enemy(
    origin: pygame.Vector2, enemies: list[Enemy], max_range_sq: float
) -> Enemy | None:
    """Return the closest alive enemy within range, or None."""
    best: Enemy | None = None
    best_dist_sq = max_range_sq

    for enemy in enemies:
        if not enemy.alive:
            continue
        d_sq = origin.distance_squared_to(enemy.pos)
        if d_sq <= best_dist_sq:
            best_dist_sq = d_sq
            best = enemy

    return best


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
        """Read the cell's power-up tile (if any) and scale effective stats."""
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
                self.effective_cooldown = self.cooldown_max / multiplier

        self._range_sq = self.effective_range ** 2

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Tick timers, scan world.enemies, and fire if the cooldown allows.

        Args:
            dt: Clamped delta-time in seconds.
            world: Shared ``World`` context.
        """
        if self._cooldown_remaining > 0.0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        if self._shot_flash > 0.0:
            self._shot_flash -= dt
            if self._shot_flash <= 0.0:
                self._shot_target = None

        self._barrel_angle = (self._barrel_angle + _IDLE_SPIN_RATE * dt) % 360.0

        if self._cooldown_remaining > 0.0:
            return

        target = _nearest_enemy(self.center, world.enemies, self._range_sq)
        if target is None:
            return

        was_alive = target.alive
        target.take_damage(self.effective_damage)
        self._cooldown_remaining = self.effective_cooldown
        self._shot_target = pygame.Vector2(target.pos)
        self._shot_flash = _SHOT_FLASH_DURATION

        if was_alive and not target.alive:
            world.request_earn(target.bounty)

        delta = target.pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

    def draw(self, surface: pygame.Surface) -> None:
        """Render the tower body, rotating barrel triangle, and shot FX."""
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
        """Draw a small equilateral triangle pointing in ``_barrel_angle``."""
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
        """Toggle selection when the tower cell is clicked."""
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


# ---------------------------------------------------------------------------
# ConcretePump
# ---------------------------------------------------------------------------

@dataclass
class ConcretePump:
    """AoE artillery pump firing slow-down concrete globs.

    Satisfies ``Entity`` and ``Clickable`` at layer 20.

    Attributes:
        col: Grid column.
        row: Grid row.
        cost: Purchase cost in dollars ($750).
        cooldown_max: Seconds between glob launches (2.5s).
        base_range: Attack range in pixels (150px).
        base_damage: Direct hit splash damage (5.0).
    """

    col: int
    row: int
    center: pygame.Vector2 = field(init=False)
    cost: int = CONCRETE_PUMP_COST
    base_range: float = CONCRETE_PUMP_RANGE
    base_damage: float = CONCRETE_PUMP_DAMAGE
    cooldown_max: float = CONCRETE_PUMP_COOLDOWN
    effective_range: float = field(init=False)
    effective_damage: float = field(init=False)
    effective_cooldown: float = field(init=False)
    _range_sq: float = field(init=False)
    _cooldown_remaining: float = field(default=0.0, init=False)
    _barrel_angle: float = field(default=0.0, init=False)
    selected: bool = field(default=False, init=False)
    layer: int = field(default=20, init=False)

    def __post_init__(self) -> None:
        """Derive cell center coordinate and power-up stats."""
        half = CELL_SIZE // 2
        self.center = pygame.Vector2(
            self.col * CELL_SIZE + half,
            self.row * CELL_SIZE + half,
        )
        self._apply_modifiers()

    def _apply_modifiers(self) -> None:
        """Scale effective attributes based on power-up tile."""
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
                self.effective_cooldown = self.cooldown_max / multiplier

        self._range_sq = self.effective_range ** 2

    # ------------------------------------------------------------------
    # Entity Protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Tick cooldown, scan nearest enemy, launch ConcreteGlob."""
        if self._cooldown_remaining > 0.0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        self._barrel_angle = (self._barrel_angle + (_IDLE_SPIN_RATE * 0.5) * dt) % 360.0

        if self._cooldown_remaining > 0.0:
            return

        target = _nearest_enemy(self.center, world.enemies, self._range_sq)
        if target is None:
            return

        delta = target.pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

        # Launch ConcreteGlob aimed at current target pos
        glob = ConcreteGlob(
            pos=pygame.Vector2(self.center),
            target_pos=pygame.Vector2(target.pos),
            damage=self.effective_damage,
        )
        world.projectiles.append(glob)
        self._cooldown_remaining = self.effective_cooldown

    def draw(self, surface: pygame.Surface) -> None:
        """Draw concrete pump body, hose nozzle, and selection range ring."""
        rect = cell_rect(self.col, self.row)
        body_rect = rect.inflate(-10, -10)
        pygame.draw.rect(surface, _COLOR_CONCRETE_BODY, body_rect, border_radius=6)
        pygame.draw.rect(surface, (45, 45, 40), body_rect, width=2, border_radius=6)

        if self.selected:
            pygame.draw.circle(
                surface,
                _COLOR_RANGE_RING,
                (int(self.center.x), int(self.center.y)),
                int(self.effective_range),
                width=1,
            )

        self._draw_nozzle(surface)

    def _draw_nozzle(self, surface: pygame.Surface) -> None:
        """Render thick concrete hose pipe pointing toward ``_barrel_angle``."""
        angle_rad = math.radians(self._barrel_angle)
        pipe_length = 22.0
        pipe_width = 8

        end_pos = pygame.Vector2(
            self.center.x + math.cos(angle_rad) * pipe_length,
            self.center.y + math.sin(angle_rad) * pipe_length,
        )
        pygame.draw.line(
            surface,
            _COLOR_CONCRETE_NOZZLE,
            (int(self.center.x), int(self.center.y)),
            (int(end_pos.x), int(end_pos.y)),
            pipe_width,
        )
        pygame.draw.circle(
            surface,
            (40, 40, 40),
            (int(self.center.x), int(self.center.y)),
            7,
        )

    # ------------------------------------------------------------------
    # Clickable Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Toggle selection on click."""
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
    cp: ConcretePump = ConcretePump(col=0, row=0)
    _e1: Entity = ng
    _c1: Clickable = ng
    _e2: Entity = cp
    _c2: Clickable = cp
