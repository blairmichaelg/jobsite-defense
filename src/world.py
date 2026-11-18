"""Jobsite Defense — World context object.

Phase 3 changes
---------------
* Added ``projectiles: list[ConcreteGlob]`` container for active ballistic entities.
* Expanded ``towers`` mapping to hold both ``NailGunner`` and ``ConcretePump``.
* Centralized tower construction via ``try_build(col, row, cost, tower_type)``:
  validates coordinates, road occupancy, prior tower existence, and affordability.
* Added ``sell_tower(col, row)``: liquidates tower, returning 70% of cost to the player.
* Elimination of circular dependencies via type-checking imports in downstream modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.economy import Economy
from src.enemy import Enemy
from src.level import ROAD_CELLS
from src.projectile import ConcreteGlob
from src.settings import GRID_COLS, GRID_ROWS
from src.tower import ConcretePump, NailGunner

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
    towers: dict[tuple[int, int], NailGunner | ConcretePump] = field(
        default_factory=dict
    )
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
    # Tower Construction & Liquidation
    # ------------------------------------------------------------------

    def try_build(self, col: int, row: int, cost: int, tower_type: str) -> bool:
        """Validate and construct a new tower at (col, row).

        Validation checks:
        1. Coordinates are inside grid boundaries.
        2. Cell is not part of the road.
        3. Cell is not already occupied by another tower.
        4. Economy has sufficient budget for *cost*.

        Args:
            col: Grid column.
            row: Grid row.
            cost: Purchase price to deduct.
            tower_type: Identifier (e.g. "nail_gunner", "concrete_pump").

        Returns:
            ``True`` if the tower was successfully placed; ``False`` otherwise.
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
        tower: NailGunner | ConcretePump
        if "concrete" in norm_type or "pump" in norm_type:
            tower = ConcretePump(col=col, row=row)
        elif "nail" in norm_type or "gunner" in norm_type:
            tower = NailGunner(col=col, row=row)
        else:
            return False

        if not self.economy.spend(cost):
            return False

        self.towers[(col, row)] = tower
        return True

    def sell_tower(self, col: int, row: int) -> None:
        """Dismantle the tower at (col, row) and refund 70% of its base cost.

        Args:
            col: Grid column.
            row: Grid row.
        """
        tower = self.towers.pop((col, row), None)
        if tower is None:
            return
        refund = int(tower.cost * 0.7)
        if refund > 0:
            self.economy.earn(refund)
