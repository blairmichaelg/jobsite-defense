"""Jobsite Defense — main entry point and game loop.

Phase 5 changes
---------------
* Added ``GameState.MAIN_MENU``: boots into a title screen prompting for ENTER to start.
* Cached overlay surfaces for Main Menu, Game Over, and Victory to avoid per-frame allocations.
* Clears active clickables when ``game_state != GameState.PLAYING``.
* Added ``R`` key restart handler to re-initialize game state without process restarts.
* Invokes ``world.refresh_auras()`` immediately after the dead-enemy cull pass.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import pygame

from src.economy import Economy
from src.level import load_level
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

    MAIN_MENU = "MAIN_MENU"
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


def _build_screen_overlay(
    bg_rgba: tuple[int, int, int, int],
    title_text: str,
    title_color: tuple[int, int, int],
    sub_text: str,
    sub_color: tuple[int, int, int],
    title_font: pygame.font.Font,
    sub_font: pygame.font.Font,
) -> pygame.Surface:
    """Pre-render and bake a static modal overlay surface."""
    surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    surf.fill(bg_rgba)

    t_rendered = title_font.render(title_text, True, title_color)
    s_rendered = sub_font.render(sub_text, True, sub_color)

    surf.blit(
        t_rendered,
        t_rendered.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 25)),
    )
    surf.blit(
        s_rendered,
        s_rendered.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 30)),
    )
    return surf


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Jobsite Defense Phase 5 game loop."""
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
    sub_banner_font = pygame.font.Font(None, 24)

    static_layer = build_static_layer(label_font)

    # Pre-render modal overlay surfaces outside game loop
    menu_overlay = _build_screen_overlay(
        (20, 25, 20, 200),
        "Jobsite Defense",
        (240, 220, 100),
        "Press ENTER to start The Foundation",
        (220, 230, 220),
        banner_font,
        sub_banner_font,
    )

    game_over_overlay = _build_screen_overlay(
        (35, 0, 0, 200),
        "YOU'RE FIRED!",
        (240, 60, 60),
        "The client ran out of patience. (Press R to restart, ESC to exit)",
        (220, 200, 200),
        banner_font,
        sub_banner_font,
    )

    victory_overlay = _build_screen_overlay(
        (0, 35, 0, 200),
        "CONTRACT COMPLETE!",
        (80, 230, 80),
        "Jobsite defended on schedule and under budget! (Press R to restart, ESC to exit)",
        (200, 240, 200),
        banner_font,
        sub_banner_font,
    )

    # Level loading & state setup
    level_path = Path("levels/level_1.json")
    level_data = load_level(str(level_path)) if level_path.exists() else None

    world = World(economy=Economy())
    wave_manager = (
        WaveManager(waves=level_data.waves)
        if level_data
        else WaveManager()
    )
    game_state = GameState.MAIN_MENU

    menu = RadialMenu()
    menu.configure(world)
    entities: list[Entity] = _build_entity_list(world, menu, wave_manager)

    # HUD cache
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

    def _reset_game() -> None:
        nonlocal world, wave_manager, menu, entities, game_state, prev_budget, hud_surfaces
        world = World(economy=Economy())
        wave_manager = (
            WaveManager(waves=level_data.waves)
            if level_data
            else WaveManager()
        )
        menu = RadialMenu()
        menu.configure(world)
        entities = _build_entity_list(world, menu, wave_manager)
        prev_budget = world.economy.project_budget
        hud_surfaces = _rebuild_hud()
        game_state = GameState.PLAYING

    # ------------------------------------------------------------------
    # Game Loop
    # ------------------------------------------------------------------
    running = True
    while running:
        dt = min(clock.tick(TARGET_FPS) / 1000.0, _DT_MAX)

        raw_events = pygame.event.get()
        clickables: list[Clickable] = [
            e for e in reversed(entities) if isinstance(e, Clickable)
        ]
        if game_state != GameState.PLAYING:
            clickables = []

        for event in raw_events:
            if event.type == pygame.QUIT:
                running = False
                break

            consumed = any(c.handle_event(event) for c in clickables)

            if not consumed and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    break
                if event.key == pygame.K_RETURN and game_state == GameState.MAIN_MENU:
                    _reset_game()
                    break
                if event.key == pygame.K_r and game_state in (
                    GameState.GAME_OVER,
                    GameState.VICTORY,
                    GameState.PLAYING,
                ):
                    _reset_game()
                    break

        if not running:
            break

        # Simulation pass
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

            # Re-evaluate all persistent enemy auras
            world.refresh_auras()

            if world.economy.game_over:
                game_state = GameState.GAME_OVER
            elif wave_manager.state == WaveState.VICTORY and not world.enemies:
                game_state = GameState.VICTORY

        entities = _build_entity_list(world, menu, wave_manager)

        # HUD Refresh
        hud_timer -= dt
        budget_changed = world.economy.project_budget != prev_budget
        if hud_timer <= 0.0 or budget_changed or patience_changed or earned > 0:
            hud_surfaces = _rebuild_hud()
            hud_timer = _HUD_REFRESH_INTERVAL
            prev_budget = world.economy.project_budget

        # Rendering
        screen.blit(static_layer, (0, 0))
        for ent in entities:
            ent.draw(screen)

        for i, surf in enumerate(hud_surfaces):
            screen.blit(surf, (_HUD_X, _HUD_Y + i * _HUD_LINE_H))

        # Modals
        if game_state == GameState.MAIN_MENU:
            screen.blit(menu_overlay, (0, 0))
        elif game_state == GameState.GAME_OVER:
            screen.blit(game_over_overlay, (0, 0))
        elif game_state == GameState.VICTORY:
            screen.blit(victory_overlay, (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
