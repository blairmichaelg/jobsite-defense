"""Jobsite Defense — enemy entity, archetypes, and movement.

Phase 6 updates:
- Stun status framework with boss stun-lockout immunity (_stun_lockout).
- Centralized modifier ticking (_tick_modifiers).
- Multi-modifier travel budget accounting for overlapping stun and speed debuffs.
- Route decoupling: Enemy.path holds route pixels from world.level.paths.
- RainCloud flies from path[0] to path[-1].
- OSHA Inspector stops radiating aura when stunned.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

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
    STUN_LOCKOUT_BOSS,
    STUN_LOCKOUT_REGULAR,
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
class StunModifier:
    """Temporary total movement and action incapacitation.

    Attributes:
        duration: Remaining stun duration in seconds.
    """

    duration: float = 1.5


@dataclass
class Enemy:
    """Base class for all creep entities traversing a navigational path.

    Attributes:
        pos: Current world position with sub-pixel precision.
        path: Ordered pixel coordinate tuples for the entity's path.
        waypoint_index: Index of the *next* pixel waypoint to reach.
        speed: Base movement speed in pixels per second.
        health: Remaining hit-points.
        bounty: Dollars awarded to the player when killed by towers/projectiles.
        patience_cost: Patience lost if this enemy escapes off-screen.
        is_flying: Whether the entity bypasses ground pathing.
        is_boss: Whether this entity has boss status immunities (e.g. stun lockout).
        alive: ``False`` once the enemy has left the field or died.
        reached_end: ``True`` when the enemy exited via the final waypoint.
        layer: Render/update layer — enemies sit at layer 10.
        modifiers: Status effects keyed by name (e.g. ``"speed"``, ``"stun"``).
        _stun_lockout: Seconds remaining before another stun can affect this unit.
    """

    pos: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0.0, 0.0))
    path: tuple[tuple[float, float], ...] = ()
    waypoint_index: int = 1
    speed: float = ENEMY_SPEED
    health: float = ENEMY_MAX_HEALTH
    bounty: int = 15
    patience_cost: int = 1
    is_flying: bool = False
    is_boss: bool = False
    alive: bool = True
    reached_end: bool = False
    layer: int = 10
    modifiers: dict[str, SpeedModifier | StunModifier] = field(default_factory=dict)
    _stun_lockout: float = 0.0

    def __post_init__(self) -> None:
        """Initialize position from path if not explicitly provided."""
        if not self.path:
            raise ValueError("Enemy requires a valid non-empty path tuple.")

        if self.pos.x == 0.0 and self.pos.y == 0.0:
            self.pos = pygame.Vector2(*self.path[0])

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
        """Apply or refresh a speed debuff according to stacking rules."""
        current = self.modifiers.get("speed")
        if current is None or not isinstance(current, SpeedModifier) or mult < current.multiplier:
            self.modifiers["speed"] = SpeedModifier(multiplier=mult, duration=dur)
        elif math.isclose(mult, current.multiplier, rel_tol=1e-5):
            current.duration = max(current.duration, dur)

    def apply_stun(self, dur: float) -> None:
        """Apply a stun debuff, respecting stun-lockout immunity."""
        if self._stun_lockout > 0.0:
            return
        self.modifiers["stun"] = StunModifier(duration=dur)
        if self.is_boss:
            self._stun_lockout = dur + STUN_LOCKOUT_BOSS
        else:
            self._stun_lockout = dur + STUN_LOCKOUT_REGULAR

    def _tick_modifiers(self, dt: float) -> None:
        """Tick all active status effects and update boss stun lockout."""
        if self._stun_lockout > 0.0:
            self._stun_lockout = max(0.0, self._stun_lockout - dt)

        expired: list[str] = []
        for key, mod in self.modifiers.items():
            mod.duration -= dt
            if mod.duration <= 0.0:
                expired.append(key)
        for key in expired:
            del self.modifiers[key]

    # ------------------------------------------------------------------
    # Position Prediction (Target Leading) & Aura
    # ------------------------------------------------------------------

    def _travel_budget(self, seconds: float) -> float:
        """Calculate exact pixel travel, accounting for concurrent stun and speed modifiers."""
        stun_mod = self.modifiers.get("stun")
        stun_dur = stun_mod.duration if stun_mod else 0.0

        stun_time = min(seconds, stun_dur)
        moving_time = seconds - stun_time

        if moving_time <= 0.0:
            return 0.0

        speed_mod = self.modifiers.get("speed")
        if speed_mod is None or not isinstance(speed_mod, SpeedModifier):
            return self.speed * moving_time

        remaining_speed_dur = max(0.0, speed_mod.duration - stun_time)
        slowed_time = min(moving_time, remaining_speed_dur)
        normal_time = moving_time - slowed_time

        return self.speed * (speed_mod.multiplier * slowed_time + normal_time)

    def predict_pos(self, seconds: float) -> pygame.Vector2:
        """Simulate future position after *seconds* along the waypoint path."""
        budget = self._travel_budget(seconds)
        pos = pygame.Vector2(self.pos)
        wp_idx = self.waypoint_index

        while budget > 0.0 and wp_idx < len(self.path):
            wx, wy = self.path[wp_idx]
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

    def apply_aura(self, world: World) -> None:
        """Apply any persistent area-of-effect aura to the world."""

    # ------------------------------------------------------------------
    # Update & Render
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Advance the enemy along its path, ticking status effects."""
        if not self.alive:
            return

        self._tick_modifiers(dt)

        # Stun incapacitates all movement
        if "stun" in self.modifiers:
            return

        if not self.path and world.level and world.level.paths:
            self.path = world.level.primary_path.pixels

        if not self.path:
            return

        effective_speed = self.speed
        speed_mod = self.modifiers.get("speed")
        if isinstance(speed_mod, SpeedModifier):
            effective_speed *= speed_mod.multiplier

        budget = effective_speed * dt

        while budget > 0.0 and self.waypoint_index < len(self.path):
            wx, wy = self.path[self.waypoint_index]
            target = pygame.Vector2(wx, wy)
            dist_to_target = self.pos.distance_to(target)

            if budget >= dist_to_target:
                self.pos = target
                budget -= dist_to_target
                self.waypoint_index += 1
            else:
                self.pos = self.pos.move_towards(target, budget)
                budget = 0.0

        if self.waypoint_index >= len(self.path):
            self.alive = False
            self.reached_end = True

    def draw(self, surface: pygame.Surface) -> None:
        """Render the enemy circle with outline and optional status rings."""
        center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.circle(surface, COLOR_ENEMY, center, ENEMY_RADIUS)
        pygame.draw.circle(surface, COLOR_ENEMY_OUTLINE, center, ENEMY_RADIUS, width=2)

        if "speed" in self.modifiers:
            pygame.draw.circle(surface, (150, 155, 150), center, ENEMY_RADIUS + 3, width=2)
        if "stun" in self.modifiers:
            pygame.draw.circle(surface, (255, 255, 100), center, ENEMY_RADIUS + 5, width=2)


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
        if "stun" in self.modifiers:
            pygame.draw.circle(surface, (255, 255, 100), center, radius + 5, width=2)


@dataclass
class RainCloud(Enemy):
    """Flying hazard creep — ignores the road, flies straight from path[0] to path[-1].

    Ground towers cannot target it unless equipped with air capability.
    """

    speed: float = RAIN_CLOUD_SPEED
    health: float = RAIN_CLOUD_HEALTH
    bounty: int = RAIN_CLOUD_BOUNTY
    patience_cost: int = 1
    is_flying: bool = True

    def predict_pos(self, seconds: float) -> pygame.Vector2:
        """Simulate future position flying directly toward final exit waypoint."""
        if not self.path:
            return pygame.Vector2(self.pos)
        target = pygame.Vector2(*self.path[-1])
        budget = self._travel_budget(seconds)
        dist = self.pos.distance_to(target)
        if budget >= dist:
            return target
        return self.pos.move_towards(target, budget)

    def update(self, dt: float, world: World) -> None:
        """Fly in a straight line from path[0] toward path[-1]."""
        if not self.alive:
            return

        self._tick_modifiers(dt)

        if "stun" in self.modifiers:
            return

        if not self.path and world.level and world.level.paths:
            self.path = world.level.primary_path.pixels

        if not self.path:
            return

        effective_speed = self.speed
        speed_mod = self.modifiers.get("speed")
        if isinstance(speed_mod, SpeedModifier):
            effective_speed *= speed_mod.multiplier

        target = pygame.Vector2(*self.path[-1])
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
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD, (cx - 8, cy), 12)
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD, (cx + 8, cy), 12)
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD, (cx, cy - 6), 14)
        pygame.draw.circle(surface, COLOR_RAIN_CLOUD_OUTLINE, (cx, cy), 16, width=1)
        pygame.draw.line(surface, (100, 160, 240), (cx - 6, cy + 14), (cx - 9, cy + 22), 2)
        pygame.draw.line(surface, (100, 160, 240), (cx + 6, cy + 14), (cx + 3, cy + 22), 2)

        if "stun" in self.modifiers:
            pygame.draw.circle(surface, (255, 255, 100), (cx, cy), 20, width=2)


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
    is_boss: bool = True

    def apply_aura(self, world: World) -> None:
        """Radiate Stop-Work Order disabling aura to towers within 150px unless stunned."""
        if not self.alive or "stun" in self.modifiers:
            return
        aura_sq = self.aura_radius ** 2
        for tower in world.towers.values():
            if self.pos.distance_squared_to(tower.center) <= aura_sq:
                tower.is_disabled = True

    def draw(self, surface: pygame.Surface) -> None:
        """Render the OSHA inspector with safety helmet and Stop-Work aura ring."""
        cx, cy = int(self.pos.x), int(self.pos.y)

        if self.alive and "stun" not in self.modifiers:
            pygame.draw.circle(surface, (230, 40, 40), (cx, cy), int(self.aura_radius), width=1)

        boss_radius = 18
        pygame.draw.circle(surface, COLOR_OSHA, (cx, cy), boss_radius)
        pygame.draw.circle(surface, COLOR_OSHA_OUTLINE, (cx, cy), boss_radius, width=3)
        pygame.draw.line(surface, (255, 255, 255), (cx - 10, cy - 6), (cx + 10, cy - 6), 3)

        if "stun" in self.modifiers:
            pygame.draw.circle(surface, (255, 255, 100), (cx, cy), boss_radius + 6, width=2)

        bar_w = 40
        bar_h = 5
        pct = max(0.0, self.health / OSHA_INSPECTOR_HEALTH)
        pygame.draw.rect(surface, (40, 40, 40), (cx - bar_w // 2, cy - 28, bar_w, bar_h))
        pygame.draw.rect(
            surface, (220, 50, 50), (cx - bar_w // 2, cy - 28, int(bar_w * pct), bar_h)
        )
