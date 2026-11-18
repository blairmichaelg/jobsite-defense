"""Jobsite Defense — Economy manager.

Tracks player financial resources (Project Budget) and client goodwill (Patience lives):
- Guards expenditures against overdrafts with atomic spending validation.
- Credits bounties earned from eliminated enemies.
- Tracks loss of patience on escaped creeps to signal contract termination.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Economy:
    """Central economy state for one game session.

    Attributes:
        project_budget: Spendable dollars.  Start: $1 500.
        client_patience: Lives remaining.  Start: 100.
    """

    project_budget: int = 1500
    client_patience: int = 100

    # ------------------------------------------------------------------
    # Spending & earning
    # ------------------------------------------------------------------

    def can_afford(self, cost: int) -> bool:
        """Return ``True`` if *cost* is within the current budget.

        Args:
            cost: Price in dollars.
        """
        return self.project_budget >= cost

    def spend(self, cost: int) -> bool:
        """Deduct *cost* from the budget if affordable.

        Args:
            cost: Price in dollars.

        Returns:
            ``True`` if the deduction succeeded; ``False`` if insufficient
            funds (budget is unchanged on failure).
        """
        if not self.can_afford(cost):
            return False
        self.project_budget -= cost
        return True

    def earn(self, amount: int) -> None:
        """Credit *amount* dollars to the project budget.

        Args:
            amount: Dollars to add.  Must be ≥ 0.
        """
        if amount < 0:
            raise ValueError(f"earn() amount must be non-negative, got {amount}")
        self.project_budget += amount

    # ------------------------------------------------------------------
    # Patience
    # ------------------------------------------------------------------

    def lose_patience(self, amount: int = 1) -> None:
        """Decrement client patience when an enemy escapes.

        Clamps to 0 — patience never goes negative.

        Args:
            amount: How many patience points to deduct (default 1).
        """
        self.client_patience = max(0, self.client_patience - amount)

    @property
    def game_over(self) -> bool:
        """``True`` when the client has lost all patience."""
        return self.client_patience <= 0
