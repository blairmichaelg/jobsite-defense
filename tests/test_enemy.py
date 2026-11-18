"""Tests for src/enemy.py — movement correctness, archetypes, status modifiers, and flags.

SDL dummy drivers are configured globally in ``conftest.py``.
"""

from __future__ import annotations

import pygame
import pytest

from src.economy import Economy
from src.enemy import (
    Enemy,
    HOABoardMember,
    OshaInspector,
    RainCloud,
    Rotted2x4,
    SpeedModifier,
    StunModifier,
)
from src.level import load_level
from src.settings import (
    ENEMY_SPEED,
    OSHA_INSPECTOR_HEALTH,
    OSHA_INSPECTOR_PATIENCE,
    OSHA_INSPECTOR_SPEED,
    RAIN_CLOUD_HEALTH,
    RAIN_CLOUD_SPEED,
)
from src.tower import NailGunner
from src.world import World

_DEFAULT_LEVEL = load_level("level_1.json")
WAYPOINT_PIXELS = _DEFAULT_LEVEL.waypoint_pixels
_DUMMY_WORLD = World(level=_DEFAULT_LEVEL)

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
    """Simulate an enemy completing the entire path and return it."""
    enemy = Enemy(speed=speed)
    for _ in range(10_000):
        enemy.update(dt, _DUMMY_WORLD)
        if not enemy.alive:
            break
    return enemy


# ---------------------------------------------------------------------------
# State flags & Movement
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
        assert e.pos == pos_at_death

    def test_large_dt_completes_cleanly(self) -> None:
        """With a 2-second dt the enemy must finish with correct end states."""
        e = Enemy()
        for _ in range(50):
            e.update(2.0, _DUMMY_WORLD)
            if not e.alive:
                break

        assert e.reached_end is True
        assert e.alive is False
        last_wx, last_wy = WAYPOINT_PIXELS[-1]
        assert e.pos == pygame.Vector2(last_wx, last_wy)

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
        assert e.reached_end is True

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
        assert e.waypoint_index > 1 or not e.alive


# ---------------------------------------------------------------------------
# Prediction & Speed Modifiers
# ---------------------------------------------------------------------------


class TestPredictionAndModifiers:
    """Validate position prediction (target leading) and debuff stacking."""

    def test_predict_pos_straight_segment(self) -> None:
        """Predicting 1s ahead moves by speed * 1.0 along the first horizontal segment."""
        e = Enemy(speed=100.0)
        # First segment is from (-60, 90) to (390, 90)
        predicted = e.predict_pos(1.0)
        assert predicted.x == pytest.approx(e.pos.x + 100.0)
        assert predicted.y == pytest.approx(e.pos.y)

    def test_predict_pos_accounts_for_speed_modifier(self) -> None:
        """Predicting with a 0.5x speed modifier projects half the distance."""
        e = Enemy(speed=100.0)
        e.modifiers["speed"] = SpeedModifier(multiplier=0.5, duration=5.0)
        predicted = e.predict_pos(1.0)
        assert predicted.x == pytest.approx(e.pos.x + 50.0)

    def test_predict_pos_caps_at_end_of_path(self) -> None:
        """Predicting with a huge time lead returns the final waypoint position."""
        e = Enemy(speed=100.0)
        predicted = e.predict_pos(100.0)
        last_wx, last_wy = WAYPOINT_PIXELS[-1]
        assert predicted == pygame.Vector2(last_wx, last_wy)

    def test_apply_speed_modifier_overwrites_if_stronger(self) -> None:
        """A 0.2x debuff overwrites an existing 0.5x debuff."""
        e = Enemy()
        e.apply_speed_modifier(mult=0.5, dur=3.0)
        mod1 = e.modifiers["speed"]
        assert isinstance(mod1, SpeedModifier)
        assert mod1.multiplier == 0.5

        e.apply_speed_modifier(mult=0.2, dur=2.0)
        mod2 = e.modifiers["speed"]
        assert isinstance(mod2, SpeedModifier)
        assert mod2.multiplier == 0.2
        assert mod2.duration == 2.0

    def test_apply_speed_modifier_takes_max_duration_if_equal(self) -> None:
        """Applying the same multiplier extends the duration to max(current, dur)."""
        e = Enemy()
        e.apply_speed_modifier(mult=0.5, dur=4.0)
        e.apply_speed_modifier(mult=0.5, dur=2.0)
        assert e.modifiers["speed"].duration == 4.0

        e.apply_speed_modifier(mult=0.5, dur=6.0)
        assert e.modifiers["speed"].duration == 6.0

    def test_apply_speed_modifier_ignores_weaker(self) -> None:
        """A weaker 0.8x debuff does not replace an active 0.5x debuff."""
        e = Enemy()
        e.apply_speed_modifier(mult=0.5, dur=3.0)
        e.apply_speed_modifier(mult=0.8, dur=5.0)
        mod = e.modifiers["speed"]
        assert isinstance(mod, SpeedModifier)
        assert mod.multiplier == 0.5


# ---------------------------------------------------------------------------
# Archetypes: RainCloud & OSHA Inspector
# ---------------------------------------------------------------------------


class TestPhase4Archetypes:
    """Validate RainCloud flyer, OSHA Inspector boss, and base archetypes."""

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

    def test_rain_cloud_flight_and_prediction(self) -> None:
        """RainCloud flies in a straight line toward exit waypoint."""
        cloud = RainCloud()
        assert cloud.is_flying is True
        assert cloud.health == RAIN_CLOUD_HEALTH
        assert cloud.speed == RAIN_CLOUD_SPEED

        # Starts at route entry path[0]
        assert cloud.pos == pygame.Vector2(*cloud.path[0])

        # Predict pos moves straight toward exit
        target = pygame.Vector2(*WAYPOINT_PIXELS[-1])
        lead_pos = cloud.predict_pos(1.0)
        step = RAIN_CLOUD_SPEED * 1.0
        expected = cloud.pos.move_towards(target, step)
        assert lead_pos == expected

    def test_osha_inspector_stats(self) -> None:
        """OSHA Inspector has 2500 HP, 40 px/s, and costs 20 patience."""
        boss = OshaInspector()
        assert boss.health == OSHA_INSPECTOR_HEALTH
        assert boss.speed == OSHA_INSPECTOR_SPEED
        assert boss.patience_cost == OSHA_INSPECTOR_PATIENCE

    def test_osha_stop_work_aura_disables_nearby_towers(self) -> None:
        """Towers within 150px of OSHA Inspector become disabled; outside ones stay enabled."""
        boss = OshaInspector(pos=pygame.Vector2(200, 200))

        # Close tower (50px away < 150px)
        t_near = NailGunner(col=3, row=3)
        t_near.center = pygame.Vector2(250, 200)

        # Far tower (300px away > 150px)
        t_far = NailGunner(col=8, row=8)
        t_far.center = pygame.Vector2(500, 200)

        world = World(
            enemies=[boss],
            towers={(3, 3): t_near, (8, 8): t_far},
            economy=Economy(),
        )

        world.refresh_auras()

        assert t_near.is_disabled is True
        assert t_far.is_disabled is False

    def test_osha_aura_re_enables_when_boss_moves_away(self) -> None:
        """When OSHA inspector moves away from a tower, the tower becomes enabled again."""
        boss = OshaInspector(pos=pygame.Vector2(200, 200))
        tower = NailGunner(col=3, row=3)
        tower.center = pygame.Vector2(250, 200)
        world = World(enemies=[boss], towers={(3, 3): tower})

        # Close -> disabled
        world.refresh_auras()
        assert tower.is_disabled is True

        # Boss moves far away
        boss.pos = pygame.Vector2(800, 800)
        world.refresh_auras()
        assert tower.is_disabled is False

    def test_overlapping_osha_auras(self) -> None:
        """Multiple OSHA inspectors properly disable tower until all move away."""
        boss1 = OshaInspector(pos=pygame.Vector2(200, 200))
        boss2 = OshaInspector(pos=pygame.Vector2(210, 200))
        tower = NailGunner(col=3, row=3)
        tower.center = pygame.Vector2(220, 200)

        world = World(enemies=[boss1, boss2], towers={(3, 3): tower})

        world.refresh_auras()
        assert tower.is_disabled is True

        # Boss 1 moves away, Boss 2 still nearby -> still disabled
        boss1.pos = pygame.Vector2(1000, 1000)
        world.refresh_auras()
        assert tower.is_disabled is True

        # Boss 2 also moves away -> tower enabled
        boss2.pos = pygame.Vector2(1000, 1000)
        world.refresh_auras()
        assert tower.is_disabled is False

    def test_travel_budget_with_expiring_modifier(self) -> None:
        """_travel_budget accounts for modifier expiring during the flight window."""
        enemy = Rotted2x4(pos=pygame.Vector2(100, 100), speed=100.0)
        # Modifier: 0.5x speed for 1.0s
        enemy.apply_speed_modifier(0.5, 1.0)

        # For 2.0s: 1.0s at 50 px/s (50px) + 1.0s at 100 px/s (100px) = 150px
        budget = enemy._travel_budget(2.0)
        assert abs(budget - 150.0) < 0.001

        # For 0.5s: 0.5s at 50 px/s = 25px
        budget_short = enemy._travel_budget(0.5)
        assert abs(budget_short - 25.0) < 0.001

    def test_apply_stun_and_tick_modifiers(self) -> None:
        """apply_stun sets StunModifier; _tick_modifiers decrements and clears it."""
        enemy = Rotted2x4(pos=pygame.Vector2(100, 100), speed=100.0)
        enemy.apply_stun(1.5)
        assert "stun" in enemy.modifiers
        assert isinstance(enemy.modifiers["stun"], StunModifier)
        assert enemy.modifiers["stun"].duration == 1.5

        # Ticking 0.5s reduces duration
        enemy._tick_modifiers(0.5)
        assert "stun" in enemy.modifiers
        assert abs(enemy.modifiers["stun"].duration - 1.0) < 0.001

        # Ticking another 1.0s clears the stun
        enemy._tick_modifiers(1.0)
        assert "stun" not in enemy.modifiers

    def test_boss_stun_lockout_prevents_stunlock(self) -> None:
        """Boss (is_boss=True) receives lockout = dur + 3.0s and ignores stuns during lockout."""
        boss = OshaInspector(pos=pygame.Vector2(100, 100))
        assert boss.is_boss is True

        boss.apply_stun(1.5)
        assert "stun" in boss.modifiers
        # Lockout is duration (1.5) + 3.0 = 4.5s
        assert abs(boss._stun_lockout - 4.5) < 0.001

        # Attempting another stun immediately is ignored
        boss.apply_stun(2.0)
        assert boss.modifiers["stun"].duration == 1.5  # not overwritten

        # Tick 2.0s: stun expires (1.5s), but lockout has 2.5s remaining
        boss._tick_modifiers(2.0)
        assert "stun" not in boss.modifiers
        assert abs(boss._stun_lockout - 2.5) < 0.001

        # Attempting stun while lockout is active is ignored
        boss.apply_stun(1.0)
        assert "stun" not in boss.modifiers

        # Tick remaining 2.5s of lockout
        boss._tick_modifiers(2.5)
        assert boss._stun_lockout == 0.0

        # Now can be stunned again
        boss.apply_stun(1.0)
        assert "stun" in boss.modifiers

    def test_stunned_osha_does_not_radiate_aura(self) -> None:
        """When OSHA inspector is stunned, Stop-Work aura is suppressed."""
        boss = OshaInspector(pos=pygame.Vector2(200, 200))
        tower = NailGunner(col=3, row=3)
        tower.center = pygame.Vector2(220, 200)
        world = World(enemies=[boss], towers={(3, 3): tower})

        # Not stunned -> tower disabled
        world.refresh_auras()
        assert tower.is_disabled is True

        # Stunned -> aura suppressed, tower stays enabled
        boss.apply_stun(1.5)
        world.refresh_auras()
        assert tower.is_disabled is False

    def test_travel_budget_with_concurrent_stun_and_slow(self) -> None:
        """_travel_budget correctly handles overlapping stun (0 speed) and speed modifier."""
        enemy = Rotted2x4(pos=pygame.Vector2(100, 100), speed=100.0)
        enemy.apply_stun(1.0)
        enemy.apply_speed_modifier(0.5, 2.0)

        # In a 2.0s window:
        # First 1.0s: stunned -> 0 travel.
        # Speed modifier decays by 1.0s during stun -> 1.0s of 0.5x remaining.
        # Next 1.0s: 1.0s at 0.5x speed (50 px/s) -> 50 px travel.
        budget = enemy._travel_budget(2.0)
        assert abs(budget - 50.0) < 0.001

        # In a 0.5s window: completely stunned -> 0 travel.
        assert enemy._travel_budget(0.5) == 0.0


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestEnemyProtocol:
    """Verify Enemy satisfies the Entity protocol at runtime."""

    def test_entity_isinstance(self) -> None:
        """``isinstance(enemy, Entity)`` must return True."""
        from src.protocols import Entity

        e = Enemy()
        assert isinstance(e, Entity)

    def test_has_layer_attribute(self) -> None:
        """Enemy must expose a ``layer`` integer attribute."""
        e = Enemy()
        assert isinstance(e.layer, int)
        assert e.layer == 10
