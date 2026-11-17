"""Jobsite Defense — main entry point and game loop.

Phase 2 changes
---------------
* ``Economy`` dataclass added; patience decrements on enemy escape.
* ``entities: list[Entity]`` replaces the bare ``enemy`` variable.
  Entities are sorted by ``layer`` ascending; the loop iterates once for
  ``update`` and once for ``draw``.  Towers live in a parallel
  ``towers: dict[tuple[int,int], NailGunner]`` for fast spatial lookups.
* ``RadialMenu`` handles its own click events via the ``Clickable``
  protocol; the game loop dispatches events to all ``Clickable`` entities
  in reverse layer order (top-most UI first) and stops on first consumer.
* HUD now displays Budget ($$) and Patience alongside FPS.
* Display remains ``SCALED | DOUBLEBUF`` with ``vsync=1``; dt clamped to
  0.05 s.
"""

from __future__ import annotations

import sys

import pygame

from src.economy import Economy
from src.enemy import Enemy
from src.level import WAYPOINT_PIXELS
from src.protocols import Clickable, Entity
from src.render import build_static_layer
from src.settings import (
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from src.tower import NailGunner
from src.ui import RadialMenu

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DT_MAX: float = 0.05
_HUD_REFRESH_INTERVAL: float = 0.5

# HUD layout
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

def _make_enemy() -> Enemy:
    """Construct a fresh ``Enemy`` positioned at the spawn waypoint."""
    wx, wy = WAYPOINT_PIXELS[0]
    return Enemy(pos=pygame.Vector2(wx, wy))


def _sorted_entities(raw: list[Entity]) -> list[Entity]:
    """Return *raw* sorted ascending by ``layer`` (stable sort)."""
    return sorted(raw, key=lambda e: e.layer)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the Jobsite Defense Phase 2 game loop."""
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

    # Fonts
    label_font = pygame.font.Font(None, 20)
    hud_font = pygame.font.Font(None, 22)

    # Static background — baked once at startup
    static_layer = build_static_layer(label_font)

    # Game state
    economy = Economy()
    towers: dict[tuple[int, int], NailGunner] = {}

    # Radial menu — wired up to economy + towers dict
    menu = RadialMenu()
    menu.configure(economy, towers)

    # Seed first enemy
    enemy = _make_enemy()

    # Entity list (re-sorted whenever composition changes)
    entities: list[Entity] = _sorted_entities([enemy, menu])

    # HUD cache
    hud_surfaces: list[pygame.Surface] = []
    hud_timer = 0.0

    def _rebuild_hud() -> list[pygame.Surface]:
        patience_color = (
            _COLOR_HUD_PATIENCE_LOW
            if economy.client_patience <= _PATIENCE_LOW_THRESHOLD
            else _COLOR_HUD_PATIENCE_OK
        )
        fps_txt = f"FPS: {clock.get_fps():.0f}"
        budget_txt = f"Budget: ${economy.project_budget:,}"
        patience_txt = f"Patience: {economy.client_patience}"
        return [
            hud_font.render(fps_txt, True, _COLOR_HUD_TEXT),
            hud_font.render(budget_txt, True, _COLOR_HUD_TEXT),
            hud_font.render(patience_txt, True, patience_color),
        ]

    hud_surfaces = _rebuild_hud()

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------
    running = True
    while running:
        # 1. Clamped variable time-step
        dt = min(clock.tick(TARGET_FPS) / 1000.0, _DT_MAX)

        # 2. Events — dispatched to Clickable entities (highest layer first)
        raw_events = pygame.event.get()
        clickables: list[Clickable] = [
            e for e in reversed(entities) if isinstance(e, Clickable)
        ]
        for event in raw_events:
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                break

            consumed = False
            for clickable in clickables:
                if clickable.handle_event(event):
                    consumed = True
                    break

            # Towers placed via menu: sync entities list
            if not consumed and event.type == pygame.MOUSEBUTTONDOWN:
                pass   # menu handles its own purchase; list rebuilt below

        # Sync entity list whenever the towers dict changes
        active_enemies: list[Enemy] = [e for e in entities if isinstance(e, Enemy) and e.alive]
        all_tower_entities: list[NailGunner] = list(towers.values())
        entities = _sorted_entities(
            active_enemies + all_tower_entities + [menu]
        )
        # Re-attach clickables after sort
        clickables = [e for e in reversed(entities) if isinstance(e, Clickable)]

        # 3. Update
        for ent in entities:
            if isinstance(ent, NailGunner):
                # Towers need the live enemy list
                live_enemies = [e for e in entities if isinstance(e, Enemy) and e.alive]
                ent.update_with_enemies(dt, live_enemies)
            else:
                ent.update(dt)

        # Handle enemy lifecycle
        for ent in list(entities):
            if isinstance(ent, Enemy) and not ent.alive:
                if ent.reached_end:
                    economy.lose_patience()
                # Spawn a fresh enemy for continuous demo
                new_enemy = _make_enemy()
                entities = _sorted_entities(
                    [e for e in entities if e is not ent]
                    + [new_enemy]
                )

        # Rebuild HUD on a throttle
        hud_timer -= dt
        if hud_timer <= 0.0:
            hud_surfaces = _rebuild_hud()
            hud_timer = _HUD_REFRESH_INTERVAL

        # 4. Render (back → front)
        screen.blit(static_layer, (0, 0))

        for ent in entities:
            ent.draw(screen)

        # 5. HUD overlay (top-left)
        for i, surf in enumerate(hud_surfaces):
            screen.blit(surf, (_HUD_X, _HUD_Y + i * _HUD_LINE_H))

        pygame.display.flip()

        # Game-over check
        if economy.game_over:
            # Phase 2: simply stop the loop (Phase 3 will show a screen)
            running = False

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
