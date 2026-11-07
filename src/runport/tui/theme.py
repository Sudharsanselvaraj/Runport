"""Visual design system, color palette, and styling constants for Runport TUI.

Design Characteristics:
- Deep navy / near-black terminal background (#0d1117)
- Muted lavender primary accent (#c084fc)
- Restrained cyan secondary accent (#38bdf8)
- Muted green for successful states (#4ade80)
- Cool grey for secondary information (#94a3b8, #64748b)
- Minimal borders, monospace typography, and deliberate alignment
- Zero excessive emojis or unnecessary gradients
"""

from typing import List, Optional, Tuple
from rich.style import Style

# Almost-black terminal background per OpenSRE visual reference
BG_DARK = "#111111"  # Almost-black canvas
PANEL_BG = "#161616"  # Subtle elevated dark container background
PANEL_BG_SECONDARY = "#1c1c1c"  # Elevated container background
BORDER_CHARCOAL = "#282828"  # Refined minimal dark border
BORDER_FOCUSED = "#C5A6E8"  # Muted lavender border for active focused panel
BORDER_MUTED = "#222222"  # Subtle divider border
BORDER_TEAL = BORDER_CHARCOAL  # Backwards compatibility alias

# Accents - Single-colour muted lavender branding
ACCENT_LAVENDER = "#C5A6E8"  # Primary muted lavender
ACCENT_LAVENDER_LIGHT = "#E2D3F5"  # Soft light lavender highlight
ACCENT_CYAN = "#C5A6E8"  # Replaced bright cyan with restrained lavender per spec
CYAN_HIGHLIGHT = "#C5A6E8"  # Lavender highlight alias

# Typography colors - Clean white and grey typography
TEXT_PRIMARY = "#E5E5E5"  # Clean white / light grey primary text
TEXT_SECONDARY = "#858585"  # Balanced secondary grey
TEXT_MUTED = "#555555"  # Muted grey for metadata and secondary hints
TEXT_BRIGHT = "#FFFFFF"  # Crisp white highlights

# Clean Status Colors (Used only where meaningful)
COLOR_SUCCESS = "#75B88A"  # Soft green check
COLOR_WARNING = "#D9B45B"  # Muted amber warning
COLOR_ERROR = "#D97979"  # Soft red error
COLOR_INFO = "#C5A6E8"  # Elegant lavender info

# Rich Style Objects
STYLE_TITLE = Style(color=ACCENT_LAVENDER, bold=True)
STYLE_MUTED = Style(color=TEXT_MUTED)
STYLE_SECONDARY = Style(color=TEXT_SECONDARY)
STYLE_SUCCESS = Style(color=COLOR_SUCCESS, bold=True)
STYLE_WARNING = Style(color=COLOR_WARNING, bold=True)
STYLE_ERROR = Style(color=COLOR_ERROR, bold=True)
STYLE_CYAN = Style(color=ACCENT_LAVENDER, bold=True)
STYLE_PANEL = Style(color=TEXT_PRIMARY, bgcolor=PANEL_BG)

# Refined Selection Highlights - Restrained dark purple background
SELECTION_BG = "#261933"  # Restrained dark purple
STYLE_ROW_SELECTED = Style(color="#FFFFFF", bgcolor="#261933", bold=True)
STYLE_ROW_HOVER = Style(color="#E5E5E5", bgcolor="#1C1C1C")

# Sparkline characters (Unicode Block Elements U+2581 to U+2588)
SPARK_CHARS = (" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█")


def render_sparkline(
    values: list[float],
    min_val: float = 0.0,
    max_val: float = 100.0,
    length: int = 24,
) -> str:
    """Renders a compact horizontal sparkline from a series of numeric samples."""
    if not values:
        return "─" * length

    samples = values[-length:]
    if len(samples) < length:
        samples = [min_val] * (length - len(samples)) + samples

    span = max_val - min_val if max_val > min_val else 1.0
    chars = []
    for v in samples:
        norm = max(0.0, min(1.0, (v - min_val) / span))
        idx = int(norm * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    return "".join(chars)


def render_2row_histogram(
    values: List[float],
    min_val: float = 0.0,
    max_val: float = 100.0,
    width: int = 18,
) -> Tuple[str, str, str]:
    """Renders a 2-tier terminal histogram matching btop systems engineering reference.

    Returns:
        (top_tier_chars, bottom_tier_chars, baseline_str)
        - top_tier_chars: Represents values in range [(min+max)/2 .. max]
        - bottom_tier_chars: Represents values in range [min .. (min+max)/2]
        - baseline_str: Horizontal axis line ('─' * width)
    """
    if not values:
        # Empty state: empty space between axis marks and baseline
        return (" " * width, " " * width, "─" * width)

    # Take latest `width` samples
    samples = list(values[-width:])
    if len(samples) < width:
        # Left-pad with min_val so chart advances from right
        samples = [min_val] * (width - len(samples)) + samples

    midpoint = (min_val + max_val) / 2.0
    half_span = (max_val - min_val) / 2.0 if max_val > min_val else 1.0

    top_row = []
    bot_row = []

    for v in samples:
        if v <= min_val:
            bot_row.append(" ")
            top_row.append(" ")
        elif v <= midpoint:
            ratio = (v - min_val) / half_span
            idx = max(1, min(len(SPARK_CHARS) - 1, int(ratio * (len(SPARK_CHARS) - 1))))
            bot_row.append(SPARK_CHARS[idx])
            top_row.append(" ")
        else:
            # Bottom row is fully saturated
            bot_row.append("█")
            ratio = (v - midpoint) / half_span
            idx = max(0, min(len(SPARK_CHARS) - 1, int(ratio * (len(SPARK_CHARS) - 1))))
            top_row.append(SPARK_CHARS[idx])

    return ("".join(top_row), "".join(bot_row), "─" * width)
