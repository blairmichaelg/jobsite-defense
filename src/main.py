"""Jobsite Defense — main entry point and game loop.

Phase 4 changes
---------------
* Added ``GameState`` enum (``PLAYING``, ``GAME_OVER``, ``VICTORY``).
* End-state overlays: "YOU'RE FIRED!" on patience depletion;
  "CONTRACT COMPLETE!" on wave campaign completion.
* Clean termination on ESC without invoking ``sys.exit()``.
* Leaked enemies deduct archetype-specific ``enemy.patience_cost`` (20 for OSHA boss).
"""

from __future__ import annotations

from enum import Enum

import pygame

from src.economy import Economy
from src.protocols import Clickable, Entity
from src.render import build_static_layer
from src.settings import (
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from src.ui import RadialMenu
from src.wave import WaveManager, WaveState
from src.world import World

# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------


class GameState(Enum):
    """Overall gameplay session state."""

    PLAYING = "PLAYING"
    GAME_OVER = "GAME_OVER"
    VICTORY = "VICTORY"


_DT_MAX: float = 0.05
_HUD_REFRESH_INTERVAL: float = 0.5

_HUD_X: int = 8
_HUD_Y: int = 6
_HUD_LINE_H: int = 18
_COLOR_HUD_TEXT: tuple[int, int, int] = (220, 220, 220)
_COLOR_HUD_PATIENCE_OK: tuple[int, int, int] = (100, 220, 100)
_COLOR_HUD_PATIENCE_LOW: tuple[int, int, int] = (220, 80, 80)
_PATIENCE_LOW_THRESHOLD: int = 25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_entity_list(
    world: World, menu: RadialMenu, wave_manager: WaveManager
) -> list[Entity]:
    """Return entities sorted by layer from live world state."""
    alive_enemies: list[Entity] = [e for e in world.enemies if e.alive]
    alive_projectiles: list[Entity] = [p for p in world.projectiles if p.alive]
    towers: list[Entity] = list(world.towers.values())
    return sorted(
        alive_enemies + alive_projectiles + towers + [menu, wave_manager],
        key=lambda e: e.layer,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Jobsite Defense Phase 4 game loop."""
    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT),
        pygame.SCALED | pygame.DOUBLEBUF,
        vsync=1,
    )
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    label_font = pygame.font.Font(None, 20)
    hud_font = pygame.font.Font(None, 22)
    banner_font = pygame.font.Font(None, 56)
    sub_banner_font = pygame.font.Font(None, 26)

    static_layer = build_static_layer(label_font)

    # --- World & Systems -------------------------------------------------
    world = World(economy=Economy())
    wave_manager = WaveManager()
    game_state = GameState.PLAYING

    # --- Radial menu (Clickable UI) --------------------------------------
    menu = RadialMenu()
    menu.configure(world)

    # --- Entity list -----------------------------------------------------
    entities: list[Entity] = _build_entity_list(world, menu, wave_manager)

    # --- HUD cache -------------------------------------------------------
    prev_budget = world.economy.project_budget

    def _rebuild_hud() -> list[pygame.Surface]:
        patience_color = (
            _COLOR_HUD_PATIENCE_LOW
            if world.economy.client_patience <= _PATIENCE_LOW_THRESHOLD
            else _COLOR_HUD_PATIENCE_OK
        )
        return [
            hud_font.render(f"FPS: {clock.get_fps():.0f}", True, _COLOR_HUD_TEXT),
            hud_font.render(
                f"Budget: ${world.economy.project_budget:,}", True, _COLOR_HUD_TEXT
            ),
            hud_font.render(
                f"Patience: {world.economy.client_patience}", True, patience_color
            ),
        ]

    hud_surfaces = _rebuild_hud()
    hud_timer = _HUD_REFRESH_INTERVAL

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------
    running = True
    while running:
        # 1. Clamped variable time-step
        dt = min(clock.tick(TARGET_FPS) / 1000.0, _DT_MAX)

        # 2. Events — Clickables consume first; unhandled ESC quits
        raw_events = pygame.event.get()
        clickables: list[Clickable] = [
            e for e in reversed(entities) if isinstance(e, Clickable)
        ]
        for event in raw_events:
            if event.type == pygame.QUIT:
                running = False
                break

            consumed = any(c.handle_event(event) for c in clickables)

            if not consumed and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                break

        if not running:
            break

        # 3. Simulation (only if actively playing)
        earned = 0
        patience_changed = False

        if game_state == GameState.PLAYING:
            for ent in entities:
                ent.update(dt, world)

            earned = world.flush_earnings()

            for enemy in world.enemies:
                if not enemy.alive and enemy.reached_end:
                    world.economy.lose_patience(enemy.patience_cost)
                    patience_changed = True

            # In-place slice cull
            world.enemies[:] = [e for e in world.enemies if e.alive]
            world.projectiles[:] = [p for p in world.projectiles if p.alive]

            # Check game-over / victory conditions
            if world.economy.game_over:
                game_state = GameState.GAME_OVER
            elif wave_manager.state == WaveState.VICTORY and not world.enemies:
                game_state = GameState.VICTORY

        # 4. Rebuild entity list
        entities = _build_entity_list(world, menu, wave_manager)

        # 5. HUD — throttled refresh + immediate on stat change
        hud_timer -= dt
        budget_changed = world.economy.project_budget != prev_budget
        if hud_timer <= 0.0 or budget_changed or patience_changed or earned > 0:
            hud_surfaces = _rebuild_hud()
            hud_timer = _HUD_REFRESH_INTERVAL
            prev_budget = world.economy.project_budget

        # 6. Render (back → front)
        screen.blit(static_layer, (0, 0))
        for ent in entities:
            ent.draw(screen)

        # 7. HUD overlay (top-left)
        for i, surf in enumerate(hud_surfaces):
            screen.blit(surf, (_HUD_X, _HUD_Y + i * _HUD_LINE_H))

        # 8. End-state Banners
        if game_state == GameState.GAME_OVER:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((30, 0, 0, 190))
            screen.blit(overlay, (0, 0))

            title = banner_font.render("YOU'RE FIRED!", True, (240, 60, 60))
            screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 25)))

            sub = sub_banner_font.render(
                "The client ran out of patience. (Press ESC to exit)",
                True,
                (220, 200, 200),
            )
            screen.blit(sub, sub.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 25)))

        elif game_state == GameState.VICTORY:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 30, 0, 190))
            screen.blit(overlay, (0, 0))

            title = banner_font.render("CONTRACT COMPLETE!", True, (80, 230, 80))
            screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 25)))

            sub = sub_banner_font.render(
                "Jobsite defended on schedule and under budget! (Press ESC to exit)",
                True,
                (200, 240, 200),
            )
            screen.blit(sub, sub.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 25)))

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Clean Shutdown without sys.exit()
    # ------------------------------------------------------------------
    pygame.quit()


if __name__ == "__main__":
    main()
