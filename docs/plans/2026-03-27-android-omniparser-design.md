# Android OmniParser 视觉方案设计

## 背景

桌面端 som-* 工具经过 eBay 全流程验证，架构稳定。Android 端需要同样的视觉操作能力，用于操作闲鱼、小红书等中国 App。之前尝试过 uiautomator 结构化方案，因 Flutter 渲染和各 App 按钮命名不统一而放弃。

视觉方案的优势：不依赖 App 内部实现，对 Flutter/WebView/原生一视同仁。

## 数据流

```
手机屏幕
  ↓ adb exec-out screencap -p
截图 PNG (720x1640)
  ↓ som-server (localhost:8765) 或本地 OmniParser
OmniParser 检测 (bbox 比例值)
  ↓ bbox × 物理分辨率 = ADB 坐标
JSON 元素列表 + 标注图
  ↓ som-android-find 查询
som-android-click/type/scroll 执行
  ↓ adb shell input tap/text/swipe
手机响应
```

OmniParser 输出 0-1 比例值，乘以手机物理分辨率即为 ADB 坐标，无需 Retina 逻辑像素映射。

检测层完全复用桌面端 som-server，不需要额外部署。

## 工具清单

7 个独立脚本，放在 som-toolkit/ 下，和桌面端风格一致。

### som-android-annotate

截图 + OmniParser 检测 + 输出元素列表。

```
som-android-annotate -o page.jpg -j page.json -q
som-android-annotate --caption -o page.jpg -j page.json   # 开启 Florence-2
som-android-annotate --screenshot existing.png -j page.json
```

参数：
- `-o / --output`：标注图路径（默认 som_annotated.png）
- `-j / --json`：元素 JSON 路径（默认 som_elements.json）
- `-q / --quiet`：安静模式
- `--wait`：截图前等待秒数（默认 0.5）
- `--screenshot`：用已有截图而非 ADB 截图
- `--caption`：开启 Florence-2 icon 描述（默认关闭）

**关于 --caption**：默认关闭（~8s），开启后 ~60-80s。手机端纯图标较多（汉堡菜单、底部 tab bar），但 Florence-2 caption 质量一般。推荐策略：首次进入陌生 App 开一次 `--caption` 做完整分析，后续操作用默认快速模式。

流程：
1. `adb exec-out screencap -p` 拿截图
2. `adb shell wm size` 拿物理分辨率
3. 发送到 som-server 或本地加载 OmniParser
4. bbox 比例 × 分辨率 = 坐标
5. 输出 JSON + 标注图

### som-android-click

```
som-android-click 42 -j page.json          # 按编号点击
som-android-click --xy 360,820             # 直接坐标
som-android-click 42 --long -j page.json   # 长按
```

执行：
- 点击：`adb shell input tap x y`
- 长按：`adb shell input swipe x y x y 800`

### som-android-type

```
som-android-type 42 "你好" -j page.json     # 点击后输入
som-android-type --text "你好"               # 直接输入
som-android-type 42 "hello" --clear         # 先清空再输入
```

中文输入：`am broadcast -a ADB_INPUT_TEXT --es msg "你好"`（需安装 ADB Keyboard）
ASCII 输入：`adb shell input text "hello"`
清空：先全选（长按 + 全选），再删除

### som-android-scroll

```
som-android-scroll down                # 向下滑一屏
som-android-scroll down --lines 3      # 精细滑 300px
som-android-scroll up
som-android-scroll left / right        # 横向滑动
som-android-scroll top / bottom        # 滑到顶/底（多次 swipe）
```

执行：`adb shell input swipe x1 y1 x2 y2 duration`
- 一屏：从屏幕 75% 高度滑到 25%
- 精细：按 lines × 100px 计算位移
- 横向：从屏幕 75% 宽度滑到 25%（或反向）

### som-android-find

纯 JSON 查询，复用 som-find 逻辑（thin wrapper 或直接调用）。

```
som-android-find "购买" -j page.json
som-android-find --summary -j page.json
som-android-find "价格" --extract -j page.json
```

### som-android-key

Android 专有按键。

```
som-android-key back          # 返回
som-android-key home          # Home
som-android-key recent        # 最近任务
som-android-key enter         # 确认/回车
som-android-key delete        # 删除
som-android-key power         # 电源键（亮屏/灭屏）
```

执行：`adb shell input keyevent KEYCODE_BACK` 等。

### som-android-app

App 启动和切换。

```
som-android-app xianyu                  # 别名启动
som-android-app com.taobao.idlefish     # 包名启动
som-android-app --list                  # 列出别名
som-android-app --current               # 当前前台 App
```

内置别名：
- xianyu → com.taobao.idlefish
- xhs → com.xingin.xhs
- weibo → com.sina.weibo
- zhihu → com.zhihu.android

执行：`adb shell monkey -p <package> -c android.intent.category.LAUNCHER 1`

## 设计决策

1. **独立命令而非参数切换**：手机和桌面操作语义差异大（手机有返回键、长按、横向滑动），独立命令保持每个工具干净
2. **复用 som-server**：检测层平台无关，不需要额外部署
3. **默认关闭 caption**：速度 8s vs 60-80s，agent 按需开启
4. **ADB 设备发现内联**：每个工具 5 行代码，不做共享模块抽象
5. **JSON 格式完全一致**：som-android-find 直接复用 som-find，agent 操作习惯不变

## ADB 设备发现

每个工具开头统一逻辑：
```python
def get_device():
    """获取 ADB 设备 serial，支持环境变量指定。"""
    serial = os.environ.get("ADB_SERIAL", "")
    if serial:
        return ["-s", serial]
    # 检查是否只有一个设备
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
    if len(lines) == 0:
        sys.exit("ERROR: No ADB device connected. Check USB connection.")
    if len(lines) > 1:
        sys.exit(f"ERROR: Multiple devices found. Set ADB_SERIAL=<serial>\n{result.stdout}")
    return []  # 只有一个设备，不需要 -s
```

## Agent Prompt 要点（后续写入技能描述）

- 操作循环和桌面端一致：`som-android-annotate → som-android-find → som-android-click → som-android-annotate 验证`
- 首次进入陌生 App 用 `--caption` 做完整分析，后续用默认快速模式
- 手机 App 页面切换后必须重新 annotate（元素编号全部失效）
- 中文输入需要 ADB Keyboard，确认已安装
