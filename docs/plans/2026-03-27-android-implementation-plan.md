# Android OmniParser 工具集实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 som-toolkit 添加 7 个 som-android-* 工具，通过 ADB 截图 + OmniParser 检测 + ADB 动作执行，实现对 Android 手机 App 的视觉自动化操作。

**Architecture:** 每个工具是独立 Python 脚本，ADB 设备发现逻辑内联（不共享模块）。检测层复用桌面端 som-server（localhost:8765）。JSON 元素格式与桌面端完全一致。

**Tech Stack:** Python 3, ADB, OmniParser, PIL, ADB Keyboard (中文输入)

**设计文档:** `docs/plans/2026-03-27-android-omniparser-design.md`

**测试设备:** Redmi, Android 15, 720x1640, USB 连接, serial=VOCIW8BMSKUG69RG

**前置条件:** som-server 已启动（`som-server status` 确认）

---

### Task 1: som-android-key（最简单，验证 ADB 通路）

**Files:**
- Create: `som-toolkit/som-android-key`

**Step 1: 创建 som-android-key**

```python
#!/usr/bin/env python3
"""
som-android-key: Android 按键操作
用法:
    som-android-key back          # 返回
    som-android-key home          # Home
    som-android-key recent        # 最近任务
    som-android-key enter         # 确认
    som-android-key delete        # 删除
    som-android-key power         # 电源键
"""
import argparse
import os
import subprocess
import sys


KEY_MAP = {
    "back": "KEYCODE_BACK",
    "home": "KEYCODE_HOME",
    "recent": "KEYCODE_APP_SWITCH",
    "enter": "KEYCODE_ENTER",
    "delete": "KEYCODE_DEL",
    "power": "KEYCODE_POWER",
    "tab": "KEYCODE_TAB",
    "escape": "KEYCODE_ESCAPE",
    "up": "KEYCODE_DPAD_UP",
    "down": "KEYCODE_DPAD_DOWN",
    "left": "KEYCODE_DPAD_LEFT",
    "right": "KEYCODE_DPAD_RIGHT",
    "volume_up": "KEYCODE_VOLUME_UP",
    "volume_down": "KEYCODE_VOLUME_DOWN",
    "menu": "KEYCODE_MENU",
}


def get_device():
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def main():
    ap = argparse.ArgumentParser(description="Android key events")
    ap.add_argument("key", nargs="?", help=f"Key name: {', '.join(KEY_MAP.keys())}")
    ap.add_argument("--list", action="store_true", help="List available keys")
    ap.add_argument("--keycode", help="Raw KEYCODE_* (e.g. KEYCODE_CAMERA)")
    args = ap.parse_args()

    if args.list:
        for name, code in KEY_MAP.items():
            print(f"  {name:15s} → {code}")
        return 0

    if args.keycode:
        keycode = args.keycode
    elif args.key:
        key = args.key.lower()
        if key not in KEY_MAP:
            print(f"ERROR: Unknown key '{key}'. Use --list to see available keys.", file=sys.stderr)
            return 1
        keycode = KEY_MAP[key]
    else:
        ap.print_help()
        return 1

    adb("shell", "input", "keyevent", keycode)
    print(f"Key: {keycode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: 设置可执行权限并测试**

```bash
chmod +x som-toolkit/som-android-key
```

Run: `python3 som-toolkit/som-android-key --list`
Expected: 打印所有按键名称和 KEYCODE

Run: `python3 som-toolkit/som-android-key back`
Expected: 手机执行返回操作，输出 "Key: KEYCODE_BACK"

Run: `python3 som-toolkit/som-android-key home`
Expected: 手机回到桌面

**Step 3: Commit**

```bash
git add som-toolkit/som-android-key
git commit -m "feat: add som-android-key for Android key events"
```

---

### Task 2: som-android-app

**Files:**
- Create: `som-toolkit/som-android-app`

**Step 1: 创建 som-android-app**

```python
#!/usr/bin/env python3
"""
som-android-app: Android App 启动和切换
用法:
    som-android-app xianyu                  # 别名启动
    som-android-app com.taobao.idlefish     # 包名启动
    som-android-app --list                  # 列出别名
    som-android-app --current               # 当前前台 App
"""
import argparse
import os
import subprocess
import sys


APP_ALIASES = {
    "xianyu": "com.taobao.idlefish",
    "xhs": "com.xingin.xhs",
    "weibo": "com.sina.weibo",
    "zhihu": "com.zhihu.android",
    "wechat": "com.tencent.mm",
    "alipay": "com.eg.android.AlipayGphone",
    "taobao": "com.taobao.taobao",
    "douyin": "com.ss.android.ugc.aweme",
    "settings": "com.android.settings",
    "chrome": "com.android.chrome",
}


def get_device():
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def get_current_app():
    result = adb("shell", "dumpsys", "activity", "recents")
    for line in result.stdout.split("\n"):
        if "realActivity=" in line:
            # Extract package/activity from realActivity=com.foo/.BarActivity
            part = line.split("realActivity=")[1].split()[0]
            package = part.split("/")[0]
            return package
    return "unknown"


def main():
    ap = argparse.ArgumentParser(description="Android app launcher")
    ap.add_argument("app", nargs="?", help="App alias or package name")
    ap.add_argument("--list", action="store_true", help="List known app aliases")
    ap.add_argument("--current", action="store_true", help="Show current foreground app")
    args = ap.parse_args()

    if args.list:
        for alias, pkg in sorted(APP_ALIASES.items()):
            print(f"  {alias:12s} → {pkg}")
        return 0

    if args.current:
        pkg = get_current_app()
        print(f"Current: {pkg}")
        return 0

    if not args.app:
        ap.print_help()
        return 1

    # Resolve alias
    package = APP_ALIASES.get(args.app.lower(), args.app)

    # Launch via monkey (most reliable, doesn't need activity name)
    result = adb("shell", "monkey", "-p", package,
                 "-c", "android.intent.category.LAUNCHER", "1")
    if "No activities found" in result.stdout:
        print(f"ERROR: App not installed or no launcher activity: {package}", file=sys.stderr)
        return 1

    print(f"Launched: {package}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: 测试**

```bash
chmod +x som-toolkit/som-android-app
```

Run: `python3 som-toolkit/som-android-app --list`
Expected: 打印别名表

Run: `python3 som-toolkit/som-android-app --current`
Expected: 打印当前前台 App 包名

Run: `python3 som-toolkit/som-android-app xianyu`
Expected: 手机打开闲鱼，输出 "Launched: com.taobao.idlefish"

Run: `python3 som-toolkit/som-android-key home` (回到桌面)

**Step 3: Commit**

```bash
git add som-toolkit/som-android-app
git commit -m "feat: add som-android-app for launching Android apps"
```

---

### Task 3: som-android-click

**Files:**
- Create: `som-toolkit/som-android-click`

**Step 1: 创建 som-android-click**

```python
#!/usr/bin/env python3
"""
som-android-click: 根据 SoM 编号点击 Android 屏幕元素
用法:
    som-android-click 42                          # 点击编号 42
    som-android-click 42 --json som_elements.json # 指定元素文件
    som-android-click --xy 360,820                # 直接坐标
    som-android-click 42 --long                   # 长按
    som-android-click 42 --double                 # 双击
"""
import argparse
import json
import os
import subprocess
import sys
import time


def get_device():
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def tap(x, y):
    adb("shell", "input", "tap", str(x), str(y))


def long_press(x, y, duration_ms=800):
    adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms))


def double_tap(x, y):
    tap(x, y)
    time.sleep(0.1)
    tap(x, y)


def main():
    ap = argparse.ArgumentParser(description="Click Android element by SoM index")
    ap.add_argument("index", nargs="?", type=int, help="Element index to click")
    ap.add_argument("--json", "-j", default="som_elements.json", help="Elements JSON path")
    ap.add_argument("--xy", help="Direct coordinates x,y")
    ap.add_argument("--long", action="store_true", help="Long press (~800ms)")
    ap.add_argument("--double", action="store_true", help="Double tap")
    args = ap.parse_args()

    if args.xy:
        x, y = map(int, args.xy.split(","))
    elif args.index is not None:
        if not os.path.exists(args.json):
            print(f"ERROR: {args.json} not found. Run som-android-annotate first.", file=sys.stderr)
            return 1
        with open(args.json) as f:
            elements = json.load(f)
        matches = [e for e in elements if e["index"] == args.index]
        if not matches:
            print(f"ERROR: Element [{args.index}] not found. Max index: {max(e['index'] for e in elements)}", file=sys.stderr)
            return 1
        elem = matches[0]
        x, y = elem["center_x"], elem["center_y"]
        content = elem.get("content", "")
        print(f'Clicking [{args.index}] at ({x},{y}) "{content}"', file=sys.stderr)
    else:
        ap.print_help()
        return 1

    if getattr(args, 'long'):
        long_press(x, y)
        print(f"Long press OK ({x},{y})")
    elif args.double:
        double_tap(x, y)
        print(f"Double tap OK ({x},{y})")
    else:
        tap(x, y)
        print(f"OK ({x},{y})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

注意：`--long` 是 Python 保留的 argparse 属性名冲突风险，用 `getattr(args, 'long')` 访问。

**Step 2: 测试**

```bash
chmod +x som-toolkit/som-android-click
```

先确保手机在桌面：`python3 som-toolkit/som-android-key home`

Run: `python3 som-toolkit/som-android-click --xy 360,820`
Expected: 手机屏幕在 (360,820) 位置被点击，输出 "OK (360,820)"

Run: `python3 som-toolkit/som-android-click --xy 360,820 --long`
Expected: 长按操作，输出 "Long press OK (360,820)"

**Step 3: Commit**

```bash
git add som-toolkit/som-android-click
git commit -m "feat: add som-android-click for tapping Android elements"
```

---

### Task 4: som-android-scroll

**Files:**
- Create: `som-toolkit/som-android-scroll`

**Step 1: 创建 som-android-scroll**

```python
#!/usr/bin/env python3
"""
som-android-scroll: Android 屏幕滑动
用法:
    som-android-scroll down              # 向下滑一屏
    som-android-scroll down --lines 3    # 精细滑 300px
    som-android-scroll up
    som-android-scroll left / right      # 横向滑动
    som-android-scroll top / bottom      # 滑到顶/底
"""
import argparse
import os
import subprocess
import sys
import time


PIXELS_PER_LINE = 100


def get_device():
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def get_screen_size():
    result = subprocess.run(["adb"] + get_device() + ["shell", "wm", "size"],
                            capture_output=True, text=True, check=True)
    # "Physical size: 720x1640"
    parts = result.stdout.strip().split()[-1].split("x")
    return int(parts[0]), int(parts[1])


def swipe(x1, y1, x2, y2, duration_ms=300):
    adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))


def main():
    ap = argparse.ArgumentParser(description="Android screen scroll")
    ap.add_argument("direction", choices=["down", "up", "left", "right", "top", "bottom"])
    ap.add_argument("-n", "--count", type=int, default=1, help="Number of scrolls")
    ap.add_argument("-l", "--lines", type=int, default=0,
                    help="Fine scroll N lines (1 line=100px). 0=full page swipe.")
    args = ap.parse_args()

    w, h = get_screen_size()
    cx, cy = w // 2, h // 2  # Screen center

    for _ in range(args.count):
        if args.direction == "top":
            # Swipe down from top (pull to top)
            for _ in range(10):
                swipe(cx, int(h * 0.25), cx, int(h * 0.75), 200)
                time.sleep(0.1)
        elif args.direction == "bottom":
            for _ in range(10):
                swipe(cx, int(h * 0.75), cx, int(h * 0.25), 200)
                time.sleep(0.1)
        elif args.direction in ("down", "up", "left", "right"):
            if args.lines > 0:
                pixels = args.lines * PIXELS_PER_LINE
            else:
                # Full page: swipe 50% of screen dimension
                pixels = h // 2 if args.direction in ("down", "up") else w // 2

            if args.direction == "down":
                swipe(cx, int(h * 0.65), cx, int(h * 0.65) - pixels, 300)
            elif args.direction == "up":
                swipe(cx, int(h * 0.35), cx, int(h * 0.35) + pixels, 300)
            elif args.direction == "left":
                swipe(int(w * 0.65), cy, int(w * 0.65) - pixels, cy, 300)
            elif args.direction == "right":
                swipe(int(w * 0.35), cy, int(w * 0.35) + pixels, cy, 300)

            time.sleep(0.3)

    mode = f"{args.lines} lines" if args.lines > 0 else "page"
    print(f"Scrolled {args.direction} x{args.count} ({mode})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: 测试**

```bash
chmod +x som-toolkit/som-android-scroll
```

先打开一个有内容的 App：`python3 som-toolkit/som-android-app xianyu`，等 3 秒。

Run: `python3 som-toolkit/som-android-scroll down`
Expected: 手机向下滑一屏

Run: `python3 som-toolkit/som-android-scroll up --lines 3`
Expected: 手机向上精细滑 300px

Run: `python3 som-toolkit/som-android-scroll top`
Expected: 手机滑到页面顶部

**Step 3: Commit**

```bash
git add som-toolkit/som-android-scroll
git commit -m "feat: add som-android-scroll for Android swipe scrolling"
```

---

### Task 5: som-android-type

**Files:**
- Create: `som-toolkit/som-android-type`

**Step 1: 创建 som-android-type**

```python
#!/usr/bin/env python3
"""
som-android-type: 点击元素后输入文字
用法:
    som-android-type 42 "你好" -j page.json     # 点击后输入
    som-android-type --text "你好"               # 直接输入（不点击）
    som-android-type 42 "hello" --clear         # 先清空再输入
    som-android-type --key enter                # 按键
"""
import argparse
import json
import os
import subprocess
import sys
import time


def get_device():
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def tap(x, y):
    adb("shell", "input", "tap", str(x), str(y))


def input_text(text):
    """Input text via ADB. Uses ADB Keyboard for non-ASCII (Chinese etc)."""
    if all(ord(c) < 128 for c in text):
        # ASCII: use input text (need to escape spaces and special chars)
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace("|", "\\|")
        adb("shell", "input", "text", escaped)
    else:
        # Non-ASCII: use ADB Keyboard broadcast
        adb("shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", text)


def clear_field():
    """Select all and delete."""
    # Move to end, select all, delete
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    time.sleep(0.1)
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_HOME", "--longpress")
    # Alternative: Ctrl+A equivalent
    # Some apps support it, some don't. Use triple-tap as fallback.
    time.sleep(0.1)
    adb("shell", "input", "keyevent", "KEYCODE_DEL")


def main():
    ap = argparse.ArgumentParser(description="Type text on Android element")
    ap.add_argument("index", nargs="?", type=int, help="Element index to click first")
    ap.add_argument("text", nargs="?", help="Text to type")
    ap.add_argument("--json", "-j", default="som_elements.json")
    ap.add_argument("--xy", help="Direct coordinates x,y")
    ap.add_argument("--text-only", dest="text_direct", help="Type text without clicking")
    ap.add_argument("--clear", action="store_true", help="Clear field first")
    ap.add_argument("--key", help="Press a key (e.g. enter, back, delete)")
    args = ap.parse_args()

    # Key-only mode (no click needed)
    if args.key and args.index is None and not args.xy:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run([sys.executable, os.path.join(script_dir, "som-android-key"), args.key], check=True)
        return 0

    # Direct text input without clicking
    if args.text_direct:
        input_text(args.text_direct)
        print(f'Typed "{args.text_direct}"')
        return 0

    # Determine click target
    if args.xy:
        x, y = map(int, args.xy.split(","))
    elif args.index is not None:
        if not os.path.exists(args.json):
            print(f"ERROR: {args.json} not found. Run som-android-annotate first.", file=sys.stderr)
            return 1
        with open(args.json) as f:
            elements = json.load(f)
        matches = [e for e in elements if e["index"] == args.index]
        if not matches:
            print(f"ERROR: Element [{args.index}] not found.", file=sys.stderr)
            return 1
        elem = matches[0]
        x, y = elem["center_x"], elem["center_y"]
    else:
        ap.print_help()
        return 1

    # Click
    tap(x, y)
    time.sleep(0.5)

    # Clear if requested
    if args.clear:
        clear_field()
        time.sleep(0.2)

    # Type or press key
    if args.key:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run([sys.executable, os.path.join(script_dir, "som-android-key"), args.key], check=True)
        print(f"Key: {args.key} at ({x},{y})")
    elif args.text:
        input_text(args.text)
        print(f'Typed "{args.text}" at ({x},{y})')
    else:
        print(f"Clicked ({x},{y})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: 测试**

```bash
chmod +x som-toolkit/som-android-type
```

打开设置 App 的搜索框做测试：
```bash
python3 som-toolkit/som-android-app settings
sleep 2
```

Run: `python3 som-toolkit/som-android-type --text-only "hello"`
Expected: 在当前焦点处输入 hello

Run: `python3 som-toolkit/som-android-type --text-only "你好"`
Expected: 通过 ADB Keyboard 输入中文"你好"

Run: `python3 som-toolkit/som-android-type --key enter`
Expected: 按回车键

**Step 3: Commit**

```bash
git add som-toolkit/som-android-type
git commit -m "feat: add som-android-type for Android text input"
```

---

### Task 6: som-android-annotate（核心工具）

**Files:**
- Create: `som-toolkit/som-android-annotate`

**Step 1: 创建 som-android-annotate**

```python
#!/usr/bin/env python3
"""
som-android-annotate: Android 截图 + OmniParser 标注 + 输出元素列表
用法:
    som-android-annotate                              # 标注手机屏幕
    som-android-annotate -o page.jpg -j page.json -q  # 指定输出
    som-android-annotate --caption                    # 开启 Florence-2 icon 描述
    som-android-annotate --screenshot existing.png    # 用已有截图
"""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_device():
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def adb_raw(*args):
    """ADB command returning raw bytes (for screencap)."""
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, check=True)


def take_screenshot(output_path):
    """Take screenshot via ADB screencap."""
    result = adb_raw("exec-out", "screencap", "-p")
    with open(output_path, "wb") as f:
        f.write(result.stdout)
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        sys.exit("ERROR: Screenshot failed. Check ADB connection.")


def get_screen_size():
    """Get phone physical resolution via wm size."""
    result = subprocess.run(["adb"] + get_device() + ["shell", "wm", "size"],
                            capture_output=True, text=True, check=True)
    parts = result.stdout.strip().split()[-1].split("x")
    return int(parts[0]), int(parts[1])


def try_server(image_path, screen_w, screen_h, use_caption=False, quiet=False):
    """Try som-server for fast parsing."""
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=2)
        if resp.read() != b"ok":
            return None
    except Exception:
        return None

    if not quiet:
        print("Using som-server (fast mode)...", file=sys.stderr)

    from PIL import Image as PILImage

    img = PILImage.open(image_path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    req_data = json.dumps({
        "image_base64": img_b64,
        "screen_w": screen_w,
        "screen_h": screen_h,
    }).encode()

    req = urllib.request.Request(
        "http://127.0.0.1:8765/parse",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=300)
    result = json.loads(resp.read())

    return result["labeled_image_base64"], result["elements"]


def find_omniparser():
    candidates = [
        os.environ.get("OMNIPARSER_DIR", ""),
        os.path.join(os.path.expanduser("~"), "data", "omniparser"),
        os.path.join(SCRIPT_DIR, "omniparser"),
        os.path.join(SCRIPT_DIR, "..", "OmniParser"),
        os.path.join(os.path.expanduser("~"), "OmniParser"),
    ]
    for path in candidates:
        if path and os.path.isfile(os.path.join(path, "util", "omniparser.py")):
            return path
    sys.exit("ERROR: OmniParser not found. Run install.sh first.")


def parse_local(image_path, screen_w, screen_h, use_caption=False, quiet=False):
    """Parse using local OmniParser (slow, fallback)."""
    omni_dir = find_omniparser()
    sys.path.insert(0, omni_dir)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    from util.omniparser import Omniparser
    from PIL import Image

    default_weights = os.path.join(os.path.expanduser("~"), "data", "models", "omniparser")
    weights_dir = os.environ.get("SOM_WEIGHTS_DIR", default_weights)
    if not os.path.isdir(os.path.join(weights_dir, "icon_detect")):
        legacy = os.path.join(omni_dir, "weights")
        if os.path.isdir(os.path.join(legacy, "icon_detect")):
            weights_dir = legacy

    config = {
        "som_model_path": os.path.join(weights_dir, "icon_detect", "model.pt"),
        "caption_model_name": "florence2",
        "caption_model_path": os.path.join(weights_dir, "icon_caption_florence"),
        "BOX_TRESHOLD": 0.05,
        "use_caption": use_caption,
    }

    if not quiet:
        print("Loading OmniParser locally (slow)...", file=sys.stderr)
        print("TIP: Run 'som-server start' for fast mode.", file=sys.stderr)

    parser = Omniparser(config)

    img = Image.open(image_path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    labeled_b64, parsed_content = parser.parse(img_b64)

    elements = []
    for idx, item in enumerate(parsed_content):
        bbox = item["bbox"]
        cx = int((bbox[0] + bbox[2]) / 2 * screen_w)
        cy = int((bbox[1] + bbox[3]) / 2 * screen_h)
        w = int((bbox[2] - bbox[0]) * screen_w)
        h = int((bbox[3] - bbox[1]) * screen_h)
        elements.append({
            "index": idx,
            "type": item.get("type", ""),
            "content": item.get("content", ""),
            "interactivity": item.get("interactivity", False),
            "center_x": cx, "center_y": cy,
            "width": w, "height": h,
            "bbox_ratio": bbox,
        })

    return labeled_b64, elements


def main():
    ap = argparse.ArgumentParser(description="Android SoM screen annotator")
    ap.add_argument("--output", "-o", default="som_annotated.png", help="Annotated screenshot path")
    ap.add_argument("--json", "-j", default="som_elements.json", help="Elements JSON path")
    ap.add_argument("--screenshot", "-s", help="Use existing screenshot instead of ADB capture")
    ap.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    ap.add_argument("--wait", "-w", type=float, default=0.5, help="Wait seconds before screenshot (default 0.5)")
    ap.add_argument("--caption", action="store_true",
                    help="Enable Florence-2 icon caption. Slow (~60-80s) but describes icons without text. "
                         "Recommended for first visit to unfamiliar apps.")
    args = ap.parse_args()

    screen_w, screen_h = get_screen_size()
    if not args.quiet:
        print(f"Phone screen: {screen_w}x{screen_h}", file=sys.stderr)

    # Screenshot
    raw_path = args.screenshot or "/tmp/som_android_screenshot.png"
    if not args.screenshot:
        if args.wait > 0:
            time.sleep(args.wait)
        if not args.quiet:
            print("Taking screenshot via ADB...", file=sys.stderr)
        take_screenshot(raw_path)

    # Parse
    t0 = time.time()
    server_result = try_server(raw_path, screen_w, screen_h,
                               use_caption=args.caption, quiet=args.quiet)

    if server_result:
        labeled_b64, elements = server_result
    else:
        labeled_b64, elements = parse_local(raw_path, screen_w, screen_h,
                                             use_caption=args.caption, quiet=args.quiet)

    elapsed = time.time() - t0

    # Save annotated image
    from PIL import Image
    labeled_img = Image.open(io.BytesIO(base64.b64decode(labeled_b64)))
    if args.output.lower().endswith(('.jpg', '.jpeg')):
        labeled_img.save(args.output, quality=85)
    else:
        labeled_img.save(args.output)

    # Save elements JSON
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print(f"Detected {len(elements)} elements in {elapsed:.1f}s", file=sys.stderr)
        print(f"Annotated: {args.output}", file=sys.stderr)
        print(f"Elements:  {args.json}", file=sys.stderr)

    # Print element summary to stdout
    for e in elements:
        content = (e.get("content") or "").strip()
        if content:
            print(f'[{e["index"]}] ({e["center_x"]},{e["center_y"]}) {e["type"]} "{content}"')

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: 测试**

```bash
chmod +x som-toolkit/som-android-annotate
```

确保 som-server 运行中：`python3 som-toolkit/som-server status`

如果没运行：`python3 som-toolkit/som-server start --no-caption`

Run: `python3 som-toolkit/som-android-annotate -o /tmp/android_test.jpg -j /tmp/android_test.json -q`
Expected:
- 截图成功，检测到 N 个元素
- `/tmp/android_test.jpg` 有标注的截图
- `/tmp/android_test.json` 有元素列表，每个元素有 center_x, center_y 在 720x1640 范围内

验证坐标范围：
```bash
python3 -c "
import json
elements = json.load(open('/tmp/android_test.json'))
for e in elements[:5]:
    print(f'[{e[\"index\"]}] ({e[\"center_x\"]},{e[\"center_y\"]}) \"{e.get(\"content\",\"\")[:30]}\"')
assert all(0 <= e['center_x'] <= 720 for e in elements), 'X out of range!'
assert all(0 <= e['center_y'] <= 1640 for e in elements), 'Y out of range!'
print(f'All {len(elements)} elements within 720x1640 range. OK.')
"
```

**Step 3: Commit**

```bash
git add som-toolkit/som-android-annotate
git commit -m "feat: add som-android-annotate for Android screenshot + OmniParser detection"
```

---

### Task 7: som-android-find（thin wrapper）

**Files:**
- Create: `som-toolkit/som-android-find`

**Step 1: 创建 som-android-find**

som-find 的逻辑是纯 JSON 操作，直接委托给 som-find：

```python
#!/usr/bin/env python3
"""
som-android-find: 从 Android SoM 元素中搜索（委托给 som-find）
用法与 som-find 完全一致:
    som-android-find "购买" -j page.json
    som-android-find --summary -j page.json
    som-android-find "价格" --extract -j page.json
"""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    som_find = os.path.join(SCRIPT_DIR, "som-find")
    sys.exit(subprocess.run([sys.executable, som_find] + sys.argv[1:]).returncode)
```

**Step 2: 测试**

```bash
chmod +x som-toolkit/som-android-find
```

需要先有 JSON（上一步 Task 6 应已生成 /tmp/android_test.json）。

Run: `python3 som-toolkit/som-android-find --summary -j /tmp/android_test.json`
Expected: 打印页面概览

Run: `python3 som-toolkit/som-android-find --extract -j /tmp/android_test.json`
Expected: 打印结构化信息（可能为空，取决于当前页面）

**Step 3: Commit**

```bash
git add som-toolkit/som-android-find
git commit -m "feat: add som-android-find as thin wrapper over som-find"
```

---

### Task 8: 全链路端到端验证

**Files:** 无新文件

**Step 1: 完整操作循环测试**

在手机上执行一次完整的操作循环：启动 App → 截图标注 → 查找元素 → 点击 → 验证。

```bash
# 1. 启动闲鱼
python3 som-toolkit/som-android-app xianyu
sleep 3

# 2. 截图 + 标注
python3 som-toolkit/som-android-annotate -o /tmp/xianyu.jpg -j /tmp/xianyu.json -q

# 3. 查看页面概览
python3 som-toolkit/som-android-find --summary -j /tmp/xianyu.json

# 4. 搜索特定元素（如"首页"、"消息"等底部 tab）
python3 som-toolkit/som-android-find "首页" -j /tmp/xianyu.json

# 5. 如果找到元素，尝试点击
# （根据 Step 4 输出的编号替换 N）
# python3 som-toolkit/som-android-click N -j /tmp/xianyu.json

# 6. 验证：重新截图
# python3 som-toolkit/som-android-annotate -o /tmp/xianyu2.jpg -j /tmp/xianyu2.json -q

# 7. 回到桌面
python3 som-toolkit/som-android-key home
```

Expected:
- 每个步骤正常完成，无报错
- JSON 元素坐标都在 720x1640 范围内
- 点击后手机有响应

**Step 2: 查看标注图确认视觉效果**

用 Read 工具查看 /tmp/xianyu.jpg，确认标注框和编号正确覆盖在元素上。

**Step 3: Commit（如有修复）**

如果测试中发现并修复了问题，提交修复。

---

### Task 9: 更新 CLAUDE.md 工具描述

**Files:**
- Modify: `som-toolkit/CLAUDE.md`

**Step 1: 在 CLAUDE.md 中添加 Android 工具章节**

在现有桌面端工具表格之后，添加 Android 工具章节。关键要点：

1. 工具表格（som-android-* 系列）
2. 操作循环（和桌面端一致）
3. **--caption 使用策略**：首次进入陌生 App 用 `--caption`，后续用默认快速模式
4. ADB 环境变量（ADB_SERIAL）
5. 中文输入需要 ADB Keyboard

**Step 2: 验证 CLAUDE.md 可读性**

读一遍确保 agent 能理解。

**Step 3: Commit**

```bash
git add som-toolkit/CLAUDE.md
git commit -m "docs: add Android som-android-* tools to CLAUDE.md"
```
