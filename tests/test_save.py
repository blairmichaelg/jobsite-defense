"""Tests for src/save.py — atomic persistence, meta-progression, and perk storage.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pygame
import pytest

from src.save import SaveData, get_save_path
from src.scene import SceneManager
from src.talent_ui import TalentTreeScene


class TestSaveDataPersistence:
    """Validate SaveData atomic saving and error-resilient loading."""

    def test_default_save_data(self) -> None:
        """Fresh SaveData has 0 equity and empty perks set."""
        save = SaveData()
        assert save.equity == 0
        assert save.perks == set()

    def test_atomic_save_creates_tmp_then_replaces(self, tmp_path: Path) -> None:
        """SaveData.save writes to .tmp first and replaces atomically."""
        dest = tmp_path / "save_data.json"
        save = SaveData(equity=350, perks={"better_ammo", "union_dues"})
        save.save(dest)

        assert dest.is_file()
        assert not (tmp_path / "save_data.json.tmp").exists()

        content = json.loads(dest.read_text(encoding="utf-8"))
        assert content["equity"] == 350
        assert sorted(content["perks"]) == ["better_ammo", "union_dues"]

    def test_load_existing_valid_file(self, tmp_path: Path) -> None:
        """SaveData.load correctly parses a well-formed JSON file."""
        dest = tmp_path / "custom_save.json"
        payload = {"equity": 500, "perks": ["overtime"]}
        dest.write_text(json.dumps(payload), encoding="utf-8")

        loaded = SaveData.load(dest)
        assert loaded.equity == 500
        assert loaded.perks == {"overtime"}

    def test_load_nonexistent_file_returns_default(self, tmp_path: Path) -> None:
        """Loading a missing file gracefully returns fresh default SaveData."""
        loaded = SaveData.load(tmp_path / "missing.json")
        assert loaded.equity == 0
        assert loaded.perks == set()

    def test_load_corrupted_file_returns_default(self, tmp_path: Path) -> None:
        """Loading a corrupted or non-JSON file returns fresh default SaveData."""
        dest = tmp_path / "corrupted.json"
        dest.write_text("invalid json content {{{", encoding="utf-8")

        loaded = SaveData.load(dest)
        assert loaded.equity == 0
        assert loaded.perks == set()

    def test_save_permission_error_retries_and_succeeds(self, tmp_path: Path) -> None:
        """SaveData.save retries on Windows PermissionError file locking."""
        dest = tmp_path / "save_retry.json"
        save = SaveData(equity=100)

        attempts = 0
        original_replace = os.replace

        def mock_replace(src: Path | str, dst: Path | str) -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise PermissionError("File locked by external process")
            original_replace(src, dst)

        with patch("os.replace", side_effect=mock_replace):
            save.save(dest)

        assert attempts == 3
        assert dest.is_file()

    def test_save_permission_error_exhaustion_raises(self, tmp_path: Path) -> None:
        """SaveData.save raises PermissionError after 5 failed attempts."""
        dest = tmp_path / "save_fail.json"
        save = SaveData(equity=100)

        with (
            patch("os.replace", side_effect=PermissionError("Locked")),
            pytest.raises(PermissionError),
        ):
            save.save(dest)

    def test_talent_tree_rollback_on_save_failure(self) -> None:
        """TalentTreeScene rolls back in-memory equity and perks if save raises."""
        save = SaveData(equity=300, perks=set())
        sm = SceneManager()
        scene = TalentTreeScene(sm, save_data=save)
        scene._ensure_fonts()

        # Mock save to raise PermissionError
        save.save = MagicMock(side_effect=PermissionError("Locked"))  # type: ignore[method-assign]

        # First perk is Union Dues ($100)
        card_rect = scene._perk_rects[0][1]
        click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=card_rect.center
        )

        consumed = scene.handle_event(click_event)
        assert consumed is True

        # State rolled back!
        assert save.equity == 300
        assert "union_dues" not in save.perks

    def test_get_save_path_resolution(self) -> None:
        """get_save_path uses APPDATA on Windows and .local/share on POSIX."""
        with patch.dict(os.environ, {"APPDATA": "C:\\MockAppData"}):
            p = get_save_path()
            assert "MockAppData" in str(p)
            assert "JobsiteDefense" in str(p)

        with patch.dict(os.environ, {"USERPROFILE": "C:\\Users\\MockUser"}, clear=True):
            p = get_save_path()
            assert ".local" in str(p) or "share" in str(p)
            assert "JobsiteDefense" in str(p)
