"""Jobsite Defense — wave management and creep spawning.

Phase 3 implementation
----------------------
* ``WaveManager``: Coordinates scheduled enemy waves across 3 lifecycle states:
  - ``SPAWNING``: Periodically instantiates enemies at the spawn waypoint.
  - ``ACTIVE``: Awaiting total clearance of active creeps from the board.
  - ``COOLDOWN``: 15-second breather between successive waves.
* Satisfies the ``Entity`` protocol at layer 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import pygame

from src.enemy import HOABoardMember, Rotted2x4
from src.settings import WINDOW_WIDTH

if TYPE_CHECKING:
    from src.world import World


class WaveState(Enum):
    """Lifecycle states of the wave progression system."""

    SPAWNING = "SPAWNING"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    VICTORY = "VICTORY"


# Hardcoded wave campaign specifications
DEFAULT_WAVES: list[dict[str, Any]] = [
    {"enemy_type": "Rotted2x4", "count": 6, "interval": 1.0},
    {"enemy_type": "HOABoardMember", "count": 15, "interval": 0.25},
    {"enemy_type": "Rotted2x4", "count": 10, "interval": 0.7},
    {"enemy_type": "HOABoardMember", "count": 25, "interval": 0.2},
]


@dataclass
class WaveManager:
    """Manages wave progression, timers, and spawning creeps into ``World``.

    Attributes:
        waves: Sequence of wave definitions (enemy_type, count, interval).
        wave_index: 0-based index of the currently active wave.
        state: Current lifecycle state (SPAWNING, ACTIVE, COOLDOWN, VICTORY).
        spawn_timer: Countdown until next creep spawn.
        spawned_count: Creeps spawned so far in the current wave.
        cooldown_timer: Countdown remaining in COOLDOWN state (15s default).
        layer: Render/update layer — wave manager sits at layer 5.
    """

    waves: list[dict[str, Any]] = field(
        default_factory=lambda: [dict(w) for w in DEFAULT_WAVES]
    )
    wave_index: int = 0
    state: WaveState = WaveState.SPAWNING
    spawn_timer: float = 0.0
    spawned_count: int = 0
    cooldown_duration: float = 15.0
    cooldown_timer: float = 15.0
    layer: int = 5

    _font: pygame.font.Font | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize font safely (None until pygame.font is ready)."""
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

        if self.state == WaveState.SPAWNING:
            current_wave = self.waves[self.wave_index]
            total_count = int(current_wave["count"])
            interval = float(current_wave["interval"])

            self.spawn_timer -= dt
            if self.spawn_timer <= 0.0 and self.spawned_count < total_count:
                self.spawn_timer = interval
                self.spawned_count += 1
                self._spawn_enemy(current_wave["enemy_type"], world)

                if self.spawned_count >= total_count:
                    self.state = WaveState.ACTIVE

        elif self.state == WaveState.ACTIVE:
            # Check if all enemies in the world are eliminated
            if not world.enemies or not any(e.alive for e in world.enemies):
                self.wave_index += 1
                if self.wave_index < len(self.waves):
                    self.state = WaveState.COOLDOWN
                    self.cooldown_timer = self.cooldown_duration
                else:
                    self.state = WaveState.VICTORY

        elif self.state == WaveState.COOLDOWN:
            self.cooldown_timer -= dt
            if self.cooldown_timer <= 0.0:
                self.state = WaveState.SPAWNING
                self.spawned_count = 0
                self.spawn_timer = 0.0

    def _spawn_enemy(self, enemy_type: str, world: World) -> None:
        """Instantiate and append a creep of the requested archetype."""
        norm_type = enemy_type.lower().replace(" ", "").replace("_", "")
        if "hoa" in norm_type:
            world.enemies.append(HOABoardMember())
        else:
            world.enemies.append(Rotted2x4())

    def draw(self, surface: pygame.Surface) -> None:
        """Render wave progression indicator in the top-right corner."""
        if self._font is None and pygame.font.get_init():
            self._font = pygame.font.Font(None, 22)
        if self._font is None:
            return

        if self.state == WaveState.VICTORY:
            txt = "All Waves Cleared! (Contract Complete)"
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
                f"({self.spawned_count}/{current_wave['count']})"
            )
            color = (220, 220, 220)

        surf = self._font.render(txt, True, color)
        surface.blit(surf, (WINDOW_WIDTH - surf.get_width() - 10, 6))
