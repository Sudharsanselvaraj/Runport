"""Tests for Runport hexagonal terminal art constants, capability rules, and welcome screen rendering."""

import io
import os
import re
from rich.console import Console

from runport.tui.logo_ascii import (
    RUNPORT_EMBLEM,
    RUNPORT_EMBLEM_LINES,
    RUNPORT_EMBLEM_SOLID,
    RUNPORT_EMBLEM_SOLID_LINES,
)
from runport.tui.welcome import WelcomeScreen, _should_show_emblem


def _clean_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07", "", text)


def test_emblem_dimensions_and_equal_width():
    """Assert emblem line lists have exact line counts and equal width across all rows."""
    # Braille dotted variant: 12 lines of width 28
    assert len(RUNPORT_EMBLEM_LINES) == 12
    expected_braille_width = 28
    for idx, line in enumerate(RUNPORT_EMBLEM_LINES):
        assert len(line) == expected_braille_width, f"Braille line {idx} width mismatch: {len(line)} != {expected_braille_width}"
    assert RUNPORT_EMBLEM == "\n".join(RUNPORT_EMBLEM_LINES)

    # Solid half-block variant: 12 lines of width 28
    assert len(RUNPORT_EMBLEM_SOLID_LINES) == 12
    expected_solid_width = 28
    for idx, line in enumerate(RUNPORT_EMBLEM_SOLID_LINES):
        assert len(line) == expected_solid_width, f"Solid line {idx} width mismatch: {len(line)} != {expected_solid_width}"
    assert RUNPORT_EMBLEM_SOLID == "\n".join(RUNPORT_EMBLEM_SOLID_LINES)


def test_welcome_renders_emblem_on_large_terminal(monkeypatch):
    """Assert welcome output contains the full emblem on a large terminal."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("RUNPORT_LOGO_STYLE", raising=False)

    buf = io.StringIO()
    console = Console(file=buf, width=110, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    output = _clean_ansi(buf.getvalue())

    # Asserts emblem presence and text hierarchy
    assert RUNPORT_EMBLEM_LINES[0].strip() in output
    assert RUNPORT_EMBLEM_LINES[6].strip() in output
    assert "Welcome to Runport" in output
    assert "The universal open-source LLM, prompt, and workflow benchmarking platform." in output
    assert "Spend: $0.00 / $5 cap" in output


def test_welcome_compact_fallback_on_small_terminal(monkeypatch):
    """Assert compact fallback 'RUNPORT' title is used when terminal is too small."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)

    buf = io.StringIO()
    console = Console(file=buf, width=65, height=30, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    output = _clean_ansi(buf.getvalue())

    assert "RUNPORT" in output
    assert RUNPORT_EMBLEM_LINES[0].strip() not in output
    assert "Welcome to Runport" in output


def test_welcome_compact_fallback_on_non_utf8_encoding(monkeypatch):
    """Assert compact fallback is used when output encoding is not UTF-8."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)

    class AsciiStream(io.StringIO):
        encoding = "ascii"

    stream = AsciiStream()
    console = Console(file=stream, width=110, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    output = _clean_ansi(stream.getvalue())

    assert "RUNPORT" in output
    assert RUNPORT_EMBLEM_LINES[0].strip() not in output


def test_welcome_compact_fallback_when_no_color_set(monkeypatch):
    """Assert compact fallback is used when NO_COLOR environment variable is set."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("NO_COLOR", "1")

    buf = io.StringIO()
    console = Console(file=buf, width=110, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    output = _clean_ansi(buf.getvalue())

    assert "RUNPORT" in output
    assert RUNPORT_EMBLEM_LINES[0].strip() not in output


def test_welcome_compact_fallback_when_term_is_dumb(monkeypatch):
    """Assert compact fallback is used when TERM is 'dumb'."""
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.delenv("NO_COLOR", raising=False)

    buf = io.StringIO()
    console = Console(file=buf, width=110, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    output = _clean_ansi(buf.getvalue())

    assert "RUNPORT" in output
    assert RUNPORT_EMBLEM_LINES[0].strip() not in output


def test_welcome_selects_solid_art_style(monkeypatch):
    """Assert RUNPORT_LOGO_STYLE=solid selects RUNPORT_EMBLEM_SOLID art."""
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("RUNPORT_LOGO_STYLE", "solid")

    buf = io.StringIO()
    console = Console(file=buf, width=110, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    output = _clean_ansi(buf.getvalue())

    assert RUNPORT_EMBLEM_SOLID_LINES[0].strip() in output
    assert RUNPORT_EMBLEM_LINES[0].strip() not in output


def test_logo_capability_rule_never_raises():
    """Assert _should_show_emblem never raises an exception under invalid inputs."""
    assert not _should_show_emblem(None, True, -1, -1)
    assert not _should_show_emblem(Console(file=io.StringIO()), False, 0, 0)
