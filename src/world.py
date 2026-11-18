"""Jobsite Defense — World context object.

Phase 6 changes:
- Decoupled level geometry: World owns `level: LevelData`.
- Meta-progression integration: World holds `save_data: SaveData`.
- Perk application: `apply_perks()` buffs newly built towers (e.g. better_ammo)
  and grants starting budget bonuses (union_dues).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import pygame

from src.economy import Economy
from src.enemy import Enemy
from src.level import LevelData, load_level
from src.protocols import Projectile
from src.save import SaveData
from src.settings import GRID_COLS, GRID_ROWS
from src.tower import TOWER_TYPES, Tower

if TYPE_CHECKING:
    pass

KILL_BOUNTY: int = 15
"""Default dollars awarded per enemy killed."""


class GameEvent(Enum):
    """Event types broadcasted to the world event queue."""

    SHOT = auto()
    KILL = auto()
    LEAK = auto()
    BUILD = auto()
    SELL = auto()
    UPGRADE = auto()
    STUN = auto()
    SPLASH = auto()


@dataclass
class Event:
    """A single game event recording an action and its coordinates."""

    kind: GameEvent
    pos: pygame.Vector2
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class World:
    """Shared game-state context passed to every ``Entity.update``.

    Attributes:
        level: Active level layout and geometry.
        enemies: All ``Enemy`` instances currently on the field.
        projectiles: Active ballistic and homing projectiles.
        towers: Spatial map of placed towers — ``{(col, row): Tower}``.
        economy: Shared economy tracking budget and patience.
        save_data: Active meta-progression state and unlocked perks.
        events: Event queue collected during updates.
        kill_bounty: Default fallback bounty amount.
        _pending_earn: Accumulated bounties to pay out this frame.
    """

    level: LevelData = field(default_factory=lambda: load_level("level_1.json"))
    enemies: list[Enemy] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    towers: dict[tuple[int, int], Tower] = field(default_factory=dict)
    economy: Economy = field(default_factory=Economy)
    save_data: SaveData = field(default_factory=SaveData)
    events: list[Event] = field(default_factory=list)
    kill_bounty: int = KILL_BOUNTY
    _pending_earn: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """Apply passive starting perks (e.g. Union Dues starting cash)."""
        if "union_dues" in self.save_data.perks:
            self.economy.project_budget += 250

    def emit(self, kind: GameEvent, pos: pygame.Vector2, **data: Any) -> None:
        """Record a new event to the frame's event queue."""
        self.events.append(Event(kind=kind, pos=pygame.Vector2(pos), data=data))

    def drain_events(self) -> list[Event]:
        """Drain and return all queued events for this frame."""
        ev = self.events
        self.events = []
        return ev

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
    # Aura State Management
    # ------------------------------------------------------------------

    def refresh_auras(self) -> None:
        """Reset disabled state on all towers and reapply auras from alive enemies."""
        for tower in self.towers.values():
            tower.is_disabled = False
        for enemy in self.enemies:
            if enemy.alive:
                enemy.apply_aura(self)

    # ------------------------------------------------------------------
    # Meta-Progression & Perks
    # ------------------------------------------------------------------

    def apply_perks(self, tower: Tower) -> None:
        """Apply active meta-progression perks to newly placed tower."""
        from src.tower import NailGunner

        if "better_ammo" in self.save_data.perks and isinstance(tower, NailGunner):
            tower.base_damage += 5.0
            tower._apply_modifiers()

    # ------------------------------------------------------------------
    # Tower Construction, Upgrades, & Liquidation
    # ------------------------------------------------------------------

    def try_build(self, col: int, row: int, cost: int, tower_type: str) -> bool:
        """Validate and construct a new tower at (col, row).

        Reads canonical ``cls.COST`` from the tower class in ``TOWER_TYPES``.
        """
        if not (0 <= col < GRID_COLS and 0 <= row < GRID_ROWS):
            return False
        if (col, row) in self.level.road_cells:
            return False
        if (col, row) in self.towers:
            return False

        norm_type = tower_type.lower().replace(" ", "").replace("_", "")
        cls = TOWER_TYPES.get(norm_type) or TOWER_TYPES.get(tower_type.lower())
        if cls is None:
            return False

        actual_cost = cls.COST
        if not self.economy.can_afford(actual_cost):
            return False

        if not self.economy.spend(actual_cost):
            return False

        powerup = self.level.powerup_tiles.get((col, row))
        tower = cls(col=col, row=row, powerup_tile=powerup)
        tower.invested = actual_cost
        self.apply_perks(tower)
        self.towers[(col, row)] = tower
        self.emit(GameEvent.BUILD, tower.center, tower_type=tower_type, col=col, row=row)
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
        self.emit(
            GameEvent.UPGRADE,
            tower.center,
            level=tower.upgrade_level,
            name=tower.next_upgrade_name or "Max Tier",
            col=col,
            row=row,
        )
        return True

    def sell_tower(self, col: int, row: int) -> None:
        """Dismantle tower at (col, row) and refund 70% of total invested capital."""
        tower = self.towers.pop((col, row), None)
        if tower is None:
            return
        refund = int(tower.invested * 0.7)
        if refund > 0:
            self.economy.earn(refund)
        self.emit(GameEvent.SELL, tower.center, refund=refund, col=col, row=row)
