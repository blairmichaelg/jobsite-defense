"""Jobsite Defense — enemy entity and movement.

Phase 2 changes
---------------
* ``layer: int = 10`` added to satisfy the updated ``Entity`` protocol.
* ``WAYPOINT_PIXELS`` is now ``tuple[tuple[float, float], ...]``; every
  read that previously relied on ``Vector2`` arithmetic now wraps the
  primitive pair in a fresh ``pygame.Vector2(wx, wy)`` to avoid shared-
  state mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from src.level import WAYPOINT_PIXELS
from src.settings import (
    COLOR_ENEMY,
    COLOR_ENEMY_OUTLINE,
    ENEMY_MAX_HEALTH,
    ENEMY_RADIUS,
    ENEMY_SPEED,
)


@dataclass
class Enemy:
    """A single enemy entity that walks along the pre-computed pixel path.

    Attributes:
        pos: Current world position with sub-pixel precision.
        waypoint_index: Index of the *next* pixel waypoint to reach.
        speed: Movement speed in pixels per second.
        health: Remaining hit-points.
        alive: ``False`` once the enemy has left the field or died.
        reached_end: ``True`` when the enemy exited via the final waypoint.
            The game loop reads this to decrement ``Economy.client_patience``.
        layer: Render/update layer — enemies sit at layer 10.
    """

    pos: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(*WAYPOINT_PIXELS[0])
    )
    waypoint_index: int = 1
    speed: float = ENEMY_SPEED
    health: float = ENEMY_MAX_HEALTH
    alive: bool = True
    reached_end: bool = False
    layer: int = 10

    # ------------------------------------------------------------------
    # Damage
    # ------------------------------------------------------------------

    def take_damage(self, amount: float) -> None:
        """Reduce health by *amount*; mark dead if health drops to zero.

        Args:
            amount: Raw damage to apply (before any future resistances).
        """
        if not self.alive:
            return
        self.health -= amount
        if self.health <= 0.0:
            self.alive = False

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the enemy along the waypoint path.

        Leftover movement distance from reaching a waypoint is forwarded
        to the next segment in the same frame, preventing corner micro-
        stutters at high frame-rates or large ``dt`` values.

        Args:
            dt: Clamped delta-time (≤ 0.05 s) in seconds.
        """
        if not self.alive:
            return

        budget = self.speed * dt

        while budget > 0.0 and self.waypoint_index < len(WAYPOINT_PIXELS):
            wx, wy = WAYPOINT_PIXELS[self.waypoint_index]
            target = pygame.Vector2(wx, wy)
            dist_to_target = self.pos.distance_to(target)

            if budget >= dist_to_target:
                self.pos = target          # snap exactly to corner
                budget -= dist_to_target
                self.waypoint_index += 1
            else:
                self.pos = self.pos.move_towards(target, budget)
                budget = 0.0

        if self.waypoint_index >= len(WAYPOINT_PIXELS):
            self.alive = False
            self.reached_end = True

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the enemy as a filled circle with a darker outline ring.

        Args:
            surface: The main display surface to draw on.
        """
        center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, COLOR_ENEMY, center, ENEMY_RADIUS)
        pygame.draw.circle(surface, COLOR_ENEMY_OUTLINE, center, ENEMY_RADIUS, width=2)
