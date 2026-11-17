"""Jobsite Defense — main entry point and game loop.

Phase 2.5 changes
-----------------
* ``World`` context object introduced.  Every ``Entity.update(dt, world)``
  call passes ``world`` so entities can read enemies, towers, and economy
  without storing globals.
* Entity list is a **persistent** ``list[Entity]``; dead enemies are culled
  once after the update pass — no auto-respawn.  Phase 3's Wave Manager
  will append enemies via ``world.enemies``.
* ESC fix: Clickable dispatch runs first on every event.  ``running = False``
  is only set when QUIT arrives or ESC is unhandled by all Clickables.
* HUD rebuilds immediately when ``project_budget`` or ``client_patience``
  change (tracked via snapshot), not just on the 0.5 s timer.
* Kill bounty: ``world.flush_earnings()`` pays queued rewards after the
  update pass and forces an immediate HUD refresh.
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
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from src.ui import RadialMenu
from src.world import World

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

def _make_enemy() -> Enemy:
    """Construct a fresh ``Enemy`` positioned at the spawn waypoint."""
    wx, wy = WAYPOINT_PIXELS[0]
    return Enemy(pos=pygame.Vector2(wx, wy))


def _build_entity_list(world: World, menu: RadialMenu) -> list[Entity]:
    """Return entities sorted by layer from live world state.

    Includes alive enemies, all placed towers, and the menu.  Dead
    enemies are excluded — the Phase 3 Wave Manager will handle spawning.

    Args:
        world: Shared game state.
        menu: The persistent radial-menu singleton.
    """
    alive: list[Entity] = [e for e in world.enemies if e.alive]
    towers: list[Entity] = list(world.towers.values())
    return sorted(alive + towers + [menu], key=lambda e: e.layer)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the Jobsite Defense Phase 2.5 game loop."""
    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, 720),
        pygame.SCALED | pygame.DOUBLEBUF,
        vsync=1,
    )
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    label_font = pygame.font.Font(None, 20)
    hud_font = pygame.font.Font(None, 22)

    static_layer = build_static_layer(label_font)

    # --- World -----------------------------------------------------------
    world = World(
        enemies=[_make_enemy()],   # one demo enemy for Phase 2.5
        economy=Economy(),
    )

    # --- Radial menu (Clickable UI, not in world.enemies) ----------------
    menu = RadialMenu()
    menu.configure(world.economy, world.towers)

    # --- Entity list (rebuilt after each mutation) -----------------------
    entities: list[Entity] = _build_entity_list(world, menu)

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

            # Let every Clickable try to consume the event first.
            consumed = any(c.handle_event(event) for c in clickables)

            # Only quit on ESC if no Clickable wanted it.
            if not consumed and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                break

        if not running:
            break

        # 3. Update all entities with the shared world
        for ent in entities:
            ent.update(dt, world)

        # 4. Flush kill bounties & enemy lifecycle
        earned = world.flush_earnings()

        patience_changed = False
        for enemy in list(world.enemies):
            if not enemy.alive:
                if enemy.reached_end:
                    world.economy.lose_patience()
                    patience_changed = True
                world.enemies.remove(enemy)

        # 5. Rebuild entity list (towers dict may have changed via menu)
        entities = _build_entity_list(world, menu)
        clickables = [e for e in reversed(entities) if isinstance(e, Clickable)]

        # 6. HUD — throttled refresh + immediate on stat change
        hud_timer -= dt
        budget_changed = world.economy.project_budget != prev_budget
        if hud_timer <= 0.0 or budget_changed or patience_changed or earned > 0:
            hud_surfaces = _rebuild_hud()
            hud_timer = _HUD_REFRESH_INTERVAL
            prev_budget = world.economy.project_budget

        # 7. Render (back → front)
        screen.blit(static_layer, (0, 0))
        for ent in entities:
            ent.draw(screen)

        # 8. HUD overlay (top-left)
        for i, surf in enumerate(hud_surfaces):
            screen.blit(surf, (_HUD_X, _HUD_Y + i * _HUD_LINE_H))

        pygame.display.flip()

        if world.economy.game_over:
            running = False

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
