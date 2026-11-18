"""Tests for src/world.py — construction validation and tower liquidation.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

from src.economy import Economy
from src.level import ROAD_CELLS
from src.settings import NAIL_GUNNER_COST
from src.tower import ConcretePump, NailGunner
from src.world import World


class TestWorldTryBuild:
    """Validate World.try_build rules."""

    def test_try_build_succeeds_on_empty_grass(self) -> None:
        """Building a NailGunner on an empty grass tile with budget succeeds."""
        world = World(economy=Economy(project_budget=1500))
        # (0, 3) is a grass tile outside ROAD_CELLS
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

        # Attempt to build another tower on the exact same tile
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


class TestWorldSellTower:
    """Validate World.sell_tower liquidation and refunds."""

    def test_sell_tower_removes_and_refunds_70_percent(self) -> None:
        """Selling a tower deletes it and refunds 70% of base cost to economy."""
        world = World(economy=Economy(project_budget=1500))
        world.try_build(0, 3, NAIL_GUNNER_COST, "nail_gunner")
        assert world.economy.project_budget == 1000

        # Sell Nail Gunner: cost 500 * 0.7 = 350 refund
        world.sell_tower(0, 3)
        assert (0, 3) not in world.towers
        assert world.economy.project_budget == 1350

    def test_sell_nonexistent_tower_is_no_op(self) -> None:
        """Calling sell_tower on an empty cell must not raise or modify budget."""
        world = World(economy=Economy(project_budget=1000))
        world.sell_tower(5, 5)
        assert world.economy.project_budget == 1000
