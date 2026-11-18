"""Tests for src/wave.py — Wave state machine, WaveSpec typing, and creep spawning.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

from src.economy import Economy
from src.enemy import HOABoardMember, Rotted2x4
from src.wave import WaveManager, WaveSpec, WaveState
from src.world import World


def _get_state(m: WaveManager) -> WaveState:
    """Return manager state without static narrowing."""
    return m.state


class TestWaveManager:
    """Verify WaveManager state transitions, initial cooldown, and typed specs."""

    def test_wave_manager_starts_in_cooldown_before_wave_1(self) -> None:
        """WaveManager must start in COOLDOWN (15s breather) before wave 1 begins."""
        waves = [WaveSpec(enemy=Rotted2x4, count=2, interval=0.5)]
        manager = WaveManager(waves=waves, cooldown_duration=15.0)
        assert _get_state(manager) == WaveState.COOLDOWN
        assert manager.cooldown_timer == 15.0

    def test_wave_manager_spawns_on_interval_after_cooldown(self) -> None:
        """WaveManager starts after cooldown, spawning creeps on interval into world.enemies."""
        waves = [WaveSpec(enemy=Rotted2x4, count=2, interval=0.5)]
        manager = WaveManager(waves=waves, cooldown_duration=1.0)
        world = World(economy=Economy())

        # Step 0.5s into cooldown
        manager.update(0.5, world)
        assert _get_state(manager) == WaveState.COOLDOWN
        assert len(world.enemies) == 0

        # Step remaining 0.6s to finish cooldown (1.1s total) -> transitions to SPAWNING
        manager.update(0.6, world)
        assert _get_state(manager) == WaveState.SPAWNING
        # First spawn triggers immediately upon entering SPAWNING
        assert len(world.enemies) == 1
        assert isinstance(world.enemies[0], Rotted2x4)
        assert manager.spawned_count == 1

        # Step 0.2s — interval is 0.5s, no second spawn yet
        manager.update(0.2, world)
        assert len(world.enemies) == 1

        # Step 0.4s — 0.6s > 0.5s interval -> second spawn triggers
        manager.update(0.4, world)
        assert len(world.enemies) == 2
        assert manager.spawned_count == 2
        assert _get_state(manager) == WaveState.ACTIVE

    def test_wave_transitions_to_cooldown_and_next_wave(self) -> None:
        """After all wave enemies are dead, manager enters COOLDOWN then spawns wave 2."""
        waves = [
            WaveSpec(enemy=Rotted2x4, count=1, interval=0.1),
            WaveSpec(enemy=HOABoardMember, count=1, interval=0.1),
        ]
        manager = WaveManager(waves=waves, cooldown_duration=1.0)
        world = World(economy=Economy())

        # Finish initial cooldown (1.0s)
        manager.update(1.1, world)
        assert _get_state(manager) == WaveState.ACTIVE  # 1 count spawns immediately -> ACTIVE
        assert len(world.enemies) == 1

        # Kill creep and cull
        world.enemies[0].alive = False
        world.enemies[:] = [e for e in world.enemies if e.alive]

        # Update manager: enters COOLDOWN for wave 2
        manager.update(0.1, world)
        assert _get_state(manager) == WaveState.COOLDOWN
        assert manager.wave_index == 1

        # Finish wave 2 cooldown
        manager.update(1.1, world)
        assert len(world.enemies) == 1
        assert isinstance(world.enemies[0], HOABoardMember)
