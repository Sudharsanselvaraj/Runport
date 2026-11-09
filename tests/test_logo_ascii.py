"""Tests for official Runport logo asset packaging, resolution, terminal graphics protocols, and fallbacks."""

import io
import os
import re
from pathlib import Path
from rich.console import Console

from runport.tui.banner import (
    APP_SUBTITLE,
    APP_TITLE,
    APP_VERSION,
    CLI_WORDMARK,
    RUNPORT_EMBLEM,
    RUNPORT_EMBLEM_LINES,
    RUNPORT_EMBLEM_SOLID,
    RUNPORT_EMBLEM_SOLID_LINES,
    detect_image_protocol,
    encode_iterm2,
    encode_kitty,
    get_logo_bytes,
    get_logo_path,
    is_logo_available,
    render_official_logo,
)
from runport.tui.components import RunportLogo
from runport.tui.welcome import WelcomeScreen, _should_show_emblem


def _clean_ansi(text: str) -> str:
    """Strips standard ANSI formatting while preserving raw text."""
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b_[^\x1b]*\x1b\\", "", text)


def test_official_logo_asset_packaged_and_available():
    """Assert official Runport emblem PNG asset exists, is non-empty, and has PNG signature."""
    assert is_logo_available() is True
    data = get_logo_bytes()
    assert data is not None
    assert len(data) > 1000
    # PNG Magic bytes: \x89PNG\r\n\x1a\n
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_asset_path_resolution():
    """Assert get_logo_path resolves to an existing file ending with .png."""
    path = get_logo_path()
    assert path is not None
    assert isinstance(path, Path)
    assert path.is_file()
    assert path.name == "runport-emblem.png"


def test_no_dependency_on_cwd(tmp_path, monkeypatch):
    """Assert logo path resolution and byte reading work from an arbitrary isolated directory."""
    monkeypatch.chdir(tmp_path)
    assert os.getcwd() == str(tmp_path)

    # Must resolve via packaged resources or module relative path, not cwd
    resolved = get_logo_path()
    assert resolved is not None
    assert resolved.is_file()

    bytes_read = get_logo_bytes()
    assert bytes_read is not None and bytes_read[:8] == b"\x89PNG\r\n\x1a\n"


def test_official_terminal_emblem_constants_dimensions():
    """Assert official terminal emblem lines are non-empty and uniform in column width."""
    assert len(RUNPORT_EMBLEM_LINES) == 27
    assert all(len(line) == 64 for line in RUNPORT_EMBLEM_LINES)
    assert len(RUNPORT_EMBLEM_SOLID_LINES) == 31
    assert all(len(line) == 72 for line in RUNPORT_EMBLEM_SOLID_LINES)
    assert len(RUNPORT_EMBLEM) > 0
    assert len(RUNPORT_EMBLEM_SOLID) > 0


def test_terminal_image_protocol_detection(monkeypatch):
    """Assert detect_image_protocol accurately detects terminal emulator capabilities."""
    monkeypatch.delenv("RUNPORT_IMAGE_PROTOCOL", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    # 1. macOS Terminal (Apple_Terminal) explicitly does NOT support inline graphics protocols
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert detect_image_protocol() is None

    # 2. iTerm2 supports iterm2 protocol
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    assert detect_image_protocol() == "iterm2"

    # 3. WezTerm supports iterm2 protocol
    monkeypatch.setenv("TERM_PROGRAM", "WezTerm")
    assert detect_image_protocol() == "iterm2"

    # 4. VS Code integrated terminal supports iterm2 protocol
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    assert detect_image_protocol() == "iterm2"

    # 5. Ghostty supports kitty graphics protocol
    monkeypatch.setenv("TERM_PROGRAM", "ghostty")
    assert detect_image_protocol() == "kitty"

    # 6. Kitty terminal supports kitty graphics protocol
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.setenv("KITTY_WINDOW_ID", "1")
    assert detect_image_protocol() == "kitty"

    # 7. NO_COLOR disables image protocols
    monkeypatch.setenv("NO_COLOR", "1")
    assert detect_image_protocol() is None
    monkeypatch.delenv("NO_COLOR", raising=False)

    # 8. TERM=dumb disables image protocols
    monkeypatch.setenv("TERM", "dumb")
    assert detect_image_protocol() is None
    monkeypatch.setenv("TERM", "xterm-256color")

    # 9. Explicit override takes precedence
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "iterm2")
    assert detect_image_protocol() == "iterm2"
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "kitty")
    assert detect_image_protocol() == "kitty"
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "none")
    assert detect_image_protocol() is None


def test_iterm2_and_kitty_encoding():
    """Assert iTerm2 OSC 1337 and Kitty APC chunked encoding formatting."""
    dummy_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 5000

    iterm_seq = encode_iterm2(dummy_png, rows=6)
    assert iterm_seq.startswith("\033]1337;File=inline=1;height=6;preserveAspectRatio=1:")
    assert iterm_seq.endswith("\a")

    kitty_seq = encode_kitty(dummy_png, rows=6)
    assert kitty_seq.startswith("\033_Ga=T,f=100,r=6,m=1;")
    assert "\033_Gm=0;" in kitty_seq
    assert kitty_seq.endswith("\033\\")


def test_welcome_fallback_on_macos_terminal(monkeypatch):
    """Assert macOS Terminal (Apple_Terminal) uses clean terminal emblem fallback and zero corrupted image escapes."""
    monkeypatch.delenv("RUNPORT_IMAGE_PROTOCOL", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")

    buf = io.StringIO()
    console = Console(file=buf, width=100, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    raw = buf.getvalue()
    plain = _clean_ansi(raw)

    # Must NOT emit raw image escape codes
    assert "\033]1337" not in raw
    assert "\033_G" not in raw

    # In 100x50 terminal without image support, it renders the official terminal art emblem
    assert any(0x2800 <= ord(c) <= 0x28FF for c in raw)

    # Must contain official wordmark and welcome hierarchy
    assert "RUNPORT CLI" in plain
    assert "Welcome to Runport" in plain
    assert "The universal open-source LLM, prompt, and workflow benchmarking platform." in plain
    assert "Runtime" in plain
    assert "Workspace" in plain


def test_welcome_renders_image_when_supported(monkeypatch):
    """Assert welcome screen renders actual image escape code when terminal supports it."""
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "iterm2")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    buf = io.StringIO()
    console = Console(file=buf, width=100, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    raw = buf.getvalue()
    plain = _clean_ansi(raw)

    # Must contain iTerm2 inline image sequence
    assert "\033]1337;File=inline=1" in raw
    assert "height=6" in raw
    assert "preserveAspectRatio=1" in raw

    # Must also contain the text hierarchy
    assert "RUNPORT CLI" in plain
    assert "Welcome to Runport" in plain


def test_welcome_renders_kitty_when_supported(monkeypatch):
    """Assert welcome screen renders Kitty APC graphics escape sequence when supported."""
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "kitty")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    buf = io.StringIO()
    console = Console(file=buf, width=100, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    raw = buf.getvalue()
    plain = _clean_ansi(raw)

    # Must contain Kitty graphics protocol sequence
    assert "\033_Ga=T,f=100,r=6" in raw
    assert "RUNPORT CLI" in plain


def test_graceful_fallback_when_asset_missing(monkeypatch):
    """Assert graceful fallback to typographic header when logo asset is unreadable or missing."""
    import runport.tui.logo as logo_mod

    monkeypatch.setattr(logo_mod, "get_logo_bytes", lambda: None)
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "iterm2")

    buf = io.StringIO()
    console = Console(file=buf, width=100, height=50, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    raw = buf.getvalue()
    plain = _clean_ansi(raw)

    # Gracefully falls back: no escape sequence, but welcome layout intact
    assert "\033]1337" not in raw
    assert "RUNPORT CLI" in plain
    assert "Welcome to Runport" in plain


def test_compact_terminal_suppresses_logo(monkeypatch):
    """Assert compact viewports (< 28 rows) cleanly suppress both image and emblem logo."""
    monkeypatch.setenv("RUNPORT_IMAGE_PROTOCOL", "iterm2")

    buf = io.StringIO()
    console = Console(file=buf, width=100, height=24, force_terminal=True)
    screen = WelcomeScreen(console=console)
    screen.render(clear=False)
    raw = buf.getvalue()

    # Image and Braille emblem are suppressed in tight viewports
    assert "\033]1337" not in raw
    assert not any(0x2800 <= ord(c) <= 0x28FF for c in raw)
    assert "RUNPORT CLI" in raw
