"""Jobsite Defense — static render-layer builder.

Baking all geometry that never changes (grass, road, power-up tiles, and
grid lines) onto a single pre-converted ``pygame.Surface`` at startup
reduces per-frame draw calls from 75+ to a **single** ``blit``.

On the target Intel HD 620 this matters: software-rasterised ``draw.rect``
and ``draw.line`` are CPU-bound.  One blit is a DMA copy the driver can
schedule efficiently.

Public API
----------
``build_static_layer(label_font)`` — call once after ``pygame.init()``.
Return value should be stored and blitted to ``screen`` at the top of
each render pass.
"""

from __future__ import annotations

import pygame

from src.grid import cell_rect
from src.level import POWERUP_LABELS, POWERUP_TILES, ROAD_CELLS
from src.settings import (
    CELL_SIZE,
    COLOR_GRASS,
    COLOR_GRID_LINE,
    COLOR_ROAD,
    GRID_COLS,
    GRID_ROWS,
    POWERUP_COLORS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


def build_static_layer(label_font: pygame.font.Font) -> pygame.Surface:
    """Compose the immutable background into one pre-converted surface.

    Rendering order (painter's algorithm, back → front):

    1. Grass fill
    2. Road cell rectangles
    3. Power-up tile overlays + border highlights + labels
    4. Grid lines

    The returned surface is ``convert()``-ed to the display pixel format
    for the fastest possible per-frame blit.

    Args:
        label_font: Font used to render the three-letter power-up labels
                    (``"SPD"``, ``"DMG"``, ``"RNG"``).  Pass the same
                    font instance used for other small UI text.

    Returns:
        A display-format ``pygame.Surface`` ready to blit each frame.
    """
    # Work on an SRCALPHA surface so power-up overlays composite cleanly,
    # then convert to display format at the end.
    layer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)

    # ------------------------------------------------------------------
    # 1. Grass background
    # ------------------------------------------------------------------
    layer.fill(COLOR_GRASS)

    # ------------------------------------------------------------------
    # 2. Road cells
    # ------------------------------------------------------------------
    for col, row in ROAD_CELLS:
        pygame.draw.rect(layer, COLOR_ROAD, cell_rect(col, row))

    # ------------------------------------------------------------------
    # 3. Power-up tiles — semi-transparent fill + border + label
    # ------------------------------------------------------------------
    overlay = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
    for (col, row), (effect, _mult) in POWERUP_TILES.items():
        color = POWERUP_COLORS.get(effect, (255, 255, 255))
        rect = cell_rect(col, row)

        overlay.fill((*color, 90))
        layer.blit(overlay, rect.topleft)

        pygame.draw.rect(layer, color, rect, width=2)

        label = POWERUP_LABELS.get(effect, "???")
        text_surf = label_font.render(label, True, (255, 255, 255))
        layer.blit(text_surf, text_surf.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # 4. Grid lines (drawn last so they sit on top of road/power-ups)
    # ------------------------------------------------------------------
    for col in range(GRID_COLS + 1):
        x = col * CELL_SIZE
        pygame.draw.line(layer, COLOR_GRID_LINE, (x, 0), (x, WINDOW_HEIGHT))
    for row in range(GRID_ROWS + 1):
        y = row * CELL_SIZE
        pygame.draw.line(layer, COLOR_GRID_LINE, (0, y), (WINDOW_WIDTH, y))

    return layer.convert()
