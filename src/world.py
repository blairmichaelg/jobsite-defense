"""Jobsite Defense — World context object.

``World`` is the single shared-state container passed to every
``Entity.update(dt, world)`` call each frame.  It replaces the ad-hoc
``isinstance``-special-casing that plagued the Phase 2 game loop.

Design goals
------------
* No global state — ``World`` is constructed in ``main()`` and lives only
  as a local variable.
* Every entity that needs to read or write game state (towers finding
  enemies, economy granting bounties, the wave manager spawning creeps)
  does so through ``World``.
* Cheap to extend: adding a new subsystem (projectiles, wave data) is
  one new field here plus whatever uses it in the protocol.

Phase 3 note
------------
The ``Wave`` manager will add enemies by calling
``world.enemies.append(enemy)``; the main loop never spawns enemies
directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.economy import Economy
from src.enemy import Enemy
from src.tower import NailGunner

# Kill bounty awarded when a tower destroys an enemy before it exits.
KILL_BOUNTY: int = 15
"""Dollars awarded per enemy killed by a tower."""


@dataclass
class World:
    """Shared game-state context passed to every ``Entity.update``.

    Attributes:
        enemies: All ``Enemy`` instances currently on the field, including
            newly dead ones.  The main loop culls dead enemies after the
            update pass.
        towers: Spatial map of placed towers — ``{(col, row): NailGunner}``.
            Mutable; the radial menu appends here on purchase.
        economy: Shared economy (budget + patience).
        kill_bounty: Dollars awarded when a tower kills an enemy.
        _pending_earn: Accumulated bounties to pay out this frame.
            Internal use; main loop reads and resets after update pass.
    """

    enemies: list[Enemy] = field(default_factory=list)
    towers: dict[tuple[int, int], NailGunner] = field(default_factory=dict)
    economy: Economy = field(default_factory=Economy)
    kill_bounty: int = KILL_BOUNTY
    _pending_earn: int = field(default=0, init=False)

    def request_earn(self, amount: int) -> None:
        """Queue a bounty to be paid to the player this frame.

        Called by towers when they deal a killing blow.  The main loop
        flushes ``_pending_earn`` via :meth:`flush_earnings` after all
        entities have updated, ensuring the economy is mutated exactly
        once per frame rather than mid-loop.

        Args:
            amount: Dollars to award.
        """
        self._pending_earn += amount

    def flush_earnings(self) -> int:
        """Pay out all queued earnings and reset the counter.

        Returns:
            Total dollars earned this frame (may be 0).
        """
        amount = self._pending_earn
        if amount:
            self.economy.earn(amount)
        self._pending_earn = 0
        return amount
