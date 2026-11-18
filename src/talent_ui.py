"""Jobsite Defense — talent tree scene and meta-progression store.

Allows players to spend Equity earned from contract completions on persistent
perks (Union Dues, Heavy Duty Nails, Overtime).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from src.save import SaveData
from src.settings import WINDOW_HEIGHT, WINDOW_WIDTH

if TYPE_CHECKING:
    from src.scene import SceneManager


@dataclass(frozen=True)
class PerkOption:
    """Specification for an unlockable talent perk."""

    perk_id: str
    name: str
    cost: int
    description: str


PERK_OPTIONS: list[PerkOption] = [
    PerkOption(
        perk_id="union_dues",
        name="Union Dues",
        cost=100,
        description="+$250 Starting Project Budget",
    ),
    PerkOption(
        perk_id="better_ammo",
        name="Heavy Duty Nails",
        cost=250,
        description="Nail Gunner Base Damage +5",
    ),
    PerkOption(
        perk_id="overtime",
        name="Overtime",
        cost=150,
        description="Wave Cooldowns Extended to 20s",
    ),
]


class TalentTreeScene:
    """Scene allowing players to view and unlock persistent talent tree perks."""

    def __init__(
        self,
        scene_manager: SceneManager,
        save_data: SaveData | None = None,
    ) -> None:
        self.scene_manager = scene_manager
        self.save_data = save_data if save_data is not None else SaveData.load()

        self._font_title: pygame.font.Font | None = None
        self._font_header: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None

        # Button bounding rects initialized in _ensure_fonts()
        self._perk_rects: list[tuple[PerkOption, pygame.Rect]] = []
        self._back_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 65, 200, 40
        )

    def _ensure_fonts(self) -> None:
        if self._font_title is None and pygame.font.get_init():
            self._font_title = pygame.font.Font(None, 42)
            self._font_header = pygame.font.Font(None, 26)
            self._font_body = pygame.font.Font(None, 20)

            # Precalculate 3 horizontal card rects
            card_w = 460
            card_h = 75
            start_y = 150
            spacing = 90
            self._perk_rects = [
                (
                    opt,
                    pygame.Rect(
                        (WINDOW_WIDTH - card_w) // 2,
                        start_y + i * spacing,
                        card_w,
                        card_h,
                    ),
                )
                for i, opt in enumerate(PERK_OPTIONS)
            ]

    # ------------------------------------------------------------------
    # Scene Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle mouse clicks for purchasing perks and returning."""
        self._ensure_fonts()

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.scene_manager.pop()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # Back button
            if self._back_rect.collidepoint(mx, my):
                self.scene_manager.pop()
                return True

            # Perk cards
            for opt, rect in self._perk_rects:
                if rect.collidepoint(mx, my):
                    if (
                        opt.perk_id not in self.save_data.perks
                        and self.save_data.equity >= opt.cost
                    ):
                        self.save_data.equity -= opt.cost
                        self.save_data.perks.add(opt.perk_id)
                        self.save_data.save()
                    return True

        return False

    def update(self, dt: float) -> None:
        """Talent tree has no continuous simulation logic."""

    def draw(self, surface: pygame.Surface) -> None:
        """Render the talent tree cards, equity counter, and back button."""
        self._ensure_fonts()
        if self._font_title is None or self._font_header is None or self._font_body is None:
            return

        # Background fill
        surface.fill((22, 28, 38))

        # Title
        title_surf = self._font_title.render("UNION HALL — TALENT TREE", True, (245, 200, 70))
        surface.blit(title_surf, title_surf.get_rect(center=(WINDOW_WIDTH // 2, 50)))

        # Available Equity
        equity_surf = self._font_header.render(
            f"Available Equity: {self.save_data.equity} Eq", True, (130, 220, 130)
        )
        surface.blit(equity_surf, equity_surf.get_rect(center=(WINDOW_WIDTH // 2, 95)))

        mouse_pos = pygame.mouse.get_pos()

        # Render each perk card
        for opt, rect in self._perk_rects:
            owned = opt.perk_id in self.save_data.perks
            can_afford = self.save_data.equity >= opt.cost
            hovered = rect.collidepoint(mouse_pos)

            if owned:
                bg_color = (30, 55, 35)
                border_color = (80, 210, 80)
                status_text = "PURCHASED"
                status_color = (120, 240, 120)
            elif can_afford:
                bg_color = (45, 55, 75) if hovered else (35, 42, 60)
                border_color = (100, 180, 255)
                status_text = f"UNLOCK ({opt.cost} Eq)"
                status_color = (255, 215, 80)
            else:
                bg_color = (28, 30, 36)
                border_color = (80, 80, 85)
                status_text = f"NEED {opt.cost} Eq"
                status_color = (180, 100, 100)

            pygame.draw.rect(surface, bg_color, rect, border_radius=6)
            pygame.draw.rect(surface, border_color, rect, width=2, border_radius=6)

            # Name
            name_surf = self._font_header.render(opt.name, True, (240, 240, 240))
            surface.blit(name_surf, (rect.x + 16, rect.y + 12))

            # Description
            desc_surf = self._font_body.render(opt.description, True, (180, 190, 205))
            surface.blit(desc_surf, (rect.x + 16, rect.y + 42))

            # Status pill
            pill_surf = self._font_header.render(status_text, True, status_color)
            surface.blit(
                pill_surf, pill_surf.get_rect(midright=(rect.right - 16, rect.centery))
            )

        # Back Button
        back_hovered = self._back_rect.collidepoint(mouse_pos)
        back_bg = (50, 60, 80) if back_hovered else (35, 42, 55)
        pygame.draw.rect(surface, back_bg, self._back_rect, border_radius=4)
        pygame.draw.rect(surface, (140, 150, 170), self._back_rect, width=1, border_radius=4)
        back_surf = self._font_body.render("BACK TO MENU", True, (230, 230, 230))
        surface.blit(back_surf, back_surf.get_rect(center=self._back_rect.center))
