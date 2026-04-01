"""
som_android_common: Android 工具共享的 ADB 辅助函数
"""
import os
import subprocess
import sys


def get_device():
    """Get ADB device serial args. Exits if no device or multiple without ADB_SERIAL."""
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []


def adb(*args):
    """Run ADB command, return CompletedProcess with text output."""
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)


def adb_raw(*args):
    """Run ADB command returning raw bytes (for screencap)."""
    cmd = ["adb"] + get_device() + list(args)
    return subprocess.run(cmd, capture_output=True, check=True, timeout=15)


def get_screen_size():
    """Get phone physical resolution via wm size."""
    result = subprocess.run(["adb"] + get_device() + ["shell", "wm", "size"],
                            capture_output=True, text=True, check=True)
    for line in result.stdout.strip().split("\n"):
        if "Physical size:" in line:
            parts = line.split()[-1].split("x")
            return int(parts[0]), int(parts[1])
    # Fallback: last line
    parts = result.stdout.strip().split()
    if not parts or "x" not in parts[-1]:
        sys.exit("ERROR: Cannot parse screen size. Check ADB connection.")
    w, h = parts[-1].split("x")
    return int(w), int(h)


def tap(x, y):
    """Tap at screen coordinates."""
    adb("shell", "input", "tap", str(x), str(y))
