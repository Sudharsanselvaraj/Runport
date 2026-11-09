"""Official brand banners, emblems, and visual constants for the Runport terminal UI."""

from __future__ import annotations

from typing import List

from runport import __version__
from runport.tui.logo import (
    OFFICIAL_EMBLEM_LINES,
    TerminalImage,
    detect_image_protocol,
    encode_iterm2,
    encode_kitty,
    get_logo_bytes,
    get_logo_path,
    is_logo_available,
    render_official_logo,
    render_solid_emblem,
)
from runport.tui.theme import ACCENT_LAVENDER

APP_TITLE = "[bold bright_white]RUNPORT[/bold bright_white]"
APP_VERSION = f"[dim]v{__version__}[/dim]"
APP_SUBTITLE = "[dim]The universal open-source LLM, prompt, and workflow benchmarking platform.[/dim]"
CLI_WORDMARK = f"[bold {ACCENT_LAVENDER}]RUNPORT CLI[/bold {ACCENT_LAVENDER}]"

# Deprecated: ASCII/Braille logo approximations have been removed.
RUNPORT_EMBLEM_LINES: List[str] = []
RUNPORT_EMBLEM_SOLID_LINES: List[str] = []
RUNPORT_EMBLEM: str = ""
RUNPORT_EMBLEM_SOLID: str = ""

__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "APP_SUBTITLE",
    "CLI_WORDMARK",
    "OFFICIAL_EMBLEM_LINES",
    "RUNPORT_EMBLEM",
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
    "render_solid_emblem",
]
