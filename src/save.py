"""Jobsite Defense — meta-progression and persistent save state.

Tracks equity earned from completed contracts (remaining client patience)
and unlocked talent tree perks. Writes atomically to temporary files with
OS buffer flushing and retry logic to prevent Windows file-locking corruption.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


def get_save_path() -> Path:
    """Return platform-appropriate persistent save data path."""
    if "APPDATA" in os.environ:
        base = Path(os.environ["APPDATA"]) / "JobsiteDefense"
    else:
        base = Path.home() / ".local" / "share" / "JobsiteDefense"
    return base / "save_data.json"


@dataclass
class SaveData:
    """Persistent player progression and perks.

    Attributes:
        equity: Spendable meta-currency awarded upon victory.
        perks: Set of unlocked perk identifier strings.
    """

    equity: int = 0
    perks: set[str] = field(default_factory=set)

    def save(self, filepath: str | Path | None = None) -> None:
        """Atomically persist save state to disk using a temporary file.

        Args:
            filepath: Destination file path (defaults to platform user data directory).
        """
        target = Path(filepath) if filepath is not None else get_save_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(f"{target.suffix}.tmp")

        payload = {
            "equity": self.equity,
            "perks": sorted(self.perks),
        }

        with open(tmp_target, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2))
            f.flush()
            os.fsync(f.fileno())

        for attempt in range(5):
            try:
                os.replace(tmp_target, target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))

    @classmethod
    def load(cls, filepath: str | Path | None = None) -> SaveData:
        """Load persistent save state from disk, returning defaults on any failure.

        Args:
            filepath: Source file path (defaults to platform user data directory).

        Returns:
            Populated ``SaveData`` container.
        """
        target = Path(filepath) if filepath is not None else get_save_path()
        if not target.is_file():
            return cls()

        try:
            content = target.read_text(encoding="utf-8")
            data = json.loads(content)
            equity = int(data.get("equity", 0))
            perks = set(data.get("perks", []))
            return cls(equity=equity, perks=perks)
        except Exception:
            return cls()
