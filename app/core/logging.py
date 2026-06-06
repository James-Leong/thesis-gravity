from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from app.core.config import settings


def setup_logging() -> None:
    log_dir = Path(settings.base_dir) / "logs"
    log_dir.mkdir(exist_ok=True)

    root_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(root_level)

    for h in root.handlers[:]:
        root.removeHandler(h)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(root_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if settings.log_to_console:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(root_level)
        console.setFormatter(formatter)
        root.addHandler(console)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True

    for name in ("httpx", "python_multipart", "httpcore", "hpack"):
        logging.getLogger(name).setLevel(logging.WARNING)

    llm_handler = logging.handlers.RotatingFileHandler(
        log_dir / "llm.log",
        maxBytes=50 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    llm_handler.setLevel(logging.DEBUG)
    llm_handler.setFormatter(formatter)

    llm_metrics_logger = logging.getLogger("app.llm_metrics")
    llm_metrics_logger.setLevel(logging.INFO)
    llm_metrics_logger.handlers.clear()
    llm_metrics_logger.addHandler(llm_handler)
    llm_metrics_logger.propagate = True

    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.DEBUG)
    openai_logger.handlers.clear()
    openai_logger.addHandler(llm_handler)
    openai_logger.propagate = False
