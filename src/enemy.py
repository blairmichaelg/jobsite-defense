"""Jobsite Defense — enemy entity and movement.

Phase 1.5 changes
-----------------
* Imports waypoint pixel data from :mod:`level` (``WAYPOINT_PIXELS``).
* ``update()`` carries leftover movement distance across waypoint corners
  to eliminate micro-stutters.
* No looping: ``alive`` is set to ``False`` and ``reached_end`` is set to
  ``True`` when the final waypoint is passed.  Respawning is the
  responsibility of the caller (``main.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from src.level import WAYPOINT_PIXELS
from src.settings import COLOR_ENEMY, COLOR_ENEMY_OUTLINE, ENEMY_RADIUS, ENEMY_SPEED


@dataclass
class Enemy:
    """A single enemy entity that walks along the pre-computed pixel path.

    Attributes:
        pos: Current world position with sub-pixel precision.
        waypoint_index: Index of the *next* pixel waypoint to reach.
        speed: Movement speed in pixels per second.
        alive: ``False`` once the enemy has left the field.
        reached_end: ``True`` when the enemy exited via the final waypoint.
            The game loop reads this to decrement player lives.
    """

    pos: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(WAYPOINT_PIXELS[0])
    )
    waypoint_index: int = 1
    speed: float = ENEMY_SPEED
    alive: bool = True
    reached_end: bool = False

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

        budget = self.speed * dt  # total pixels available this frame

        while budget > 0.0 and self.waypoint_index < len(WAYPOINT_PIXELS):
            target = WAYPOINT_PIXELS[self.waypoint_index]
            dist_to_target = self.pos.distance_to(target)

            if budget >= dist_to_target:
                # Snap exactly to corner, carry remainder to next segment.
                self.pos = pygame.Vector2(target)
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
