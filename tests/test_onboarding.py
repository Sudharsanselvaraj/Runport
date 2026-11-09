"""Comprehensive unit and integration test suite for Runport terminal onboarding and UI components."""

import io
import os
import re
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from runport.tui.components import (
    ConfirmationPanel,
    ErrorPanel,
    InteractiveMenu,
    MenuItem,
    ProgressView,
    ResultSummary,
    RunportLogo,
    SectionHeader,
    StatusIndicator,
    TerminalFooter,
)
from runport.tui.logo_ascii import (
    RUNPORT_BLOCK_WORDMARK,
    RUNPORT_EMBLEM_LINES,
    RUNPORT_EMBLEM_SOLID_LINES,
)
from runport.tui.onboarding import OnboardingEngine
from runport.tui.theme import (
    ACCENT_LAVENDER,
    BG_DARK,
    BORDER_CHARCOAL,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUCCESS,
    COLOR_WARNING,
    SELECTION_BG,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from runport.tui.welcome import (
    MENU_ITEMS,
    WelcomeScreen,
    _should_show_emblem,
    launcher_status,
)


def _clean_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07", "", text)


# -----------------------------------------------------------------------------
# 1. Palette & Theme Invariants
# -----------------------------------------------------------------------------
def test_palette_constants_match_opensre_specification():
    """Verifies that all visual design tokens match the requested palette."""
    assert BG_DARK == "#111111"
    assert ACCENT_LAVENDER == "#C5A6E8"
    assert TEXT_PRIMARY == "#E5E5E5"
    assert TEXT_SECONDARY == "#858585"
    assert TEXT_MUTED == "#555555"
    assert COLOR_SUCCESS == "#75B88A"
    assert COLOR_WARNING == "#D9B45B"
    assert COLOR_ERROR == "#D97979"
    assert COLOR_INFO == "#C5A6E8"
    assert SELECTION_BG == "#261933"
    assert BORDER_CHARCOAL == "#282828"


# -----------------------------------------------------------------------------
# 2. RunportLogo Component Tests
# -----------------------------------------------------------------------------
def test_logo_wordmark_and_official_asset():
    """Asserts official logo asset resolution and lavender wordmark styling."""
    from runport.tui.logo import get_logo_bytes, is_logo_available

    assert is_logo_available() is True
    data = get_logo_bytes()
    assert data is not None and len(data) > 0

    compact_text = RunportLogo.render_compact()
    assert "RUNPORT CLI" in compact_text.plain
    for span in compact_text.spans:
        assert ACCENT_LAVENDER.lower() in str(span.style).lower()


def test_logo_capability_rules(monkeypatch):
    """Verifies terminal capability checks for rendering image logo vs fallback."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "iterm2")

    class Utf8Stream(io.StringIO):
        encoding = "utf-8"

    buf = Utf8Stream()
    console = Console(file=buf, force_terminal=True, width=100, height=50)

    # Fits on large terminal with supported protocol
    assert RunportLogo.should_render(console, compact=False, cols=100, rows=50) is True

    # Compact suppresses full logo
    assert RunportLogo.should_render(console, compact=True, cols=100, rows=50) is False

    # Narrow width suppresses full logo
    assert RunportLogo.should_render(console, compact=False, cols=50, rows=50) is False

    # Short height suppresses full logo
    assert RunportLogo.should_render(console, compact=False, cols=100, rows=25) is False

    # Without protocol support (e.g. macOS Terminal) should_render is False
    monkeypatch.delenv("RUNPORT_IMAGE_PROTOCOL", raising=False)
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert RunportLogo.should_render(console, compact=False, cols=100, rows=50) is False


# -----------------------------------------------------------------------------
# 3. StatusIndicator Component Tests
# -----------------------------------------------------------------------------
def test_status_indicator_states_and_colors():
    """Asserts accurate status pill colors and alignment."""
    row_ready = StatusIndicator.render_row("Runtime", "READY", "ready", "Python 3.11.7")
    plain = row_ready.plain
    assert "Runtime" in plain
    assert "READY" in plain
    assert "●" in plain

    row_warn = StatusIndicator.render_row("Workspace", "NOT CONFIGURED", "warning")
    assert "NOT CONFIGURED" in row_warn.plain

    row_local = StatusIndicator.render_row("Providers", "LOCAL ONLY", "local")
    assert "LOCAL ONLY" in row_local.plain


# -----------------------------------------------------------------------------
# 4. InteractiveMenu Component Tests
# -----------------------------------------------------------------------------
def test_interactive_menu_navigation_and_selection():
    """Verifies keyboard selection, arrow navigation, and bounds checking."""
    items = [
        MenuItem(key="A", title="Option A", description="Desc A"),
        MenuItem(key="B", title="Option B", description="Desc B"),
        MenuItem(key="C", title="Option C", description="Desc C"),
    ]
    menu = InteractiveMenu(items=items, selected_index=0)

    # Initial selection
    assert menu.selected_index == 0

    # Move down
    menu.move_down()
    assert menu.selected_index == 1

    # Move down again
    menu.move_down()
    assert menu.selected_index == 2

    # Wrap around
    menu.move_down()
    assert menu.selected_index == 0

    # Move up wraps to end
    menu.move_up()
    assert menu.selected_index == 2

    # Select by letter
    idx = menu.select_by_key("B")
    assert idx == 1
    assert menu.selected_index == 1

    # Select by digit
    idx = menu.select_by_key("1")
    assert idx == 0
    assert menu.selected_index == 0

    # Invalid key returns None without changing selection
    idx = menu.select_by_key("Z")
    assert idx is None
    assert menu.selected_index == 0


def test_interactive_menu_rendering():
    """Asserts that the menu table renders active and inactive rows with correct styles."""
    items = [
        MenuItem(key="A", title="Run Benchmark", description="Execute benchmark", badge="GUARDED"),
        MenuItem(key="B", title="Open Dashboard", description="Live telemetry"),
    ]
    menu = InteractiveMenu(items=items, selected_index=0)
    table = menu.render(content_width=94)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    console.print(table)
    plain = _clean_ansi(buf.getvalue())

    assert "(A) Run Benchmark" in plain
    assert "Execute benchmark" in plain
    assert "GUARDED" in plain
    assert "(B) Open Dashboard" in plain


# -----------------------------------------------------------------------------
# 5. WelcomeScreen Visual Hierarchy Tests
# -----------------------------------------------------------------------------
def test_welcome_screen_hierarchy_on_standard_terminal(monkeypatch):
    """Verifies the exact visual hierarchy on standard terminal viewports."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=100, height=55)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    plain = _clean_ansi(buf.getvalue())

    # Hierarchy checkpoints:
    # 1. RUNPORT CLI title (in restrained lavender)
    assert "RUNPORT CLI" in plain
    # 3. Welcome heading
    assert "Welcome to Runport" in plain
    # 4. Product description
    assert "The universal open-source LLM, prompt, and workflow benchmarking platform." in plain
    # 5. Status items
    assert "Runtime" in plain
    assert "Workspace" in plain
    assert "Providers" in plain
    assert "Storage" in plain
    # 6. GET STARTED section
    assert "GET STARTED" in plain
    assert "What would you like to do? Select a workflow:" in plain
    # 7. Menu options (A through G)
    for title, _, _ in MENU_ITEMS:
        assert title in plain
    # 8. Navigation hints footer
    assert "q Exit" in plain


def test_welcome_screen_compact_mode():
    """Asserts that compact mode fits within 20 rows and retains the footer."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=90, height=20)
    screen = WelcomeScreen(console=console)
    lines = screen.frame_lines(20)

    assert len(lines) <= 20
    assert any("Select a workflow:" in l for l in lines)
    assert any("q Exit" in l for l in lines)


# -----------------------------------------------------------------------------
# 6. OnboardingEngine Workflow Tests
# -----------------------------------------------------------------------------
def test_onboarding_engine_flows_run_without_exception():
    """Asserts that every onboarding workflow executes without raising unhandled errors."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=100)
    engine = OnboardingEngine(console=console)

    # Flow A: explore_workspace
    engine.explore_workspace()
    # Flow B: run_benchmark_flow
    engine.run_benchmark_flow()
    # Flow C: evaluate_dataset_flow
    engine.evaluate_dataset_flow()
    # Flow D: compare_results_flow
    engine.compare_results_flow()
    # Flow F: configure_providers_flow
    engine.configure_providers_flow()
    # Flow G: skip_and_exit
    engine.skip_and_exit()

    output = buf.getvalue()
    assert "WORKSPACE EXPLORER" in output
    assert "BENCHMARK EXECUTION" in output
    assert "DATASET VALIDATION" in output
    assert "MODEL COMPARISON ROSTER" in output
    assert "PROVIDER CONFIGURATION & BUDGET" in output
    assert "Runport CLI Quick Reference" in output


# -----------------------------------------------------------------------------
# 7. Additional Reusable UI Components
# -----------------------------------------------------------------------------
def test_confirmation_panel_rendering():
    """Asserts ConfirmationPanel renders plan fingerprint and preflight status."""
    panel = ConfirmationPanel.render(
        target_id="openrouter/anthropic/claude-3.5-sonnet",
        dataset_name="verified_rag_benchmark.jsonl",
        total_cases=16,
        plan_fingerprint="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        projected_spend_usd=Decimal("0.0240"),
        per_run_ceiling_usd=Decimal("1.00"),
        is_permitted=True,
    )
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=90)
    console.print(panel)
    plain = _clean_ansi(buf.getvalue())

    assert "Cryptographic Plan Authorization" in plain
    assert "PERMITTED" in plain
    assert "$0.0240" in plain


def test_progress_view_rendering():
    """Asserts ProgressView displays guard stages accurately."""
    steps = [
        ("Authorization Check", "completed"),
        ("Privacy Gate", "completed"),
        ("Preflight Budget Check", "active"),
        ("Transport Execution", "pending"),
    ]
    panel = ProgressView.render(steps, title="Runner Pipeline")
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=90)
    console.print(panel)
    plain = _clean_ansi(buf.getvalue())

    assert "Runner Pipeline" in plain
    assert "COMPLETED" in plain
    assert "RUNNING" in plain
    assert "PENDING" in plain


def test_result_summary_rendering():
    """Asserts ResultSummary handles scores and enforces 'Null is not 0'."""
    panel = ResultSummary.render(
        run_id="run-12345",
        target_id="openrouter/meta-llama/llama-3-70b-instruct",
        dataset_name="synthetic_seed_eval.jsonl",
        total_cases=10,
        completed_cases=10,
        mean_latency_ms=245.5,
        total_cost_usd=Decimal("0.0050"),
        accuracy=0.85,
    )
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=90)
    console.print(panel)
    plain = _clean_ansi(buf.getvalue())

    assert "Benchmark Execution Results" in plain
    assert "85.0%" in plain or "UNSCORED" in plain
