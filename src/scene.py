"""Jobsite Defense — scene architecture and screen state manager.

Phase 6 addition:
- Formal `Scene` protocol with handle_event, update, and draw.
- Stack-based `SceneManager` supporting push, pop, and replace.
- Specific scenes: `TitleScene`, `LevelSelectScene`, `GameplayScene`, and `PauseScene`.
- Decouples UI, HUD rendering, and event routing from the root main loop.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

import pygame

from src.level import LevelData, LevelError, load_level
from src.protocols import Clickable, Entity
from src.render import build_static_layer
from src.save import SaveData
from src.settings import (
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from src.talent_ui import TalentTreeScene
from src.ui import RadialMenu
from src.wave import WaveManager, WaveState
from src.world import World

# ---------------------------------------------------------------------------
# Visual Constants
# ---------------------------------------------------------------------------

_COLOR_HUD_TEXT: tuple[int, int, int] = (240, 240, 240)
_COLOR_HUD_PATIENCE_OK: tuple[int, int, int] = (100, 220, 100)
_COLOR_HUD_PATIENCE_LOW: tuple[int, int, int] = (220, 60, 60)
_PATIENCE_LOW_THRESHOLD: int = 30
_HUD_REFRESH_INTERVAL: float = 0.5


class GameState(Enum):
    """Status lifecycle within active gameplay."""

    PLAYING = "PLAYING"
    GAME_OVER = "GAME_OVER"
    VICTORY = "VICTORY"


# ---------------------------------------------------------------------------
# Scene Protocol & Stack Manager
# ---------------------------------------------------------------------------


@runtime_checkable
class Scene(Protocol):
    """Protocol satisfied by all screen controllers in the game."""

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process input event. Returns True if event was consumed."""
        ...

    def update(self, dt: float) -> None:
        """Advance simulation timers and entities by dt seconds."""
        ...

    def draw(self, surface: pygame.Surface) -> None:
        """Render the scene onto the display surface."""
        ...


class SceneManager:
    """Stack-based scene manager supporting modal overlays and state transitions."""

    def __init__(self, initial_scene: Scene | None = None) -> None:
        self._stack: list[Scene] = []
        self.fps: float = 60.0
        if initial_scene is not None:
            self._stack.append(initial_scene)

    @property
    def current(self) -> Scene | None:
        """Top-most active scene receiving input and updates."""
        return self._stack[-1] if self._stack else None

    def push(self, scene: Scene) -> None:
        """Push a modal scene (e.g. Pause overlay) onto the top of the stack."""
        self._stack.append(scene)

    def pop(self) -> Scene | None:
        """Remove and return the top-most scene."""
        if self._stack:
            return self._stack.pop()
        return None

    def change(self, scene: Scene) -> None:
        """Clear stack and replace with a new base scene."""
        self._stack.clear()
        self._stack.append(scene)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Forward input event to top-most active scene."""
        if self._stack:
            return self._stack[-1].handle_event(event)
        return False

    def update(self, dt: float) -> None:
        """Advance only the top-most active scene."""
        if self._stack:
            self._stack[-1].update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Render scenes in stack order (enables bottom gameplay + top overlay)."""
        for scene in self._stack:
            scene.draw(surface)


# ---------------------------------------------------------------------------
# Overlay Helper
# ---------------------------------------------------------------------------


def _build_screen_overlay(
    bg_rgba: tuple[int, int, int, int],
    title_text: str,
    title_color: tuple[int, int, int],
    subtitle_text: str,
    subtitle_color: tuple[int, int, int],
    title_font: pygame.font.Font,
    sub_font: pygame.font.Font,
) -> pygame.Surface:
    """Pre-bake a semi-transparent modal overlay surface."""
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill(bg_rgba)

    title_surf = title_font.render(title_text, True, title_color)
    sub_surf = sub_font.render(subtitle_text, True, subtitle_color)

    cx = WINDOW_WIDTH // 2
    cy = WINDOW_HEIGHT // 2
    overlay.blit(title_surf, title_surf.get_rect(center=(cx, cy - 30)))
    overlay.blit(sub_surf, sub_surf.get_rect(center=(cx, cy + 30)))
    return overlay


# ---------------------------------------------------------------------------
# TitleScene
# ---------------------------------------------------------------------------


class TitleScene:
    """Main menu title screen displaying options to start, select level, or enter talent tree."""

    def __init__(
        self,
        scene_manager: SceneManager,
        save_data: SaveData | None = None,
    ) -> None:
        self.scene_manager = scene_manager
        self.save_data = save_data if save_data is not None else SaveData.load()

        self._font_title: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None

        self._btn_play = pygame.Rect(WINDOW_WIDTH // 2 - 140, 240, 280, 48)
        self._btn_levels = pygame.Rect(WINDOW_WIDTH // 2 - 140, 305, 280, 48)
        self._btn_tree = pygame.Rect(WINDOW_WIDTH // 2 - 140, 370, 280, 48)
        self._btn_quit = pygame.Rect(WINDOW_WIDTH // 2 - 140, 435, 280, 48)
        self.last_error: str | None = None

    def _ensure_fonts(self) -> None:
        if self._font_title is None and pygame.font.get_init():
            self._font_title = pygame.font.Font(None, 56)
            self._font_body = pygame.font.Font(None, 24)

    def _start_level(self, level_file: str) -> bool:
        """Safely attempt to transition into GameplayScene."""
        try:
            self.scene_manager.change(
                GameplayScene(level_file, self.save_data, self.scene_manager)
            )
            return True
        except LevelError as err:
            self.last_error = str(err)
            return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                return self._start_level("level_1.json")
            if event.key == pygame.K_l:
                self.scene_manager.push(LevelSelectScene(self.scene_manager, self.save_data))
                return True
            if event.key == pygame.K_t:
                self.scene_manager.push(TalentTreeScene(self.scene_manager, self.save_data))
                return True
            if event.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._btn_play.collidepoint(mx, my):
                return self._start_level("level_1.json")
            if self._btn_levels.collidepoint(mx, my):
                self.scene_manager.push(LevelSelectScene(self.scene_manager, self.save_data))
                return True
            if self._btn_tree.collidepoint(mx, my):
                self.scene_manager.push(TalentTreeScene(self.scene_manager, self.save_data))
                return True
            if self._btn_quit.collidepoint(mx, my):
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return True

        return False

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        if self._font_title is None or self._font_body is None:
            return

        surface.fill((20, 24, 34))

        # Title
        title_surf = self._font_title.render("JOBSITE DEFENSE", True, (245, 200, 60))
        surface.blit(title_surf, title_surf.get_rect(center=(WINDOW_WIDTH // 2, 110)))

        # Subtitle
        sub_surf = self._font_body.render(
            "Commercial Framing & Heavy Machinery Tower Defense", True, (170, 185, 205)
        )
        surface.blit(sub_surf, sub_surf.get_rect(center=(WINDOW_WIDTH // 2, 160)))

        # Equity counter
        eq_surf = self._font_body.render(
            f"Union Equity: {self.save_data.equity} Eq", True, (120, 220, 120)
        )
        surface.blit(eq_surf, eq_surf.get_rect(center=(WINDOW_WIDTH // 2, 195)))

        mouse_pos = pygame.mouse.get_pos()

        buttons = [
            (self._btn_play, "ENTER — Start The Foundation"),
            (self._btn_levels, "L — Level Select"),
            (self._btn_tree, "T — Union Hall / Talent Tree"),
            (self._btn_quit, "ESC — Exit Game"),
        ]

        for rect, label in buttons:
            hovered = rect.collidepoint(mouse_pos)
            bg = (45, 55, 75) if hovered else (32, 40, 56)
            border = (120, 180, 240) if hovered else (70, 85, 115)
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, border, rect, width=2, border_radius=6)

            txt = self._font_body.render(label, True, (240, 240, 240))
            surface.blit(txt, txt.get_rect(center=rect.center))


# ---------------------------------------------------------------------------
# LevelSelectScene
# ---------------------------------------------------------------------------


class LevelSelectScene:
    """Scene for selecting blueprint contracts (Level 1, Level 2)."""

    def __init__(
        self,
        scene_manager: SceneManager,
        save_data: SaveData,
    ) -> None:
        self.scene_manager = scene_manager
        self.save_data = save_data
        self._font_title: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None

        self._btn_lvl1 = pygame.Rect(WINDOW_WIDTH // 2 - 180, 160, 360, 60)
        self._btn_lvl2 = pygame.Rect(WINDOW_WIDTH // 2 - 180, 240, 360, 60)
        self._btn_back = pygame.Rect(WINDOW_WIDTH // 2 - 100, 350, 200, 40)
        self.last_error: str | None = None

    def _ensure_fonts(self) -> None:
        if self._font_title is None and pygame.font.get_init():
            self._font_title = pygame.font.Font(None, 40)
            self._font_body = pygame.font.Font(None, 22)

    def _start_level(self, level_file: str) -> bool:
        """Safely attempt to transition into GameplayScene."""
        try:
            self.scene_manager.change(
                GameplayScene(level_file, self.save_data, self.scene_manager)
            )
            return True
        except LevelError as err:
            self.last_error = str(err)
            return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.scene_manager.pop()
                return True
            if event.key == pygame.K_1:
                return self._start_level("level_1.json")
            if event.key == pygame.K_2:
                return self._start_level("level_2.json")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._btn_lvl1.collidepoint(mx, my):
                return self._start_level("level_1.json")
            if self._btn_lvl2.collidepoint(mx, my):
                return self._start_level("level_2.json")
            if self._btn_back.collidepoint(mx, my):
                self.scene_manager.pop()
                return True

        return False

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        if self._font_title is None or self._font_body is None:
            return

        surface.fill((18, 22, 32))

        title = self._font_title.render("SELECT BLUEPRINT CONTRACT", True, (240, 200, 60))
        surface.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 80)))

        mouse_pos = pygame.mouse.get_pos()

        for rect, key_txt, desc in [
            (self._btn_lvl1, "1. The Foundation", "Single Primary Path • Standard Waves"),
            (self._btn_lvl2, "2. The Subcontract", "Multi-Route Pathing • Main & Flank Assault"),
        ]:
            hovered = rect.collidepoint(mouse_pos)
            bg = (40, 50, 70) if hovered else (28, 35, 50)
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, (100, 160, 230), rect, width=2, border_radius=6)

            t1 = self._font_title.render(key_txt, True, (240, 240, 240))
            t2 = self._font_body.render(desc, True, (170, 185, 205))
            surface.blit(t1, (rect.x + 16, rect.y + 10))
            surface.blit(t2, (rect.x + 16, rect.y + 36))

        # Back
        pygame.draw.rect(surface, (35, 42, 55), self._btn_back, border_radius=4)
        pygame.draw.rect(surface, (140, 150, 170), self._btn_back, width=1, border_radius=4)
        back_surf = self._font_body.render("BACK TO MENU", True, (220, 220, 220))
        surface.blit(back_surf, back_surf.get_rect(center=self._btn_back.center))


# ---------------------------------------------------------------------------
# PauseScene (Modal Overlay)
# ---------------------------------------------------------------------------


class PauseScene:
    """Modal pause overlay pushed onto the stack during active gameplay."""

    def __init__(self, scene_manager: SceneManager) -> None:
        self.scene_manager = scene_manager
        self._font_title: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None
        self._overlay_surf: pygame.Surface | None = None

    def _ensure_overlay(self) -> None:
        if self._overlay_surf is None and pygame.font.get_init():
            self._font_title = pygame.font.Font(None, 52)
            self._font_body = pygame.font.Font(None, 24)
            self._overlay_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            self._overlay_surf.fill((10, 15, 25, 210))

            t_surf = self._font_title.render("JOBSITE PAUSED", True, (240, 200, 60))
            sub_surf = self._font_body.render(
                "Press ESC or P to Resume  |  Press Q to Quit to Menu", True, (220, 230, 240)
            )
            cx = WINDOW_WIDTH // 2
            cy = WINDOW_HEIGHT // 2
            self._overlay_surf.blit(t_surf, t_surf.get_rect(center=(cx, cy - 25)))
            self._overlay_surf.blit(sub_surf, sub_surf.get_rect(center=(cx, cy + 25)))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.scene_manager.pop()
                return True
            if event.key == pygame.K_q:
                self.scene_manager.change(TitleScene(self.scene_manager))
                return True
        return False

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_overlay()
        if self._overlay_surf is not None:
            surface.blit(self._overlay_surf, (0, 0))


# ---------------------------------------------------------------------------
# GameplayScene
# ---------------------------------------------------------------------------


class GameplayScene:
    """Core simulation scene managing level geometry, waves, towers, and combat."""

    def __init__(
        self,
        level_file: str | Path,
        save_data: SaveData,
        scene_manager: SceneManager,
    ) -> None:
        self.level_file = level_file
        self.save_data = save_data
        self.scene_manager = scene_manager

        self.level: LevelData = load_level(level_file)
        self.world = World(level=self.level, save_data=self.save_data)

        # Overtime perk grants 20s wave breather
        cooldown = 20.0 if "overtime" in self.save_data.perks else 15.0
        self.wave_manager = WaveManager(waves=self.level.waves, cooldown_duration=cooldown)

        self.menu = RadialMenu()
        self.menu.configure(self.world)

        self.game_state = GameState.PLAYING
        self.equity_awarded: bool = False

        self._font_hud: pygame.font.Font | None = None
        self._static_layer: pygame.Surface | None = None
        self._game_over_overlay: pygame.Surface | None = None
        self._victory_overlay: pygame.Surface | None = None

        self._prev_budget: int = self.world.economy.project_budget
        self._hud_surfaces: list[pygame.Surface] = []
        self._hud_timer: float = _HUD_REFRESH_INTERVAL

        self._dirty: bool = True
        self._cached_entities: list[Entity] = []

    def _ensure_assets(self) -> None:
        if self._static_layer is None and pygame.font.get_init():
            label_font = pygame.font.Font(None, 16)
            self._font_hud = pygame.font.Font(None, 24)
            banner_font = pygame.font.Font(None, 48)
            sub_font = pygame.font.Font(None, 22)

            self._static_layer = build_static_layer(label_font, self.level)

            self._game_over_overlay = _build_screen_overlay(
                (45, 0, 0, 200),
                "CONTRACT CANCELLED",
                (230, 60, 60),
                "Client ran out of patience! (Press R to restart, ESC for menu)",
                (240, 200, 200),
                banner_font,
                sub_font,
            )

            self._victory_overlay = _build_screen_overlay(
                (0, 35, 0, 200),
                "CONTRACT COMPLETE!",
                (80, 230, 80),
                "Jobsite defended under budget! (Press R to restart, ESC for menu)",
                (200, 240, 200),
                banner_font,
                sub_font,
            )
            self._rebuild_hud(0.0)

    def _reset(self) -> None:
        """Reset match state for restart."""
        self.world = World(level=self.level, save_data=self.save_data)
        cooldown = 20.0 if "overtime" in self.save_data.perks else 15.0
        self.wave_manager = WaveManager(waves=self.level.waves, cooldown_duration=cooldown)
        self.menu = RadialMenu()
        self.menu.configure(self.world)
        self.game_state = GameState.PLAYING
        self.equity_awarded = False
        self._prev_budget = self.world.economy.project_budget
        self._dirty = True
        self._rebuild_hud(0.0)

    def _rebuild_hud(self, fps: float) -> None:
        if self._font_hud is None:
            return
        patience_color = (
            _COLOR_HUD_PATIENCE_LOW
            if self.world.economy.client_patience <= _PATIENCE_LOW_THRESHOLD
            else _COLOR_HUD_PATIENCE_OK
        )
        self._hud_surfaces = [
            self._font_hud.render(f"FPS: {fps:.0f}", True, _COLOR_HUD_TEXT),
            self._font_hud.render(
                f"Budget: ${self.world.economy.project_budget:,}", True, _COLOR_HUD_TEXT
            ),
            self._font_hud.render(
                f"Patience: {self.world.economy.client_patience}", True, patience_color
            ),
        ]

    def _build_entity_list(self) -> list[Entity]:
        if not self._dirty:
            return self._cached_entities
        alive_enemies: list[Entity] = [e for e in self.world.enemies if e.alive]
        alive_projectiles: list[Entity] = [p for p in self.world.projectiles if p.alive]
        towers: list[Entity] = list(self.world.towers.values())
        self._cached_entities = sorted(
            alive_enemies + alive_projectiles + towers + [self.menu, self.wave_manager],
            key=lambda e: e.layer,
        )
        self._dirty = False
        return self._cached_entities

    # ------------------------------------------------------------------
    # Scene Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        self._ensure_assets()
        entities = self._build_entity_list()

        # Clickables receive input only during active play
        if self.game_state == GameState.PLAYING:
            clickables: list[Clickable] = [
                e for e in reversed(entities) if isinstance(e, Clickable)
            ]
            for c in clickables:
                if c.handle_event(event):
                    self._dirty = True
                    return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_state == GameState.PLAYING:
                    self.scene_manager.push(PauseScene(self.scene_manager))
                else:
                    self.scene_manager.change(TitleScene(self.scene_manager, self.save_data))
                return True

            if (
                event.key == pygame.K_r
                and self.game_state in (GameState.GAME_OVER, GameState.VICTORY)
            ):
                self._reset()
                return True

        return False

    def update(self, dt: float) -> None:
        self._ensure_assets()
        if self.game_state != GameState.PLAYING:
            return

        prev_enemies = len(self.world.enemies)
        prev_proj = len(self.world.projectiles)
        prev_towers = len(self.world.towers)

        entities = self._build_entity_list()
        for e in entities:
            e.update(dt, self.world)

        self.world.flush_earnings()

        # Check enemies that escaped or died
        from src.world import GameEvent

        for enemy in self.world.enemies:
            if not enemy.alive:
                if enemy.reached_end:
                    self.world.emit(
                        GameEvent.LEAK, enemy.pos, patience_cost=enemy.patience_cost
                    )
                    self.world.economy.lose_patience(enemy.patience_cost)
                else:
                    self.world.emit(GameEvent.KILL, enemy.pos, bounty=enemy.bounty)

        # In-place cull
        self.world.enemies[:] = [e for e in self.world.enemies if e.alive]
        self.world.projectiles[:] = [p for p in self.world.projectiles if p.alive]

        if (
            len(self.world.enemies) != prev_enemies
            or len(self.world.projectiles) != prev_proj
            or len(self.world.towers) != prev_towers
        ):
            self._dirty = True

        self.world.refresh_auras()

        # Drain frame events from the world event bus
        self.world.drain_events()

        # Check win/loss triggers
        if self.world.economy.game_over:
            self.game_state = GameState.GAME_OVER
        elif self.wave_manager.state == WaveState.VICTORY and not self.world.enemies:
            self.game_state = GameState.VICTORY
            if not self.equity_awarded:
                self.save_data.equity += self.world.economy.client_patience
                self.save_data.save()
                self.equity_awarded = True

        # HUD Refresh check
        self._hud_timer -= dt
        budget_changed = self.world.economy.project_budget != self._prev_budget
        if self._hud_timer <= 0.0 or budget_changed:
            self._hud_timer = _HUD_REFRESH_INTERVAL
            self._prev_budget = self.world.economy.project_budget
            self._rebuild_hud(self.scene_manager.fps)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_assets()
        if self._static_layer is not None:
            surface.blit(self._static_layer, (0, 0))

        entities = self._build_entity_list()
        for e in entities:
            e.draw(surface)

        # Draw HUD items
        hud_x = 10
        for s in self._hud_surfaces:
            surface.blit(s, (hud_x, 6))
            hud_x += s.get_width() + 15

        if self.game_state == GameState.GAME_OVER and self._game_over_overlay is not None:
            surface.blit(self._game_over_overlay, (0, 0))
        elif self.game_state == GameState.VICTORY and self._victory_overlay is not None:
            surface.blit(self._victory_overlay, (0, 0))
