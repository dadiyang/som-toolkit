---
name: mob-android-automation
description: Android 手机 UI 自动化技能。通过 ADB + uiautomator 结构化数据做精确操作，OCR 做 WebView 内容补充。覆盖闲鱼、小红书等中国 App 的养号和商品浏览场景。当操作 Android 手机、用 ADB 控制 App、做手机自动化测试、或为中国 App 做数据采集时触发。
---

# Android 手机 UI 自动化技能

## 核心架构：uiautomator 为主，OCR 为辅

```
mob-annotate → uiautomator dump（结构化 UI 树，3-5秒）
     ↓
  原生 UI 元素有文字？→ 是 → 直接用（精确）
     ↓ 否
  WebView 区域 → 截图 + OCR 补充
```

**为什么不纯视觉**：uiautomator 给出的坐标精确到像素（来自系统 API），OCR 坐标有误差。能用结构化数据就不用视觉。

**为什么不纯 uiautomator**：中国主流 App（闲鱼、小红书、淘宝）的内容区域全部 WebView 渲染，uiautomator 拿不到文字。

## 工具集

| 工具 | 作用 | 速度 |
|------|------|------|
| `mob-annotate` | UI 树 dump + 截图标注 | 3-5 秒 |
| `mob-click` | 点击（编号/文字/resource_id/坐标） | 即时 |
| `mob-find` | 搜索元素（--summary/--extract/关键词） | 即时 |
| `mob-type` | 输入文字 + 按键 | 即时 |
| `mob-scroll` | 滑动（可配像素距离） | 即时 |

## 操作循环

```
mob-annotate → mob-find 找目标 → mob-click 操作 → mob-annotate 验证
```

**和桌面版一样**：每次操作后必须重新 `mob-annotate`，编号会变。

## 各 App uiautomator 覆盖率（实测）

| App | 首页/Feed | 商品详情 | 搜索结果 | 聊天 |
|-----|----------|---------|---------|------|
| **闲鱼** | 41%（标签+部分Feed） | **5%**（WebView） | **WebView**（用deeplink搜索） | 原生较好 |
| **小红书** | **5%**（WebView） | 未测 | 未测 | 未测 |
| **淘宝** | 未测 | 预期 WebView | 预期 WebView | 未测 |

**规律**：导航栏、底部 Tab 是原生控件（uiautomator 可读）；内容区、商品详情、搜索结果几乎全是 WebView。

## 实战踩坑记录

### 坑 1：find_and_tap 模糊匹配点错元素

**场景**：`mob-click --text "同意"` 想点同意按钮，但匹配到了协议正文里的"同意"字样。

**规则**：`find_and_tap` 必须优先匹配 clickable 元素的精确文字，再模糊匹配。

**已修复**：5 级回退策略——精确+clickable → 部分+clickable → resource_id → content_desc → 部分+任意元素。

### 坑 2：闲鱼搜索是 WebView，ADB 输入不进去

**场景**：点击闲鱼搜索栏后，ADB Keyboard broadcast 无法注入文字到 WebView input。

**规则**：闲鱼搜索用 deeplink，不操作搜索框。

```bash
adb shell am start -a android.intent.action.VIEW -d "fleamarket://searchresult?keyword=iPhone16"
```

### 坑 3：uiautomator dump 超时

**场景**：App 启动动画期间 `uiautomator dump` 超过 10 秒超时。

**规则**：默认超时设为 30 秒。App 启动后等 5-8 秒再 dump。

### 坑 4：自定义字体图标显示为韩文乱码

**场景**：闲鱼使用 iconfont 自定义图标字体，uiautomator 读出来是 `쁪`、`턍` 等 Unicode 私用区字符。

**规则**：忽略这些字符。按钮的语义通过 resource_id 或 content-desc 判断，不依赖 text。

### 坑 5：RGBA 截图保存为 JPEG 崩溃

**场景**：Android 截图是 RGBA 格式（带透明通道），PIL 无法直接保存为 JPEG。

**规则**：保存 JPEG 前 `img.convert("RGB")`。

### 坑 6：闲鱼启动弹出登录验证 + 协议确认

**场景**：闲鱼冷启动后依次弹出：一键登录 → 服务协议同意。

**处理流程**：
```bash
mob-click --text "一键登录"    # 等 5 秒
mob-annotate                   # 看到协议弹窗
mob-click 2 -j xxx.json        # 点"同意"（用编号，不用模糊文字匹配）
```

### 坑 7：OCR 提取 WebView 价格——easyocr 中文模型

**场景**：商品详情页的价格、标题、运费都在 WebView 里，uiautomator 拿不到。

**方案**：
```python
import easyocr
reader = easyocr.Reader(['en', 'ch_sim'], gpu=False)
results = reader.readtext('screenshot.jpg')
# 结果包含 bbox + 文字 + 置信度
```

**实测**：闲鱼 iPhone 16 Pro 详情页，价格 "4599" 置信度 1.00，运费 "快递:包邮" 置信度 0.68。

## 各 App 搜索方式

| App | 搜索方式 | URL/Scheme |
|-----|---------|-----------|
| 闲鱼 | **Deeplink**（搜索框是 WebView 不可输入） | `fleamarket://searchresult?keyword=XXX` |
| 淘宝 | Intent | `taobao://s.taobao.com/search?q=XXX` |
| 小红书 | 待验证 | `xhsdiscover://search?keyword=XXX` |
| 微博 | 待验证 | - |
| 拼多多 | 待验证 | - |

## 养号操作模板

### 浏览 Feed（通用）
```bash
# 1. 启动 App
adb shell monkey -p <package> -c android.intent.category.LAUNCHER 1
sleep 5

# 2. 确认在首页
mob-annotate -j page.json --no-screenshot
mob-find --summary -j page.json

# 3. 滑动浏览
for i in $(seq 1 5); do
    mob-scroll down --pixels 400 --slow   # 拟人速度
    sleep $(shuf -i 3-8 -n 1)             # 随机停留
done
```

### 浏览商品详情（闲鱼）
```bash
# 1. 搜索商品
adb shell am start -a android.intent.action.VIEW -d "fleamarket://searchresult?keyword=手机"
sleep 5

# 2. 点击商品（从搜索结果页的坐标点击，因为是 WebView）
mob-click --xy 180,500
sleep 5

# 3. 提取信息（混合方式）
mob-annotate -j detail.json               # uiautomator 部分
# WebView 区域用 OCR 补充
python3 -c "
import easyocr
reader = easyocr.Reader(['en', 'ch_sim'], gpu=False)
for _, text, conf in reader.readtext('/tmp/mob_raw_screenshot.png'):
    if conf > 0.5: print(text)
"

# 4. 返回
mob-type --key BACK
```
