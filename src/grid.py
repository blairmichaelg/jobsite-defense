"""Jobsite Defense — grid rendering utilities.

Draws the background grass fill and the thin overlay grid lines that
give the playing field its structure.
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
    """Fill the entire surface with the grass color.

    Args:
        surface: The main display surface to draw on.
    """
    surface.fill(COLOR_GRASS)


def draw_grid_lines(surface: pygame.Surface) -> None:
    """Draw thin vertical and horizontal lines over the grid.

    Args:
        surface: The main display surface to draw on.
    """
    for col in range(GRID_COLS + 1):
        x: int = col * CELL_SIZE
        pygame.draw.line(surface, COLOR_GRID_LINE, (x, 0), (x, WINDOW_HEIGHT))
    for row in range(GRID_ROWS + 1):
        y: int = row * CELL_SIZE
        pygame.draw.line(surface, COLOR_GRID_LINE, (0, y), (WINDOW_WIDTH, y))


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
    """Return the pixel center of a grid cell as a ``Vector2``.

    Args:
        col: Zero-based column index.
        row: Zero-based row index.

    Returns:
        A ``pygame.Vector2`` pointing at the cell's center pixel.
    """
    return pygame.Vector2(
        col * CELL_SIZE + CELL_SIZE // 2,
        row * CELL_SIZE + CELL_SIZE // 2,
    )
