"""Jobsite Defense — World context object.

Phase 4 changes
---------------
* Uses ``Tower`` base class and ``TOWER_TYPES`` registry for scalable tower management.
* Added ``try_upgrade_tower(col, row) -> bool``: checks tier availability, deducts budget,
  and invokes ``tower.upgrade()``.
* Updated ``sell_tower(col, row)``: refunds 70% of total ``invested`` dollars
  (including all purchase and upgrade expenditures).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.economy import Economy
from src.enemy import Enemy
from src.level import ROAD_CELLS
from src.projectile import ConcreteGlob
from src.settings import GRID_COLS, GRID_ROWS
from src.tower import TOWER_TYPES, Tower

KILL_BOUNTY: int = 15
"""Default dollars awarded per enemy killed."""


@dataclass
class World:
    """Shared game-state context passed to every ``Entity.update``.

    Attributes:
        enemies: All ``Enemy`` instances currently on the field.
        projectiles: Active ballistic projectiles (e.g. ``ConcreteGlob``).
        towers: Spatial map of placed towers — ``{(col, row): Tower}``.
        economy: Shared economy tracking budget and patience.
        kill_bounty: Default fallback bounty amount.
        _pending_earn: Accumulated bounties to pay out this frame.
    """

    enemies: list[Enemy] = field(default_factory=list)
    projectiles: list[ConcreteGlob] = field(default_factory=list)
    towers: dict[tuple[int, int], Tower] = field(default_factory=dict)
    economy: Economy = field(default_factory=Economy)
    kill_bounty: int = KILL_BOUNTY
    _pending_earn: int = field(default=0, init=False)

    # ------------------------------------------------------------------
    # Economy & Bounty Queue
    # ------------------------------------------------------------------

    def request_earn(self, amount: int) -> None:
        """Queue a bounty reward to be paid at the end of the update pass."""
        self._pending_earn += amount

    def flush_earnings(self) -> int:
        """Pay out all queued earnings to the economy and reset the queue."""
        amount = self._pending_earn
        if amount:
            self.economy.earn(amount)
        self._pending_earn = 0
        return amount

    # ------------------------------------------------------------------
    # Tower Construction, Upgrades, & Liquidation
    # ------------------------------------------------------------------

    def try_build(self, col: int, row: int, cost: int, tower_type: str) -> bool:
        """Validate and construct a new tower at (col, row).

        Validation checks:
        1. Coordinates are inside grid boundaries.
        2. Cell is not part of the road.
        3. Cell is not already occupied by another tower.
        4. Economy has sufficient budget for *cost*.
        """
        if not (0 <= col < GRID_COLS and 0 <= row < GRID_ROWS):
            return False
        if (col, row) in ROAD_CELLS:
            return False
        if (col, row) in self.towers:
            return False
        if not self.economy.can_afford(cost):
            return False

        norm_type = tower_type.lower().replace(" ", "").replace("_", "")
        cls = TOWER_TYPES.get(norm_type) or TOWER_TYPES.get(tower_type.lower())
        if cls is None:
            return False

        if not self.economy.spend(cost):
            return False

        tower = cls(col=col, row=row)
        tower.invested = cost
        self.towers[(col, row)] = tower
        return True

    def try_upgrade_tower(self, col: int, row: int) -> bool:
        """Upgrade the tower at (col, row) if affordable.

        Returns:
            ``True`` if upgraded; ``False`` if no tower, max tier, or broke.
        """
        tower = self.towers.get((col, row))
        if tower is None:
            return False

        upgrade_cost = tower.next_upgrade_cost
        if upgrade_cost is None:
            return False

        if not self.economy.spend(upgrade_cost):
            return False

        tower.upgrade()
        return True

    def sell_tower(self, col: int, row: int) -> None:
        """Dismantle tower at (col, row) and refund 70% of total invested capital."""
        tower = self.towers.pop((col, row), None)
        if tower is None:
            return
        refund = int(tower.invested * 0.7)
        if refund > 0:
            self.economy.earn(refund)
