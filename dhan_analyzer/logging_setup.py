from __future__ import annotations

import logging

from dhan_analyzer.config import Settings


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(settings.log_dir / "dhan_analyzer.log")],
    )
