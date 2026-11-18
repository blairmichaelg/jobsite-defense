"""Tests for src/save.py — atomic persistence, meta-progression, and perk storage.

SDL dummy drivers are configured in conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.save import SaveData


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
