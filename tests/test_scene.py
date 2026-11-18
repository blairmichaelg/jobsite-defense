"""Tests for src/scene.py & src/talent_ui.py — SceneManager stack, transitions, and overlays.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from src.save import SaveData
from src.scene import (
    GameplayScene,
    GameState,
    LevelSelectScene,
    PauseScene,
    SceneManager,
    TitleScene,
)
from src.talent_ui import TalentTreeScene


class TestSceneManagerStack:
    """Validate stack operations on SceneManager."""

    def test_push_pop_and_change(self) -> None:
        """SceneManager pushes, pops, and changes top scenes."""
        sm = SceneManager()
        assert sm.current is None

        title = TitleScene(sm)
        sm.change(title)
        assert sm.current is title

        pause = PauseScene(sm)
        sm.push(pause)
        assert sm.current is pause

        popped = sm.pop()
        assert popped is pause
        assert sm.current is title

    def test_draw_renders_stack_in_order(self) -> None:
        """SceneManager.draw renders scenes in order onto target surface."""
        sm = SceneManager()
        title = TitleScene(sm)
        sm.push(title)

        surf = pygame.Surface((400, 300))
        # Must not raise
        sm.draw(surf)


class TestSceneTransitions:
    """Validate user input transitions between Title, Pause, and Gameplay."""

    def test_title_enter_transitions_to_gameplay(self) -> None:
        """Pressing ENTER on TitleScene switches to GameplayScene."""
        sm = SceneManager()
        title = TitleScene(sm)
        sm.change(title)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert isinstance(sm.current, GameplayScene)

    def test_title_t_pushes_talent_tree(self) -> None:
        """Pressing T on TitleScene pushes TalentTreeScene."""
        sm = SceneManager()
        title = TitleScene(sm)
        sm.change(title)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert isinstance(sm.current, TalentTreeScene)

    def test_title_l_pushes_level_select(self) -> None:
        """Pressing L on TitleScene pushes LevelSelectScene."""
        sm = SceneManager()
        title = TitleScene(sm)
        sm.change(title)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert isinstance(sm.current, LevelSelectScene)

    def test_gameplay_esc_pushes_pause_scene_during_active_play(self) -> None:
        """Pressing ESC during active play pushes PauseScene modal overlay."""
        sm = SceneManager()
        save = SaveData()
        gameplay = GameplayScene("level_1.json", save, sm)
        sm.change(gameplay)

        assert sm.current is gameplay
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert isinstance(sm.current, PauseScene)

    def test_pause_scene_resumes_on_esc(self) -> None:
        """Pressing ESC or P in PauseScene pops overlay and resumes gameplay."""
        sm = SceneManager()
        save = SaveData()
        gameplay = GameplayScene("level_1.json", save, sm)
        sm.change(gameplay)

        sm.push(PauseScene(sm))
        top_scene = sm.current
        assert isinstance(top_scene, PauseScene)

        # Press ESC to resume
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert sm.current is gameplay

    def test_pause_scene_q_quits_to_title(self) -> None:
        """Pressing Q in PauseScene switches back to TitleScene."""
        sm = SceneManager()
        save = SaveData()
        gameplay = GameplayScene("level_1.json", save, sm)
        sm.change(gameplay)

        sm.push(PauseScene(sm))
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert isinstance(sm.current, TitleScene)


class TestGameplayStateAndEquity:
    """Validate gameplay victory equity rewards and R key restart gating."""

    def test_r_restart_only_works_on_game_over_or_victory(self) -> None:
        """Pressing R does nothing during PLAYING; restarts during GAME_OVER."""
        sm = SceneManager()
        save = SaveData()
        gameplay = GameplayScene("level_1.json", save, sm)
        sm.change(gameplay)

        # During active PLAYING -> ignored
        assert gameplay.game_state == GameState.PLAYING
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        assert gameplay.handle_event(event) is False

        # In GAME_OVER -> resets to PLAYING
        gameplay.game_state = GameState.GAME_OVER
        assert gameplay.handle_event(event) is True
        assert gameplay.game_state == GameState.PLAYING

    def test_victory_awards_equity_and_saves_exactly_once(
        self, tmp_path: Path
    ) -> None:
        """Reaching VICTORY awards client patience as equity and writes to disk."""
        save_file = tmp_path / "test_equity_save.json"
        save = SaveData(equity=50)
        save.save(save_file)

        sm = SceneManager()
        gameplay = GameplayScene("level_1.json", save, sm)
        gameplay.world.economy.client_patience = 85

        # Trigger victory condition: wave manager VICTORY and no alive enemies
        from src.wave import WaveState

        gameplay.wave_manager.state = WaveState.VICTORY
        gameplay.world.enemies = []

        # First update awards equity
        gameplay.update(0.01)
        assert gameplay.game_state == GameState.VICTORY
        assert gameplay.equity_awarded is True
        assert save.equity == 50 + 85

        # Second update does NOT award equity again
        gameplay.update(0.01)
        assert save.equity == 135


class TestTalentTreeScene:
    """Validate TalentTreeScene perk purchasing and affordability checks."""

    def test_cannot_purchase_unaffordable_perk(self, tmp_path: Path) -> None:
        """Clicking an unaffordable perk does not deduct equity or grant perk."""
        save_file = tmp_path / "save.json"
        save = SaveData(equity=50)
        save.save(save_file)

        sm = SceneManager()
        scene = TalentTreeScene(sm, save)
        scene._ensure_fonts()

        # Click Heavy Duty Nails (costs 250 Eq, player only has 50)
        perk_opt, rect = next(
            (opt, r) for opt, r in scene._perk_rects if opt.perk_id == "better_ammo"
        )
        click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center
        )
        consumed = scene.handle_event(click_event)

        assert consumed is True
        assert "better_ammo" not in save.perks
        assert save.equity == 50

    def test_purchase_affordable_perk_deducts_and_saves(self, tmp_path: Path) -> None:
        """Clicking an affordable perk deducts equity, unlocks perk, and saves."""
        save_file = tmp_path / "save.json"
        save = SaveData(equity=200)
        save.save(save_file)

        sm = SceneManager()
        scene = TalentTreeScene(sm, save)
        scene._ensure_fonts()

        # Click Union Dues (costs 100 Eq)
        perk_opt, rect = next(
            (opt, r) for opt, r in scene._perk_rects if opt.perk_id == "union_dues"
        )
        click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center
        )
        consumed = scene.handle_event(click_event)

        assert consumed is True
        assert "union_dues" in save.perks
        assert save.equity == 100

    def test_talent_tree_esc_pops_scene(self) -> None:
        """Pressing ESC in TalentTreeScene pops it from the stack."""
        sm = SceneManager()
        sm.push(TitleScene(sm))
        scene = TalentTreeScene(sm)
        sm.push(scene)

        assert sm.current is scene
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        consumed = sm.handle_event(event)

        assert consumed is True
        assert isinstance(sm.current, TitleScene)
