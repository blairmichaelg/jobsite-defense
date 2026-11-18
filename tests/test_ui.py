"""Tests for src/ui.py — Radial build menu, safe clamping, and upgrades.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

import pygame

from src.economy import Economy
from src.level import load_level
from src.settings import CELL_SIZE, WINDOW_HEIGHT
from src.ui import _BUTTON_RADIUS, RadialMenu
from src.world import World

_DEFAULT_LEVEL = load_level("level_1.json")
ROAD_CELLS = _DEFAULT_LEVEL.road_cells


def _find_grass_col(row: int) -> int:
    """Find a column in *row* that does not overlap the road."""
    for col in range(16):
        if (col, row) not in ROAD_CELLS:
            return col
    raise RuntimeError(f"No grass cells in row {row}")


class TestRadialMenuSafeClamping:
    """Verify that buttons are strictly clamped within the window boundaries."""

    def test_row_0_buttons_clamped_safely(self) -> None:
        """On row 0, button centers must be clamped >= _BUTTON_RADIUS so they are on-screen."""
        world = World(economy=Economy())
        menu = RadialMenu()
        menu.configure(world)

        col = _find_grass_col(0)
        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 0 * CELL_SIZE + CELL_SIZE // 2

        opened = menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        assert opened is True
        assert menu.open is True
        assert len(menu._buttons) == 2

        for btn in menu._buttons:
            # Center must be at least _BUTTON_RADIUS from top, so top edge >= 0
            assert btn.center.y >= _BUTTON_RADIUS
            assert btn.center.y - _BUTTON_RADIUS >= 0

    def test_row_11_buttons_clamped_safely(self) -> None:
        """On row 11 (bottom row), button centers must be <= WINDOW_HEIGHT - _BUTTON_RADIUS."""
        world = World(economy=Economy())
        menu = RadialMenu()
        menu.configure(world)

        col = _find_grass_col(11)
        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 11 * CELL_SIZE + CELL_SIZE // 2

        opened = menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        assert opened is True
        assert menu.open is True

        for btn in menu._buttons:
            # Bottom edge <= WINDOW_HEIGHT
            assert btn.center.y <= WINDOW_HEIGHT - _BUTTON_RADIUS
            assert btn.center.y + _BUTTON_RADIUS <= WINDOW_HEIGHT


class TestRadialMenuActions:
    """Verify menu interactions for building, selling, upgrades, and budget restrictions."""

    def test_unaffordable_button_ignores_clicks(self) -> None:
        """Clicking an unaffordable option consumes event without building."""
        world = World(economy=Economy(project_budget=100))
        menu = RadialMenu()
        menu.configure(world)

        col = _find_grass_col(3)
        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 3 * CELL_SIZE + CELL_SIZE // 2

        menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        assert menu.open is True

        # Click Nail Gunner button ($500 vs $100 budget)
        nail_btn = next(b for b in menu._buttons if b.action == "nail_gunner")
        consumed = menu.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=(int(nail_btn.center.x), int(nail_btn.center.y)),
            )
        )
        assert consumed is True
        assert (col, 3) not in world.towers
        assert world.economy.project_budget == 100

    def test_occupied_cell_spawns_sell_and_upgrade_options(self) -> None:
        """Clicking an occupied tile opens menu offering Sell and Tier 2 Upgrade."""
        world = World(economy=Economy(project_budget=1500))
        col = _find_grass_col(3)
        world.try_build(col, 3, 500, "nail_gunner")

        menu = RadialMenu()
        menu.configure(world)

        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 3 * CELL_SIZE + CELL_SIZE // 2

        opened = menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        assert opened is True
        assert menu.open is True

        sell_btn = next((b for b in menu._buttons if b.action == "sell"), None)
        assert sell_btn is not None
        assert sell_btn.subtext == "+$350"  # 70% of 500

        up_btn = next((b for b in menu._buttons if b.action == "upgrade"), None)
        assert up_btn is not None
        assert up_btn.label == "Pneumatic Overdrive"
        assert up_btn.cost == 300

    def test_clicking_upgrade_button_upgrades_tower(self) -> None:
        """Clicking the upgrade button spends budget and advances tower level."""
        world = World(economy=Economy(project_budget=1000))
        col = _find_grass_col(3)
        world.try_build(col, 3, 500, "nail_gunner")  # $500 remaining

        menu = RadialMenu()
        menu.configure(world)

        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 3 * CELL_SIZE + CELL_SIZE // 2

        menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        up_btn = next(b for b in menu._buttons if b.action == "upgrade")

        # Click the upgrade button
        menu.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=(int(up_btn.center.x), int(up_btn.center.y)),
            )
        )

        assert world.towers[(col, 3)].upgrade_level == 2
        assert world.economy.project_budget == 200  # 500 - 300
