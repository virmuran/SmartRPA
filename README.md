# SmartRPA — 视觉驱动的智能桌面自动化

> 不修改程序数据，不录制固定坐标，用"眼睛"看屏幕，像真人一样操作。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 它能做什么

```
传统连点器/录制脚本             SmartRPA
─────────────────────      ─────────────────────
坐标写死 → 窗口动了就废       图像识别 → 窗口随便拖
固定延迟 → 容易封号           随机延迟 + 贝塞尔鼠标 → 像真人
弹窗弹出 → 脚本卡死           自动检测弹窗 → 关闭后继续
一个任务一套代码              一套框架适配所有任务
```

### 典型场景

| 场景 | 传统方案 | SmartRPA |
| --- | --- | --- |
| 游戏重复刷本 | 连点器（封号风险） | 视觉识别 + 随机操作，安全 |
| 网站每日签到 | 手动点（浪费时间） | 自动识别按钮，弹窗自动关 |
| 数据批量录入 | 手工复制粘贴 | 识别表格 → 自动填写 |
| 多步骤重复操作 | 录屏回放（脆弱） | 行为树驱动，自适应 |

## 界面一览

SmartRPA 提供 5 个页面，通过左侧图标侧栏切换：

| 页面 | 功能 |
| --- | --- |
| 📋 **自动化任务** | 三栏布局：任务列表 → 参数配置 → 实时日志。选择任务一键运行，所见即所得 |
| 🗂 **流程编辑** | 全屏可视化流程编辑器，拖拽节点搭建自动化流程。支持行为树(BT)和平铺图两种格式 |
| ✏️ **任务编辑器** | 文字型任务列表编辑，适合快速修改 JSON 配置。BT 格式任务会提示到流程编辑页面查看 |
| ⚙ **设置** | 全局偏好：模板目录、速度模式、弹窗检测开关等 |
| ℹ **关于** | 品牌展示页，版本信息与技术栈 |

## 可视化流程编辑器

SmartRPA v2 的核心升级——用**节点 + 连线**的方式搭建自动化流程，告别手写 JSON：

- **18 种节点**，覆盖鼠标/键盘/等待/视觉/流程控制/系统操作
- **拖拽添加** → 连线建立执行顺序 → 属性面板配置参数
- **贝塞尔曲线箭头**：绿色 = 成功路径，红色 = 失败/降级路径
- **网格吸附 + 对齐辅助线**，快捷键缩放/平移
- **撤销/重做** (Ctrl+Z / Ctrl+Y)，50 步历史
- **截图关联**：属性面板直接截取目标区域作为模板
- **按键录制**：点击录制按钮 → 按键 → 自动填入键名

> 详细的节点说明请参考 [NODE_REFERENCE.md](NODE_REFERENCE.md)

## 设计理念

**不修改目标程序的数据，不注入代码，完全通过屏幕图像理解 + 模拟真人操作。**

```
┌──────────────────────────────────────────────────────────┐
│                    SmartRPA 架构 v2                       │
├────────────┬────────────┬────────────┬───────────────────┤
│  视觉识别   │  行为树引擎 │  真人模拟   │    干扰处理       │
│  模板匹配   │  BT 节点树  │  贝塞尔轨迹 │   弹窗检测        │
│  OCR 识别  │  智能重试   │  随机延迟  │   自动恢复        │
│  颜色匹配   │  分支决策   │  自然操作  │   错误降级        │
├────────────┴────────────┴────────────┴───────────────────┤
│                    设备控制层                              │
│             截图(mss) + 键鼠(pynput/pydirectinput)        │
└──────────────────────────────────────────────────────────┘
```

### 行为树引擎（v2 核心）

SmartRPA 从扁平状态机升级为**行为树 (Behavior Tree)** 驱动：

- **复合节点**：`Sequence` 顺序执行、`Selector` 择优降级、`Retry` 失败重试、`Timeout` 限时执行、`Repeat` 循环迭代
- **叶子节点**：`Action` 执行具体 RPA 操作、`Condition` 条件判断
- **JSON 序列化**：流程图所见即文件，`to_dict` / `from_dict` 双向转换
- **向后兼容**：旧版扁平 JSON 格式自动转换为 BT 树

每个节点返回三种状态之一：`SUCCESS` / `FAILURE` / `RUNNING`。

### BT 任务文件格式

```json
{
  "_meta": {
    "name": "贴吧签到",
    "window": "*百度贴吧*",
    "retry_on_failure": 2,
    "global_timeout": 600
  },
  "root": {
    "type": "sequence",
    "name": "签到流程",
    "children": [
      { "type": "click", "desc": "签到按钮", "template": "sign_btn.png", "retry": 3 },
      { "type": "wait_until", "desc": "等待结果", "template": "result.png", "timeout": 30 },
      { "type": "log", "msg": "签到完成" }
    ]
  }
}
```

## 快速开始

### 方式一：直接运行 exe（推荐，无需安装任何东西）

双击 `dist/SmartRPA.exe`

### 方式二：Python 运行

```bash
pip install -r requirements.txt
python gui.py
```

## 如何创建你的第一个自动化任务

1. **切换到「流程编辑」页面**（左侧第二个图标 🗂）
2. **在顶部下拉框选择/创建任务**
3. **从左侧节点面板拖拽节点到画布**，或点击节点按钮添加
4. **连线**：从节点的输出端口（右侧圆点）拖到下一个节点的输入端口（左侧圆点）
5. **配置参数**：双击节点打开属性面板，设置模板、阈值、等待时间等
6. **Ctrl+S 保存**，切换到「自动化任务」页面选择任务，点击「开始运行」

### 典型流程模式

```
「点击按钮(retry)」→「等待页面打开(wait_until)」→「输入文字(type)」→「回车确认(hotkey)」
```

```
「查找弹窗(find)」──找到──→「点击关闭(click)」
                  └没找到──→ 继续（selector 自动降级）
```

## 项目结构

```
SmartRPA/
├── gui.py                    # PySide6 主界面（1200+ 行，5 个页面）
├── main.py                   # 应用入口
├── requirements.txt          # Python 依赖
├── README.md                 # 你在这里
├── NODE_REFERENCE.md         # 节点速查表
├── build.bat / pack.bat      # 打包脚本
├── SmartRPA.spec             # PyInstaller spec
│
├── smartrpa/                 # 核心库
│   ├── __init__.py
│   ├── core/
│   │   ├── behavior_tree.py  #   行为树引擎（1300+ 行）
│   │   │                     #     BTNode → Sequence/Selector/Retry/
│   │   │                     #     Timeout/Inverter/Repeat/Parallel
│   │   │                     #     ActionNode 支持 18 种 RPA 操作
│   │   │                     #     ConditionNode 条件判断
│   │   │                     #     _meta 全局重试/超时/窗口锚定
│   │   ├── controller.py     #   设备控制（截图 mss + 键鼠 pynput）
│   │   ├── vision.py         #   视觉识别器（模板匹配/OCR/颜色）
│   │   ├── human.py          #   人类行为模拟（贝塞尔轨迹/随机延迟）
│   │   └── popup.py          #   弹窗检测拦截
│   └── ui/
│       ├── __init__.py
│       └── flow_editor.py    #   可视化流程编辑器（1700+ 行）
│                              #     FlowScene / FlowNode / FlowArrow
│                              #     PropertyEditor / NodePalettePanel
│                              #     撤销重做 / 网格吸附 / 辅助线
│
├── examples/                 # 示例任务
│   ├── tieba/                #   贴吧签到（BT 格式，38 节点）
│   └── bing_farmer/          #   Bing Rewards 刷分
│
├── config/                   # 全局配置
│   └── maa_option.json       #   MAA 风格参数
│
└── tests/                    # 测试
```

## 常见问题

**Q: 不知道该用什么节点？**
A: 参考 [NODE_REFERENCE.md](NODE_REFERENCE.md)，按「鼠标 / 键盘 / 等待 / 视觉 / 流程 / 系统」六大类查找。遇到具体场景不知怎么组合，从「顺序执行 + 关键步骤加 retry」开始就够用了。

**Q: 弹窗老是被识别错？**
A: 检查模板截图的精度——尽量截取弹窗的**唯一特征**部分。可以在节点属性里提高 `threshold`（精确度阈值，默认 0.8）。

**Q: BT 格式和旧版 JSON 有什么区别？**
A: 旧版是扁平的任务列表（"TaskA" → "TaskB"），BT 是树形结构，支持复合节点嵌套。系统会自动检测格式，旧版任务运行时自动转换为 BT。

## 如何贡献

欢迎提交 Issue 和 PR！

- 新增任务模板 → `examples/` 目录
- 修复 Bug → 提 PR
- 新功能建议 → 开 Discussion

## License

MIT License — 版权归社区所有，欢迎自由使用和修改。
