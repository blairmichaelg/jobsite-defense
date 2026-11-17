"""Jobsite Defense — enemy entity and movement.

A minimal enemy implementation for Phase 1: a colored circle that
follows the waypoint path using ``pygame.Vector2.move_towards()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from src.grid import cell_center
from src.settings import (
    COLOR_ENEMY,
    COLOR_ENEMY_OUTLINE,
    ENEMY_RADIUS,
    ENEMY_SPEED,
    WAYPOINTS,
)


@dataclass
class Enemy:
    """A single enemy entity that walks along the waypoint path.

    Attributes:
        pos: Current world position (sub-pixel precision).
        waypoint_index: Index of the *next* waypoint the enemy is heading toward.
        speed: Movement speed in pixels per second.
        alive: Whether this enemy is still on the field.
    """

    pos: pygame.Vector2 = field(default_factory=lambda: cell_center(*WAYPOINTS[0]))
    waypoint_index: int = 1
    speed: float = ENEMY_SPEED
    alive: bool = True

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the enemy along the waypoint path.

        Uses ``Vector2.move_towards()`` for smooth, frame-rate-independent
        movement.  When the enemy reaches the final waypoint it is marked
        as no longer alive and resets to the start (looping for Phase 1
        demonstration purposes).

        Args:
            dt: Delta-time in seconds since the last frame.
        """
        if not self.alive:
            return

        if self.waypoint_index >= len(WAYPOINTS):
            # Reached the end — loop back for the demo
            self._reset()
            return

        target: pygame.Vector2 = cell_center(*WAYPOINTS[self.waypoint_index])
        max_dist: float = self.speed * dt
        self.pos = self.pos.move_towards(target, max_dist)

        # Arrived at waypoint — advance to the next one
        if self.pos.distance_to(target) < 0.5:
            self.waypoint_index += 1

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the enemy as a filled circle with an outline ring.

        Args:
            surface: The main display surface to draw on.
        """
        center: tuple[int, int] = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, COLOR_ENEMY, center, ENEMY_RADIUS)
        pygame.draw.circle(surface, COLOR_ENEMY_OUTLINE, center, ENEMY_RADIUS, width=2)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        """Return the enemy to the first waypoint (Phase 1 looping demo)."""
        self.pos = cell_center(*WAYPOINTS[0])
        self.waypoint_index = 1
