from __future__ import annotations

from datetime import datetime
from pathlib import Path


class RunLogger:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = self.base_dir / f"run_{timestamp}.log"

    def write(self, line: str) -> None:
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
