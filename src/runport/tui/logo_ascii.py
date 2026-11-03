"""Official Runport hexagonal terminal art constants.

Generated from the official brand logo assets/runport-logo-white.png.
Regenerate with scripts/make_ascii_logo.py.
"""

from typing import List

RUNPORT_EMBLEM_LINES: List[str] = [
    "      ⣴⣾⣿⣿⡟⢁⣴⣿⣿⣿⣿⣿⣿⣿⣷⣤⡀     ",
    "    ⢀⣾⣿⣿⣿⠏⢠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀    ",
    "   ⢠⣾⣿⣿⣿⠋⣰⣿⣿⣿⡟⠁⢠⣤⣤⣤⣤⣤⣤⣤⣤⡀   ",
    "  ⣠⣿⣿⣿⡿⠃⣴⣿⣿⣿⠏  ⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆  ",
    " ⣴⣿⣿⣿⡿⢁⣼⣿⣿⣿⠋   ⠸⠿⠿⠿⠿⠿⠿⢿⣿⣿⣿⣦ ",
    "⣼⣿⣿⣿⡟⢀⣾⣿⣿⡿⠃        ⣴⣶⣶⣄⠹⣿⣿⣿⣧",
    "⢿⣿⣿⣿⣆⠘⠿⠿⠟⠁       ⢀⣾⣿⣿⣿⠏⣠⣿⣿⣿⡿",
    "⠈⢿⣿⣿⣿⣷⣶⣶⣶⣶⣶⣶⣦   ⢠⣿⣿⣿⣿⠃⣰⣿⣿⣿⡿⠁",
    "  ⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿  ⣰⣿⣿⣿⡿⢁⣼⣿⣿⣿⠟  ",
    "   ⠙⠻⠿⠿⠿⠿⠿⠿⠿⠟ ⣼⣿⣿⣿⡟⢀⣾⣿⣿⣿⠋   ",
    "     ⢶⣶⣶⣶⣶⣶⣶⣶⣿⣿⣿⣿⠏⢠⣿⣿⣿⡿⠃    ",
    "     ⠈⠻⢿⣿⣿⣿⣿⣿⣿⣿⡿⠋⣰⣿⣿⡿⠟⠁     ",
]

RUNPORT_EMBLEM_SOLID_LINES: List[str] = [
    "      ▄████ ▄████████▄      ",
    "     ████▀ ████████████     ",
    "   ▄████▀▄████  ▄▄▄▄▄▄▄▄    ",
    "  ▄████ ▄███▀   █████████▄  ",
    " ▄████ ████▀    ██████████▄ ",
    "████▀ ████         ▄▄▄▄▀████",
    "████▄▀██▀         ████▀▄████",
    " █████▄▄▄▄▄▄▄   ▄████▀▄████ ",
    "  ▀██████████  ▄████ ▄███▀  ",
    "   ▀▀▀▀▀▀▀▀▀▀ ▄███▀ ████▀   ",
    "     ████████████▀▄████▀    ",
    "      ▀█████████▀▄███▀      ",
]

RUNPORT_EMBLEM: str = "\n".join(RUNPORT_EMBLEM_LINES)
RUNPORT_EMBLEM_SOLID: str = "\n".join(RUNPORT_EMBLEM_SOLID_LINES)
