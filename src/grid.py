"""Jobsite Defense — grid geometry and cell coordinate utilities.

Provides coordinate math and bounding rectangle lookups for the 16x12 cell grid,
along with baseline raster routines for background fills and overlay lines.
"""

from __future__ import annotations

import pygame

from src.settings import (
    CELL_SIZE,
    COLOR_GRASS,
    COLOR_GRID_LINE,
    GRID_COLS,
    GRID_ROWS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


def draw_background(surface: pygame.Surface) -> None:
    """Fill the entire surface with the grass colour.

    Args:
        surface: Target surface to draw on.
    """
    surface.fill(COLOR_GRASS)


def draw_grid_lines(surface: pygame.Surface) -> None:
    """Draw thin vertical and horizontal lines over the grid.

    Args:
        surface: Target surface to draw on.
    """
    for col in range(GRID_COLS + 1):
        pygame.draw.line(
            surface, COLOR_GRID_LINE,
            (col * CELL_SIZE, 0), (col * CELL_SIZE, WINDOW_HEIGHT),
        )
    for row in range(GRID_ROWS + 1):
        pygame.draw.line(
            surface, COLOR_GRID_LINE,
            (0, row * CELL_SIZE), (WINDOW_WIDTH, row * CELL_SIZE),
        )


def cell_rect(col: int, row: int) -> pygame.Rect:
    """Return the pixel ``Rect`` for a given grid cell.

    Args:
        col: Zero-based column index.
        row: Zero-based row index.

    Returns:
        A ``pygame.Rect`` covering the cell.
    """
    return pygame.Rect(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)


def cell_center(col: int, row: int) -> pygame.Vector2:
    """Return the pixel centre of a grid cell as a ``Vector2``.

    Args:
        col: Zero-based column index.
        row: Zero-based row index.

    Returns:
        A ``pygame.Vector2`` pointing at the cell's centre pixel.
    """
    return pygame.Vector2(
        col * CELL_SIZE + CELL_SIZE // 2,
        row * CELL_SIZE + CELL_SIZE // 2,
    )
