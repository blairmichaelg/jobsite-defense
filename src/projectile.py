"""Jobsite Defense — projectile entities and splash mechanics.

Phase 5 additions
-----------------
* ``TarpProjectile``: Fast homing missile launched by ``TarpCannon``.
  Tracks flying or ground target continuously, deals 10 direct damage,
  and grants kill bounties.
* ``ConcreteGlob`` continues to provide predictive AoE concrete splash.
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
        self.alive = False

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
        alive: Becomes ``False`` on impact; culled by the game loop.
        layer: Render/update layer — projectiles sit at layer 30.
    """

    pos: pygame.Vector2
    target: Enemy
    speed: float = 400.0
    damage: float = 10.0
    alive: bool = True
    layer: int = 30

    def update(self, dt: float, world: World) -> None:
        """Advance toward current target position; detonate on impact."""
        if not self.alive:
            return

        dest = self.target.pos if self.target.alive else self.pos
        dist = self.pos.distance_to(dest)
        step = self.speed * dt

        if dist <= step or dist < 12.0:
            self.pos = pygame.Vector2(dest)
            self.alive = False
            if self.target.alive:
                was_alive = self.target.alive
                self.target.take_damage(self.damage)
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
