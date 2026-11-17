"""Jobsite Defense — main entry point and game loop.

Initialises Pygame-CE, opens the game window, and runs the core loop:
    1. Tick the clock (variable time-step).
    2. Process events.
    3. Update entities.
    4. Render the frame.

This module can be executed directly (``python -m src.main``) or via the
convenience launcher ``run.py``.
"""

from __future__ import annotations

import sys

import pygame

from src.enemy import Enemy
from src.grid import draw_background, draw_grid_lines
from src.powerup import draw_powerups
from src.road import draw_road
from src.settings import (
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)


def main() -> None:
    """Run the Jobsite Defense Phase 1 demo loop."""
    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    pygame.init()
    screen: pygame.Surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock: pygame.time.Clock = pygame.time.Clock()

    # Small font for power-up labels
    label_font: pygame.font.Font = pygame.font.Font(None, 20)

    # HUD font for FPS display
    hud_font: pygame.font.Font = pygame.font.Font(None, 26)

    # Spawn a single test enemy
    enemy: Enemy = Enemy()

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------
    running: bool = True
    while running:
        # 1. Variable time-step
        dt: float = clock.tick(TARGET_FPS) / 1000.0

        # 2. Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # 3. Update
        enemy.update(dt)

        # 4. Render (painter's order: back → front)
        draw_background(screen)
        draw_road(screen)
        draw_powerups(screen, label_font)
        draw_grid_lines(screen)
        enemy.draw(screen)

        # Mini HUD — FPS counter (top-right)
        fps_text: str = f"FPS: {clock.get_fps():.0f}"
        fps_surf: pygame.Surface = hud_font.render(fps_text, True, (220, 220, 220))
        screen.blit(fps_surf, (WINDOW_WIDTH - fps_surf.get_width() - 8, 6))

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
