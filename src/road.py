"""Jobsite Defense — road data and rendering.

Phase 1.5: imports ``ROAD_CELLS`` from :mod:`src.level` instead of
:mod:`src.settings`.  The ``draw_road`` function is retained for cases
where callers need to paint road cells onto an arbitrary surface outside
the static layer (e.g. a minimap).  The main render path uses
``build_static_layer`` instead.
"""

from __future__ import annotations

import pygame

from src.grid import cell_rect
from src.level import load_level
from src.settings import COLOR_ROAD


def draw_road(
    surface: pygame.Surface,
    road_cells: frozenset[tuple[int, int]] | None = None,
) -> None:
    """Shade every road cell with the asphalt-grey color."""
    cells = road_cells if road_cells is not None else load_level("level_1.json").road_cells
    for col, row in cells:
        pygame.draw.rect(surface, COLOR_ROAD, cell_rect(col, row))
