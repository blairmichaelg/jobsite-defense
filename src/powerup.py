"""Jobsite Defense — power-up tile data and rendering.

Power-up tiles are stored as a dictionary of ``{(col, row): (effect, mult)}``
in :mod:`settings`.  This module draws each tile as a semi-transparent
colored overlay on the grid.
"""

from __future__ import annotations

import pygame

from src.grid import cell_rect
from src.settings import (
    CELL_SIZE,
    POWERUP_COLORS,
    POWERUP_TILES,
)

# Labels rendered on each tile for visual identification
_POWERUP_LABELS: dict[str, str] = {
    "attack_speed": "SPD",
    "damage": "DMG",
    "range": "RNG",
}


def draw_powerups(surface: pygame.Surface, font: pygame.font.Font) -> None:
    """Draw all power-up tiles as colored cells with a text label.

    A semi-transparent overlay is blitted onto each power-up cell, then
    a short label (e.g. ``"SPD"``) is centered on top.

    Args:
        surface: The main display surface to draw on.
        font: A ``pygame.font.Font`` used for the label text.
    """
    overlay: pygame.Surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)

    for (col, row), (effect, _mult) in POWERUP_TILES.items():
        color: tuple[int, int, int] = POWERUP_COLORS.get(effect, (255, 255, 255))

        # Semi-transparent fill
        overlay.fill((*color, 90))
        rect: pygame.Rect = cell_rect(col, row)
        surface.blit(overlay, rect.topleft)

        # Border highlight
        pygame.draw.rect(surface, color, rect, width=2)

        # Centered label
        label: str = _POWERUP_LABELS.get(effect, "???")
        text_surf: pygame.Surface = font.render(label, True, (255, 255, 255))
        text_rect: pygame.Rect = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, text_rect)
