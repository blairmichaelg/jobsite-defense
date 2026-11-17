"""Jobsite Defense — road data and rendering.

The road is stored as a ``frozenset`` of ``(col, row)`` tuples
(defined in :mod:`settings`).  This module exposes a single draw
function that fills those cells with asphalt grey.
"""

from __future__ import annotations

import pygame

from src.grid import cell_rect
from src.settings import COLOR_ROAD, ROAD_CELLS


def draw_road(surface: pygame.Surface) -> None:
    """Shade every road cell with the asphalt-grey color.

    Args:
        surface: The main display surface to draw on.
    """
    for col, row in ROAD_CELLS:
        pygame.draw.rect(surface, COLOR_ROAD, cell_rect(col, row))
