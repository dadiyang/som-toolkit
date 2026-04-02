# Windows 支持设计

## 目标

用 pyautogui 统一三平台（macOS / Linux / Windows）桌面操作，消除 24 个 if/elif 平台分支。

## 背景

当前桌面端工具（som-annotate/click/type/scroll/tab）只支持 macOS 和 Linux，通过平台特定工具实现：
- macOS: cliclick / CGEvent (pyobjc) / screencapture / osascript / pbcopy
- Linux: xdotool / scrot / xclip

Windows 没有对应实现。与其加第三套平台分支（36 个分支点），选择用 pyautogui 统一。

## 方案：pyautogui 统一

### 操作映射

| 操作 | 当前实现 | pyautogui 替代 |
|------|---------|---------------|
| 截图 | scrot / screencapture | `pyautogui.screenshot()` |
| 屏幕尺寸 | xdotool / AppKit | `pyautogui.size()` |
| 鼠标点击 | xdotool / cliclick / CGEvent | `pyautogui.click(x, y)` |
| 双击 | xdotool / cliclick / CGEvent | `pyautogui.doubleClick(x, y)` |
| 右键 | xdotool / cliclick / CGEvent | `pyautogui.rightClick(x, y)` |
| 修饰键+点击 | xdotool keydown / cliclick kd | `pyautogui.keyDown()` + click + `keyUp()` |
| 键盘按键 | xdotool key / osascript | `pyautogui.hotkey()` / `pyautogui.press()` |
| 剪贴板 | xclip / pbcopy | `pyperclip`（pyautogui 依赖） |
| 滚动 | xdotool click / CGEvent / osascript | `pyautogui.scroll()` |

### 改动范围

| 文件 | 改动内容 |
|------|---------|
| **som-annotate** | take_screenshot → pyautogui.screenshot()；get_screen_size → pyautogui.size() |
| **som-click** | click_at/double_click_at/right_click_at → pyautogui；删除 cliclick/CGEvent 分支；修饰键用 keyDown/keyUp |
| **som-type** | set_clipboard → pyperclip；type_text → pyperclip + pyautogui.hotkey('ctrl','v')；press_key → pyautogui.hotkey() |
| **som-scroll** | scroll → pyautogui.scroll()；精细滚动需验证精度 |
| **som-tab** | press_key → pyautogui.hotkey() |
| **som-server** | daemon os.fork() → Windows 用 subprocess.Popen + DETACHED_PROCESS |
| **install.sh** | 去掉 cliclick/pyobjc/scrot 平台分支，统一 pip install pyautogui pyperclip |

### 不改的文件

- som_common.py / som_android_common.py — 无平台逻辑
- som-find / som-android-find — 纯 JSON 操作
- som-android-annotate/click/type/scroll/key/app — 依赖 adb，已跨平台

### 关键注意点

1. **HiDPI 坐标**：pyautogui.size() 在 Retina Mac 上返回逻辑像素（已验证），与当前行为一致
2. **滚动精度**：pyautogui.scroll(n) 单位是滚轮刻度（不是像素）。当前 `--lines N` 是 N*100px 精细滚动，需要换算或保留平台特定实现
3. **修饰键时序**：keyDown → click → keyUp 间需要短 sleep 确保浏览器识别
4. **Windows daemon**：os.fork() 不可用，改用 subprocess.Popen + CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS
5. **macOS Cmd vs Ctrl**：pyautogui 中 macOS 用 'command'，Windows/Linux 用 'ctrl'。som-tab 的 Ctrl→Cmd 替换逻辑仍需保留

## 验证策略

feature 分支开发，在 Mac 上全流程验证后合入主干：
1. `som-annotate → som-find → som-click → som-annotate` 循环
2. 真实浏览器场景：搜索 + 点击商品 + 滚动 + 提取信息
3. 中文输入验证

## 依赖变化

新增：pyautogui, pyperclip
移除：pyobjc-framework-Cocoa, pyobjc-framework-Quartz, pyobjc-framework-ApplicationServices（macOS 专用）
保留：scrot (Linux), xdotool (Linux) — pyautogui 在 Linux 底层仍需要
