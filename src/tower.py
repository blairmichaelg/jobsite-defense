"""Jobsite Defense — tower base class, archetypes, and upgrade trees.

Phase 4 changes
---------------
* Created ``Tower`` base class with:
  - ``COST`` and ``invested`` tracking total dollars spent (purchase + upgrades).
  - ``is_disabled`` state triggered by OSHA Inspector aura (freezes update, draws red X).
  - ``can_target_air`` capability checking (RainCloud targeting).
  - ``upgrade_level: int = 1`` and ``upgrade()`` system.
  - Common selection and range ring rendering.
* ``TOWER_TYPES`` dictionary registry mapping tower type strings to subclasses.
* Target leading for ``ConcretePump``: computes flight time and aims at ``target.predict_pos()``.
* **NailGunner Upgrades:**
  - Tier 2 ($300): "Pneumatic Overdrive" -> Cooldown divided by 2.
  - Tier 3 ($800): "The Scaffold" -> Range doubled; ``can_target_air = True``.
* **ConcretePump Upgrades:**
  - Tier 2 ($450): "Quick-Dry" -> Slow debuff becomes 0.2x.
  - Tier 3 ($1000): "Cement Truck" -> Doubles splash radius.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

import pygame

from src.grid import cell_rect
from src.projectile import ConcreteGlob
from src.protocols import Clickable, Entity
from src.settings import (
    CELL_SIZE,
    CONCRETE_GLOB_SPEED,
    CONCRETE_PUMP_COOLDOWN,
    CONCRETE_PUMP_COST,
    CONCRETE_PUMP_DAMAGE,
    CONCRETE_PUMP_RANGE,
    CONCRETE_PUMP_TIER2_COST,
    CONCRETE_PUMP_TIER3_COST,
    CONCRETE_SPLASH_RADIUS,
    NAIL_GUNNER_COOLDOWN,
    NAIL_GUNNER_COST,
    NAIL_GUNNER_DAMAGE,
    NAIL_GUNNER_RANGE,
    NAIL_GUNNER_TIER2_COST,
    NAIL_GUNNER_TIER3_COST,
    TARP_CANNON_TIER2_COST,
    TARP_CANNON_TIER3_COST,
    TARP_SLOW_MULTIPLIER,
    TARP_STUN_DURATION,
)

if TYPE_CHECKING:
    from src.enemy import Enemy
    from src.world import World

# ---------------------------------------------------------------------------
# Visual Constants
# ---------------------------------------------------------------------------

_COLOR_TOWER_BODY: tuple[int, int, int] = (60, 60, 65)
_COLOR_CONCRETE_BODY: tuple[int, int, int] = (75, 75, 70)
_COLOR_BARREL: tuple[int, int, int] = (230, 130, 30)           # orange tip
_COLOR_CONCRETE_NOZZLE: tuple[int, int, int] = (180, 180, 175) # metallic pipe
_COLOR_SHOT: tuple[int, int, int] = (255, 240, 50)              # yellow nail flash
_COLOR_RANGE_RING: tuple[int, int, int] = (200, 200, 200)
_COLOR_DISABLED_X: tuple[int, int, int] = (220, 40, 40)
_SHOT_FLASH_DURATION: float = 0.07
_IDLE_SPIN_RATE: float = 60.0


# ---------------------------------------------------------------------------
# Base Tower Class
# ---------------------------------------------------------------------------

@dataclass
class Tower:
    """Base class for all defensive towers.

    Satisfies ``Entity`` (layer 20) and ``Clickable``.
    """

    col: int
    row: int
    cost: int = 500
    invested: int = 500
    upgrade_level: int = 1
    can_target_air: bool = False
    is_disabled: bool = False
    powerup_tile: tuple[str, float] | None = None
    selected: bool = field(default=False, init=False)
    layer: int = field(default=20, init=False)

    center: pygame.Vector2 = field(init=False)
    base_range: float = 120.0
    base_damage: float = 25.0
    cooldown_max: float = 0.8

    effective_range: float = field(init=False)
    effective_damage: float = field(init=False)
    effective_cooldown: float = field(init=False)
    _range_sq: float = field(init=False)
    _cooldown_remaining: float = field(default=0.0, init=False)
    _barrel_angle: float = field(default=0.0, init=False)

    COST: ClassVar[int] = 500
    NAME: ClassVar[str] = "Tower"
    TYPE_KEY: ClassVar[str] = "tower"

    def __post_init__(self) -> None:
        """Derive cell center coordinate and power-up stats."""
        half = CELL_SIZE // 2
        self.center = pygame.Vector2(
            self.col * CELL_SIZE + half,
            self.row * CELL_SIZE + half,
        )
        self.invested = self.cost
        self._apply_modifiers()

    def _apply_modifiers(self) -> None:
        """Scale effective attributes based on power-up tile."""
        self.effective_range = self.base_range
        self.effective_damage = self.base_damage
        self.effective_cooldown = self.cooldown_max

        tile = self.powerup_tile
        if tile is not None:
            effect, multiplier = tile
            if effect == "range":
                self.effective_range = self.base_range * multiplier
            elif effect == "damage":
                self.effective_damage = self.base_damage * multiplier
            elif effect == "attack_speed":
                self.effective_cooldown = self.cooldown_max / multiplier

        self._range_sq = self.effective_range ** 2

    @property
    def next_upgrade_cost(self) -> int | None:
        """Cost of the next tier, or None if at max tier."""
        return None

    @property
    def next_upgrade_name(self) -> str | None:
        """Name of the next tier, or None if at max tier."""
        return None

    def upgrade(self) -> None:
        """Advance to next upgrade tier, scaling stats and updating invested."""

    def _nearest_enemy(self, enemies: list[Enemy]) -> Enemy | None:
        """Return the closest targetable alive enemy within range, or None."""
        best: Enemy | None = None
        best_dist_sq = self._range_sq

        for enemy in enemies:
            if not enemy.alive:
                continue
            if enemy.is_flying and not self.can_target_air:
                continue
            d_sq = self.center.distance_squared_to(enemy.pos)
            if d_sq <= best_dist_sq:
                best_dist_sq = d_sq
                best = enemy

        return best

    def update(self, dt: float, world: World) -> None:
        """Advance tower state by dt."""

    def draw(self, surface: pygame.Surface) -> None:
        """Render tower on surface."""

    # ------------------------------------------------------------------
    # Clickable Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Toggle selection on left-click; deselect on right-click."""
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

    def _draw_disabled_x(self, surface: pygame.Surface) -> None:
        """Overlay a prominent red 'X' when tower is disabled by Stop-Work order."""
        rect = cell_rect(self.col, self.row).inflate(-8, -8)
        pygame.draw.line(surface, _COLOR_DISABLED_X, rect.topleft, rect.bottomright, 4)
        pygame.draw.line(surface, _COLOR_DISABLED_X, rect.topright, rect.bottomleft, 4)


# ---------------------------------------------------------------------------
# NailGunner
# ---------------------------------------------------------------------------

@dataclass
class NailGunner(Tower):
    """Single-target hit-scan tower with anti-air upgrade at Tier 3."""

    COST: ClassVar[int] = NAIL_GUNNER_COST
    NAME: ClassVar[str] = "Nail Gunner"
    TYPE_KEY: ClassVar[str] = "nail_gunner"
    cost: int = NAIL_GUNNER_COST
    base_range: float = NAIL_GUNNER_RANGE
    base_damage: float = NAIL_GUNNER_DAMAGE
    cooldown_max: float = NAIL_GUNNER_COOLDOWN

    _shot_target: pygame.Vector2 | None = field(default=None, init=False)
    _shot_flash: float = field(default=0.0, init=False)

    @property
    def next_upgrade_cost(self) -> int | None:
        if self.upgrade_level == 1:
            return NAIL_GUNNER_TIER2_COST
        if self.upgrade_level == 2:
            return NAIL_GUNNER_TIER3_COST
        return None

    @property
    def next_upgrade_name(self) -> str | None:
        if self.upgrade_level == 1:
            return "Pneumatic Overdrive"
        if self.upgrade_level == 2:
            return "The Scaffold"
        return None

    def upgrade(self) -> None:
        """Apply Tier 2 or Tier 3 upgrades."""
        cost = self.next_upgrade_cost
        if cost is None:
            return

        if self.upgrade_level == 1:
            # Tier 2: Pneumatic Overdrive — Cooldown cut in half
            self.cooldown_max /= 2.0
            self.upgrade_level = 2
        elif self.upgrade_level == 2:
            # Tier 3: The Scaffold — Range doubled, anti-air enabled
            self.base_range *= 2.0
            self.can_target_air = True
            self.upgrade_level = 3

        self.invested += cost
        self._apply_modifiers()

    def update(self, dt: float, world: World) -> None:
        """Tick timers and fire hitscan shots unless disabled by OSHA."""
        if self.is_disabled:
            return

        if self._cooldown_remaining > 0.0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        if self._shot_flash > 0.0:
            self._shot_flash -= dt
            if self._shot_flash <= 0.0:
                self._shot_target = None

        self._barrel_angle = (self._barrel_angle + _IDLE_SPIN_RATE * dt) % 360.0

        if self._cooldown_remaining > 0.0:
            return

        target = self._nearest_enemy(world.enemies)
        if target is None:
            return

        was_alive = target.alive
        target.take_damage(self.effective_damage)
        self._cooldown_remaining = self.effective_cooldown
        self._shot_target = pygame.Vector2(target.pos)
        self._shot_flash = _SHOT_FLASH_DURATION

        from src.world import GameEvent

        world.emit(
            GameEvent.SHOT,
            self.center,
            target_pos=target.pos,
            damage=self.effective_damage,
        )

        if was_alive and not target.alive:
            world.request_earn(target.bounty)

        delta = target.pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

    def draw(self, surface: pygame.Surface) -> None:
        """Render the tower body, rotating barrel, range ring, or disabled X."""
        rect = cell_rect(self.col, self.row)
        body_rect = rect.inflate(-12, -12)
        pygame.draw.rect(surface, _COLOR_TOWER_BODY, body_rect, border_radius=4)

        if self.upgrade_level >= 3:
            # Scaffold visual accent
            pygame.draw.rect(surface, (180, 180, 120), body_rect, width=2, border_radius=4)

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

        if self.is_disabled:
            self._draw_disabled_x(surface)

    def _draw_barrel(self, surface: pygame.Surface) -> None:
        """Draw equilateral triangle pointing in ``_barrel_angle``."""
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


# ---------------------------------------------------------------------------
# ConcretePump
# ---------------------------------------------------------------------------

@dataclass
class ConcretePump(Tower):
    """AoE artillery pump launching predictive wet concrete globs."""

    COST: ClassVar[int] = CONCRETE_PUMP_COST
    NAME: ClassVar[str] = "Concrete Pump"
    TYPE_KEY: ClassVar[str] = "concrete_pump"
    cost: int = CONCRETE_PUMP_COST
    base_range: float = CONCRETE_PUMP_RANGE
    base_damage: float = CONCRETE_PUMP_DAMAGE
    cooldown_max: float = CONCRETE_PUMP_COOLDOWN

    splash_radius: float = CONCRETE_SPLASH_RADIUS
    slow_multiplier: float = 0.5

    @property
    def next_upgrade_cost(self) -> int | None:
        if self.upgrade_level == 1:
            return CONCRETE_PUMP_TIER2_COST
        if self.upgrade_level == 2:
            return CONCRETE_PUMP_TIER3_COST
        return None

    @property
    def next_upgrade_name(self) -> str | None:
        if self.upgrade_level == 1:
            return "Quick-Dry"
        if self.upgrade_level == 2:
            return "Cement Truck"
        return None

    def upgrade(self) -> None:
        """Apply Tier 2 or Tier 3 upgrades."""
        cost = self.next_upgrade_cost
        if cost is None:
            return

        if self.upgrade_level == 1:
            # Tier 2: Quick-Dry — Debuff multiplier becomes 0.2x (was 0.5x)
            self.slow_multiplier = 0.2
            self.upgrade_level = 2
        elif self.upgrade_level == 2:
            # Tier 3: Cement Truck — Doubles splash radius
            self.splash_radius *= 2.0
            self.upgrade_level = 3

        self.invested += cost
        self._apply_modifiers()

    def update(self, dt: float, world: World) -> None:
        """Tick cooldown and launch predictive concrete glob unless disabled."""
        if self.is_disabled:
            return

        if self._cooldown_remaining > 0.0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        self._barrel_angle = (self._barrel_angle + (_IDLE_SPIN_RATE * 0.5) * dt) % 360.0

        if self._cooldown_remaining > 0.0:
            return

        target = self._nearest_enemy(world.enemies)
        if target is None:
            return

        # 3-pass iterative lead calculation
        aim_pos = pygame.Vector2(target.pos)
        for _ in range(3):
            flight = self.center.distance_to(aim_pos) / CONCRETE_GLOB_SPEED
            aim_pos = target.predict_pos(flight)

        delta = aim_pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

        glob = ConcreteGlob(
            pos=pygame.Vector2(self.center),
            target_pos=pygame.Vector2(aim_pos),
            damage=self.effective_damage,
            splash_radius=self.splash_radius,
            slow_multiplier=self.slow_multiplier,
        )
        world.projectiles.append(glob)
        from src.world import GameEvent

        world.emit(GameEvent.SHOT, self.center, target_pos=aim_pos)
        self._cooldown_remaining = self.effective_cooldown

    def draw(self, surface: pygame.Surface) -> None:
        """Draw concrete pump body, nozzle, range ring, or disabled X."""
        rect = cell_rect(self.col, self.row)
        body_rect = rect.inflate(-10, -10)
        pygame.draw.rect(surface, _COLOR_CONCRETE_BODY, body_rect, border_radius=6)
        pygame.draw.rect(surface, (45, 45, 40), body_rect, width=2, border_radius=6)

        if self.upgrade_level >= 3:
            pygame.draw.rect(surface, (140, 200, 140), body_rect, width=2, border_radius=6)

        if self.selected:
            pygame.draw.circle(
                surface,
                _COLOR_RANGE_RING,
                (int(self.center.x), int(self.center.y)),
                int(self.effective_range),
                width=1,
            )

        self._draw_nozzle(surface)

        if self.is_disabled:
            self._draw_disabled_x(surface)

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


# ---------------------------------------------------------------------------
# TarpCannon
# ---------------------------------------------------------------------------

@dataclass
class TarpCannon(Tower):
    """Anti-air prioritized rapid-fire cannon launching homing tarp nets.

    Filters and prioritizes flying enemies first.
    """

    COST: ClassVar[int] = 400
    NAME: ClassVar[str] = "Tarp Cannon"
    TYPE_KEY: ClassVar[str] = "tarp_cannon"
    cost: int = 400
    base_range: float = 160.0
    base_damage: float = 10.0
    cooldown_max: float = 0.3
    can_target_air: bool = True

    @property
    def next_upgrade_cost(self) -> int | None:
        if self.upgrade_level == 1:
            return TARP_CANNON_TIER2_COST
        if self.upgrade_level == 2:
            return TARP_CANNON_TIER3_COST
        return None

    @property
    def next_upgrade_name(self) -> str | None:
        if self.upgrade_level == 1:
            return "Sticky Resin"
        if self.upgrade_level == 2:
            return "EMP Net"
        return None

    def upgrade(self) -> None:
        """Apply Tier 2 Sticky Resin or Tier 3 EMP Net upgrade."""
        cost = self.next_upgrade_cost
        if cost is None:
            return
        if self.upgrade_level == 1:
            self.upgrade_level = 2
        elif self.upgrade_level == 2:
            self.upgrade_level = 3
        self.invested += cost
        self._apply_modifiers()

    def _nearest_enemy(self, enemies: list[Enemy]) -> Enemy | None:
        """Prioritize flying enemies; target ground creeps only if no flyers in range."""
        flyers = [e for e in enemies if e.alive and e.is_flying]
        flyer_target = super()._nearest_enemy(flyers)
        if flyer_target is not None:
            return flyer_target
        ground = [e for e in enemies if e.alive and not e.is_flying]
        return super()._nearest_enemy(ground)

    def update(self, dt: float, world: World) -> None:
        """Tick cooldown and fire homing net projectile unless disabled."""
        if self.is_disabled:
            return

        if self._cooldown_remaining > 0.0:
            self._cooldown_remaining = max(0.0, self._cooldown_remaining - dt)

        self._barrel_angle = (self._barrel_angle + _IDLE_SPIN_RATE * dt) % 360.0

        if self._cooldown_remaining > 0.0:
            return

        target = self._nearest_enemy(world.enemies)
        if target is None:
            return

        delta = target.pos - self.center
        if delta.length_squared() > 0:
            self._barrel_angle = math.degrees(math.atan2(delta.y, delta.x))

        from src.projectile import TarpProjectile
        from src.world import GameEvent

        slow_mult = TARP_SLOW_MULTIPLIER if self.upgrade_level >= 2 else None
        stun_dur = TARP_STUN_DURATION if self.upgrade_level >= 3 else None

        tarp = TarpProjectile(
            pos=pygame.Vector2(self.center),
            target=target,
            damage=self.effective_damage,
            slow_multiplier=slow_mult,
            stun_duration=stun_dur,
        )
        world.projectiles.append(tarp)
        world.emit(GameEvent.SHOT, self.center, target_pos=target.pos)
        self._cooldown_remaining = self.effective_cooldown

    def draw(self, surface: pygame.Surface) -> None:
        """Draw tarp cannon body, blue barrel, range ring, or disabled X."""
        rect = cell_rect(self.col, self.row)
        body_rect = rect.inflate(-12, -12)
        pygame.draw.rect(surface, (40, 50, 70), body_rect, border_radius=4)
        pygame.draw.rect(surface, (70, 130, 200), body_rect, width=2, border_radius=4)

        if self.selected:
            pygame.draw.circle(
                surface,
                _COLOR_RANGE_RING,
                (int(self.center.x), int(self.center.y)),
                int(self.effective_range),
                width=1,
            )

        angle_rad = math.radians(self._barrel_angle)
        end_pos = pygame.Vector2(
            self.center.x + math.cos(angle_rad) * 20.0,
            self.center.y + math.sin(angle_rad) * 20.0,
        )
        pygame.draw.line(
            surface,
            (80, 160, 240),
            (int(self.center.x), int(self.center.y)),
            (int(end_pos.x), int(end_pos.y)),
            6,
        )
        pygame.draw.circle(
            surface, (30, 40, 60), (int(self.center.x), int(self.center.y)), 5
        )

        if self.is_disabled:
            self._draw_disabled_x(surface)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BUILDABLE: tuple[type[Tower], ...] = (
    NailGunner,
    ConcretePump,
    TarpCannon,
)
"""Canonical list of player-constructible towers shown in build menus."""

TOWER_TYPES: dict[str, type[Tower]] = {
    "nail_gunner": NailGunner,
    "nailgunner": NailGunner,
    "concrete_pump": ConcretePump,
    "concretepump": ConcretePump,
    "tarp_cannon": TarpCannon,
    "tarpcannon": TarpCannon,
}


# Type narrowing assertions for the Protocol checker.
def _assert_protocols() -> None:  # pragma: no cover
    ng: NailGunner = NailGunner(col=0, row=0)
    cp: ConcretePump = ConcretePump(col=0, row=0)
    _e1: Entity = ng
    _c1: Clickable = ng
    _e2: Entity = cp
    _c2: Clickable = cp
