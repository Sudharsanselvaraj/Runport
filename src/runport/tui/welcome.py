"""Interactive, developer-grade welcome screen and onboarding launcher for Runport.

Design Characteristics:
- Deep navy / near-black terminal background (#0d1117)
- Official Runport dot-matrix & Braille brand emblem
- Live system & workspace status telemetry (Runtime, Workspace, Providers, Storage)
- Generous, deliberate alignment and monospace typography
- Interactive option selector (Arrow keys, Enter, Letters A-G, Numbers 1-7, Esc/q to exit)
- Graceful terminal resizing with compact mode fallback for small viewports
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from runport.tui.components import (
    ConfirmationPanel,
    InteractiveMenu,
    MenuItem,
    RunportLogo,
    SectionHeader,
    StatusIndicator,
    TerminalFooter,
)
from runport.tui.input import KeyReader
from runport.tui.theme import (
    ACCENT_CYAN,
    ACCENT_LAVENDER,
    ACCENT_LAVENDER_LIGHT,
    BG_DARK,
    BORDER_CHARCOAL,
    COLOR_SUCCESS,
    COLOR_WARNING,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def _should_show_emblem(console: Console, compact: bool, cols: int, rows: int) -> bool:
    """Size and terminal capability rule for displaying the hexagonal brand emblem."""
    return RunportLogo.should_render(console, compact, cols, rows)


# Menu items specification for onboarding actions (A through G)
MENU_ITEMS: List[Tuple[str, str, Optional[str]]] = [
    ("Explore a benchmark workspace", "Workspace config & datasets", None),
    ("Run a model benchmark", "Guarded evaluation", "GUARDED"),
    ("Evaluate a dataset", "Schema validation & leakage", None),
    ("Compare models and inspect results", "Past benchmark runs & metrics", None),
    ("Open the interactive dashboard", "Live telemetry", "DASHBOARD"),
    ("Configure providers and settings", "API keys, ceilings & storage", None),
    ("Skip onboarding and open the shell", "Exit to command line prompt", None),
]

_MENU_KEYS = ["A", "B", "C", "D", "E", "F", "G"]


def _git(*args: str) -> Optional[str]:
    """Helper to run git commands with short timeout."""
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


def launcher_status() -> Dict[str, Any]:
    """Live facts for the launcher header. Every value is read from actual local files, environment, or ledger."""
    from runport import __version__

    ver = f"v{__version__}"
    sha = _git("rev-parse", "--short", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    date = _git("log", "-1", "--format=%cd", "--date=format:%Y.%m.%d")
    build_info = f"{ver} · {sha or 'release'} ({date or 'local'})"

    # 1. Runtime Status
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    runtime_state = "ready" if py_ok else "error"
    runtime_status = "READY" if py_ok else "UNSUPPORTED"
    runtime_detail = f"Python {py_ver} ({sys.platform})"

    # 2. Workspace Status
    from runport.core.workspace import find_workspace_file, load_workspace_config

    ws_file = find_workspace_file()
    ws_cfg = load_workspace_config()
    target_count = len(ws_cfg.targets)
    if ws_file is not None:
        ws_state = "connected"
        ws_status = "CONNECTED"
        ws_detail = f"{ws_file.name} ({target_count} target{'s' if target_count != 1 else ''})"
    else:
        ws_state = "unconfigured"
        ws_status = "NOT CONFIGURED"
        ws_detail = "no runport.yaml found in current directory"

    # 3. Providers Status
    key = os.environ.get("OPENROUTER_API_KEY")
    key_present = bool(key and key.strip())
    if key_present:
        prov_state = "connected"
        prov_status = "CONFIGURED"
        prov_detail = "API key: set (OpenRouter)"
    else:
        prov_state = "local"
        prov_status = "LOCAL ONLY"
        prov_detail = "API key: not set (local endpoints & offline replay)"

    # 4. Storage & Budget Status
    storage_state = "ready"
    storage_status = "READY"
    spend_str = "$0.00 / $5 cap"
    try:
        from runport.core.config import settings
        from runport.core.budget import BudgetService
        from runport.storage.db import DatabaseManager

        db_path = Path(settings.db_path)
        if db_path.exists():
            db_mgr = DatabaseManager(settings.db_path)
            db_mgr.init_db()
            b_pol = ws_cfg.budget.to_budget_policy()
            b = BudgetService(db=db_mgr, policy=b_pol).get_status()
            spend_str = f"${b.cumulative_spend_usd:.2f} / ${b.total_ceiling_usd:.0f} cap"
            storage_detail = f"WAL active · Spend: {spend_str}"
        else:
            storage_state = "unconfigured"
            storage_status = "INITIALIZING"
            storage_detail = f"{settings.db_path} · Spend: {spend_str}"
    except Exception:
        storage_detail = f"Spend: {spend_str}"

    return {
        "version": ver,
        "build_info": build_info,
        "runtime": (runtime_status, runtime_state, runtime_detail),
        "workspace": (ws_status, ws_state, ws_detail),
        "providers": (prov_status, prov_state, prov_detail),
        "storage": (storage_status, storage_state, storage_detail),
        "spend_summary": spend_str,
    }


class WelcomeScreen:
    """Renders the Runport Welcome & Onboarding screen with real-time status."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console(color_system="auto", legacy_windows=False)
        self.key_reader = KeyReader()
        self.selected_index: int = 0

        # Construct menu items for InteractiveMenu
        self.menu_items = [
            MenuItem(
                key=_MENU_KEYS[i],
                title=MENU_ITEMS[i][0],
                description=MENU_ITEMS[i][1],
                badge=MENU_ITEMS[i][2],
            )
            for i in range(len(MENU_ITEMS))
        ]
        self.menu = InteractiveMenu(self.menu_items, selected_index=0)

    def _build(self, compact: bool = False, rows: Optional[int] = None) -> Align:
        """Builds the complete welcome screen as a centered Rich renderable."""
        content_width = 94
        facts = launcher_status()

        grid = Table.grid(padding=(0, 0))
        grid.add_column(width=content_width)

        size = shutil.get_terminal_size((100, 50))
        cols = self.console.width if self.console.width else size.columns
        eff_rows = rows if rows is not None else (self.console.height if (self.console.is_terminal and self.console.height) else 50)

        # Compact View for tight terminal viewports (< 28 rows)
        if compact or (rows is not None and rows < 28):
            grid.add_row(Align.center(Text(f"RUNPORT CLI {facts['version']}", style=f"bold {ACCENT_LAVENDER}")))
            grid.add_row(Align.center(Text("Welcome to Runport", style=f"bold {TEXT_PRIMARY}")))
            grid.add_row(Align.center(Text("Select a workflow:", style=TEXT_SECONDARY)))
            grid.add_row(SectionHeader.divider(width=content_width))
            self.menu.selected_index = self.selected_index
            grid.add_row(self.menu.render(content_width=content_width, compact=True))
            grid.add_row(SectionHeader.divider(width=content_width))
            footer_hints = [("↑↓", "Navigate"), ("Enter", "Select"), ("A-G", "Jump"), ("q", "Exit")]
            grid.add_row(TerminalFooter.render(hints=footer_hints, width=content_width))
            return Align.center(grid)

        # 1. Header / Logo Section: Official Symbol (White)
        if _should_show_emblem(self.console, compact, cols, eff_rows):
            image_renderable = RunportLogo.render_image(self.console, rows=6, width_cells=12)
            if image_renderable is not None:
                grid.add_row(image_renderable)
            else:
                # Fallback for terminals without inline image protocols (e.g. macOS Terminal)
                grid.add_row(Align.center(RunportLogo.render_emblem()))

        # 2. Brand Title & Version Hierarchy
        grid.add_row(Align.center(Text("RUNPORT CLI", style=f"bold {ACCENT_LAVENDER}")))
        grid.add_row(Align.center(Text(facts["build_info"].upper(), style=f"dim {TEXT_SECONDARY}")))
        grid.add_row(Align.center(Text("Welcome to Runport", style=f"bold {TEXT_PRIMARY}")))
        grid.add_row(Align.center(Text("The universal open-source LLM, prompt, and workflow benchmarking platform.", style=TEXT_SECONDARY)))

        if not compact:
            grid.add_row(Text(""))

        # 6. Live System Status Block
        status_box = Table.grid(padding=(0, 1))
        status_box.add_column(width=content_width)

        rt_st, rt_state, rt_det = facts["runtime"]
        ws_st, ws_state, ws_det = facts["workspace"]
        pr_st, pr_state, pr_det = facts["providers"]
        st_st, st_state, st_det = facts["storage"]

        status_box.add_row(StatusIndicator.render_row("Runtime", rt_st, rt_state, rt_det))
        status_box.add_row(StatusIndicator.render_row("Workspace", ws_st, ws_state, ws_det))
        status_box.add_row(StatusIndicator.render_row("Providers", pr_st, pr_state, pr_det))
        status_box.add_row(StatusIndicator.render_row("Storage", st_st, st_state, st_det))

        grid.add_row(status_box)

        # 7. Section Separator & Header
        if not compact:
            grid.add_row(Text(""))
        grid.add_row(SectionHeader.divider(width=content_width))
        if not compact:
            grid.add_row(Text(""))
        grid.add_row(Align.center(Text("GET STARTED", style=f"bold {ACCENT_LAVENDER}")))
        grid.add_row(Align.center(Text("What would you like to do? Select a workflow:", style=TEXT_SECONDARY)))
        if not compact:
            grid.add_row(Text(""))

        # 9. Interactive Options Menu
        self.menu.selected_index = self.selected_index
        grid.add_row(self.menu.render(content_width=content_width))

        if not compact:
            grid.add_row(Text(""))

        # 10. Navigation Footer
        footer_hints = [
            ("↑↓", "Navigate"),
            ("Enter", "Select"),
            ("A-G", "Jump"),
            ("q", "Exit"),
        ]
        grid.add_row(TerminalFooter.render(hints=footer_hints, width=content_width))

        return Align.center(grid)

    def render(self, clear: bool = True) -> None:
        """Prints one frame (used for non-interactive output, piping, and tests)."""
        if clear and self.key_reader.is_tty:
            self.console.clear()
        self.console.print(self._build())

    def frame_lines(self, rows: int) -> List[str]:
        """Renders the screen and fits it into `rows` without scrollback overflow."""
        for compact in (False, True):
            with self.console.capture() as cap:
                self.console.print(self._build(compact=compact, rows=rows))
            lines = cap.get().rstrip("\n").split("\n")
            if len(lines) <= rows:
                if not compact and rows >= 40:
                    top_pad = max(0, (rows - len(lines)) // 2)
                    return [""] * top_pad + lines
                return lines
        return lines[:rows]

    def run(self) -> int:
        """Runs the interactive loop until a choice is made. Returns 1-based action code (1-7)."""
        if not self.key_reader.is_tty:
            self.render(clear=False)
            return 0

        # Apply deep navy / near-black background to terminal canvas
        try:
            sys.stdout.write(f"\033]11;{BG_DARK}\007")
            sys.stdout.flush()
        except Exception:
            pass

        # Switch to alternate screen, hide cursor
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()

        last_size = None
        dirty = True
        try:
            while True:
                size = shutil.get_terminal_size((100, 30))
                if dirty or size != last_size:
                    rows = max(8, size.lines)
                    lines = self.frame_lines(rows)
                    sys.stdout.write("\033[H" + "\033[K\n".join(lines) + "\033[K\033[J")
                    sys.stdout.flush()
                    last_size, dirty = size, False

                key = self.key_reader.read_key(timeout=0.3)
                if key == "TIMEOUT":
                    continue
                dirty = True

                # Arrow Navigation
                if key in ("UP", "k", "K"):
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                elif key in ("DOWN", "j", "J"):
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                elif key in ("ENTER", "SPACE"):
                    return self.selected_index + 1
                elif key in ("q", "Q", "ESC"):
                    return len(self.menu_items)  # Option 7: Skip/Exit
                elif key == "EOF":
                    return len(self.menu_items)

                # Direct key selection by letter A-G
                elif key.upper() in _MENU_KEYS:
                    idx = _MENU_KEYS.index(key.upper())
                    self.selected_index = idx
                    return idx + 1

                # Direct selection by digit (1-7, with 8/9 legacy aliases)
                elif key.isdigit():
                    num = int(key)
                    if 1 <= num <= len(self.menu_items):
                        self.selected_index = num - 1
                        return num
                    elif num == 8:
                        self.selected_index = 5  # Option F: Configure providers
                        return 6
                    elif num == 9:
                        self.selected_index = 6  # Option G: Exit
                        return 7

                elif key == "?":
                    self.selected_index = 4  # Option E: Open dashboard
                    return 5

        finally:
            try:
                sys.stdout.write("\033[?25h\033[?1049l")  # Restore cursor and main screen
                sys.stdout.write("\033]111\007")  # Restore terminal background
                sys.stdout.flush()
            except Exception:
                pass


def show_welcome_screen() -> int:
    """Convenience helper to launch the welcome screen."""
    screen = WelcomeScreen()
    return screen.run()
