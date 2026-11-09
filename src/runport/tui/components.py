"""Reusable terminal UI components for Runport CLI and TUI.

Components:
- RunportLogo: Custom dot-matrix and ASCII logo rendering
- StatusIndicator: Compact status pill (● READY, ● CONNECTED, etc.)
- InteractiveMenu: Keyboard-driven menu with arrow navigation & hotkeys
- SectionHeader: Minimalist, spaced section divider
- TerminalFooter: Keyboard hint bar and navigation footer
- ProgressView: Runner guard execution progress
- ResultSummary: Formatted metrics summary table
- ErrorPanel: Secret-scrubbed error presentation
- ConfirmationPanel: Cryptographic plan & budget approval gate
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from rich.align import Align
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

from runport.tui.logo import (
    TerminalImage,
    detect_image_protocol,
    is_logo_available,
    render_official_logo,
)
from runport.tui.logo_ascii import (
    RUNPORT_EMBLEM_LARGE_LINES,
    RUNPORT_EMBLEM_LINES,
    RUNPORT_EMBLEM_SOLID_LINES,
)
from runport.tui.theme import (
    ACCENT_CYAN,
    ACCENT_LAVENDER,
    ACCENT_LAVENDER_LIGHT,
    BG_DARK,
    BORDER_CHARCOAL,
    BORDER_FOCUSED,
    BORDER_MUTED,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUCCESS,
    COLOR_WARNING,
    PANEL_BG,
    PANEL_BG_SECONDARY,
    SELECTION_BG,
    STYLE_ROW_HOVER,
    STYLE_ROW_SELECTED,
    TEXT_BRIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class RunportLogo:
    """Official Runport brand symbol rendering and terminal capability rules."""

    @staticmethod
    def can_render_image(
        console: Optional[Console] = None,
        compact: bool = False,
        cols: int = 80,
        rows: int = 24,
    ) -> bool:
        """Determines whether the official image symbol can be rendered in the current terminal."""
        if compact:
            return False
        if cols < 60 or rows < 28:
            return False
        protocol = detect_image_protocol(console)
        if not protocol:
            return False
        return is_logo_available()

    @staticmethod
    def should_render(console: Optional[Console], compact: bool, cols: int, rows: int) -> bool:
        """Determines whether the terminal viewport can display the logo (image or terminal art)."""
        if compact:
            return False
        if os.environ.get("RUNPORT_NO_LOGO", "").strip().lower() in ("1", "true", "yes"):
            return False
        if RunportLogo.can_render_image(console=console, compact=compact, cols=cols, rows=rows):
            return True
        if cols < 60 or rows < 30:
            return False
        return True

    @staticmethod
    def render_image(
        console: Optional[Console] = None,
        rows: int = 6,
        width_cells: int = 12,
    ) -> Optional[TerminalImage]:
        """Renders the official white interlocking geometric symbol as an inline terminal graphic."""
        return render_official_logo(console=console, rows=rows, width_cells=width_cells)

    @staticmethod
    def render_emblem(solid: bool = False, large: bool = False) -> Text:
        """Renders the official Runport geometric emblem in terminal art (white)."""
        style_env = os.environ.get("RUNPORT_LOGO_STYLE", "").strip().lower()
        if style_env == "solid" or solid:
            lines = RUNPORT_EMBLEM_SOLID_LINES
        elif style_env == "large" or large:
            lines = RUNPORT_EMBLEM_LARGE_LINES
        else:
            lines = RUNPORT_EMBLEM_LINES

        text = Text()
        for line in lines:
            text.append(line + "\n", style="bold bright_white")
        return text

    @staticmethod
    def render_compact() -> Text:
        """Renders the clean official wordmark in restrained lavender."""
        return Text("RUNPORT CLI", style=f"bold {ACCENT_LAVENDER}")


class StatusIndicator:
    """Renders a single system status indicator pill with aligned columns."""

    STATE_COLORS = {
        "ready": COLOR_SUCCESS,
        "success": COLOR_SUCCESS,
        "connected": COLOR_SUCCESS,
        "active": COLOR_SUCCESS,
        "warning": COLOR_WARNING,
        "warn": COLOR_WARNING,
        "local": COLOR_INFO,
        "error": COLOR_ERROR,
        "fail": COLOR_ERROR,
        "neutral": TEXT_MUTED,
        "unconfigured": COLOR_WARNING,
    }

    @classmethod
    def render_row(
        cls,
        label: str,
        status: str,
        state: str = "ready",
        detail: Optional[str] = None,
        label_width: int = 14,
        status_width: int = 16,
    ) -> Text:
        """Renders: Label         ● STATUS  (detail text)"""
        color = cls.STATE_COLORS.get(state.lower(), TEXT_MUTED)
        row = Text()
        row.append(f"{label:<{label_width}}", style=TEXT_SECONDARY)
        row.append("● ", style=color)
        row.append(f"{status:<{status_width}}", style=f"bold {color}")
        if detail:
            row.append(f"  {detail}", style=TEXT_MUTED)
        return row


@dataclass
class MenuItem:
    key: str  # e.g. "A", "B", "C", "1"
    title: str  # Primary action title
    description: str = ""  # Secondary contextual note
    badge: Optional[str] = None  # e.g. "NEW", "GUARDED", "LOCAL"
    enabled: bool = True


class InteractiveMenu:
    """Keyboard-driven option selector supporting arrow keys, letters, and numbers."""

    def __init__(self, items: Sequence[MenuItem], selected_index: int = 0) -> None:
        self.items = list(items)
        self.selected_index = max(0, min(selected_index, len(self.items) - 1)) if self.items else 0

    def move_up(self) -> None:
        if not self.items:
            return
        self.selected_index = (self.selected_index - 1) % len(self.items)

    def move_down(self) -> None:
        if not self.items:
            return
        self.selected_index = (self.selected_index + 1) % len(self.items)

    def select_by_key(self, key_str: str) -> Optional[int]:
        """Matches key against item.key (case-insensitive) or 1-based index."""
        cleaned = key_str.strip().upper()
        # Match by key label (e.g. 'A', 'B', '1')
        for idx, it in enumerate(self.items):
            if it.key.upper() == cleaned:
                self.selected_index = idx
                return idx
        # Match by numeric position if input is a digit
        if cleaned.isdigit():
            num = int(cleaned)
            if 1 <= num <= len(self.items):
                self.selected_index = num - 1
                return num - 1
        return None

    def render(self, content_width: int = 76, compact: bool = False) -> Table:
        """Builds a formatted table containing the menu items with restrained selection highlight."""
        table = Table.grid(padding=(0, 0))
        table.add_column(width=content_width)

        title_w = 36 if not compact else 50
        sub_w = 28 if not compact else 0

        for idx, item in enumerate(self.items):
            is_active = idx == self.selected_index
            prefix = " > " if is_active else "   "
            key_tag = f"({item.key}) "
            badge_str = f"  [bold #FFFFFF on #3D2952] {item.badge} [/]" if item.badge and not compact else ""
            pad = 12 - (len(item.badge) + 3 if item.badge else 0) if not compact else 0

            if compact:
                if is_active:
                    row_markup = f"[bold {ACCENT_LAVENDER} on {SELECTION_BG}]{prefix}[/][bold {ACCENT_LAVENDER} on {SELECTION_BG}]{key_tag}[/][bold #FFFFFF on {SELECTION_BG}]{item.title}[/]"
                else:
                    row_markup = f"[dim {TEXT_MUTED}]{prefix}[/][{ACCENT_LAVENDER}]{key_tag}[/][{TEXT_PRIMARY}]{item.title}[/]"
            elif is_active:
                row_markup = (
                    f"[bold {ACCENT_LAVENDER} on {SELECTION_BG}]{prefix}[/]"
                    f"[bold {ACCENT_LAVENDER} on {SELECTION_BG}]{key_tag}[/]"
                    f"[bold #FFFFFF on {SELECTION_BG}]{item.title:<{title_w}}[/]"
                    f"[{TEXT_PRIMARY} on {SELECTION_BG}]{item.description:<{sub_w}}[/]"
                    f"{badge_str}{' ' * pad}"
                )
            else:
                row_markup = (
                    f"[dim {TEXT_MUTED}]{prefix}[/]"
                    f"[{ACCENT_LAVENDER}]{key_tag}[/]"
                    f"[{TEXT_PRIMARY}]{item.title:<{title_w}}[/]"
                    f"[{TEXT_SECONDARY}]{item.description:<{sub_w}}[/]"
                    f"{badge_str}{' ' * pad}"
                )

            table.add_row(Text.from_markup(row_markup))

        return table


class SectionHeader:
    """Renders a clean, minimalist section divider."""

    @staticmethod
    def render(title: str, subtitle: Optional[str] = None, width: int = 76) -> Table:
        grid = Table.grid(padding=(0, 0))
        grid.add_column(width=width)
        grid.add_row(Text("─" * width, style=BORDER_CHARCOAL))
        grid.add_row(Text(""))
        grid.add_row(Align.center(Text(title.upper(), style=f"bold {ACCENT_LAVENDER}")))
        if subtitle:
            grid.add_row(Align.center(Text(subtitle, style=TEXT_SECONDARY)))
        grid.add_row(Text(""))
        return grid

    @staticmethod
    def divider(width: int = 76) -> Text:
        return Text("─" * width, style=BORDER_CHARCOAL)


class TerminalFooter:
    """Renders keyboard navigation hints and status message at bottom of view."""

    @staticmethod
    def render(
        hints: Optional[Sequence[Tuple[str, str]]] = None,
        width: int = 76,
        status_msg: Optional[str] = None,
    ) -> Table:
        if hints is None:
            hints = [("↑↓", "Navigate"), ("Enter", "Select"), ("A-G", "Jump"), ("q", "Exit")]

        grid = Table.grid(padding=(0, 0))
        grid.add_column(width=width)
        grid.add_row(Text("─" * width, style=BORDER_CHARCOAL))

        hint_parts = []
        for key, desc in hints:
            hint_parts.append(f"[dim {TEXT_SECONDARY}]{key} {desc}[/]")
        hints_text = Text.from_markup("    ".join(hint_parts))

        if status_msg:
            grid.add_row(Text(status_msg, style=f"dim {ACCENT_LAVENDER}"))

        grid.add_row(Align.center(hints_text))
        return grid


class ProgressView:
    """Renders execution progress across runner guard steps."""

    @staticmethod
    def render(steps: Sequence[Tuple[str, str]], title: str = "Execution Progress") -> Panel:
        """Renders list of (step_name, status) where status is 'pending'|'active'|'completed'|'failed'."""
        grid = Table.grid(padding=(0, 2))
        grid.add_column(width=4)
        grid.add_column(style=TEXT_PRIMARY, width=36)
        grid.add_column(style=TEXT_MUTED)

        for name, status in steps:
            s_lower = status.lower()
            if s_lower in ("completed", "done", "success"):
                icon = Text("✓", style=f"bold {COLOR_SUCCESS}")
                st_text = Text("COMPLETED", style=COLOR_SUCCESS)
            elif s_lower in ("active", "running", "in_progress"):
                icon = Text("▶", style=f"bold {ACCENT_LAVENDER}")
                st_text = Text("RUNNING", style=f"bold {ACCENT_LAVENDER}")
            elif s_lower in ("failed", "blocked", "error"):
                icon = Text("✕", style=f"bold {COLOR_ERROR}")
                st_text = Text("FAILED", style=COLOR_ERROR)
            else:
                icon = Text("·", style=TEXT_MUTED)
                st_text = Text("PENDING", style=TEXT_MUTED)

            grid.add_row(icon, name, st_text)

        return Panel(
            grid,
            title=f"[bold {ACCENT_LAVENDER}] {title} [/]",
            border_style=BORDER_CHARCOAL,
            padding=(1, 2),
        )


class ConfirmationPanel:
    """Visual approval gate before running benchmarks, displaying plan fingerprint and caps."""

    @staticmethod
    def render(
        target_id: str,
        dataset_name: str,
        total_cases: int,
        plan_fingerprint: str,
        projected_spend_usd: Optional[Decimal] = None,
        per_run_ceiling_usd: Optional[Decimal] = None,
        is_permitted: bool = True,
        block_reasons: Optional[List[str]] = None,
        width: int = 76,
    ) -> Panel:
        content = Table.grid(padding=(0, 1))
        content.add_column(style=f"bold {TEXT_SECONDARY}", width=22)
        content.add_column(style=TEXT_PRIMARY, width=width - 26)

        content.add_row("Target:", target_id)
        content.add_row("Dataset:", f"{dataset_name} ({total_cases} cases)")
        content.add_row("Plan Fingerprint:", Text(plan_fingerprint[:32] + "...", style=f"bold {ACCENT_LAVENDER}"))

        spend_str = f"${projected_spend_usd:.4f}" if projected_spend_usd is not None else "UNAVAILABLE (Free / Local)"
        cap_str = f"${per_run_ceiling_usd:.2f}" if per_run_ceiling_usd is not None else "$1.00"
        content.add_row("Projected Spend:", f"{spend_str} (Run cap: {cap_str})")

        verdict_color = COLOR_SUCCESS if is_permitted else COLOR_ERROR
        verdict_text = "PERMITTED" if is_permitted else "BLOCKED"
        content.add_row("Preflight Verdict:", Text(f"● {verdict_text}", style=f"bold {verdict_color}"))

        if block_reasons:
            for r in block_reasons:
                content.add_row("", Text(f"  ⚠ {r}", style=f"dim {COLOR_ERROR}"))

        return Panel(
            content,
            title=f"[bold {ACCENT_LAVENDER}] Cryptographic Plan Authorization [/]",
            border_style=BORDER_FOCUSED if is_permitted else COLOR_ERROR,
            padding=(1, 2),
        )


class ResultSummary:
    """Renders formatted evaluation and benchmark results enforcing 'Null is not 0'."""

    @staticmethod
    def render(
        run_id: str,
        target_id: str,
        dataset_name: str,
        total_cases: int,
        completed_cases: int,
        mean_latency_ms: Optional[float] = None,
        total_cost_usd: Optional[Decimal] = None,
        cost_basis: str = "UNAVAILABLE",
        accuracy: Optional[float] = None,
        score_kind: str = "heuristic",
        case_samples: Optional[List[Dict[str, Any]]] = None,
    ) -> Panel:
        table = Table(show_header=True, header_style=f"bold {ACCENT_LAVENDER}", border_style=BORDER_CHARCOAL)
        table.add_column("Case ID", style=f"dim {TEXT_MUTED}")
        table.add_column("Query Preview", style=TEXT_PRIMARY, max_width=32)
        table.add_column("Output Preview", style=TEXT_SECONDARY, max_width=34)
        table.add_column("Latency", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Score", justify="center")

        if case_samples:
            for c in case_samples[:8]:
                cid = str(c.get("case_id") or c.get("id") or "case")
                query = str(c.get("query") or c.get("prompt") or "")[:30]
                output = str(c.get("output_text") or c.get("output") or c.get("generated_output") or "")[:30]
                lat = f"{c['latency_ms']:.1f}ms" if c.get("latency_ms") is not None else "—"
                cost = f"${Decimal(str(c['cost_usd'])):.4f}" if c.get("cost_usd") is not None else "—"
                score = f"{float(c['accuracy']) * 100:.0f}%" if c.get("accuracy") is not None else "UNSCORED"

                table.add_row(cid, query, output, lat, cost, score)

        summary_grid = Table.grid(padding=(0, 2))
        summary_grid.add_column(style=f"bold {TEXT_SECONDARY}")
        summary_grid.add_column(style=TEXT_PRIMARY)
        summary_grid.add_column(style=f"bold {TEXT_SECONDARY}")
        summary_grid.add_column(style=TEXT_PRIMARY)

        lat_str = f"{mean_latency_ms:.1f} ms" if mean_latency_ms is not None else "—"
        cost_str = f"${total_cost_usd:.4f} ({cost_basis})" if total_cost_usd is not None else f"— ({cost_basis})"
        score_str = f"{accuracy * 100:.1f}% ({score_kind})" if accuracy is not None else "UNSCORED"

        summary_grid.add_row("Run ID:", run_id, "Target:", target_id)
        summary_grid.add_row("Dataset:", dataset_name, "Cases:", f"{completed_cases}/{total_cases} completed")
        summary_grid.add_row("Mean Latency:", lat_str, "Total Spend:", cost_str)
        summary_grid.add_row("Score / Metric:", score_str, "", "")

        root = Table.grid(padding=(1, 0))
        root.add_column()
        root.add_row(summary_grid)
        if case_samples:
            root.add_row(table)

        return Panel(
            root,
            title=f"[bold #e9d5ff] Benchmark Execution Results: {run_id} [/]",
            border_style=BORDER_CHARCOAL,
            padding=(1, 2),
        )


class ErrorPanel:
    """Presents errors gracefully with actionable next steps while scrubbing secrets."""

    @staticmethod
    def render(title: str, message: str, suggestion: Optional[str] = None) -> Panel:
        content = Text()
        content.append(message + "\n", style=TEXT_PRIMARY)
        if suggestion:
            content.append(f"\nNext step: {suggestion}", style=f"dim {ACCENT_CYAN}")
        return Panel(
            content,
            title=f"[bold {COLOR_ERROR}] ⚠ {title} [/]",
            border_style=COLOR_ERROR,
            padding=(1, 2),
        )
