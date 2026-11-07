"""Official Runport hexagonal terminal art and typography constants.

Generated from the official brand logo assets/runport-logo-white.png.
Includes high-resolution Braille emblem, solid half-block variant, and
monospaced typography wordmarks.
"""

from typing import List

# 1. Refined Compact Braille Hexagonal Emblem (8 lines x 20 chars, reduced ~38% from original)
RUNPORT_EMBLEM_LINES: List[str] = [
    "    ⣠⣶⡿⢁⣴⣿⣿⣶⣤⡀      ",
    "   ⣰⣿⣿⠃⣼⣿⣿⠋⠉⢻⣷⡄     ",
    "  ⣼⣿⣿⠃⣰⣿⣿⠃   ⢸⣿⣷    ",
    " ⣾⣿⣿⡏ ⢻⣿⣿⠁    ⣼⣿⣿⡇  ",
    " ⢿⣿⣿⣇ ⠈⠿⠿    ⣰⣿⣿⡿   ",
    "  ⠻⣿⣿⣶⣶⣶⣶⡄  ⣼⣿⣿⠟    ",
    "   ⠉⠛⠿⠿⣿⣿⠃ ⣼⣿⣿⠋     ",
    "     ⠶⣶⣶⣿⣿⣾⣿⡿⠁      ",
]

# 2. Refined Solid Half-Block Hexagonal Emblem (8 lines x 20 chars, reduced ~38% from original)
RUNPORT_EMBLEM_SOLID_LINES: List[str] = [
    "    ▄███ ▄██████▄   ",
    "   ███▀ ██▀▀▀▀███▄  ",
    "  ▄███ ▄██   ▄▄███  ",
    " ▄███ ▄██▀    ▀████ ",
    " ████ ▀██▄    ▄████ ",
    "  ▀████▄▄▄▄   ▄████ ",
    "   ▀▀▀▀▀███ ▄████▀  ",
    "    ██████▀▄████▀   ",
]

# Full 12-line variants (preserved for reference)
RUNPORT_EMBLEM_FULL_LINES: List[str] = [
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

RUNPORT_EMBLEM_SOLID_FULL_LINES: List[str] = [
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

# 3. Compact Monospaced Wordmarks
RUNPORT_BLOCK_WORDMARK: List[str] = [
    "█▀▄ █ █ █▄ █ █▀█ █▀█ █▀▄ ▀█▀",
    "█▀▄ █▄█ █ ▀█ █▀▀ █▄█ █▀▄  █ ",
]

RUNPORT_DOT_MATRIX_LINES: List[str] = [
    "●━● ┃ ┃ ┃━┫ ●━● ●━● ●━● ━┳━",
    "●━┛ ┗━┛ ┛ ┗ ┛   ┗━┛ ┛ ┗  ┻ ",
]

RUNPORT_EMBLEM: str = "\n".join(RUNPORT_EMBLEM_LINES)
RUNPORT_EMBLEM_SOLID: str = "\n".join(RUNPORT_EMBLEM_SOLID_LINES)
RUNPORT_BLOCK: str = "\n".join(RUNPORT_BLOCK_WORDMARK)
RUNPORT_DOT_MATRIX: str = "\n".join(RUNPORT_DOT_MATRIX_LINES)
