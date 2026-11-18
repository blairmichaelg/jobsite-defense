"""Jobsite Defense — meta-progression and persistent save state.

Tracks equity earned from completed contracts (remaining client patience)
and unlocked talent tree perks.  Writes atomically via temporary files
to eliminate corruption risks.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SAVE_FILE = Path("save_data.json")


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
            filepath: Destination file path (defaults to ``save_data.json``).
        """
        target = Path(filepath) if filepath is not None else DEFAULT_SAVE_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(f"{target.suffix}.tmp")

        payload = {
            "equity": self.equity,
            "perks": sorted(self.perks),
        }

        tmp_target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_target, target)

    @classmethod
    def load(cls, filepath: str | Path | None = None) -> SaveData:
        """Load persistent save state from disk, returning defaults on any failure.

        Args:
            filepath: Source file path (defaults to ``save_data.json``).

        Returns:
            Populated ``SaveData`` container.
        """
        target = Path(filepath) if filepath is not None else DEFAULT_SAVE_FILE
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
