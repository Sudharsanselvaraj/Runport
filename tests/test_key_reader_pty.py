"""A key typed between two polls of KeyReader.read_key must not be discarded when the reader re-enters raw mode."""

import os
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pty = pytest.importorskip("pty")
pytest.importorskip("termios")

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX pty")

# Poll once (nothing typed, so it times out and restores cooked mode), signal readiness, wait, then poll again.
CHILD = """
import sys, time
from runport.tui.input import KeyReader
r = KeyReader()
print("first:" + r.read_key(timeout=0.2), flush=True)
print("READY", flush=True)
time.sleep(1.0)
print("second:" + r.read_key(timeout=5), flush=True)
"""


def test_a_key_typed_while_the_reader_is_between_polls_is_still_read():
    master, slave = pty.openpty()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.Popen([sys.executable, "-c", CHILD], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    out = b""
    deadline = time.time() + 30
    sent = False
    while time.time() < deadline and proc.poll() is None:
        r, _, _ = select.select([master], [], [], 0.05)
        if r:
            try:
                out += os.read(master, 4096)
            except OSError:
                break
        if not sent and b"READY" in out:
            os.write(master, b"3")  # arrives while the terminal is back in cooked mode
            sent = True
    try:
        while True:
            r, _, _ = select.select([master], [], [], 0.2)
            if not r:
                break
            chunk = os.read(master, 4096)
            if not chunk:
                break
            out += chunk
    except OSError:
        pass
    proc.wait(timeout=10)
    os.close(master)
    text = out.decode("utf-8", errors="replace")
    assert "first:TIMEOUT" in text
    assert "second:3" in text, text
