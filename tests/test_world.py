"""Tests for src/world.py — construction validation, upgrades, and tower liquidation.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

from src.economy import Economy
from src.level import load_level
from src.save import SaveData
from src.settings import NAIL_GUNNER_COST, NAIL_GUNNER_TIER2_COST
from src.tower import ConcretePump, NailGunner
from src.world import World

_DEFAULT_LEVEL = load_level("level_1.json")
ROAD_CELLS = _DEFAULT_LEVEL.road_cells


class TestWorldTryBuild:
    """Validate World.try_build rules."""

    def test_try_build_succeeds_on_empty_grass(self) -> None:
        """Building a NailGunner on an empty grass tile with budget succeeds."""
        world = World(economy=Economy(project_budget=1500))
        assert (0, 3) not in ROAD_CELLS
        success = world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")

        assert success is True
        assert (0, 3) in world.towers
        assert isinstance(world.towers[(0, 3)], NailGunner)
        assert world.economy.project_budget == 1000

    def test_try_build_fails_on_occupied_cell(self) -> None:
        """Building on an already occupied cell must return False without double-charging."""
        world = World(economy=Economy(project_budget=1500))
        world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")
        assert world.economy.project_budget == 1000

        second_attempt = world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")
        assert second_attempt is False
        assert world.economy.project_budget == 1000

    def test_try_build_fails_on_road_cell(self) -> None:
        """Building on a road cell must return False without deducting budget."""
        world = World(economy=Economy(project_budget=1500))
        road_col, road_row = next(iter(ROAD_CELLS))

        success = world.try_build(road_col, road_row, NAIL_GUNNER_COST, "nail_gunner")
        assert success is False
        assert (road_col, road_row) not in world.towers
        assert world.economy.project_budget == 1500

    def test_try_build_fails_with_insufficient_funds(self) -> None:
        """Building when budget is below cost must fail and leave cell empty."""
        world = World(economy=Economy(project_budget=200))
        success = world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")

        assert success is False
        assert (0, 3) not in world.towers
        assert world.economy.project_budget == 200

    def test_try_build_concrete_pump(self) -> None:
        """Building ConcretePump instantiates the correct subclass."""
        world = World(economy=Economy(project_budget=1500))
        success = world.try_build(1, 4, 750, "concrete_pump")

        assert success is True
        assert (1, 4) in world.towers
        assert isinstance(world.towers[(1, 4)], ConcretePump)
        assert world.economy.project_budget == 750


class TestWorldUpgradesAndLiquidation:
    """Validate World.try_upgrade_tower and invested refund calculations."""

    def test_try_upgrade_tower_succeeds_when_affordable(self) -> None:
        """Upgrading tower spends next tier cost and advances tower level."""
        world = World(economy=Economy(project_budget=1000))
        world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")  # $500 spent, $500 left

        success = world.try_upgrade_tower(0, 3)  # Tier 2 costs $300
        assert success is True
        assert world.economy.project_budget == 200
        tower = world.towers[(0, 3)]
        assert tower.upgrade_level == 2
        assert tower.invested == NAIL_GUNNER_COST + NAIL_GUNNER_TIER2_COST

    def test_try_upgrade_fails_when_unaffordable(self) -> None:
        """Upgrading fails when budget is below next tier cost."""
        world = World(economy=Economy(project_budget=600))
        world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")  # $100 left, tier 2 is $300

        success = world.try_upgrade_tower(0, 3)
        assert success is False
        assert world.economy.project_budget == 100
        assert world.towers[(0, 3)].upgrade_level == 1

    def test_try_upgrade_fails_on_empty_cell(self) -> None:
        """Upgrading an empty cell returns False without modifying budget."""
        world = World(economy=Economy(project_budget=500))
        assert world.try_upgrade_tower(2, 2) is False
        assert world.economy.project_budget == 500

    def test_sell_tower_refunds_70_percent_of_invested_including_upgrades(self) -> None:
        """Selling a tower refunds 70% of total invested dollars (base + upgrades)."""
        world = World(economy=Economy(project_budget=1500))
        world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")  # invested = 500
        world.try_upgrade_tower(0, 3)                           # invested = 800 (500 + 300)

        # Budget after build ($500) and upgrade ($300) = $700
        assert world.economy.project_budget == 700

        # Refund 70% of 800 = 560
        world.sell_tower(0, 3)
        assert (0, 3) not in world.towers
        assert world.economy.project_budget == 700 + 560

    def test_sell_nonexistent_tower_is_no_op(self) -> None:
        """Calling sell_tower on an empty cell must not raise or modify budget."""
        world = World(economy=Economy(project_budget=1000))
        world.sell_tower(5, 5)
        assert world.economy.project_budget == 1000


class TestWorldPerks:
    """Validate meta-progression perk integration in World."""

    def test_union_dues_grants_extra_starting_budget(self) -> None:
        """Union Dues perk adds $250 to starting project budget."""
        save = SaveData(equity=0, perks={"union_dues"})
        world = World(economy=Economy(project_budget=1500), save_data=save)
        # 1500 base + 250 bonus = 1750
        assert world.economy.project_budget == 1750

    def test_better_ammo_buffs_nail_gunner_damage(self) -> None:
        """Heavy Duty Nails perk adds +5 base damage to NailGunner upon creation."""
        save = SaveData(equity=0, perks={"better_ammo"})
        world = World(economy=Economy(project_budget=1500), save_data=save)
        assert (0, 3) not in ROAD_CELLS
        world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")

        tower = world.towers[(0, 3)]
        assert isinstance(tower, NailGunner)
        # Base was 25.0 + 5.0 bonus = 30.0
        assert tower.base_damage == 30.0
        assert tower.effective_damage == 30.0
