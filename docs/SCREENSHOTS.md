# Terminal Screenshot Generation Guide

This document describes how to deterministically regenerate the terminal screenshot assets stored in `assets/readme/`:

- `assets/readme/terminal-welcome.png`: Launcher welcome screen (`uv run runport` or `runport welcome`).
- `assets/readme/terminal-dashboard.png`: TUI dashboard (`uv run runport ui`) showing an evaluation run with provenance `REPLAYED` and `$0.00` spend.

---

## Prerequisites

- Python 3.11+ with project dependencies synced (`uv sync --extra dev`)
- Headless Chrome (`/Applications/Google Chrome.app` on macOS or `google-chrome` on Linux)
- Pillow (`PIL`)

---

## Deterministic Generation Procedure

Both screenshots are captured using Rich's built-in SVG recording console (`Console(record=True)` + `export_svg`), followed by headless browser rendering to guarantee:
1. Zero personal paths (`/Users/...`), usernames, or hostnames.
2. Zero live API keys or live inference spend.
3. High-resolution typography (Fira Code) with standard terminal window chrome (rounded corners and window buttons).
4. Transparent window background.

### Script

Run the following command from the repository root:

```bash
uv run python -c "
import os
import subprocess
from PIL import Image
from rich.console import Console
from runport.tui.welcome import WelcomeScreen
from runport.tui.app import WorkbenchTUI

os.makedirs('assets/readme', exist_ok=True)
chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# 1. Welcome Screen
console_welcome = Console(record=True, width=120)
ws = WelcomeScreen(console=console_welcome)
console_welcome.print(ws._build())
svg_welcome = console_welcome.export_svg(title='runport — welcome')
html_welcome = f'''<!DOCTYPE html>
<html>
<head><meta charset=\"utf-8\"><style>
* {{ margin: 0; padding: 0; }}
body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
svg {{ width: 994px; height: 1270px; display: block; }}
</style></head>
<body>{svg_welcome}</body>
</html>'''

with open('/tmp/welcome.html', 'w') as f:
    f.write(html_welcome)

subprocess.run([
    chrome, '--headless=new', '--disable-gpu', '--user-data-dir=/tmp/cprofile_w',
    '--window-size=1040,1320', '--hide-scrollbars', '--default-background-color=00000000',
    '--screenshot=/tmp/welcome_raw.png',
    '/tmp/welcome.html'
], check=True)

im_w = Image.open('/tmp/welcome_raw.png')
im_w.crop(im_w.getbbox()).save('assets/readme/terminal-welcome.png')

# 2. Evaluations Dashboard
console_dash = Console(record=True, width=160, height=45)
tui = WorkbenchTUI(console=console_dash)
tui.goto('evaluations')
console_dash.print(tui.build_layout())
svg_dash = console_dash.export_svg(title='runport — tui dashboard')
html_dash = f'''<!DOCTYPE html>
<html>
<head><meta charset=\"utf-8\"><style>
* {{ margin: 0; padding: 0; }}
body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
svg {{ width: 1970px; height: 1148px; display: block; }}
</style></head>
<body>{svg_dash}</body>
</html>'''

with open('/tmp/dashboard.html', 'w') as f:
    f.write(html_dash)

subprocess.run([
    chrome, '--headless=new', '--disable-gpu', '--user-data-dir=/tmp/cprofile_d',
    '--window-size=2000,1200', '--hide-scrollbars', '--default-background-color=00000000',
    '--screenshot=/tmp/dash_raw.png',
    '/tmp/dashboard.html'
], check=True)

im_d = Image.open('/tmp/dash_raw.png')
im_d.crop(im_d.getbbox()).save('assets/readme/terminal-dashboard.png')

print('Regenerated assets/readme/terminal-welcome.png and assets/readme/terminal-dashboard.png')
"
```
