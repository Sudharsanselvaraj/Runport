"""ASCII banners, emblems, and visual constants for the workbench terminal UI."""

from runport.tui.logo_ascii import (
    RUNPORT_EMBLEM,
    RUNPORT_EMBLEM_LINES,
    RUNPORT_EMBLEM_SOLID,
    RUNPORT_EMBLEM_SOLID_LINES,
)

APP_TITLE = "[bold bright_white]RUNPORT[/bold bright_white]"
APP_VERSION = "[dim]v0.1.0[/dim]"
APP_SUBTITLE = "[dim]The universal open-source LLM, prompt, and workflow benchmarking platform.[/dim]"

__all__ = [
    "RUNPORT_EMBLEM",
    "RUNPORT_EMBLEM_LINES",
    "RUNPORT_EMBLEM_SOLID",
    "RUNPORT_EMBLEM_SOLID_LINES",
    "APP_TITLE",
    "APP_VERSION",
    "APP_SUBTITLE",
]
