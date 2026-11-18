"""Tests for src/enemy.py — movement correctness, archetypes, status modifiers, and flags.

SDL dummy drivers are configured globally in ``conftest.py``; no
``os.environ`` setup is needed here.
"""

from __future__ import annotations

import pygame

from src.enemy import Enemy, HOABoardMember, Rotted2x4, SpeedModifier
from src.level import WAYPOINT_PIXELS
from src.settings import ENEMY_SPEED
from src.world import World

_DUMMY_WORLD = World()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _total_path_length() -> float:
    """Return the total pixel length of the waypoint path."""
    total = 0.0
    for i in range(len(WAYPOINT_PIXELS) - 1):
        ax, ay = WAYPOINT_PIXELS[i]
        bx, by = WAYPOINT_PIXELS[i + 1]
        total += pygame.Vector2(ax, ay).distance_to(pygame.Vector2(bx, by))
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
        enemy.update(dt, _DUMMY_WORLD)
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
        """After completing the path, reached_end must be True and alive False."""
        e = _simulate_full_run()
        assert e.reached_end is True
        assert e.alive is False

    def test_update_no_op_when_dead(self) -> None:
        """Calling update on a dead enemy must not change its position."""
        e = _simulate_full_run()
        pos_before = pygame.Vector2(e.pos)
        e.update(1.0, _DUMMY_WORLD)
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
        for _ in range(60):
            e.update(1 / 60, _DUMMY_WORLD)
        assert e.pos == pos_at_death, "Enemy moved after reaching end (looping bug)"

    def test_large_dt_completes_cleanly(self) -> None:
        """With a 2-second dt the enemy must finish with correct end states.

        Verifies:
        * ``e.reached_end is True``
        * ``e.alive is False``
        * ``e.pos`` equals the last waypoint pixel centre.
        """
        e = Enemy()
        for _ in range(50):
            e.update(2.0, _DUMMY_WORLD)   # deliberately un-clamped to stress leftover logic
            if not e.alive:
                break

        assert e.reached_end is True, "Enemy did not set reached_end after large-dt run"
        assert e.alive is False, "Enemy still marked alive after reaching end"
        last_wx, last_wy = WAYPOINT_PIXELS[-1]
        expected = pygame.Vector2(last_wx, last_wy)
        assert e.pos == expected, (
            f"Enemy pos {e.pos!r} does not match exit waypoint {expected!r}"
        )

    def test_distance_travelled_is_plausible(self) -> None:
        """Total distance the enemy covers must be close to the path length."""
        path_len = _total_path_length()
        expected_ticks = int(path_len / ENEMY_SPEED / (1 / 60)) + 10
        e = Enemy()
        _ticks = 0
        for _ticks in range(expected_ticks + 300):
            e.update(1 / 60, _DUMMY_WORLD)
            if not e.alive:
                break
        assert e.reached_end is True, (
            f"Enemy did not finish after {_ticks} ticks (path_len={path_len:.1f}px)"
        )

    def test_spawn_position_matches_first_waypoint(self) -> None:
        """A fresh enemy must spawn at WAYPOINT_PIXELS[0]."""
        e = Enemy()
        wx, wy = WAYPOINT_PIXELS[0]
        assert abs(e.pos.x - wx) < 0.01
        assert abs(e.pos.y - wy) < 0.01

    def test_waypoint_index_advances(self) -> None:
        """After enough ticks the enemy must have advanced past waypoint 1."""
        e = Enemy()
        for _ in range(240):
            e.update(1 / 60, _DUMMY_WORLD)
        assert e.waypoint_index > 1 or not e.alive, (
            "Enemy did not advance past the first waypoint after 4 s"
        )


# ---------------------------------------------------------------------------
# Archetypes & Status Effects
# ---------------------------------------------------------------------------


class TestEnemyArchetypes:
    """Validate Phase 3 enemy subclasses and status modifiers."""

    def test_rotted_2x4_stats(self) -> None:
        """Rotted2x4 has standard 100 HP, 120 px/s, and $15 bounty."""
        e = Rotted2x4()
        assert e.health == 100.0
        assert e.speed == 120.0
        assert e.bounty == 15

    def test_hoa_board_member_stats(self) -> None:
        """HOABoardMember is 50% faster (180 px/s), 1 HP, and $5 bounty."""
        e = HOABoardMember()
        assert e.health == 1.0
        assert e.speed == 180.0
        assert e.bounty == 5

    def test_speed_modifier_slows_movement(self) -> None:
        """Applying a 0.5x SpeedModifier halves the distance covered per update."""
        e_normal = Rotted2x4()
        e_slow = Rotted2x4()
        e_slow.modifiers["speed"] = SpeedModifier(multiplier=0.5, duration=3.0)

        dt = 0.05
        e_normal.update(dt, _DUMMY_WORLD)
        e_slow.update(dt, _DUMMY_WORLD)

        # Distance moved from spawn waypoint
        start = pygame.Vector2(*WAYPOINT_PIXELS[0])
        dist_normal = e_normal.pos.distance_to(start)
        dist_slow = e_slow.pos.distance_to(start)

        assert abs(dist_slow - dist_normal * 0.5) < 0.01

    def test_speed_modifier_expires_after_duration(self) -> None:
        """Modifier expires when duration drops to zero, restoring full speed."""
        e = Rotted2x4()
        e.modifiers["speed"] = SpeedModifier(multiplier=0.5, duration=0.1)

        # Step 0.06s (less than 0.1s -> modifier remains)
        e.update(0.06, _DUMMY_WORLD)
        assert "speed" in e.modifiers

        # Step another 0.06s (total 0.12s -> modifier expired)
        e.update(0.06, _DUMMY_WORLD)
        assert "speed" not in e.modifiers


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestEnemyProtocol:
    """Verify Enemy satisfies the Entity protocol at runtime."""

    def test_entity_isinstance(self) -> None:
        """``isinstance(enemy, Entity)`` must return True."""
        from src.protocols import Entity
        e = Enemy()
        assert isinstance(e, Entity), "Enemy does not satisfy the Entity protocol"

    def test_has_layer_attribute(self) -> None:
        """Enemy must expose a ``layer`` integer attribute."""
        e = Enemy()
        assert isinstance(e.layer, int)
        assert e.layer == 10
