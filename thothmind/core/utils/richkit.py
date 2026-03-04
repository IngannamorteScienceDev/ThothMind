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


def _parse_force_terminal() -> Optional[bool]:
    """Optional override for Rich terminal detection.

    PowerShell/Windows occasionally mis-detects terminal capabilities.
    Set RICH_FORCE_TERMINAL=1 to force in-place rendering.
    """
    v = os.getenv("RICH_FORCE_TERMINAL")
    if v is None or v == "":
        return None
    v = v.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return None


# Shared console for the whole project (single source of truth)
console = Console(force_terminal=_parse_force_terminal())


def setup_rich_logging(level: Optional[str] = None) -> logging.Logger:
    """Configure Rich-based logging + pretty tracebacks.

    Call once at startup (run.py).
    """
    lvl = (level or os.getenv("THOTHMIND_LOG_LEVEL") or "INFO").upper()

    # Pretty tracebacks (kept stable by using the shared console)
    install(console=console, show_locals=False, width=120)

    # NOTE: use the *same* console instance as Progress to avoid competing live renders.
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
    """Standard project progress bar style."""
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
