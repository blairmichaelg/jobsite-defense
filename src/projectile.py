"""Jobsite Defense — projectile entities, splash mechanics, and homing ballistics.

Defines projectile entities satisfying ``Entity`` (layer 30):
- ``ConcreteGlob``: Ballistic artillery glob detonating at predictive intercept coordinates,
  dealing AoE damage and applying slow status debuffs.
- ``TarpProjectile``: High-velocity homing missile tracking dynamic targets, dealing
  impact damage, and applying Sticky Resin slows or EMP Net stuns with mid-flight retargeting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.settings import (
    CONCRETE_GLOB_SPEED,
    CONCRETE_PUMP_DAMAGE,
    CONCRETE_SPLASH_RADIUS,
)

if TYPE_CHECKING:
    from src.enemy import Enemy
    from src.world import World


@dataclass
class ConcreteGlob:
    """Wet concrete projectile launched toward a target coordinate.

    Satisfies the ``Entity`` protocol at layer 30.

    Attributes:
        pos: Current world position in pixels.
        target_pos: Destination coordinate where the glob detonates.
        speed: Flight speed in pixels per second.
        damage: Splash damage dealt to all caught in detonation.
        splash_radius: Detonation radius in pixels (1.5 cells standard).
        slow_multiplier: Speed factor applied to enemies in splash (0.5 standard; 0.2 Quick-Dry).
        slow_duration: Seconds the slow debuff lasts.
        alive: Becomes ``False`` upon detonation; culled by the game loop.
        layer: Render/update layer — projectiles sit at layer 30.
    """

    pos: pygame.Vector2
    target_pos: pygame.Vector2
    speed: float = CONCRETE_GLOB_SPEED
    damage: float = CONCRETE_PUMP_DAMAGE
    splash_radius: float = CONCRETE_SPLASH_RADIUS
    slow_multiplier: float = 0.5
    slow_duration: float = 3.0
    alive: bool = True
    layer: int = 30
    _splash_radius_sq: float = field(init=False)

    def __post_init__(self) -> None:
        """Precompute squared splash radius to avoid sqrt during detonation."""
        self._splash_radius_sq = self.splash_radius ** 2

    # ------------------------------------------------------------------
    # Entity Protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Advance glob toward target; detonate upon arrival.

        Args:
            dt: Delta time in seconds.
            world: Shared ``World`` context.
        """
        if not self.alive:
            return

        dist = self.pos.distance_to(self.target_pos)
        step = self.speed * dt

        if dist <= step:
            self.pos = pygame.Vector2(self.target_pos)
            self._detonate(world)
        else:
            self.pos = self.pos.move_towards(self.target_pos, step)

    def _detonate(self, world: World) -> None:
        """Explode, damaging and slowing all enemies in splash range."""
        from src.world import GameEvent

        self.alive = False
        world.emit(GameEvent.SPLASH, self.pos, radius=self.splash_radius)

        for enemy in world.enemies:
            if not enemy.alive:
                continue

            if self.pos.distance_squared_to(enemy.pos) <= self._splash_radius_sq:
                was_alive = enemy.alive
                enemy.take_damage(self.damage)
                enemy.apply_speed_modifier(mult=self.slow_multiplier, dur=self.slow_duration)

                if was_alive and not enemy.alive:
                    world.request_earn(enemy.bounty)

    def draw(self, surface: pygame.Surface) -> None:
        """Render the flying glob of wet concrete."""
        if not self.alive:
            return
        center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, (80, 85, 80), center, 7)
        pygame.draw.circle(surface, (140, 145, 140), (center[0] - 2, center[1] - 2), 3)


@dataclass
class TarpProjectile:
    """Fast homing net missile that tracks its target continuously.

    Satisfies the ``Entity`` protocol at layer 30.

    Attributes:
        pos: Current world position.
        target: The specific ``Enemy`` being tracked.
        speed: Flight velocity in pixels per second (default 400).
        damage: Direct impact damage (default 10 HP).
        slow_multiplier: Speed debuff applied to flying targets (Tier 2).
        slow_duration: Duration of speed debuff in seconds.
        stun_duration: Incapacitation duration applied to targets (Tier 3).
        alive: Becomes ``False`` on impact or lost target; culled by the game loop.
        layer: Render/update layer — projectiles sit at layer 30.
    """

    pos: pygame.Vector2
    target: Enemy | None
    speed: float = 400.0
    damage: float = 10.0
    slow_multiplier: float | None = None
    slow_duration: float = 3.0
    stun_duration: float | None = None
    alive: bool = True
    layer: int = 30

    def _retarget(self, world: World) -> None:
        """Find the closest living enemy if current target dies mid-flight."""
        living = [e for e in world.enemies if e.alive]
        if not living:
            self.alive = False
            self.target = None
            return

        closest: Enemy | None = None
        min_sq = float("inf")
        for e in living:
            dist_sq = self.pos.distance_squared_to(e.pos)
            if dist_sq < min_sq:
                min_sq = dist_sq
                closest = e
        self.target = closest

    def update(self, dt: float, world: World) -> None:
        """Advance toward current target position; retarget if needed; detonate on impact."""
        if not self.alive:
            return

        if self.target is None or not self.target.alive:
            self._retarget(world)
            if not self.alive or self.target is None:
                return

        dest = self.target.pos
        dist = self.pos.distance_to(dest)
        step = self.speed * dt

        if dist <= step or dist < 12.0:
            self.pos = pygame.Vector2(dest)
            self.alive = False
            if self.target.alive:
                was_alive = self.target.alive
                self.target.take_damage(self.damage)

                # Tier 2 Sticky Resin: 0.3x slow to flying enemies
                if self.slow_multiplier is not None and self.target.is_flying:
                    self.target.apply_speed_modifier(
                        self.slow_multiplier, self.slow_duration
                    )

                # Tier 3 EMP Net: 1.5s stun to targets
                if self.stun_duration is not None:
                    from src.world import GameEvent

                    self.target.apply_stun(self.stun_duration)
                    world.emit(GameEvent.STUN, self.pos, duration=self.stun_duration)

                if was_alive and not self.target.alive:
                    world.request_earn(self.target.bounty)
        else:
            self.pos = self.pos.move_towards(dest, step)

    def draw(self, surface: pygame.Surface) -> None:
        """Render the blue tarp net projectile."""
        if not self.alive:
            return
        center = (int(self.pos.x), int(self.pos.y))
        # Blue tarp net with bright center
        pygame.draw.circle(surface, (50, 120, 220), center, 6)
        pygame.draw.circle(surface, (180, 220, 255), (center[0] - 1, center[1] - 1), 3)
