"""Jobsite Defense — enemy entity, archetypes, and movement.

Phase 4 changes
---------------
* Added ``predict_pos(seconds)``: advances along waypoints (or straight-line
  for flyers) to return the predicted future coordinate.
* Enhanced ``apply_speed_modifier(mult, dur)``: overwrites if slower; takes max duration if equal.
* Added ``RainCloud``: flying hazard (is_flying=True), moves in a straight line from
  (-100, 100) toward the exit waypoint. Ground towers without air capability cannot target it.
* Added ``OshaInspector``: boss enemy (2500 HP, 40 px/s, $100 bounty, costs 20 Patience).
  Emits Stop-Work Order Aura (150px) that disables nearby towers.
* Added ``patience_cost`` attribute to ``Enemy`` (defaults to 1; 20 for OSHA boss).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.level import WAYPOINT_PIXELS
from src.settings import (
    COLOR_ENEMY,
    COLOR_ENEMY_OUTLINE,
    COLOR_HOA,
    COLOR_HOA_OUTLINE,
    COLOR_OSHA,
    COLOR_OSHA_OUTLINE,
    COLOR_RAIN_CLOUD,
    COLOR_RAIN_CLOUD_OUTLINE,
    ENEMY_MAX_HEALTH,
    ENEMY_RADIUS,
    ENEMY_SPEED,
    OSHA_AURA_RADIUS,
    OSHA_INSPECTOR_BOUNTY,
    OSHA_INSPECTOR_HEALTH,
    OSHA_INSPECTOR_PATIENCE,
    OSHA_INSPECTOR_SPEED,
    RAIN_CLOUD_BOUNTY,
    RAIN_CLOUD_HEALTH,
    RAIN_CLOUD_SPEED,
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
        patience_cost: Patience lost if this enemy escapes off-screen.
        is_flying: Whether the entity bypasses ground pathing.
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
    patience_cost: int = 1
    is_flying: bool = False
    alive: bool = True
    reached_end: bool = False
    layer: int = 10
    modifiers: dict[str, SpeedModifier] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Damage & Status Effects
    # ------------------------------------------------------------------

    def take_damage(self, amount: float) -> None:
        """Reduce health by *amount*; mark dead if health drops to zero."""
        if not self.alive:
            return
        self.health -= amount
        if self.health <= 0.0:
            self.alive = False

    def apply_speed_modifier(self, mult: float, dur: float) -> None:
        """Apply or refresh a speed debuff according to stacking rules.

        Rules:
        - If new mult is strictly stronger (lower value), overwrite both mult and duration.
        - If new mult is equal to existing, extend duration to max(current, dur).
        - If new mult is weaker, do not downgrade the active debuff.
        """
        current = self.modifiers.get("speed")
        if current is None or mult < current.multiplier:
            self.modifiers["speed"] = SpeedModifier(multiplier=mult, duration=dur)
        elif math.isclose(mult, current.multiplier, rel_tol=1e-5):
            current.duration = max(current.duration, dur)

    # ------------------------------------------------------------------
    # Position Prediction (Target Leading)
    # ------------------------------------------------------------------

    def predict_pos(self, seconds: float) -> pygame.Vector2:
        """Simulate future position after *seconds* along the waypoint path.

        Args:
            seconds: Lead time in seconds (e.g. projectile flight time).

        Returns:
            Projected coordinate along the waypoint path.
        """
        effective_speed = self.speed
        if "speed" in self.modifiers:
            effective_speed *= self.modifiers["speed"].multiplier

        budget = effective_speed * seconds
        pos = pygame.Vector2(self.pos)
        wp_idx = self.waypoint_index

        while budget > 0.0 and wp_idx < len(WAYPOINT_PIXELS):
            wx, wy = WAYPOINT_PIXELS[wp_idx]
            target = pygame.Vector2(wx, wy)
            dist = pos.distance_to(target)

            if budget >= dist:
                pos = target
                budget -= dist
                wp_idx += 1
            else:
                pos = pos.move_towards(target, budget)
                budget = 0.0

        return pos

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Advance the enemy along the waypoint path, ticking status effects."""
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
                self.pos = target
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
        """Render the enemy circle with outline and optional slow effect ring."""
        center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, COLOR_ENEMY, center, ENEMY_RADIUS)
        pygame.draw.circle(surface, COLOR_ENEMY_OUTLINE, center, ENEMY_RADIUS, width=2)

        if "speed" in self.modifiers:
            pygame.draw.circle(surface, (150, 155, 150), center, ENEMY_RADIUS + 3, width=2)


@dataclass
class Rotted2x4(Enemy):
    """Standard creep archetype — rotted framing lumber."""

    speed: float = ENEMY_SPEED
    health: float = ENEMY_MAX_HEALTH
    bounty: int = 15
    patience_cost: int = 1


@dataclass
class HOABoardMember(Enemy):
    """Fast swarm creep archetype — 50% faster, 1 HP, $5 bounty."""

    speed: float = ENEMY_SPEED * 1.5
    health: float = 1.0
    bounty: int = 5
    patience_cost: int = 1

    def draw(self, surface: pygame.Surface) -> None:
        """Draw HOA board member as a fast, smaller purple circle."""
        center = (int(self.pos.x), int(self.pos.y))
        radius = 11
        pygame.draw.circle(surface, COLOR_HOA, center, radius)
        pygame.draw.circle(surface, COLOR_HOA_OUTLINE, center, radius, width=2)

        if "speed" in self.modifiers:
            pygame.draw.circle(surface, (150, 155, 150), center, radius + 3, width=2)


@dataclass
class RainCloud(Enemy):
    """Flying hazard creep — ignores the road, flies straight to the exit.

    Ground towers cannot target it unless equipped with air capability.
    """

    pos: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(-100.0, 100.0)
    )
    speed: float = RAIN_CLOUD_SPEED
    health: float = RAIN_CLOUD_HEALTH
    bounty: int = RAIN_CLOUD_BOUNTY
    patience_cost: int = 1
    is_flying: bool = True

    def predict_pos(self, seconds: float) -> pygame.Vector2:
        """Simulate future position flying directly toward final exit waypoint."""
        target = pygame.Vector2(*WAYPOINT_PIXELS[-1])
        effective_speed = self.speed
        if "speed" in self.modifiers:
            effective_speed *= self.modifiers["speed"].multiplier
        budget = effective_speed * seconds
        return self.pos.move_towards(target, budget)

    def update(self, dt: float, world: World) -> None:
        """Fly in a straight line from current pos toward final exit."""
        if not self.alive:
            return

        # Tick modifiers
        expired: list[str] = []
        for key, mod in self.modifiers.items():
            mod.duration -= dt
            if mod.duration <= 0.0:
                expired.append(key)
        for key in expired:
            del self.modifiers[key]

        effective_speed = self.speed
        if "speed" in self.modifiers:
            effective_speed *= self.modifiers["speed"].multiplier

        target = pygame.Vector2(*WAYPOINT_PIXELS[-1])
        dist = self.pos.distance_to(target)
        step = effective_speed * dt

        if dist <= step:
            self.pos = target
            self.alive = False
            self.reached_end = True
        else:
            self.pos = self.pos.move_towards(target, step)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw an overcast raincloud entity with falling rain streak."""
        cx, cy = int(self.pos.x), int(self.pos.y)
        # Cloud puffs
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD, (cx - 8, cy), 12)
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD, (cx + 8, cy), 12)
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD, (cx, cy - 6), 14)
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD_OUTLINE, (cx, cy), 16, width=1)
        # Rain streaks
        pygame.draw.line(surface, (100, 160, 240), (cx - 6, cy + 14), (cx - 9, cy + 22), 2)
        pygame.draw.line(surface, (100, 160, 240), (cx + 6, cy + 14), (cx + 3, cy + 22), 2)


@dataclass
class OshaInspector(Enemy):
    """OSHA Inspector Boss creep — slow, massive health, disables nearby towers.

    Stop-Work Order Aura: Any tower within 2.5 tiles (150px) is disabled.
    """

    speed: float = OSHA_INSPECTOR_SPEED
    health: float = OSHA_INSPECTOR_HEALTH
    bounty: int = OSHA_INSPECTOR_BOUNTY
    patience_cost: int = OSHA_INSPECTOR_PATIENCE
    aura_radius: float = OSHA_AURA_RADIUS

    def update(self, dt: float, world: World) -> None:
        """Traverse the path and radiate the Stop-Work Order disabling aura."""
        super().update(dt, world)

        aura_sq = self.aura_radius ** 2
        for tower in world.towers.values():
            if self.alive and self.pos.distance_squared_to(tower.center) <= aura_sq:
                tower.is_disabled = True
            else:
                tower.is_disabled = False

    def draw(self, surface: pygame.Surface) -> None:
        """Render the OSHA inspector with safety helmet and Stop-Work aura ring."""
        cx, cy = int(self.pos.x), int(self.pos.y)

        # Draw subtle aura ring
        if self.alive:
            pygame.draw.circle(surface, (230, 40, 40), (cx, cy), int(self.aura_radius), width=1)

        # Draw imposing boss circle
        boss_radius = 18
        pygame.draw.circle(surface, COLOR_OSHA, (cx, cy), boss_radius)
        pygame.draw.circle(surface, COLOR_OSHA_OUTLINE, (cx, cy), boss_radius, width=3)

        # Hard-hat visor stripe
        pygame.draw.line(surface, (255, 255, 255), (cx - 10, cy - 6), (cx + 10, cy - 6), 3)

        # Health bar above inspector
        bar_w = 40
        bar_h = 5
        pct = max(0.0, self.health / OSHA_INSPECTOR_HEALTH)
        pygame.draw.rect(surface, (40, 40, 40), (cx - bar_w // 2, cy - 28, bar_w, bar_h))
        pygame.draw.rect(
            surface, (220, 50, 50), (cx - bar_w // 2, cy - 28, int(bar_w * pct), bar_h)
        )
