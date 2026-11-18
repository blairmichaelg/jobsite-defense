"""Jobsite Defense — Radial Build Menu.

Phase 3 changes
---------------
* Contextual UI:
  - Empty cell: "Nail Gunner ($500)" at 90° and "Concrete Pump ($750)" at 270°.
  - Occupied cell: "Sell (Refund $X)" and placeholder "Upgrade".
* Uses ``world.try_build()`` and ``world.sell_tower()`` rather than mutating towers directly.
* Row-0 and Row-1 flip logic: checks ``candidate_y - _BUTTON_RADIUS < 0`` so buttons
  do not clip the top window boundary on rows 0 and 1.
* Disables unaffordable purchase/upgrade buttons (rendered in grey, click ignored).
* Real typing on ``update(dt, world: World)`` satisfying the ``Entity`` protocol.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from src.grid import cell_rect
from src.level import ROAD_CELLS
from src.protocols import Clickable, Entity
from src.settings import (
    CELL_SIZE,
    CONCRETE_PUMP_COST,
    NAIL_GUNNER_COST,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

if TYPE_CHECKING:
    from src.world import World


# ---------------------------------------------------------------------------
# Visual Constants
# ---------------------------------------------------------------------------

_COLOR_BUTTON_BG: tuple[int, int, int, int] = (30, 30, 30, 210)
_COLOR_BUTTON_HOVER: tuple[int, int, int, int] = (60, 60, 60, 230)
_COLOR_BUTTON_DISABLED: tuple[int, int, int, int] = (25, 25, 25, 180)
_COLOR_BUTTON_TEXT: tuple[int, int, int] = (240, 230, 200)
_COLOR_BUTTON_TEXT_DISABLED: tuple[int, int, int] = (120, 120, 120)
_COLOR_BUTTON_COST_OK: tuple[int, int, int] = (100, 220, 100)
_COLOR_BUTTON_COST_NO: tuple[int, int, int] = (220, 80, 80)
_COLOR_BUTTON_REFUND: tuple[int, int, int] = (100, 200, 255)

_BUTTON_RADIUS: int = 36       # pixel radius of each radial button
_ORBIT_RADIUS: int = 70        # distance from menu centre to button centre


# ---------------------------------------------------------------------------
# Internal button record
# ---------------------------------------------------------------------------

@dataclass
class _MenuButton:
    label: str
    cost: int
    action: str
    angle_deg: float
    center: pygame.Vector2
    subtext: str | None = None


# ---------------------------------------------------------------------------
# RadialMenu
# ---------------------------------------------------------------------------

@dataclass
class RadialMenu:
    """Contextual radial build and management menu.

    Satisfies ``Entity`` (layer 90) and ``Clickable``.
    """

    open: bool = field(default=False, init=False)
    layer: int = field(default=90, init=False)

    _cell: tuple[int, int] = field(default=(0, 0), init=False)
    _menu_center: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(0, 0), init=False
    )
    _buttons: list[_MenuButton] = field(default_factory=list, init=False)
    _is_occupied: bool = field(default=False, init=False)
    _font_label: pygame.font.Font | None = field(default=None, init=False)
    _font_cost: pygame.font.Font | None = field(default=None, init=False)
    _world: World | None = field(default=None, init=False)

    def configure(self, world: World) -> None:
        """Inject shared world dependency."""
        self._world = world
        self._font_label = pygame.font.Font(None, 16)
        self._font_cost = pygame.font.Font(None, 15)

    # ------------------------------------------------------------------
    # Entity Protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: World) -> None:
        """No per-frame simulation needed for static menu."""

    def draw(self, surface: pygame.Surface) -> None:
        """Render all active menu buttons with hover, cost, and disabled states."""
        if not self.open or self._world is None:
            return

        mouse_pos = pygame.mouse.get_pos()

        for btn in self._buttons:
            bc = (int(btn.center.x), int(btn.center.y))
            dist = math.hypot(mouse_pos[0] - bc[0], mouse_pos[1] - bc[1])
            hovering = dist <= _BUTTON_RADIUS

            can_afford = (
                self._world.economy.can_afford(btn.cost)
                if btn.cost > 0
                else True
            )

            # Draw circle background
            overlay = pygame.Surface(
                (_BUTTON_RADIUS * 2, _BUTTON_RADIUS * 2), pygame.SRCALPHA
            )
            if not can_afford:
                bg_color = _COLOR_BUTTON_DISABLED
            elif hovering:
                bg_color = _COLOR_BUTTON_HOVER
            else:
                bg_color = _COLOR_BUTTON_BG

            pygame.draw.circle(
                overlay, bg_color, (_BUTTON_RADIUS, _BUTTON_RADIUS), _BUTTON_RADIUS
            )
            surface.blit(overlay, (bc[0] - _BUTTON_RADIUS, bc[1] - _BUTTON_RADIUS))

            # Border
            if not can_afford:
                border_color = _COLOR_BUTTON_TEXT_DISABLED
            elif btn.action == "sell":
                border_color = _COLOR_BUTTON_REFUND
            elif can_afford:
                border_color = _COLOR_BUTTON_COST_OK
            else:
                border_color = _COLOR_BUTTON_COST_NO

            pygame.draw.circle(surface, border_color, bc, _BUTTON_RADIUS, width=2)

            # Text
            if self._font_label and self._font_cost:
                text_color = (
                    _COLOR_BUTTON_TEXT_DISABLED if not can_afford else _COLOR_BUTTON_TEXT
                )
                lbl = self._font_label.render(btn.label, True, text_color)
                surface.blit(lbl, lbl.get_rect(center=(bc[0], bc[1] - 7)))

                if btn.subtext:
                    sub_color = (
                        _COLOR_BUTTON_TEXT_DISABLED
                        if not can_afford
                        else _COLOR_BUTTON_REFUND
                    )
                    sub_surf = self._font_cost.render(btn.subtext, True, sub_color)
                    surface.blit(sub_surf, sub_surf.get_rect(center=(bc[0], bc[1] + 9)))
                elif btn.cost > 0:
                    cost_color = (
                        _COLOR_BUTTON_TEXT_DISABLED
                        if not can_afford
                        else _COLOR_BUTTON_COST_OK
                    )
                    cost_surf = self._font_cost.render(f"${btn.cost}", True, cost_color)
                    surface.blit(
                        cost_surf, cost_surf.get_rect(center=(bc[0], bc[1] + 9))
                    )

    # ------------------------------------------------------------------
    # Clickable Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle opening, closing, and button actions."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.open:
            self.open = False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3 and self.open:
                self.open = False
                return True

            if event.button == 1:
                if self.open:
                    for btn in self._buttons:
                        bc = (int(btn.center.x), int(btn.center.y))
                        dist = math.hypot(event.pos[0] - bc[0], event.pos[1] - bc[1])
                        if dist <= _BUTTON_RADIUS:
                            if (
                                self._world is not None
                                and btn.cost > 0
                                and not self._world.economy.can_afford(btn.cost)
                            ):
                                return True  # Unaffordable: consumed but ignored
                            self._execute_action(btn)
                            self.open = False
                            return True
                    self.open = False
                    return True
                else:
                    return self._try_open(event.pos)

        return False

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _try_open(self, mouse_pos: tuple[int, int]) -> bool:
        """Inspect clicked cell and open menu if valid."""
        mx, my = mouse_pos
        col = mx // CELL_SIZE
        row = my // CELL_SIZE

        if not (0 <= col < WINDOW_WIDTH // CELL_SIZE and 0 <= row < WINDOW_HEIGHT // CELL_SIZE):
            return False
        if (col, row) in ROAD_CELLS:
            return False
        if self._world is None:
            return False

        self._cell = (col, row)
        rect = cell_rect(col, row)
        self._menu_center = pygame.Vector2(rect.center)
        self._is_occupied = (col, row) in self._world.towers
        self._build_buttons()
        self.open = True
        return True

    def _build_buttons(self) -> None:
        """Construct contextual buttons with row-0/row-1 clipping prevention."""
        self._buttons = []
        if self._world is None:
            return

        # Pre-check if 270° button clips off top of screen (row 0 or row 1)
        test_y = self._menu_center.y + math.sin(math.radians(270.0)) * _ORBIT_RADIUS
        top_clipped = (test_y - _BUTTON_RADIUS) < 0

        if self._is_occupied:
            tower = self._world.towers[self._cell]
            refund = int(tower.cost * 0.7)
            options = [
                ("Sell", 0, "sell", 90.0, f"+${refund}"),
                ("Upgrade", 500, "upgrade", 270.0, None),
            ]
        else:
            options = [
                ("Nail Gunner", NAIL_GUNNER_COST, "nail_gunner", 90.0, None),
                ("Concrete Pump", CONCRETE_PUMP_COST, "concrete_pump", 270.0, None),
            ]

        for label, cost, action, base_angle, subtext in options:
            angle = base_angle
            if top_clipped:
                # If top would be clipped on row 0/1, flip angles downwards
                angle = 45.0 if base_angle == 90.0 else 135.0

            angle_rad = math.radians(angle)
            center = pygame.Vector2(
                self._menu_center.x + math.cos(angle_rad) * _ORBIT_RADIUS,
                self._menu_center.y + math.sin(angle_rad) * _ORBIT_RADIUS,
            )
            self._buttons.append(
                _MenuButton(
                    label=label,
                    cost=cost,
                    action=action,
                    angle_deg=angle,
                    center=center,
                    subtext=subtext,
                )
            )

    def _execute_action(self, btn: _MenuButton) -> None:
        """Dispatch action to the World manager."""
        if self._world is None:
            return

        col, row = self._cell
        if btn.action == "sell":
            self._world.sell_tower(col, row)
        elif btn.action == "upgrade":
            pass  # Placeholder
        else:
            self._world.try_build(col, row, btn.cost, btn.action)


# Type narrowing assertions for the Protocol checker.
def _assert_protocols() -> None:  # pragma: no cover
    rm: RadialMenu = RadialMenu()
    _e: Entity = rm
    _c: Clickable = rm
