"""Jobsite Defense — enemy entity, archetypes, and movement.

Phase 3 changes
---------------
* Refactored ``Enemy`` into an extensible base class with status effect support.
* ``modifiers: dict[str, SpeedModifier]`` tracks active status effects
  (such as temporary concrete slows) with elapsed duration ticking.
* Added ``Rotted2x4`` subclass: standard framing lumber creep (100 HP, 120 px/s, $15 bounty).
* Added ``HOABoardMember`` subclass: swarm creep (1 HP, 180 px/s, $5 bounty).
* Real typing on ``update(dt, world: World)`` satisfying the ``Entity`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.level import WAYPOINT_PIXELS
from src.settings import (
    COLOR_ENEMY,
    COLOR_ENEMY_OUTLINE,
    COLOR_HOA,
    COLOR_HOA_OUTLINE,
    ENEMY_MAX_HEALTH,
    ENEMY_RADIUS,
    ENEMY_SPEED,
)

if TYPE_CHECKING:
    from src.world import World


@dataclass
class SpeedModifier:
    """Temporary movement speed adjustment.

    Attributes:
        multiplier: Factor to scale movement speed (e.g. 0.5 for 50% slow).
        duration: Remaining duration in seconds.
    """

    multiplier: float = 0.5
    duration: float = 3.0


@dataclass
class Enemy:
    """Base class for all creep entities traversing the waypoint path.

    Attributes:
        pos: Current world position with sub-pixel precision.
        waypoint_index: Index of the *next* pixel waypoint to reach.
        speed: Base movement speed in pixels per second.
        health: Remaining hit-points.
        bounty: Dollars awarded to the player when killed by towers/projectiles.
        alive: ``False`` once the enemy has left the field or died.
        reached_end: ``True`` when the enemy exited via the final waypoint.
        layer: Render/update layer — enemies sit at layer 10.
        modifiers: Status effects keyed by name (e.g. ``"speed"``).
    """

    pos: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(*WAYPOINT_PIXELS[0])
    )
    waypoint_index: int = 1
    speed: float = ENEMY_SPEED
    health: float = ENEMY_MAX_HEALTH
    bounty: int = 15
    alive: bool = True
    reached_end: bool = False
    layer: int = 10
    modifiers: dict[str, SpeedModifier] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Damage & Status Effects
    # ------------------------------------------------------------------

    def take_damage(self, amount: float) -> None:
        """Reduce health by *amount*; mark dead if health drops to zero.

        Args:
            amount: Raw damage to apply.
        """
        if not self.alive:
            return
        self.health -= amount
        if self.health <= 0.0:
            self.alive = False

    def apply_speed_modifier(self, multiplier: float, duration: float) -> None:
        """Apply or refresh a temporary speed modifier.

        Args:
            multiplier: Speed factor (e.g. 0.5 for 50% slow).
            duration: Duration in seconds.
        """
        self.modifiers["speed"] = SpeedModifier(
            multiplier=multiplier, duration=duration
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Advance the enemy along the waypoint path, ticking status effects.

        Leftover movement distance from reaching a waypoint is forwarded
        to the next segment in the same frame, preventing corner micro-
        stutters.

        Args:
            dt: Clamped delta-time (≤ 0.05 s) in seconds.
            world: Shared ``World`` context.
        """
        if not self.alive:
            return

        # 1. Tick and expire modifiers
        expired: list[str] = []
        for key, mod in self.modifiers.items():
            mod.duration -= dt
            if mod.duration <= 0.0:
                expired.append(key)
        for key in expired:
            del self.modifiers[key]

        # 2. Compute effective speed
        current_speed = self.speed
        if "speed" in self.modifiers:
            current_speed *= self.modifiers["speed"].multiplier

        # 3. Path travel
        budget = current_speed * dt

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
        """Render the enemy circle with outline and optional slow effect ring.

        Args:
            surface: The main display surface to draw on.
        """
        center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, COLOR_ENEMY, center, ENEMY_RADIUS)
        pygame.draw.circle(surface, COLOR_ENEMY_OUTLINE, center, ENEMY_RADIUS, width=2)

        if "speed" in self.modifiers:
            # Wet concrete slow indicator (greyish outer ring)
            pygame.draw.circle(surface, (150, 155, 150), center, ENEMY_RADIUS + 3, width=2)


@dataclass
class Rotted2x4(Enemy):
    """Standard creep archetype — rotted framing lumber.

    Attributes:
        speed: 120 px/s (standard).
        health: 100 HP.
        bounty: $15.
    """

    speed: float = ENEMY_SPEED
    health: float = ENEMY_MAX_HEALTH
    bounty: int = 15


@dataclass
class HOABoardMember(Enemy):
    """Fast swarm creep archetype — 50% faster, 1 HP, $5 bounty.

    Attributes:
        speed: 180 px/s (1.5x standard).
        health: 1.0 HP.
        bounty: $5.
    """

    speed: float = ENEMY_SPEED * 1.5
    health: float = 1.0
    bounty: int = 5

    def draw(self, surface: pygame.Surface) -> None:
        """Draw HOA board member as a fast, smaller purple circle."""
        center = (int(self.pos.x), int(self.pos.y))
        radius = 11
        pygame.draw.circle(surface, COLOR_HOA, center, radius)
        pygame.draw.circle(surface, COLOR_HOA_OUTLINE, center, radius, width=2)

        if "speed" in self.modifiers:
            pygame.draw.circle(surface, (150, 155, 150), center, radius + 3, width=2)
