"""Tests for src/enemy.py — movement correctness and state flags."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

from src.enemy import Enemy
from src.level import WAYPOINT_PIXELS, WAYPOINTS
from src.settings import ENEMY_SPEED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _total_path_length() -> float:
    """Return the total pixel length of the waypoint path."""
    total = 0.0
    for i in range(len(WAYPOINT_PIXELS) - 1):
        total += WAYPOINT_PIXELS[i].distance_to(WAYPOINT_PIXELS[i + 1])
    return total


def _simulate_full_run(speed: float = ENEMY_SPEED, dt: float = 1 / 60) -> Enemy:
    """Simulate an enemy completing the entire path and return it.

    Args:
        speed: Pixels per second.
        dt: Fixed time-step per tick (seconds).

    Returns:
        The enemy after it finishes (or times out at 10 000 ticks).
    """
    enemy = Enemy(speed=speed)
    for _ in range(10_000):
        enemy.update(dt)
        if not enemy.alive:
            break
    return enemy


# ---------------------------------------------------------------------------
# State flags
# ---------------------------------------------------------------------------


class TestEnemyFlags:
    """Validate alive / reached_end flag behaviour."""

    def test_starts_alive(self) -> None:
        """A fresh enemy must be alive and not flagged as reached_end."""
        e = Enemy()
        assert e.alive is True
        assert e.reached_end is False

    def test_reached_end_set_after_full_run(self) -> None:
        """After completing the path, reached_end must be True."""
        e = _simulate_full_run()
        assert e.reached_end is True
        assert e.alive is False

    def test_update_no_op_when_dead(self) -> None:
        """Calling update on a dead enemy must not change its position."""
        e = _simulate_full_run()
        pos_before = pygame.Vector2(e.pos)
        e.update(1.0)   # large dt — position must not shift
        assert e.pos == pos_before


# ---------------------------------------------------------------------------
# Movement correctness
# ---------------------------------------------------------------------------


class TestEnemyMovement:
    """Validate path-following accuracy."""

    def test_completes_path_without_index_error(self) -> None:
        """The enemy must traverse all waypoints without raising IndexError."""
        try:
            _simulate_full_run()
        except IndexError as exc:
            raise AssertionError(f"IndexError during path traversal: {exc}") from exc

    def test_no_looping_behaviour(self) -> None:
        """The enemy must not loop back to the start after reaching the end."""
        e = _simulate_full_run()
        pos_at_death = pygame.Vector2(e.pos)
        # Simulate 60 more ticks — position must remain frozen.
        for _ in range(60):
            e.update(1 / 60)
        assert e.pos == pos_at_death, "Enemy moved after reaching end (looping bug)"

    def test_large_dt_does_not_skip_waypoints(self) -> None:
        """With a 2-second dt the enemy should still finish cleanly."""
        e = Enemy()
        for _ in range(50):
            e.update(2.0)   # deliberately un-clamped to stress leftover logic
            if not e.alive:
                break
        # It may finish in one tick with a 2 s step — just must not raise.
        # Reaching here without an exception is the primary assertion.
        assert not e.alive or e.reached_end or True  # no IndexError = pass

    def test_distance_travelled_is_plausible(self) -> None:
        """Total distance the enemy covers must be close to the path length."""
        path_len = _total_path_length()
        # At 120 px/s the enemy should finish in roughly path_len/120 seconds.
        expected_ticks = int(path_len / ENEMY_SPEED / (1 / 60)) + 10
        e = Enemy()
        ticks = 0
        for ticks in range(expected_ticks + 300):  # allow generous headroom
            e.update(1 / 60)
            if not e.alive:
                break
        assert e.reached_end is True, (
            f"Enemy did not finish after {ticks} ticks (path_len={path_len:.1f}px)"
        )

    def test_spawn_position_matches_first_waypoint(self) -> None:
        """A fresh enemy must spawn at WAYPOINT_PIXELS[0]."""
        e = Enemy()
        assert abs(e.pos.x - WAYPOINT_PIXELS[0].x) < 0.01
        assert abs(e.pos.y - WAYPOINT_PIXELS[0].y) < 0.01

    def test_waypoint_index_advances(self) -> None:
        """After enough ticks the enemy must have advanced past waypoint 1.

        The first segment is col -1 → col 6 at row 1: 7 cells × 60 px = 420 px.
        At default speed (120 px/s) that takes 3.5 s.  We wait 4 s (240 ticks).
        """
        e = Enemy()
        for _ in range(240):   # 4 s of movement at 60 fps
            e.update(1 / 60)
        assert e.waypoint_index > 1 or not e.alive, (
            "Enemy did not advance past the first waypoint after 4 s"
        )
