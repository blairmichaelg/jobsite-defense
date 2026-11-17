"""Jobsite Defense — Radial Build Menu.

Phase 2.5 changes
-----------------
* ``update(dt, world)`` signature updated to match the ``Entity`` protocol.
* ``_build_buttons``: the default button angle is 270° (above the cell).
  If the computed button centre would have ``y < 0`` (i.e. the clicked
  cell is in row 0), the angle flips to 90° (below the cell) so the
  button remains on-screen and row-0 tiles stay buildable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pygame

from src.grid import cell_rect
from src.level import ROAD_CELLS
from src.protocols import Clickable, Entity
from src.settings import (
    CELL_SIZE,
    NAIL_GUNNER_COST,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

if TYPE_CHECKING:
    from src.economy import Economy
    from src.tower import NailGunner


# ---------------------------------------------------------------------------
# Colour palette for the menu
# ---------------------------------------------------------------------------

_COLOR_BUTTON_BG: tuple[int, int, int, int] = (30, 30, 30, 200)
_COLOR_BUTTON_HOVER: tuple[int, int, int, int] = (60, 60, 60, 220)
_COLOR_BUTTON_TEXT: tuple[int, int, int] = (240, 230, 200)
_COLOR_BUTTON_COST_OK: tuple[int, int, int] = (100, 220, 100)
_COLOR_BUTTON_COST_NO: tuple[int, int, int] = (220, 80, 80)

_BUTTON_RADIUS: int = 36       # pixel radius of each option button
_ORBIT_RADIUS: int = 70        # distance from menu centre to button centre
_DEFAULT_ANGLE: float = 270.0  # above the cell (standard)
_FLIPPED_ANGLE: float = 90.0   # below the cell (row-0 fallback)


# ---------------------------------------------------------------------------
# Internal button record
# ---------------------------------------------------------------------------

@dataclass
class _MenuButton:
    label: str
    cost: int
    angle_deg: float
    center: pygame.Vector2


# ---------------------------------------------------------------------------
# RadialMenu
# ---------------------------------------------------------------------------

@dataclass
class RadialMenu:
    """Radial build menu — opened by clicking a buildable cell.

    Attributes:
        open: Whether the menu is currently visible.
        layer: Render/update layer — UI overlays sit at layer 90.
    """

    open: bool = field(default=False, init=False)
    layer: int = field(default=90, init=False)

    _cell: tuple[int, int] = field(default=(0, 0), init=False)
    _menu_center: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(0, 0), init=False
    )
    _buttons: list[_MenuButton] = field(default_factory=list, init=False)
    _font_label: pygame.font.Font | None = field(default=None, init=False)
    _font_cost: pygame.font.Font | None = field(default=None, init=False)

    _economy: Economy | None = field(default=None, init=False)
    _towers: dict[tuple[int, int], NailGunner] = field(
        default_factory=dict, init=False
    )

    def configure(
        self,
        economy: Economy,
        towers: dict[tuple[int, int], NailGunner],
    ) -> None:
        """Inject runtime dependencies (called once from ``main.py``).

        Args:
            economy: Shared economy state.
            towers: Shared tower placement dict (mutated on purchase).
        """
        self._economy = economy
        self._towers = towers
        self._font_label = pygame.font.Font(None, 18)
        self._font_cost = pygame.font.Font(None, 16)

    # ------------------------------------------------------------------
    # Entity protocol
    # ------------------------------------------------------------------

    def update(self, dt: float, world: Any) -> None:  # noqa: ANN401, ARG002
        """No per-frame state updates needed for the menu.

        Args:
            dt: Unused; present to satisfy the ``Entity`` protocol.
            world: Unused; present to satisfy the ``Entity`` protocol.
        """

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all menu buttons with labels and cost text.

        Args:
            surface: The main display surface.
        """
        if not self.open or self._economy is None:
            return

        mouse_pos = pygame.mouse.get_pos()

        for btn in self._buttons:
            bc = (int(btn.center.x), int(btn.center.y))
            dist = math.hypot(mouse_pos[0] - bc[0], mouse_pos[1] - bc[1])
            hovering = dist <= _BUTTON_RADIUS

            overlay = pygame.Surface(
                (_BUTTON_RADIUS * 2, _BUTTON_RADIUS * 2), pygame.SRCALPHA
            )
            bg_color = _COLOR_BUTTON_HOVER if hovering else _COLOR_BUTTON_BG
            pygame.draw.circle(
                overlay, bg_color, (_BUTTON_RADIUS, _BUTTON_RADIUS), _BUTTON_RADIUS
            )
            surface.blit(overlay, (bc[0] - _BUTTON_RADIUS, bc[1] - _BUTTON_RADIUS))

            border_color = (
                _COLOR_BUTTON_COST_OK
                if self._economy.can_afford(btn.cost)
                else _COLOR_BUTTON_COST_NO
            )
            pygame.draw.circle(surface, border_color, bc, _BUTTON_RADIUS, width=2)

            if self._font_label and self._font_cost:
                lbl = self._font_label.render(btn.label, True, _COLOR_BUTTON_TEXT)
                surface.blit(lbl, lbl.get_rect(center=(bc[0], bc[1] - 7)))

                cost_color = (
                    _COLOR_BUTTON_COST_OK
                    if self._economy.can_afford(btn.cost)
                    else _COLOR_BUTTON_COST_NO
                )
                cost_txt = self._font_cost.render(f"${btn.cost}", True, cost_color)
                surface.blit(cost_txt, cost_txt.get_rect(center=(bc[0], bc[1] + 9)))

    # ------------------------------------------------------------------
    # Clickable protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route mouse / keyboard events to open, close, or purchase.

        Args:
            event: Raw pygame event.

        Returns:
            ``True`` if the event was consumed.
        """
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
                            self._try_purchase(btn)
                            self.open = False
                            return True
                    self.open = False
                    return True
                else:
                    return self._try_open(event.pos)

        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_open(self, mouse_pos: tuple[int, int]) -> bool:
        """Open the menu if ``mouse_pos`` is on a buildable grass cell.

        Args:
            mouse_pos: Screen pixel position of the click.

        Returns:
            ``True`` if the menu was opened (event consumed).
        """
        mx, my = mouse_pos
        col = mx // CELL_SIZE
        row = my // CELL_SIZE

        if not (0 <= col < WINDOW_WIDTH // CELL_SIZE and 0 <= row < WINDOW_HEIGHT // CELL_SIZE):
            return False
        if (col, row) in ROAD_CELLS:
            return False
        if (col, row) in self._towers:
            return False

        self._cell = (col, row)
        rect = cell_rect(col, row)
        self._menu_center = pygame.Vector2(rect.center)
        self._build_buttons()
        self.open = True
        return True

    def _build_buttons(self) -> None:
        """Populate ``_buttons``, flipping angle if the button would go off-screen.

        Default placement is 270° (above the clicked cell).  If the
        resulting button centre would have ``y < 0`` — which happens when
        the player clicks a row-0 cell — the angle is flipped to 90°
        (below the cell) so the button stays visible.
        """
        base_options: list[tuple[str, int]] = [
            ("Nail Gunner", NAIL_GUNNER_COST),
        ]
        self._buttons = []
        for label, cost in base_options:
            # Try the default (above) angle first; fall back to below.
            angle = _DEFAULT_ANGLE
            angle_rad = math.radians(angle)
            candidate_y = self._menu_center.y + math.sin(angle_rad) * _ORBIT_RADIUS
            if candidate_y < 0:
                angle = _FLIPPED_ANGLE
                angle_rad = math.radians(angle)

            center = pygame.Vector2(
                self._menu_center.x + math.cos(angle_rad) * _ORBIT_RADIUS,
                self._menu_center.y + math.sin(angle_rad) * _ORBIT_RADIUS,
            )
            self._buttons.append(
                _MenuButton(label=label, cost=cost, angle_deg=angle, center=center)
            )

    def _try_purchase(self, btn: _MenuButton) -> None:
        """Attempt to buy the tower associated with *btn*.

        Args:
            btn: The menu button the player clicked.
        """
        if self._economy is None:
            return
        if not self._economy.spend(btn.cost):
            return

        from src.tower import NailGunner  # local import — avoids circular dep
        col, row = self._cell
        self._towers[(col, row)] = NailGunner(col=col, row=row)


# Type narrowing assertions for the Protocol checker.
def _assert_protocols() -> None:  # pragma: no cover
    rm: RadialMenu = RadialMenu()
    _e: Entity = rm
    _c: Clickable = rm
