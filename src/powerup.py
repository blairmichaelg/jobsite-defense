"""Jobsite Defense — power-up tile rendering.

Phase 1.5: imports from :mod:`src.level` instead of :mod:`src.settings`.
``draw_powerups`` is retained for standalone use (e.g. minimap or editor).
The main render path uses ``build_static_layer`` instead.
"""

from __future__ import annotations

import pygame

from src.grid import cell_rect
from src.level import POWERUP_LABELS, load_level
from src.settings import CELL_SIZE, POWERUP_COLORS


def draw_powerups(
    surface: pygame.Surface,
    font: pygame.font.Font,
    powerup_tiles: dict[tuple[int, int], tuple[str, float]] | None = None,
) -> None:
    """Draw all power-up tiles as coloured cells with a text label."""
    tiles = powerup_tiles if powerup_tiles is not None else load_level("level_1.json").powerup_tiles
    overlay = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
    for (col, row), (effect, _mult) in tiles.items():
        color = POWERUP_COLORS.get(effect, (255, 255, 255))
        rect = cell_rect(col, row)

        overlay.fill((*color, 90))
        surface.blit(overlay, rect.topleft)

        pygame.draw.rect(surface, color, rect, width=2)

        label = POWERUP_LABELS.get(effect, "???")
        text_surf = font.render(label, True, (255, 255, 255))
        surface.blit(text_surf, text_surf.get_rect(center=rect.center))
