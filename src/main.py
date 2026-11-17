"""Jobsite Defense — main entry point and game loop.

Phase 1.5 changes
-----------------
* Display opened with ``pygame.SCALED | pygame.DOUBLEBUF`` and
  ``vsync=1`` so SDL2 locks presentation to the monitor's refresh rate
  on the Intel HD 620, eliminating tearing without busy-spin.
* Variable time-step is **clamped** to 50 ms (0.05 s) to prevent spiral-
  of-death hitches after window focus events or OS scheduler spikes.
* The static scene (grass + road + power-ups + grid) is baked once at
  startup by ``build_static_layer`` and blitted in a single call per
  frame.
* The FPS HUD surface is re-rendered at most twice per second; in between
  the cached surface is re-blitted, saving ~6 font-render calls per
  second.
* Enemy looping is managed here: when ``enemy.reached_end`` is ``True``
  a fresh ``Enemy`` replaces the old one.  The enemy class itself no
  longer loops internally.
"""

from __future__ import annotations

import sys

import pygame

from src.enemy import Enemy
from src.level import WAYPOINT_PIXELS
from src.render import build_static_layer
from src.settings import (
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)

# Maximum dt cap: prevents "spiral of death" after long pauses.
_DT_MAX: float = 0.05

# FPS HUD refresh interval in seconds (twice per second).
_HUD_REFRESH_INTERVAL: float = 0.5


def _make_enemy() -> Enemy:
    """Construct a fresh enemy positioned at the spawn waypoint.

    Returns:
        A new ``Enemy`` ready to begin its run.
    """
    return Enemy(pos=pygame.Vector2(WAYPOINT_PIXELS[0]))


def main() -> None:
    """Run the Jobsite Defense Phase 1.5 demo loop."""
    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    pygame.init()

    # SCALED  → SDL2 handles logical→physical resolution mapping.
    # DOUBLEBUF + vsync=1 → flip synchronised to monitor refresh rate.
    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT),
        pygame.SCALED | pygame.DOUBLEBUF,
        vsync=1,
    )
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    # Fonts — initialised before build_static_layer so the layer can use them.
    label_font = pygame.font.Font(None, 20)
    hud_font = pygame.font.Font(None, 26)

    # Bake the immutable background once; blit it every frame.
    static_layer = build_static_layer(label_font)

    # Spawn the first enemy.
    enemy = _make_enemy()

    # HUD state: pre-rendered surface + countdown timer.
    hud_surf = hud_font.render("FPS: --", True, (220, 220, 220))
    hud_timer = 0.0

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------
    running = True
    while running:
        # 1. Clamped variable time-step
        dt = min(clock.tick(TARGET_FPS) / 1000.0, _DT_MAX)

        # 2. Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # 3. Update
        enemy.update(dt)

        # Respawn when this enemy exits off-screen.
        if not enemy.alive:
            enemy = _make_enemy()

        # 4. Render (back → front)
        screen.blit(static_layer, (0, 0))   # single blit replaces 75+ draw calls
        enemy.draw(screen)

        # 5. HUD — throttled FPS counter
        hud_timer -= dt
        if hud_timer <= 0.0:
            fps_text = f"FPS: {clock.get_fps():.0f}"
            hud_surf = hud_font.render(fps_text, True, (220, 220, 220))
            hud_timer = _HUD_REFRESH_INTERVAL
        screen.blit(hud_surf, (WINDOW_WIDTH - hud_surf.get_width() - 8, 6))

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
