"""
mob-core: Android 操控核心模块
提供截图、UI树解析、元素定位、点击/输入/滑动等原子操作。

基于 uiautomator dump（结构化数据）做主路径，精确到像素。
截图仅用于辅助理解（颜色、图标、布局上下文）。

设计参考 mobile-use 的 3 级回退策略：bounds → resource_id → text。
"""
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


def _run_adb(*args, timeout=30):
    """Run an ADB command and return stdout."""
    cmd = ["adb"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"ADB command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def _run_adb_bytes(*args, timeout=30):
    """Run an ADB command and return raw bytes."""
    cmd = ["adb"] + list(args)
    result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"ADB command failed: {' '.join(cmd)}\n{result.stderr.decode()}")
    return result.stdout


# ─── Data Types ────────────────────────────────────────

@dataclass
class MobElement:
    index: int
    text: str
    content_desc: str
    resource_id: str
    class_name: str
    bounds: tuple  # (x1, y1, x2, y2)
    clickable: bool
    focusable: bool
    scrollable: bool
    enabled: bool
    checked: bool
    selected: bool

    @property
    def center(self):
        x1, y1, x2, y2 = self.bounds
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self):
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self):
        return self.bounds[3] - self.bounds[1]

    @property
    def label(self):
        """Best human-readable label for this element."""
        return self.text or self.content_desc or self.resource_id.split("/")[-1] if self.resource_id else ""

    def to_dict(self):
        return {
            "index": self.index,
            "text": self.text,
            "content_desc": self.content_desc,
            "resource_id": self.resource_id,
            "class_name": self.class_name,
            "bounds": list(self.bounds),
            "center_x": self.center[0],
            "center_y": self.center[1],
            "width": self.width,
            "height": self.height,
            "clickable": self.clickable,
            "focusable": self.focusable,
            "scrollable": self.scrollable,
            "label": self.label,
        }


def _parse_bounds(bounds_str):
    """Parse '[x1,y1][x2,y2]' → (x1, y1, x2, y2)"""
    match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
    if len(match) == 2:
        return (int(match[0][0]), int(match[0][1]), int(match[1][0]), int(match[1][1]))
    return (0, 0, 0, 0)


# ─── UI Tree ──────────────────────────────────────────

def dump_ui_tree(output_json=None):
    """Dump Android UI hierarchy and parse into MobElement list.

    Returns list of MobElement sorted by position (top-to-bottom, left-to-right).
    """
    # Dump to device, pull to local
    _run_adb("shell", "uiautomator", "dump", "/sdcard/ui_dump.xml")
    xml_data = _run_adb_bytes("shell", "cat", "/sdcard/ui_dump.xml")

    root = ET.fromstring(xml_data)
    elements = []
    idx = 0

    for node in root.iter("node"):
        bounds = _parse_bounds(node.get("bounds", ""))
        # Skip zero-size elements
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            continue
        # Skip off-screen elements
        if bounds[0] < 0 and bounds[2] < 0:
            continue

        clickable = node.get("clickable") == "true"
        focusable = node.get("focusable") == "true"
        scrollable = node.get("scrollable") == "true"
        text = node.get("text", "") or ""
        content_desc = node.get("content-desc", "") or ""
        resource_id = node.get("resource-id", "") or ""
        class_name = node.get("class", "") or ""
        enabled = node.get("enabled") == "true"

        # Only include elements that are interactive or have useful text
        is_interactive = clickable or focusable or scrollable
        has_content = bool(text.strip() or content_desc.strip())

        if is_interactive or has_content:
            elements.append(MobElement(
                index=idx,
                text=text,
                content_desc=content_desc,
                resource_id=resource_id,
                class_name=class_name,
                bounds=bounds,
                clickable=clickable,
                focusable=focusable,
                scrollable=scrollable,
                enabled=enabled,
                checked=node.get("checked") == "true",
                selected=node.get("selected") == "true",
            ))
            idx += 1

    # Sort by position: top-to-bottom, left-to-right
    elements.sort(key=lambda e: (e.bounds[1], e.bounds[0]))
    for i, e in enumerate(elements):
        e.index = i

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in elements], f, ensure_ascii=False, indent=2)

    return elements


# ─── Screenshot ───────────────────────────────────────

def take_screenshot(output_path):
    """Take a screenshot from the Android device."""
    raw = _run_adb_bytes("exec-out", "screencap", "-p")
    with open(output_path, "wb") as f:
        f.write(raw)
    return output_path


# ─── Actions ──────────────────────────────────────────

def tap(x, y):
    """Tap at coordinates."""
    _run_adb("shell", "input", "tap", str(x), str(y))


def tap_element(element):
    """Tap the center of an element."""
    cx, cy = element.center
    tap(cx, cy)


def long_press(x, y, duration_ms=1000):
    """Long press at coordinates."""
    _run_adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms))


def swipe(x1, y1, x2, y2, duration_ms=300):
    """Swipe from (x1,y1) to (x2,y2)."""
    _run_adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))


def scroll_down(amount=500):
    """Scroll down by swiping up. amount = pixels."""
    # Get screen size for center position
    size = get_screen_size()
    cx = size[0] // 2
    cy = size[1] // 2
    swipe(cx, cy + amount // 2, cx, cy - amount // 2, 300)


def scroll_up(amount=500):
    """Scroll up by swiping down."""
    size = get_screen_size()
    cx = size[0] // 2
    cy = size[1] // 2
    swipe(cx, cy - amount // 2, cx, cy + amount // 2, 300)


def input_text(text):
    """Input text via ADB. For CJK, uses ADB Keyboard (if installed) or clipboard."""
    # Check if text is ASCII
    if all(ord(c) < 128 for c in text):
        # Escape special chars for shell
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        _run_adb("shell", "input", "text", escaped)
    else:
        # CJK/Unicode: use ADB Keyboard broadcast if available
        try:
            _run_adb("shell", "am", "broadcast",
                     "-a", "ADB_INPUT_TEXT",
                     "--es", "msg", text)
        except RuntimeError:
            # Fallback: clipboard method
            _run_adb("shell", "input", "text", text.encode("unicode_escape").decode())


def press_key(keycode):
    """Press a key by name or code. Common: BACK, HOME, ENTER, KEYCODE_TAB."""
    if keycode.isdigit():
        _run_adb("shell", "input", "keyevent", keycode)
    else:
        if not keycode.startswith("KEYCODE_"):
            keycode = f"KEYCODE_{keycode.upper()}"
        _run_adb("shell", "input", "keyevent", keycode)


def press_back():
    press_key("BACK")


def press_home():
    press_key("HOME")


def press_enter():
    press_key("ENTER")


# ─── Screen Info ──────────────────────────────────────

def get_screen_size():
    """Get physical screen size (width, height)."""
    out = _run_adb("shell", "wm", "size")
    match = re.search(r"(\d+)x(\d+)", out)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (1080, 2400)  # Common default


def get_current_app():
    """Get current foreground app package and activity."""
    out = _run_adb("shell", "dumpsys", "window")
    match = re.search(r"mCurrentFocus=.*\s+([\w.]+)/([\w.]+)", out)
    if match:
        return match.group(1), match.group(2)
    return ("unknown", "unknown")


def launch_app(package):
    """Launch an app by package name."""
    _run_adb("shell", "monkey", "-p", package, "-c",
             "android.intent.category.LAUNCHER", "1")


def is_screen_on():
    """Check if screen is on."""
    out = _run_adb("shell", "dumpsys", "display")
    return "mScreenState=ON" in out


def wake_screen():
    """Wake the screen if off."""
    if not is_screen_on():
        press_key("WAKEUP")
        time.sleep(0.5)


# ─── Element Search (3-tier fallback like mobile-use) ─

def find_element(elements, *, text=None, resource_id=None, content_desc=None,
                 class_name=None, clickable=None):
    """Find elements matching criteria. Returns list of matches."""
    results = []
    for e in elements:
        if text and text.lower() not in e.text.lower():
            continue
        if resource_id and resource_id not in e.resource_id:
            continue
        if content_desc and content_desc.lower() not in e.content_desc.lower():
            continue
        if class_name and class_name not in e.class_name:
            continue
        if clickable is not None and e.clickable != clickable:
            continue
        results.append(e)
    return results


def find_and_tap(elements, *, text=None, resource_id=None, content_desc=None):
    """3-tier fallback with smart matching:
    1. Exact text match on clickable elements (highest priority)
    2. Partial text match on clickable elements
    3. Partial text match on all elements (fallback)

    Returns (success: bool, element_tapped: MobElement|None)
    """
    if text:
        # Tier 1: Exact text match on clickable elements
        exact_clickable = [e for e in elements
                           if e.clickable and e.text.strip() == text.strip()]
        if exact_clickable:
            tap_element(exact_clickable[0])
            return True, exact_clickable[0]

        # Tier 2: Partial match on clickable elements
        partial_clickable = [e for e in elements
                             if e.clickable and text.lower() in e.text.lower()]
        if partial_clickable:
            tap_element(partial_clickable[0])
            return True, partial_clickable[0]

    # Tier 3: resource_id match
    if resource_id:
        matches = find_element(elements, resource_id=resource_id)
        if matches:
            elem = matches[0]
            tap_element(elem)
            return True, elem

    # Tier 4: content_desc match
    if content_desc:
        matches = find_element(elements, content_desc=content_desc)
        if matches:
            elem = matches[0]
            tap_element(elem)
            return True, elem

    # Tier 5: Partial text on any element (last resort)
    if text:
        matches = find_element(elements, text=text)
        if matches:
            elem = matches[0]
            tap_element(elem)
            return True, elem

    return False, None
