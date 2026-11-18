"""Jobsite Defense — main application entry point.

Phase 6: Scene architecture driven game loop.
"""

from __future__ import annotations

import pygame

from src.save import SaveData
from src.scene import SceneManager, TitleScene
from src.settings import TARGET_FPS, WINDOW_HEIGHT, WINDOW_TITLE, WINDOW_WIDTH

_DT_MAX: float = 0.05


def main() -> None:
    """Initialize display hardware, load save state, and run the scene manager loop."""
    pygame.init()
    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT),
        pygame.SCALED,
        vsync=1,
    )
    pygame.display.set_caption(WINDOW_TITLE)

    clock = pygame.time.Clock()
    save_data = SaveData.load()
    scene_manager = SceneManager()
    title_scene = TitleScene(scene_manager, save_data)
    scene_manager.change(title_scene)

    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, _DT_MAX)
        scene_manager.fps = clock.get_fps()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            scene_manager.handle_event(event)

        scene_manager.update(dt)
        scene_manager.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
