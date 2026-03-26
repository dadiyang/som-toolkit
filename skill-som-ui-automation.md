---
name: som-ui-automation
description: 通过 SoM (Set-of-Mark) 标注实现系统 UI 自动化。截图后用 OmniParser 检测并编号所有可交互元素，agent 选编号执行操作，精度像素级。适用于浏览器自动化绕过反爬检测、桌面应用操控等场景。
---

# SoM UI 自动化技能

## 核心原理

网站反爬检测 Selenium/Playwright 的注入痕迹（navigator.webdriver、CDP 指纹等），但**无法检测系统级鼠标键盘操作**。本工具通过 OS 层控制真实浏览器，对网站来说与真人操作无区别。

大模型直接从截图估算坐标极不准确。SoM 方案将问题从"坐标回归"降维为"选择题"：
1. OmniParser 检测所有可交互 UI 元素并编号
2. Agent 看标注图选择编号（不需要猜坐标）
3. 工具用精确 bbox 中心点执行操作

## 工具集

三个命令行工具，位于 `som-toolkit/` 目录：

### som-annotate：截图 + 元素标注

```bash
som-annotate                                    # 截全屏并标注
som-annotate -o result.png -j elements.json     # 指定输出路径
som-annotate --screenshot existing.png          # 对已有截图标注
```

输出：
- 标注截图（每个元素有彩色边框 + 编号）
- `som_elements.json`：所有元素的编号、坐标、类型、内容

JSON 结构示例：
```json
{
  "index": 42,
  "type": "icon",
  "content": "A lock or padlock function.",
  "interactivity": true,
  "center_x": 1312,
  "center_y": 1092,
  "width": 87,
  "height": 83
}
```

### som-click：按编号点击

```bash
som-click 42                    # 单击编号 42
som-click 42 --double           # 双击
som-click 42 --right            # 右键
som-click --xy 500,300          # 直接坐标点击（调试用）
```

### som-find：按条件搜索元素（弱多模态 agent 专用）

不需要看图，纯文本操作：

```bash
som-find "Buy"                       # 按关键词搜索
som-find "Buy" --first --cmd         # 输出 som-click 命令（可直接执行）
som-find --type icon --interactive   # 只看可交互图标
som-find --area top                  # 按位置过滤（top/bottom/left/right/center）
som-find --summary                   # 页面概览（价格、按钮、运费分类摘要）
som-find --extract                   # 提取结构化商品信息（JSON）
```

`--extract` 输出示例：
```json
{
  "prices": [{"index": 21, "text": "US $8.99"}],
  "shipping": [{"index": 10, "text": "Free USPS Ground Advantage"}],
  "sku_options": [{"index": 32, "text": "Color: Blue"}],
  "buttons": [{"index": 29, "text": "Buy It Now"}]
}
```

### som-type：点击 + 输入文字

```bash
som-type 42 "hello world"       # 点击编号 42 后输入文字
som-type 42 "new text" --clear  # 先 Ctrl+A 清空再输入
som-type --key Return           # 按回车键
som-type --key "ctrl+a"         # 按组合键（macOS 用 cmd+a）
```

### som-scroll：滚动页面

```bash
som-scroll down                 # 向下一页
som-scroll up                   # 向上一页
som-scroll top                  # 回到顶部
som-scroll bottom               # 到底部
som-scroll down -n 3            # 连续向下 3 页
som-scroll down --annotate      # 滚动后自动标注
som-scroll down -n 3 --collect  # 滚动 3 页，合并所有视口元素（完整信息提取）
```

### som-server：模型常驻服务（加速用）

```bash
som-server start                # 后台启动（模型加载一次，后续标注快 2-3 倍）
som-server status               # 检查状态
som-server stop                 # 停止
som-server start --port 8766    # 指定端口（默认 8765）
```

启动后 `som-annotate` 自动检测 server 并使用，无需改任何命令。

## 标准操作流程

每次操作必须遵循这个循环：

```
截图标注 → 看标注图 → 选编号 → 执行操作 → 再截图验证
```

具体步骤：

1. **截图标注**：执行 `som-annotate -o current.png -j current.json`
2. **读取标注图**：用 Read 工具查看 current.png，了解当前屏幕状态
3. **查找目标**：在 current.json 中搜索要操作的元素
4. **执行操作**：`som-click <编号>` 或 `som-type <编号> "文字"`
5. **验证结果**：再次 `som-annotate` 或直接截图确认操作是否成功
6. **如果失败**：重新标注，可能元素编号已变化

## 关键经验（实测验证）

### 坐标系统
- OmniParser 输出 bbox 是**比例格式** [x1_ratio, y1_ratio, x2_ratio, y2_ratio]
- 工具内部已自动转换为屏幕坐标，agent 直接用编号即可
- macOS Retina 屏幕：截图像素 = 逻辑像素 × 2，工具已处理

### OCR 局限
- 默认英文 OCR 模型，中文会乱码（如"登录"识别成"ARepSTKEA"）
- **不影响操作精度**：YOLO 图标检测不依赖文字，bbox 坐标始终准确
- 建议：根据 icon 类型描述（如"A lock or padlock"）+ 位置来判断元素用途

### 性能
- CPU 模式：~170秒/张（首次加载模型慢，后续约 60 秒）
- GPU 模式（需要 ~3GB VRAM）：~5秒/张
- macOS Apple Silicon (MPS)：~10秒/张

### 元素编号会变
- 每次 `som-annotate` 后编号重新分配
- **永远不要缓存编号**，每次操作前必须重新标注
- 页面滚动、弹窗出现后编号全部失效

### 滚动与视口（重要）
- SoM 只能检测**当前视口内**的元素，滚动出去的看不到
- 价格在页面上方、运费在页面中下方 → 需要分别滚动后标注提取
- **完整信息提取流程**：页面顶部 `som-annotate`（提取价格/SKU）→ `Page_Down` → 再次 `som-annotate`（提取运费/退货）
- 滚动命令：`xdotool key Page_Down` / `xdotool key Page_Up` / `xdotool key Home` / `xdotool key End`

### 弱多模态 agent 操作模式

不需要看标注图，纯文本就能操作：

```
som-annotate → som-find --summary → 理解页面状态
                som-find "关键词" --first --cmd → 得到 som-click 命令
                直接执行 → 再 som-annotate 验证
```

**示例：完整购物流程（弱 agent 版）**
```bash
# 1. 搜索
echo -n "https://www.ebay.com/sch/i.html?_nkw=phone+case" | xclip -selection clipboard
xdotool key ctrl+l && sleep 0.3 && xdotool key ctrl+v && sleep 0.3 && xdotool key Return

# 2. 找第一个商品
som-annotate -j e.json
som-find "phone case" --first --cmd -j e.json   # → som-click 18
som-click 18 -j e.json

# 3. 提取价格
som-annotate -j e.json
som-find --extract -j e.json   # → {"prices": [{"text": "US $8.99"}], ...}

# 4. 选 SKU
som-find "Color" --first --cmd -j e.json   # → som-click 32
som-click 32 -j e.json
# ... 选具体颜色 ...

# 5. 下单
som-find "Buy" --first --cmd -j e.json   # → som-click 29
som-click 29 -j e.json
```

### 点击精度
- 实测在 2880x1800 分辨率下，点击误差 < 5 像素
- 验证通过：Chrome 标签切换、地址栏点击、页面按钮、搜索结果链接

### 文字输入（重要陷阱）

**`xdotool type` 不可靠**，以下场景会失败：
1. Chrome 地址栏：选中状态在 type 开始时被取消，文字被追加而非替换
2. 某些网站输入框（如百度搜索框）：过滤模拟键盘事件，xdotool type 完全无效

**可靠方案**：
- 输入 ASCII 文字：`echo -n "text" | xclip -selection clipboard && xdotool key ctrl+v`
- 输入中文/Unicode：同上（xclip 支持 UTF-8）
- macOS：`osascript -e 'tell application "System Events" to keystroke "text"'`

**地址栏操作最佳实践**：
```bash
# 1. 设置剪贴板
echo -n "https://example.com" | xclip -selection clipboard
# 2. 聚焦并全选地址栏
xdotool key ctrl+l
sleep 0.3
# 3. 粘贴（自动替换选中内容）
xdotool key ctrl+v
sleep 0.3
# 4. 回车导航
xdotool key Return
```

### 搜索操作最佳实践

**优先用 URL 参数搜索，不要操作搜索框表单**：
- 百度：`https://www.baidu.com/s?wd=关键词`
- Google：`https://www.google.com/search?q=keyword`
- 淘宝：`https://s.taobao.com/search?q=关键词`

原因：很多网站的搜索框有 JS 防护，拦截模拟键盘输入。URL 导航绕过所有前端防护。

### OmniParser 漏检情况

以下元素 OmniParser 检测不到（YOLO 的盲区）：
- **空白文本输入框**：没有 placeholder 或 placeholder 太淡的 input/textarea
- **纯 CSS 样式的可点击区域**：没有图标或文字的 div 按钮
- **iframe 内容**：跨域 iframe 中的元素

**应对方法**：
- 输入框找不到时，用已检测到的按钮做**相对定位**（如"百度一下"按钮左边就是搜索框）
- 或用 Tab 键导航到目标元素
- 或直接用 URL 参数绕过表单

## 安装

```bash
cd som-toolkit
bash install.sh
source venv/bin/activate
```

依赖：
- Python 3.10+
- PyTorch（自动选择 CUDA/MPS/CPU）
- OmniParser V2 模型权重（~1GB，自动从 HuggingFace 下载）
- Linux：xdotool + scrot
- macOS：screencapture（内置）+ osascript（内置）

## 电商网站操作实战指南（eBay 实测验证通过）

### 完整流程：搜索 → 详情 → 选 SKU → Buy

```
1. URL 导航到搜索结果页（不要用搜索框）
2. som-annotate → 在结果中找商品标题链接 → som-click
3. som-annotate → 看到详情页（价格、SKU 选项、Buy 按钮）
4. som-click 下拉 SKU → som-annotate → 找选项 → som-click 选项
5. 重复 4 直到所有 SKU 选完
6. som-annotate → som-click "Buy It Now"
```

### 电商搜索 URL 模板

```
eBay:         https://www.ebay.com/sch/i.html?_nkw=关键词
Amazon:       https://www.amazon.com/s?k=关键词
AliExpress:   https://www.aliexpress.com/wholesale?SearchText=关键词
Shopee(泰国): https://shopee.co.th/search?keyword=关键词
苏宁:         https://search.suning.com/关键词/
百度:         https://www.baidu.com/s?wd=关键词
```

### 下拉菜单操作技巧（关键经验）

**问题**：下拉菜单（select/dropdown）打开后，选项的位置 OmniParser 通常能检测到，但偶尔漏检。

**最佳操作流程**：
1. `som-click` 下拉触发元素（如 "Color: Select"）
2. 等 1-2 秒让下拉动画完成
3. **重新 `som-annotate`**（下拉选项是新 DOM 元素，必须重新标注）
4. 在新标注中找到目标选项 → `som-click`
5. 如果选项没被检测到，用**相对定位**：根据下拉触发元素的 y 坐标，选项通常按固定间距（约 60-80px）排列

**相对定位公式**（实测 eBay 下拉菜单）：
```
触发元素 y 坐标 + 80 = 第一个选项 "Select"
+70 = 第二个选项
+70 = 第三个选项
...
```

### 弹窗关闭技巧

**SoM 能检测到的**：
- 按钮文字型关闭（"Close"、"X"、"取消"）→ 直接 som-click

**SoM 检测不到的**：
- 透明遮罩层上的圆形 X 按钮（如京东登录弹窗）
- 解决：按 Escape / 点击遮罩区域 / 直接 URL 导航绕过

### 登录态说明

本工具操作的是用户的**真实浏览器**，浏览器中已有用户手动登录的 session。因此：
- 所有电商平台（京东、淘宝、Shopee、Amazon 等）都可以正常操作
- 登录态由浏览器 cookie 维持，工具只是模拟鼠标键盘，不碰 cookie
- 如果 session 过期，在浏览器里手动重新登录即可

### 从详情页提取信息

SoM 元素的 `content` 字段包含 OCR 识别的文字。可以从中提取：
- **价格**：搜索 `$`、`¥`、`US` 等关键词
- **运费**：搜索 `shipping`、`delivery`、`free`、`运费`
- **SKU 选项**：搜索 `color`、`size`、`select`、`fit`
- **库存**：搜索 `available`、`stock`、`sold`

示例（从 eBay 实测）：
```python
# 从 elements JSON 中提取价格
price_elements = [e for e in elements if '$' in e.get('content', '')]
# 结果: [{"index": 20, "content": "US $8.99", "center_x": 1913, "center_y": 1008}]
```

## 适用场景

- 电商商品信息抓取（价格、SKU、运费）—— 绕过反爬检测
- 多 SKU 商品的自动化选择和下单流程验证
- 桌面应用 UI 自动化测试
- 任何需要"像真人一样操作"的场景

## 不适用场景

- 高频操作（每次标注 ~170 秒 CPU / ~5 秒 GPU，不适合毫秒级自动化）
- 纯 API 可达的场景（有 API 就用 API，比 UI 自动化快 100 倍）
- 游戏/视频等高帧率动态界面
- 需要登录但无账号的中国电商平台
