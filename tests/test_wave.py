"""Tests for src/wave.py — Wave state machine, intervals, and creep spawning.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

from src.economy import Economy
from src.enemy import HOABoardMember, Rotted2x4
from src.wave import WaveManager, WaveState
from src.world import World


def _get_state(m: WaveManager) -> WaveState:
    """Return manager state without static narrowing."""
    return m.state


class TestWaveManager:
    """Verify WaveManager state transitions and enemy generation."""

    def test_wave_manager_spawns_on_interval(self) -> None:
        """WaveManager spawns creeps into world.enemies at the specified interval."""
        waves = [{"enemy_type": "Rotted2x4", "count": 2, "interval": 0.5}]
        manager = WaveManager(waves=waves)
        world = World(economy=Economy())

        assert _get_state(manager) == WaveState.SPAWNING
        assert len(world.enemies) == 0

        # Step 0.1s — initial spawn triggers because spawn_timer starts at 0.0
        manager.update(0.1, world)
        assert len(world.enemies) == 1
        assert isinstance(world.enemies[0], Rotted2x4)
        assert manager.spawned_count == 1
        assert _get_state(manager) == WaveState.SPAWNING

        # Step 0.2s — interval is 0.5s, so no second spawn yet
        manager.update(0.2, world)
        assert len(world.enemies) == 1

        # Step 0.3s — elapsed 0.6s > 0.5s interval, triggers second spawn
        manager.update(0.3, world)
        assert len(world.enemies) == 2
        assert manager.spawned_count == 2
        # All 2 spawned -> transitions to ACTIVE
        assert _get_state(manager) == WaveState.ACTIVE

    def test_wave_transitions_to_cooldown_and_next_wave(self) -> None:
        """After all wave enemies are dead, manager enters COOLDOWN then spawns wave 2."""
        waves = [
            {"enemy_type": "Rotted2x4", "count": 1, "interval": 0.1},
            {"enemy_type": "HOABoardMember", "count": 1, "interval": 0.1},
        ]
        manager = WaveManager(waves=waves, cooldown_duration=2.0)
        world = World(economy=Economy())

        # Spawn wave 1 creep
        manager.update(0.15, world)
        assert _get_state(manager) == WaveState.ACTIVE
        assert len(world.enemies) == 1

        # Kill the creep and cull it
        world.enemies[0].alive = False
        world.enemies[:] = [e for e in world.enemies if e.alive]

        # Update manager: sees board is clear, enters COOLDOWN
        manager.update(0.1, world)
        assert _get_state(manager) == WaveState.COOLDOWN
        assert manager.wave_index == 1

        # Fast forward through cooldown (2.0s)
        manager.update(2.1, world)
        assert _get_state(manager) == WaveState.SPAWNING

        # Next tick spawns HOABoardMember from wave 2
        manager.update(0.1, world)
        assert len(world.enemies) == 1
        assert isinstance(world.enemies[0], HOABoardMember)
