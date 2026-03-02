from __future__ import annotations

import logging
import os
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)
from rich.traceback import install

# Shared console for the whole project
console = Console()


def setup_rich_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure Rich-based logging + pretty tracebacks.

    Call once at startup (run.py).
    """
    lvl = (level or os.getenv("THOTHMIND_LOG_LEVEL") or "INFO").upper()

    install(console=console, show_locals=False, width=120)

    logging.basicConfig(
        level=lvl,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                show_time=True,
                show_level=True,
                show_path=False,
            )
        ],
    )

    log = logging.getLogger("thothmind")
    log.setLevel(lvl)
    return log


def make_progress() -> Progress:
    """
    Standard project progress bar style.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}[/bold]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )