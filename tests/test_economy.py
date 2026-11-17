"""Tests for src/economy.py — budget spending, earning, and patience."""

from __future__ import annotations

import pytest

from src.economy import Economy


class TestSpending:
    """Verify budget deduction logic."""

    def test_spend_succeeds_when_affordable(self) -> None:
        """spend() must return True and deduct the cost when funds allow."""
        eco = Economy(project_budget=1000)
        result = eco.spend(400)
        assert result is True
        assert eco.project_budget == 600

    def test_spend_fails_when_insufficient(self) -> None:
        """spend() must return False and leave budget unchanged when too low."""
        eco = Economy(project_budget=100)
        result = eco.spend(500)
        assert result is False
        assert eco.project_budget == 100

    def test_spend_fails_on_exact_zero_budget(self) -> None:
        """spend() must fail when budget is exactly 0."""
        eco = Economy(project_budget=0)
        assert eco.spend(1) is False
        assert eco.project_budget == 0

    def test_spend_succeeds_on_exact_match(self) -> None:
        """spend() must succeed when cost == budget (boundary condition)."""
        eco = Economy(project_budget=500)
        assert eco.spend(500) is True
        assert eco.project_budget == 0

    def test_can_afford_true_when_enough(self) -> None:
        eco = Economy(project_budget=1500)
        assert eco.can_afford(500) is True

    def test_can_afford_false_when_broke(self) -> None:
        eco = Economy(project_budget=50)
        assert eco.can_afford(500) is False


class TestEarning:
    """Verify budget credit logic."""

    def test_earn_increases_budget(self) -> None:
        """earn() must add the amount to project_budget."""
        eco = Economy(project_budget=1000)
        eco.earn(15)
        assert eco.project_budget == 1015

    def test_earn_zero_is_no_op(self) -> None:
        """earn(0) must leave budget unchanged."""
        eco = Economy(project_budget=800)
        eco.earn(0)
        assert eco.project_budget == 800

    def test_earn_raises_on_negative(self) -> None:
        """earn() must raise ValueError for negative amounts."""
        eco = Economy()
        with pytest.raises(ValueError, match="non-negative"):
            eco.earn(-1)

    def test_earn_multiple_times(self) -> None:
        """Multiple earn() calls must accumulate correctly."""
        eco = Economy(project_budget=0)
        eco.earn(15)
        eco.earn(15)
        eco.earn(15)
        assert eco.project_budget == 45


class TestPatience:
    """Verify client patience clamping and game-over state."""

    def test_patience_decrements(self) -> None:
        """lose_patience() must decrement by 1 by default."""
        eco = Economy(client_patience=10)
        eco.lose_patience()
        assert eco.client_patience == 9

    def test_patience_clamps_at_zero(self) -> None:
        """Patience must never go below 0, even with large deductions."""
        eco = Economy(client_patience=1)
        eco.lose_patience(amount=100)
        assert eco.client_patience == 0

    def test_patience_clamps_multiple_calls(self) -> None:
        """Calling lose_patience() on an already-zero patience stays at 0."""
        eco = Economy(client_patience=0)
        eco.lose_patience()
        eco.lose_patience()
        assert eco.client_patience == 0

    def test_game_over_when_zero(self) -> None:
        """game_over property must be True exactly when patience reaches 0."""
        eco = Economy(client_patience=1)
        assert eco.game_over is False
        eco.lose_patience()
        assert eco.game_over is True

    def test_game_over_false_when_positive(self) -> None:
        eco = Economy(client_patience=100)
        assert eco.game_over is False
