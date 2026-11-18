"""Jobsite Defense — wave management and creep spawning lifecycle.

Coordinates timed waves of enemy incursions:
- ``WaveSpec``: Immutable wave configuration (enemy class, count, spawn interval, route).
- ``WaveManager``: Lifecycle state machine (COOLDOWN -> SPAWNING -> ACTIVE -> VICTORY)
  satisfying the ``Entity`` protocol at layer 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import pygame

from src.enemy import Enemy, HOABoardMember, OshaInspector, RainCloud, Rotted2x4
from src.settings import WINDOW_WIDTH

if TYPE_CHECKING:
    from src.world import World


class WaveState(Enum):
    """Lifecycle states of the wave progression system."""

    COOLDOWN = "COOLDOWN"
    SPAWNING = "SPAWNING"
    ACTIVE = "ACTIVE"
    VICTORY = "VICTORY"


@dataclass
class WaveSpec:
    """Specification for a single wave of enemies.

    Attributes:
        enemy: The enemy subclass to instantiate.
        count: Number of enemies to spawn.
        interval: Delay between consecutive spawns in seconds.
        path: Key of the navigational path in level.paths (default "main").
    """

    enemy: type[Enemy]
    count: int
    interval: float
    path: str = "main"


# Default campaign wave progression
DEFAULT_WAVES: list[WaveSpec] = [
    WaveSpec(enemy=Rotted2x4, count=6, interval=1.0),
    WaveSpec(enemy=HOABoardMember, count=16, interval=0.25),
    WaveSpec(enemy=RainCloud, count=4, interval=1.5),
    WaveSpec(enemy=Rotted2x4, count=10, interval=0.7),
    WaveSpec(enemy=OshaInspector, count=1, interval=1.0),
]


@dataclass
class WaveManager:
    """Manages wave progression, timers, and spawning creeps into ``World``.

    Starts in COOLDOWN (15s breather) before the first wave begins.

    Attributes:
        waves: Sequence of wave definitions (WaveSpec).
        wave_index: 0-based index of the currently active wave.
        state: Current lifecycle state (COOLDOWN, SPAWNING, ACTIVE, VICTORY).
        spawn_timer: Countdown until next creep spawn.
        spawned_count: Creeps spawned so far in the current wave.
        cooldown_duration: Length of breather period in seconds.
        cooldown_timer: Countdown remaining in COOLDOWN state.
        layer: Render/update layer — wave manager sits at layer 5.
    """

    waves: list[WaveSpec] = field(default_factory=lambda: list(DEFAULT_WAVES))
    wave_index: int = 0
    state: WaveState = WaveState.COOLDOWN
    spawn_timer: float = 0.0
    spawned_count: int = 0
    cooldown_duration: float = 15.0
    cooldown_timer: float = 15.0
    layer: int = 5

    _font: pygame.font.Font | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize cooldown timer and font safely."""
        self.cooldown_timer = self.cooldown_duration
        if pygame.font.get_init():
            self._font = pygame.font.Font(None, 22)

    # ------------------------------------------------------------------
    # Entity Protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """Advance the wave state machine by *dt* seconds.

        Args:
            dt: Clamped delta-time.
            world: Shared ``World`` context.
        """
        if self.state == WaveState.VICTORY:
            return

        if self.state == WaveState.COOLDOWN:
            self.cooldown_timer -= dt
            if self.cooldown_timer <= 0.0:
                self.state = WaveState.SPAWNING
                self.spawned_count = 0
                self.spawn_timer = 0.0

        if self.state == WaveState.SPAWNING:
            current_wave = self.waves[self.wave_index]

            self.spawn_timer -= dt
            if self.spawn_timer <= 0.0 and self.spawned_count < current_wave.count:
                self.spawn_timer = current_wave.interval
                self.spawned_count += 1

                route_pixels: tuple[tuple[float, float], ...] = ()
                if world.level and world.level.paths:
                    path_data = world.level.paths.get(current_wave.path) or world.level.primary_path
                    route_pixels = path_data.pixels

                spawn_pos = (
                    pygame.Vector2(*route_pixels[0])
                    if route_pixels
                    else pygame.Vector2(0, 0)
                )
                world.enemies.append(
                    current_wave.enemy(pos=spawn_pos, path=route_pixels)
                )

                if self.spawned_count >= current_wave.count:
                    self.state = WaveState.ACTIVE

        elif self.state == WaveState.ACTIVE and (
            not world.enemies or not any(e.alive for e in world.enemies)
        ):
            self.wave_index += 1
            if self.wave_index < len(self.waves):
                self.state = WaveState.COOLDOWN
                self.cooldown_timer = self.cooldown_duration
            else:
                self.state = WaveState.VICTORY

    def draw(self, surface: pygame.Surface) -> None:
        """Render wave progression indicator in the top-right corner."""
        if self._font is None and pygame.font.get_init():
            self._font = pygame.font.Font(None, 22)
        if self._font is None:
            return

        if self.state == WaveState.VICTORY:
            txt = "All Waves Cleared! (Jobsite Safe)"
            color = (100, 230, 100)
        elif self.state == WaveState.COOLDOWN:
            txt = (
                f"Wave {self.wave_index + 1}/{len(self.waves)} "
                f"Breather: {self.cooldown_timer:.0f}s"
            )
            color = (255, 200, 80)
        else:
            current_wave = self.waves[self.wave_index]
            txt = (
                f"Wave {self.wave_index + 1}/{len(self.waves)} "
                f"({self.spawned_count}/{current_wave.count})"
            )
            color = (220, 220, 220)

        surf = self._font.render(txt, True, color)
        surface.blit(surf, (WINDOW_WIDTH - surf.get_width() - 10, 6))
