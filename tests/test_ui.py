"""Tests for src/ui.py — Radial build menu, clipping flips, and actions.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

import pygame

from src.economy import Economy
from src.level import ROAD_CELLS
from src.settings import CELL_SIZE
from src.ui import _BUTTON_RADIUS, RadialMenu
from src.world import World


def _find_grass_col(row: int) -> int:
    """Find a column in *row* that does not overlap the road."""
    for col in range(16):
        if (col, row) not in ROAD_CELLS:
            return col
    raise RuntimeError(f"No grass cells in row {row}")


class TestRadialMenuClippingFlips:
    """Verify that buttons flip downwards on row 0 and row 1 so they don't clip off-screen."""

    def test_row_0_buttons_flip_and_stay_on_screen(self) -> None:
        """On row 0, the candidate above the cell would clip; buttons must flip down."""
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
            # Top boundary check: button circle must not extend above y=0
            assert btn.center.y - _BUTTON_RADIUS >= 0, (
                f"Button {btn.label} clipped off top at y={btn.center.y}"
            )
            # The button must have flipped away from 270° (above)
            assert btn.angle_deg != 270.0

    def test_row_1_buttons_flip_and_stay_on_screen(self) -> None:
        """On row 1, candidate_y - _BUTTON_RADIUS < 0 still triggers; buttons must flip down."""
        world = World(economy=Economy())
        menu = RadialMenu()
        menu.configure(world)

        col = _find_grass_col(1)
        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 1 * CELL_SIZE + CELL_SIZE // 2

        opened = menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        assert opened is True
        assert menu.open is True

        for btn in menu._buttons:
            assert btn.center.y - _BUTTON_RADIUS >= 0, (
                f"Button {btn.label} clipped off top on row 1 at y={btn.center.y}"
            )
            assert btn.angle_deg != 270.0

    def test_row_3_buttons_keep_standard_angles(self) -> None:
        """On row 3 (deep in site), buttons retain standard 90° and 270° angles."""
        world = World(economy=Economy())
        menu = RadialMenu()
        menu.configure(world)

        col = _find_grass_col(3)
        px = col * CELL_SIZE + CELL_SIZE // 2
        py = 3 * CELL_SIZE + CELL_SIZE // 2

        opened = menu.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py))
        )
        assert opened is True
        assert menu.open is True

        angles = {btn.label: btn.angle_deg for btn in menu._buttons}
        assert angles["Nail Gunner"] == 90.0
        assert angles["Concrete Pump"] == 270.0


class TestRadialMenuActions:
    """Verify menu interactions for building, selling, and budget restrictions."""

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

    def test_occupied_cell_spawns_sell_option(self) -> None:
        """Clicking an occupied tile opens menu offering Sell liquidation."""
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
