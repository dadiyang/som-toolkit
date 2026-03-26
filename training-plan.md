# SoM Agent 培训计划

## 目标
让 Qwen3.5-35B（通过 opencode）能独立使用 SoM 工具集完成电商网站操作：搜索商品 → 进详情 → 提取价格运费 → 选 SKU → 点 Buy。

## 通信方式
- 发消息：`POST http://127.0.0.1:8981/api/inject` body `{"window_name": "local-llm-workspace", "text": "..."}`
- 读输出：`GET http://127.0.0.1:8981/api/output/local-llm-workspace`
- 工具路径：`/home/irons/local-llm-workspace/som-toolkit/`

## 训练阶段

### Phase 1：工具认知（验证能读懂技能文件）

**目标**：确认 agent 理解每个工具的用途和参数

**任务 1.1**：读技能文件
```
请阅读 som-toolkit/skill-som-ui-automation.md，然后告诉我：
1. som-annotate 是做什么的？
2. som-find --extract 输出什么？
3. 点击商品后如果在新标签打开了，下一步应该做什么？
```

**验收**：能正确回答三个问题
**预期风险**：35B 模型可能遗漏细节或编造不存在的参数

### Phase 2：单工具执行（验证能正确调用）

**目标**：逐个工具验证 agent 能正确执行

**任务 2.1**：截图标注
```
执行以下命令并告诉我结果：
DISPLAY=:10.0 PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True CUDA_VISIBLE_DEVICES="" \
  python3 som-toolkit/som-annotate --screenshot som-toolkit/omniparser/imgs/demo.png \
  -o /tmp/train_test.png -j /tmp/train_test.json -q
然后执行：python3 som-toolkit/som-find --summary -j /tmp/train_test.json
```

**任务 2.2**：查找元素
```
执行：python3 som-toolkit/som-find "button" -j /tmp/train_test.json
告诉我找到了几个按钮。
```

**任务 2.3**：点击
```
执行：python3 som-toolkit/som-click --xy 100,100
```

**验收**：每个命令能正确执行，输出合理
**预期风险**：
- 忘记设环境变量 DISPLAY
- 路径写错
- 不理解 --json 参数需要指向哪个文件

### Phase 3：两步组合（标注→查找）

**目标**：验证能组合两个工具

**任务**：
```
你的工作目录是 /home/irons/local-llm-workspace。
请完成以下步骤：
1. 对文件 som-toolkit/omniparser/imgs/demo.png 进行 SoM 标注
2. 用 som-find --summary 查看页面概览
3. 用 som-find 找到所有包含 "search" 的元素
4. 告诉我哪个编号最可能是搜索按钮
```

**验收**：能串联执行，结论合理
**预期风险**：
- 第 2 步用错 JSON 路径
- 不会根据元素内容判断哪个是搜索按钮

### Phase 4：真实网页操作（核心验证）

**目标**：操作真实浏览器访问 eBay 并提取信息

**任务 4.1**：导航
```
请执行以下操作：
1. 在浏览器中打开 eBay 搜索 "wireless earbuds"
   方法：先设置剪贴板，再用快捷键导航
   echo -n "https://www.ebay.com/sch/i.html?_nkw=wireless+earbuds" | xclip -selection clipboard
   DISPLAY=:10.0 xdotool key ctrl+l && sleep 0.3 && DISPLAY=:10.0 xdotool key ctrl+v && sleep 0.3 && DISPLAY=:10.0 xdotool key Return
2. 等待 8 秒
3. 执行 som-annotate 标注当前页面
4. 用 som-find --summary 看到了什么
```

**任务 4.2**：点击商品
```
基于上一步的标注结果：
1. 用 som-find 找到第一个商品标题（搜索 "earbuds" 相关内容）
2. 用 som-click 点击它
3. 【重要】电商网站商品会在新标签打开！执行：DISPLAY=:10.0 xdotool key ctrl+Tab
4. 等 3 秒后重新 som-annotate
5. 用 som-find --extract 提取价格信息
```

**任务 4.3**：选 SKU + Buy
```
基于当前商品详情页：
1. som-find "Color" 找到颜色选择器
2. som-click 点击它打开下拉
3. 等 2 秒，重新 som-annotate（下拉选项是新元素）
4. som-find 找到具体颜色选项，som-click 选择
5. 重复以上步骤选择其他 SKU
6. som-find "Buy" 找到购买按钮
7. 【重要】重新 som-annotate 获取最新坐标！
8. som-click 点击 Buy
9. 截图验证是否弹出结账窗口
```

**验收**：完成全流程，弹出 Sign in / Guest checkout 弹窗
**预期风险**（核心）：
- 忘记新标签切换
- 用旧编号点击（最常见错误）
- 忘记在下拉菜单打开后重新标注
- DISPLAY 环境变量漏设
- som-annotate 耗时长，agent 可能以为卡住了

### Phase 5：独立执行（毕业考试）

**目标**：不给步骤提示，只给目标

**任务**：
```
请使用 som-toolkit 工具集完成以下任务：

在 eBay 上找一个 "bluetooth speaker" 商品，进入详情页，选择一个 SKU（如颜色），
提取价格和运费信息，然后点击 Buy It Now。

工具在 som-toolkit/ 目录，技能说明在 som-toolkit/skill-som-ui-automation.md。
请先阅读技能文件，然后按文件中的标准操作流程执行。

注意事项：
- 每次操作后必须重新 som-annotate，不要用旧编号
- 商品可能在新标签打开，注意切换
- 搜索用 URL 导航，不要操作搜索框
```

**验收**：能独立完成，过程中不需要人工干预

## 训练原则

1. **每个阶段验证通过再进下一阶段**，不要跳级
2. **失败时分析根因**：是模型不理解指令？还是工具有 bug？还是技能文件描述不清？
3. **优化技能文件而非改指令**：如果 agent 反复犯同一个错误，说明技能文件需要更强调
4. **不要过度拟合具体网站**：优化的是"操作流程"，不是"eBay 的第几个按钮"
5. **记录每次失败的根因**：形成"常见错误→修复"对照表，写入技能文件的经验区
