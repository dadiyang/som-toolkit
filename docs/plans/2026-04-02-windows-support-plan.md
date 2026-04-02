# Windows Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all platform-specific tools (xdotool/cliclick/osascript/scrot/screencapture) with pyautogui, enabling Windows support and simplifying codebase.

**Architecture:** Each tool's platform if/elif branches get replaced with pyautogui calls. macOS Cmd vs Ctrl/Win key mapping handled at call sites. som-server daemon uses subprocess.Popen on Windows, keeps os.fork on Unix.

**Tech Stack:** pyautogui, pyperclip, Pillow (already present)

---

### Task 1: Create feature branch and install dependencies

**Files:**
- Modify: `install.sh`

**Step 1: Create feature branch**

```bash
git checkout -b feature/windows-support
```

**Step 2: Install pyautogui and pyperclip in current environment**

```bash
pip install pyautogui pyperclip
```

**Step 3: Verify imports work**

```bash
python3 -c "import pyautogui; print(pyautogui.size())"
python3 -c "import pyperclip; pyperclip.copy('test'); print(pyperclip.paste())"
```

**Step 4: Update install.sh — replace platform-specific deps with pyautogui**

Replace the "安装平台特定的操控工具" section (lines 52-76) with:

```bash
# 5. 安装平台操控工具（统一用 pyautogui，三平台通用）
echo "Installing UI automation tools..."
pip install pyautogui pyperclip

if [[ "$(uname)" == "Linux" ]]; then
    # pyautogui on Linux needs xdotool and scrot as backends
    if ! command -v xdotool &>/dev/null; then
        echo "WARN: xdotool not found. Install with: sudo apt install xdotool"
    fi
    if ! command -v scrot &>/dev/null; then
        echo "WARN: scrot not found. Install with: sudo apt install scrot"
    fi
fi
```

**Step 5: Commit**

```bash
git add install.sh
git commit -m "feat: replace platform deps with pyautogui in install.sh"
```

---

### Task 2: Rewrite som-annotate — screenshot and screen size

**Files:**
- Modify: `som-annotate` (functions `take_screenshot` and `get_screen_size`)

**Step 1: Rewrite `take_screenshot` (replace lines 27-70)**

```python
def take_screenshot(output_path, max_width=1920):
    """Take a screenshot, auto-resize and compress for efficiency."""
    import pyautogui
    from PIL import Image as PILImg

    if os.path.exists(output_path):
        os.remove(output_path)

    img = pyautogui.screenshot()

    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), PILImg.LANCZOS)

    if output_path.lower().endswith(('.jpg', '.jpeg')):
        img.save(output_path, quality=85)
    else:
        img.save(output_path)

    if not os.path.exists(output_path):
        sys.exit(f"ERROR: Screenshot failed: {output_path}")
```

**Step 2: Rewrite `get_screen_size` (replace lines 73-85)**

```python
def get_screen_size():
    """Get LOGICAL screen size (what mouse coordinates use)."""
    import pyautogui
    return pyautogui.size()
```

**Step 3: Clean up imports — remove `platform` and `subprocess` if no longer used elsewhere in the file**

`som-annotate` still uses `subprocess` in `load_parser` path (no) and uses `platform` nowhere else after this change. Check: `try_server` uses `urllib`, no platform. `parse_screenshot` uses PIL only. So remove `import platform` and `import subprocess`.

Actually — `load_parser` calls `build_parser_config` which is in som_common.py, no subprocess needed. Remove both `import platform` and `import subprocess` from som-annotate.

**Step 4: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('./som-annotate', doraise=True)"
```

**Step 5: Commit**

```bash
git add som-annotate
git commit -m "feat: som-annotate use pyautogui for screenshot and screen size"
```

---

### Task 3: Rewrite som-click — all mouse operations

**Files:**
- Modify: `som-click`

**Step 1: Replace the entire file body between imports and `main()`**

Delete: `_cliclick_cache`, `_cliclick_available()`, `_macos_mouse_events()`, `_CLICLICK_MOD`, `_XDOTOOL_MOD`, `click_at()`, `double_click_at()`, `right_click_at()`.

Replace with:

```python
import pyautogui

# pyautogui safety: disable the fail-safe (move to corner to abort)
# RPA agents move mouse programmatically, fail-safe would interrupt
pyautogui.FAILSAFE = False
# Remove default pause between actions for speed
pyautogui.PAUSE = 0.05


# macOS uses 'command', Windows/Linux use 'ctrl' for browser shortcuts
_MOD_MAP = {
    "cmd": "command" if platform.system() == "Darwin" else "win",
    "ctrl": "ctrl",
    "shift": "shift",
    "alt": "alt",
}


def _parse_modifiers(modifier_str):
    """Parse comma-separated modifier string into pyautogui key names."""
    if not modifier_str:
        return []
    mods = [m.strip().lower() for m in modifier_str.split(",")]
    valid = {"cmd", "shift", "alt", "ctrl"}
    for m in mods:
        if m not in valid:
            print(f"ERROR: Unknown modifier '{m}'. Valid: {', '.join(sorted(valid))}", file=sys.stderr)
            sys.exit(1)
    return [_MOD_MAP[m] for m in mods]


def click_at(x, y, modifiers=None):
    x, y = int(x), int(y)
    mods = modifiers or []
    for m in mods:
        pyautogui.keyDown(m)
    pyautogui.click(x, y)
    for m in mods:
        pyautogui.keyUp(m)


def double_click_at(x, y):
    pyautogui.doubleClick(int(x), int(y))


def right_click_at(x, y):
    pyautogui.rightClick(int(x), int(y))
```

**Step 2: Clean up imports — remove `subprocess`, `time`. Keep `platform` (for _MOD_MAP). Remove unused `json`.**

**Step 3: Update `main()` — modifiers now return pyautogui key names directly**

The `_parse_modifiers` now returns mapped names, so `main()` stays the same except the output string. Change the mod_str line:

```python
    # For display, use the original modifier names, not mapped ones
    mod_str = f" [{args.modifier}]" if args.modifier else ""
    print(f"OK ({x},{y}){mod_str}")
```

**Step 4: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('./som-click', doraise=True)"
```

**Step 5: Commit**

```bash
git add som-click
git commit -m "feat: som-click use pyautogui for all mouse operations"
```

---

### Task 4: Rewrite som-type — clipboard and keyboard

**Files:**
- Modify: `som-type`

**Step 1: Replace `set_clipboard`, `type_text`, `press_key`**

```python
import pyautogui
import pyperclip

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# Paste shortcut differs per platform
_PASTE_MOD = "command" if platform.system() == "Darwin" else "ctrl"
_SELECT_ALL_MOD = _PASTE_MOD


def set_clipboard(text):
    pyperclip.copy(text)


def type_text(text):
    set_clipboard(text)
    time.sleep(0.1)
    pyautogui.hotkey(_PASTE_MOD, 'v')


def press_key(key_combo):
    """Press a key combination like 'ctrl+a' or 'Return'."""
    parts = key_combo.lower().split("+")
    if len(parts) == 1:
        # Single key
        key = parts[0]
        key_map = {"return": "enter", "escape": "esc", "delete": "backspace",
                   "page_down": "pagedown", "page_up": "pageup"}
        pyautogui.press(key_map.get(key, key))
    else:
        # Combo: remap modifier names
        mod_map = {"cmd": "command" if platform.system() == "Darwin" else "ctrl",
                   "ctrl": "ctrl", "alt": "alt", "shift": "shift"}
        keys = [mod_map.get(k, k) for k in parts]
        pyautogui.hotkey(*keys)
```

**Step 2: Update `main()` — the clear logic**

Replace:
```python
    if args.clear:
        if platform.system() == "Darwin":
            press_key("cmd+a")
        else:
            press_key("ctrl+a")
```

With:
```python
    if args.clear:
        pyautogui.hotkey(_SELECT_ALL_MOD, 'a')
```

**Step 3: Clean up imports — remove `subprocess`. Keep `platform` (for _PASTE_MOD), `time`.**

**Step 4: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('./som-type', doraise=True)"
```

**Step 5: Commit**

```bash
git add som-type
git commit -m "feat: som-type use pyautogui/pyperclip for keyboard and clipboard"
```

---

### Task 5: Rewrite som-scroll — page and fine scrolling

**Files:**
- Modify: `som-scroll`

**Step 1: Replace `scroll()` function**

```python
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

PIXELS_PER_LINE = 100
# pyautogui.scroll(n): positive = up, negative = down
# 1 scroll unit ≈ 3 text lines ≈ ~45px on most platforms
PIXELS_PER_SCROLL_UNIT = 45


def scroll(direction, count=1, lines=0):
    """Scroll the page.

    lines=0 (default): page scroll (Page_Down/Page_Up via keypress)
    lines=N: fine scroll by N * 100px using mouse wheel.
    """
    if direction in ("top", "bottom"):
        pyautogui.press("home" if direction == "top" else "end")
        time.sleep(0.5)
        return

    if lines > 0:
        # Fine scroll: convert pixels to scroll units
        pixels = lines * PIXELS_PER_LINE
        units = max(1, pixels // PIXELS_PER_SCROLL_UNIT)
        sign = -1 if direction == "down" else 1
        for _ in range(count):
            pyautogui.scroll(sign * units)
            time.sleep(0.3)
    else:
        # Full page scroll via keyboard
        key = "pagedown" if direction == "down" else "pageup"
        for _ in range(count):
            pyautogui.press(key)
            time.sleep(0.5)
```

**Step 2: Clean up imports — remove `platform`, `subprocess`. Keep `time`.**

**Step 3: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('./som-scroll', doraise=True)"
```

**Step 4: Commit**

```bash
git add som-scroll
git commit -m "feat: som-scroll use pyautogui for scrolling"
```

---

### Task 6: Rewrite som-tab — browser tab management

**Files:**
- Modify: `som-tab`

**Step 1: Replace `press_key()` and update `main()` actions**

```python
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# Browser tab shortcuts use Cmd on macOS, Ctrl on Windows/Linux
_TAB_MOD = "command" if platform.system() == "Darwin" else "ctrl"


def main():
    ap = argparse.ArgumentParser(description="Browser tab management")
    ap.add_argument("action", help="next, prev, close, new, last, or tab number (1-9)")
    args = ap.parse_args()

    action = args.action.lower()

    if action == "next":
        pyautogui.hotkey(_TAB_MOD, "tab")
        print("Switched to next tab")
    elif action == "prev":
        pyautogui.hotkey(_TAB_MOD, "shift", "tab")
        print("Switched to previous tab")
    elif action == "close":
        pyautogui.hotkey(_TAB_MOD, "w")
        print("Closed current tab")
    elif action == "new":
        pyautogui.hotkey(_TAB_MOD, "t")
        print("Opened new tab")
    elif action == "last":
        pyautogui.hotkey(_TAB_MOD, "9")
        print("Switched to last tab")
    elif action.isdigit() and 1 <= int(action) <= 9:
        pyautogui.hotkey(_TAB_MOD, action)
        print(f"Switched to tab {action}")
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        ap.print_help()
        return 1

    time.sleep(0.5)
    return 0
```

**Step 2: Clean up imports — remove `subprocess`. Keep `platform`, `time`, `argparse`, `sys`.**

**Step 3: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('./som-tab', doraise=True)"
```

**Step 4: Commit**

```bash
git add som-tab
git commit -m "feat: som-tab use pyautogui for tab management"
```

---

### Task 7: som-server — Windows-compatible daemon mode

**Files:**
- Modify: `som-server` (only the daemon section in `main()` and `get_pid`/`stop`)

**Step 1: Replace the daemon section (lines 194-215) with cross-platform version**

```python
    elif args.action == "start":
        pid = get_pid()
        if pid:
            print(f"Already running (PID {pid})")
            return 1

        if args.foreground:
            start_server(args.port, use_caption=not args.no_caption)
        else:
            if sys.platform == "win32":
                # Windows: use subprocess with DETACHED_PROCESS
                import subprocess as sp
                cmd = [sys.executable, os.path.abspath(__file__),
                       "start", "--foreground", "--port", str(args.port)]
                if args.no_caption:
                    cmd.append("--no-caption")
                log_fd = open(LOG_PATH, "a")
                proc = sp.Popen(
                    cmd, stdout=log_fd, stderr=log_fd,
                    creationflags=sp.DETACHED_PROCESS | sp.CREATE_NEW_PROCESS_GROUP,
                )
                log_fd.close()
                child_pid = proc.pid
            else:
                # Unix: fork + setsid
                child_pid = os.fork()
                if child_pid == 0:
                    os.setsid()
                    log_fd = open(LOG_PATH, "a")
                    os.dup2(log_fd.fileno(), sys.stdout.fileno())
                    os.dup2(log_fd.fileno(), sys.stderr.fileno())
                    log_fd.close()
                    start_server(args.port, use_caption=not args.no_caption)

            print(f"Starting som-server (PID {child_pid})...")
            for _ in range(10):
                time.sleep(0.5)
                if not _pid_alive(child_pid):
                    print(f"ERROR: Server process exited. Check log: {LOG_PATH}")
                    return 1
            print(f"Server process running (PID {child_pid}). Model loading may still be in progress.")
            print(f"Log: {LOG_PATH}")
        return 0
```

**Step 2: Add `_pid_alive` helper and fix `stop` for Windows**

```python
def _pid_alive(pid):
    """Check if a process is alive (cross-platform)."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
```

**Step 3: Fix `get_pid` to use `_pid_alive`**

Replace `os.kill(pid, 0)` call in `get_pid` with `_pid_alive(pid)`.

**Step 4: Fix `stop` action for Windows**

Replace `os.kill(pid, signal.SIGTERM)` with:
```python
    if sys.platform == "win32":
        import subprocess as sp
        sp.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)
```

**Step 5: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('./som-server', doraise=True)"
```

**Step 6: Commit**

```bash
git add som-server
git commit -m "feat: som-server cross-platform daemon (Windows subprocess, Unix fork)"
```

---

### Task 8: Update docs — CLAUDE.md and skill file

**Files:**
- Modify: `CLAUDE.md`
- Modify: `skill-som-ui-automation.md`

**Step 1: Update CLAUDE.md environment variables section**

Replace the Linux-only env vars block with cross-platform version:

```markdown
环境变量：
```bash
# Linux 必须设置 DISPLAY
export DISPLAY=:10.0              # Linux only
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export CUDA_VISIBLE_DEVICES=""    # CPU 模式，有 GPU 可去掉
```
```

**Step 2: Update skill file — platform support note**

Add to skill-som-ui-automation.md prerequisites section:

```markdown
支持平台：macOS / Linux / Windows（通过 pyautogui 统一三平台）
```

**Step 3: Commit**

```bash
git add CLAUDE.md skill-som-ui-automation.md
git commit -m "docs: update for Windows support"
```

---

### Task 9: Full integration verification on Mac

**Not code — manual verification by user.**

在 Mac 上运行完整操作循环：

1. `som-server start --no-caption`
2. 打开浏览器，导航到任意网页
3. `som-annotate -o page.jpg -j page.json -q --wait 2 --no-caption`
4. `som-find --summary -j page.json`
5. `som-find "链接文字" --first --cmd -j page.json`
6. `som-click <编号> -j page.json`
7. `som-click <编号> -m cmd -j page.json` （验证新标签打开）
8. `som-scroll down --lines 3`
9. `som-scroll down`
10. `som-type <编号> "hello" -j page.json`
11. `som-tab next` / `som-tab close`

全部通过后：

```bash
git checkout main
git merge feature/windows-support
git push origin main
```
