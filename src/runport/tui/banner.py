"""Official brand banners, emblems, and visual constants for the Runport terminal UI."""

from __future__ import annotations

from typing import List

from runport import __version__
from runport.tui.logo import (
    TerminalImage,
    detect_image_protocol,
    encode_iterm2,
    encode_kitty,
    get_logo_bytes,
    get_logo_path,
    is_logo_available,
    render_official_logo,
)
from runport.tui.logo_ascii import (
    RUNPORT_EMBLEM,
    RUNPORT_EMBLEM_LARGE,
    RUNPORT_EMBLEM_LARGE_LINES,
    RUNPORT_EMBLEM_LINES,
    RUNPORT_EMBLEM_SOLID,
    RUNPORT_EMBLEM_SOLID_LINES,
)
from runport.tui.theme import ACCENT_LAVENDER

APP_TITLE = "[bold bright_white]RUNPORT[/bold bright_white]"
APP_VERSION = f"[dim]v{__version__}[/dim]"
APP_SUBTITLE = "[dim]The universal open-source LLM, prompt, and workflow benchmarking platform.[/dim]"
CLI_WORDMARK = f"[bold {ACCENT_LAVENDER}]RUNPORT CLI[/bold {ACCENT_LAVENDER}]"

__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "APP_SUBTITLE",
    "CLI_WORDMARK",
    "RUNPORT_EMBLEM",
    "RUNPORT_EMBLEM_LARGE",
    "RUNPORT_EMBLEM_LARGE_LINES",
    "RUNPORT_EMBLEM_LINES",
    "RUNPORT_EMBLEM_SOLID",
    "RUNPORT_EMBLEM_SOLID_LINES",
    "TerminalImage",
    "detect_image_protocol",
    "encode_iterm2",
    "encode_kitty",
    "get_logo_bytes",
    "get_logo_path",
    "is_logo_available",
    "render_official_logo",
]
