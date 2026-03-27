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

| App/页面 | WebView 元素数 | 有效文字 | 能读到什么 |
|---------|---------------|---------|-----------|
| **微博 Feed** | 0 | 30+ | 帖子全文、互动数据（转发/评论/赞） |
| **知乎 Feed** | 0 | 20+ | 问题标题、回答预览、互动数据 |
| **闲鱼首页 Feed** | **0** | 33 | 导航标签、商品标题、价格 |
| **闲鱼搜索结果** | **0** | 33-35 | 价格、描述、卖家地区、筛选项 |
| **闲鱼详情（个人）** | **0** | 36 | 价格、运费、卖家、SKU 全部可读 |
| **闲鱼详情（验货宝）** | **2** | 19 | 价格、原价、想要人数、购买按钮 |
| **小红书首页** | **0** | 22 | 标签、推荐内容 |

**验证方法**：通过 `class_name` 字段检查是否含 `android.webkit.WebView`，而非靠元素数量推断。

**之前"5% 覆盖率"结论是错误的**——原因是 App 刚启动/页面未加载完时测的，或 agent 实际不在目标页面上。

**修正后的规律**：
- 所有测试的中国 App（微博/知乎/闲鱼/小红书）首页和列表页都是**原生渲染**
- 只有闲鱼验货宝商品详情有少量 WebView 元素，但核心信息（价格/按钮）仍是原生可读
- **不需要 OCR 兜底**的场景比预想的多得多

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

### 坑 8：知乎回答页是 WebView

**场景**：知乎问题列表（首页 Feed）是原生 RecyclerView，uiautomator 覆盖率高。但进入问题详情后，回答内容在 WebView 里。

**规则**：知乎首页操作用 mob-find，回答内容提取用 OCR。

### 坑 9：各 App 的点赞按钮 resource_id 不同

**场景**：微博点赞是 `rightButton`，知乎不是。

**规则**：不要假设 resource_id 跨 App 通用。每次操作新 App 时，先 `mob-annotate` 查看元素结构。

**已知布局**：

| App | 点赞 resource_id | 评论 | 转发/分享 |
|-----|-----------------|------|---------|
| 微博 | rightButton | midButton | leftButton |
| 知乎 | 待确认（WebView 区域） | - | - |
| 闲鱼 | WebView 区域 | - | - |

### 坑 10：闲鱼详情页渲染方式不统一

**场景**：闲鱼的商品详情页有两种渲染方式，取决于商品类型。

| 类型 | 渲染 | uiautomator 覆盖 |
|------|------|-----------------|
| 个人闲置商品 | **原生** | 高（价格/运费/卖家/SKU 全部可读） |
| 第三方店铺/验货宝 | **WebView** | 极低（5%，只有导航栏） |

**判断方法**：`mob-annotate` 后看有没有 `detail_parent_recycler_view`（原生）还是 `ice-container`（WebView）。

**规则**：原生页面直接用 `mob-find`，WebView 页面用 OCR 补充。

### 坑 11：中国 App 按钮名在 content_desc 不在 text

**场景**：闲鱼的收藏/评论/购买/聊一聊按钮，text 字段为空，名字在 content_desc 里。

**例子**：
```
resource_id: com.taobao.idlefish:id/detail_left_button
content_desc: "收藏按钮"
text: ""  ← 空！
```

**规则**：`mob-click --text` 会自动搜索 text → content_desc → resource_id。但 `mob-find` 搜索时也要注意看 content_desc 列。

**已修复**：`find_and_tap` 新增 Tier 2b：content_desc 匹配（在 clickable 元素上）。

### 坑 12：底部 Tab 的 text 和 clickable 分离

**场景**：闲鱼底部导航栏（闲鱼/北京/消息/我的）的文字在 static 元素上，clickable 在另一个元素上且 text 为空。

**结构**：
```
clickable [67] desc="我的，未选中状态" text="" ← 实际可点击
static    [71] desc="" text="我的"              ← 只是文字标签
```

**规则**：`mob-click --text "我的"` 现在能通过 content_desc 匹配到 clickable 元素。

### 坑 13：搜索结果页（WebView）看不到底部 Tab

**场景**：闲鱼 deeplink 搜索结果是 WebView 页面，底部导航栏不在 UI 树里。

**规则**：先点"返回"回到原生首页，再操作底部 Tab。

## 闲鱼完整操作流程验证记录

以下流程已端到端验证通过（2026-03-27）：

```
1. 启动闲鱼 → 处理一键登录 → 处理协议同意
2. 底部 Tab 切换：闲鱼/消息/我的
3. Deeplink 搜索：fleamarket://searchresult?keyword=二手Switch
4. 点击搜索结果商品 → 进入详情页
5. 详情页提取：¥750, 包邮, 卖家 Lili/佛山, SKU (任天堂/续航版/日版)
6. 收藏商品：mob-click --text "收藏"
7. 返回搜索 → 滚动 → 第二个商品 → ¥1399, 包邮, 广州
8. 个人中心：用户名/鱼力值/发布数/收藏/浏览/交易
```

### 坑 14：错误归因——agent 操作失败不等于 WebView

**场景**：agent 用 deeplink 搜索闲鱼，但执行失败，停留在 MIUI 系统搜索页。agent 报告"闲鱼搜索结果是 WebView 读不到"，实际它从未到达闲鱼搜索结果页。

**验证方法**（事后用 class_name 确认）：
```python
# 检查 UI 树中是否有 WebView 元素
webview = [e for e in elements if 'WebView' in e.get('class_name', '')]
native = [e for e in elements if 'RecyclerView' in e.get('class_name', '')]
# 闲鱼搜索结果：WebView=0, RecyclerView=3 → 原生渲染
```

**教训**：
1. 不要把 agent 的操作失败当成平台特性——先确认 agent 是否在正确的页面
2. 判断 WebView 要看 `class_name` 字段，不要靠"元素少"来猜
3. 页面 3 秒和 8 秒元素数量一样（都是 33 个有效文字）——不是加载时间问题

### 坑 15：判断 WebView 的可靠方法

**不要用**：元素数量少 → 推断是 WebView（不可靠，可能是别的原因）

**要用**：检查 UI 树中是否存在 `android.webkit.WebView` 类名的元素
```bash
mob-annotate -j page.json --no-screenshot
python3 -c "
import json
d = json.load(open('page.json'))
wv = [e for e in d if 'WebView' in e.get('class_name','')]
print(f'WebView elements: {len(wv)}')
if wv: print('This is a WebView page → use OCR or coordinates')
else: print('Native page → use mob-find normally')
"
```

### 闲鱼各页面渲染方式（class_name 验证版）

| 页面 | 渲染 | WebView 元素数 | uiautomator 覆盖 |
|------|------|---------------|-----------------|
| 搜索结果列表 | **原生 RecyclerView** | **0** | ~40%（价格/描述/地区可读） |
| 搜索建议页 | 原生 | 0 | 高（所有建议可 clickable） |
| 首页 Feed | 混合 | 待确认 | ~40% |
| 商品详情（个人闲置） | 原生 | 待确认 | 高（价格/运费/SKU 全可读） |
| 商品详情（店铺/验货宝） | WebView | 待确认 | 极低（~5%） |
