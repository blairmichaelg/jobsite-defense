"""Jobsite Defense — projectile entities and splash mechanics.

Phase 3 implementation
----------------------
* ``ConcreteGlob``: AoE splash projectile fired by ``ConcretePump``.
  Flies toward a target coordinate, detonates upon arrival, damages all
  enemies within a 1.5-cell radius, applies a 50% slow (3s), and awards
  bounties on lethal hits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.enemy import SpeedModifier
from src.settings import (
    CONCRETE_GLOB_SPEED,
    CONCRETE_PUMP_DAMAGE,
    CONCRETE_SPLASH_RADIUS,
)

if TYPE_CHECKING:
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
        splash_radius: Detonation radius in pixels (1.5 cells).
        alive: Becomes ``False`` upon detonation; culled by the game loop.
        layer: Render/update layer — projectiles sit at layer 30.
    """

    pos: pygame.Vector2
    target_pos: pygame.Vector2
    speed: float = CONCRETE_GLOB_SPEED
    damage: float = CONCRETE_PUMP_DAMAGE
    splash_radius: float = CONCRETE_SPLASH_RADIUS
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
                enemy.modifiers["speed"] = SpeedModifier(multiplier=0.5, duration=3.0)

                if was_alive and not enemy.alive:
                    world.request_earn(enemy.bounty)

    def draw(self, surface: pygame.Surface) -> None:
        """Render the flying glob of wet concrete."""
        if not self.alive:
            return
        center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, (80, 85, 80), center, 7)
        pygame.draw.circle(surface, (140, 145, 140), (center[0] - 2, center[1] - 2), 3)
