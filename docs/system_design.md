# SmartRPA v3 系统架构设计文档

> 架构师：Bob（高见远） | 版本：v0.7.6 → v3.0.0 | 日期：2025-07-18

---

## 目录

1. [实现方案](#1-实现方案)
2. [架构设计](#2-架构设计)
3. [文件列表](#3-文件列表)
4. [数据结构设计](#4-数据结构设计)
5. [任务列表](#5-任务列表)
6. [依赖包列表](#6-依赖包列表)
7. [共享知识](#7-共享知识)
8. [风险与待明确事项](#8-风险与待明确事项)

---

## 1. 实现方案

### 1.1 重构策略：渐进式重构（Refactor, not Rewrite）

**核心决策：在现有代码基础上重构，而非完全重写。**

| 层级 | 策略 | 说明 |
|------|------|------|
| **引擎层** (core/) | **保留** | Controller/Vision/TaskEngine/BTEngine/Human/Popup 已经稳定，API 不变 |
| **UI 层** (gui.py) | **拆分重构** | 将 2900+ 行的单文件拆为多个模块，废弃旧 tab 结构 |
| **业务层** | **新增** | 新增 TaskManager 管理任务的增删改查和生命周期 |
| **配置/数据** | **扩展** | 新增 history 存储、设置持久化增强 |

**理由**：
- 引擎层已有 v0.7.6 的实战验证，Controller/Vision/TaskEngine 的截图+模板匹配+键鼠控制链成熟可靠
- 问题集中在 UI 层的职责混乱（2900 行单文件同时处理 UI 构建、业务逻辑、录制、运行调度）
- 完全重写 engine 风险高、收益低——现有引擎已经能"跑通"
- 重构 UI 即可满足 v3 北极星指标（< 3 分钟首次成功运行）

### 1.2 各文件处置明细

| 文件 | 操作 | 说明 |
|------|------|------|
| `gui.py` | **拆分 → 废弃** | 将内容拆入新 UI 模块后删除 |
| `main.py` | **修改** | 指向新入口 |
| `smartrpa/__init__.py` | **修改** | 版本号升级，导出新增模块 |
| `smartrpa/core/controller.py` | **保留（微调）** | 可能增加录制相关的辅助方法 |
| `smartrpa/core/vision.py` | **保留** | 不变 |
| `smartrpa/core/engine.py` | **保留** | 不变 |
| `smartrpa/core/behavior_tree.py` | **保留** | 不变 |
| `smartrpa/core/human.py` | **保留** | 不变 |
| `smartrpa/core/popup.py` | **保留** | 不变 |
| `smartrpa/ui/flow_editor.py` | **保留（微调）** | 仅高级模式可见 |
| `smartrpa/ui/` | **新增模块** | main_window, task_page, history_page, settings_page, advanced_page, recorder, worker, theme |
| `smartrpa/task_manager.py` | **新增** | 任务生命周期管理（CRUD + 扫描 + 历史） |
| `smartrpa/history.py` | **新增** | 运行历史记录管理 |
| `smartrpa/settings.py` | **新增** | 设置管理（封装 QSettings） |
| `requirements.txt` | **修改** | 保持现有依赖，无需新增 |

---

## 2. 架构设计

### 2.1 四层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     展示层 (Presentation)                     │
│  main_window.py  task_page.py  history_page.py               │
│  settings_page.py  advanced_page.py  theme.py                │
│  recorder.py  worker.py  flow_editor.py (保留)               │
├─────────────────────────────────────────────────────────────┤
│                     业务层 (Business)                         │
│  task_manager.py  history.py  settings.py                    │
├─────────────────────────────────────────────────────────────┤
│                     引擎层 (Engine)                           │
│  engine.py  behavior_tree.py  popup.py                       │
├─────────────────────────────────────────────────────────────┤
│                     驱动层 (Driver)                           │
│  controller.py  vision.py  human.py                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 各层职责与关键类

#### 驱动层：无状态工具层，负责与操作系统/硬件交互

| 类 | 文件 | 职责 |
|----|------|------|
| `Controller` | `core/controller.py` | 截图(mss)、鼠标移动/点击、键盘输入、多显示器管理。保留。 |
| `Vision` | `core/vision.py` | 模板匹配(多尺度/多角度)、颜色检测、OCR。保留。 |
| `HumanLike` | `core/human.py` | 贝塞尔曲线轨迹、随机延迟。保留。 |
| `PopupHandler` | `core/popup.py` | 弹窗检测与自动关闭。保留。 |

#### 引擎层：编排单个自动化任务的执行

| 类 | 文件 | 职责 |
|----|------|------|
| `TaskEngine` | `core/engine.py` | 状态机驱动，加载 flat JSON 并按 next 链执行。保留。 |
| `BTEngine` | `core/behavior_tree.py` | 行为树引擎，支持高级编排。保留（高级模式用）。 |
| `ActionRecorder` | `ui/recorder.py` | **从 gui.py 提取**，录制鼠标/键盘事件并生成 task.json。 |
| `TaskWorker` | `ui/worker.py` | **从 gui.py 提取**，QThread 包装，运行单个任务并发射信号。 |

#### 业务层：管理任务、历史、设置的生命周期

| 类 | 文件 | 职责 |
|----|------|------|
| `TaskManager` | `task_manager.py` | 任务扫描、CRUD、排序、重命名、删除。管理 `_task_map`。 |
| `HistoryStore` | `history.py` | 运行历史记录写入/查询/统计。JSON 文件存储。 |
| `AppSettings` | `settings.py` | 封装 QSettings，读写热键、速度、主题等配置。 |

#### 展示层：用户界面

| 类 | 文件 | 职责 |
|----|------|------|
| `Theme` | `ui/theme.py` | **从 gui.py 提取**，设计系统主题 tokens + QSS 生成。 |
| `MainWindow` | `ui/main_window.py` | 主窗口骨架：侧边栏导航 + StackedWidget 内容区 + 状态栏。 |
| `TaskPage` | `ui/task_page.py` | 首页：任务清单(QListWidget+勾选) + 录制/运行按钮 + 日志面板。 |
| `HistoryPage` | `ui/history_page.py` | 运行历史记录列表，成功/失败统计。 |
| `SettingsPage` | `ui/settings_page.py` | 设置页：热键配置、速度、模板路径等。 |
| `AdvancedPage` | `ui/advanced_page.py` | 高级模式入口：流程编辑器、行为树编辑（保留 flow_editor）。 |
| `ActionRecorder` | `ui/recorder.py` | 录制线程，从 gui.py 提取 |
| `TaskWorker` | `ui/worker.py` | 任务执行线程，从 gui.py 提取 |
| `FlowEditor` | `ui/flow_editor.py` | 保留，仅高级模式可见 |

### 2.3 MainWindow 页面导航（新版 4 Tab）

```
Sidebar（固定 180px）
├── 📋 任务      → TaskPage       (index 0, 默认)
├── 📊 历史      → HistoryPage    (index 1)
├── ⚙ 设置      → SettingsPage   (index 2)
└── 🔧 高级      → AdvancedPage   (index 3, 入口隐蔽)
```

与 PRD 完全对齐。"流程编辑"和"任务编辑器"合并为"高级"页。

---

## 3. 文件列表

```
SmartRPA/
├── main.py                              # [修改] 入口 → from smartrpa.ui.main_window import main
├── requirements.txt                     # [修改] 保持现有，无需新依赖
│
├── smartrpa/
│   ├── __init__.py                      # [修改] __version__ = "3.0.0"
│   │
│   ├── core/                            # ── 引擎层 · 全部保留 ──
│   │   ├── __init__.py                  # [保留]
│   │   ├── controller.py               # [保留，微调]
│   │   ├── vision.py                    # [保留]
│   │   ├── engine.py                    # [保留]
│   │   ├── behavior_tree.py            # [保留]
│   │   ├── human.py                     # [保留]
│   │   └── popup.py                     # [保留]
│   │
│   ├── ui/                              # ── 展示层 · 新增/拆分 ──
│   │   ├── __init__.py                  # [修改] 导出新 UI 模块
│   │   ├── theme.py                     # [新增] 从 gui.py 提取 Theme 类 + QSS 构建
│   │   ├── main_window.py              # [新增] MainWindow 主窗口骨架
│   │   ├── task_page.py                # [新增] 首页·任务清单页
│   │   ├── history_page.py             # [新增] 历史记录页
│   │   ├── settings_page.py            # [新增] 设置页
│   │   ├── advanced_page.py            # [新增] 高级模式页（包装 flow_editor）
│   │   ├── recorder.py                 # [新增] 从 gui.py 提取 ActionRecorder
│   │   ├── worker.py                   # [新增] 从 gui.py 提取 TaskWorker
│   │   └── flow_editor.py              # [保留，微调]
│   │
│   ├── task_manager.py                 # [新增] 业务层·任务管理器
│   ├── history.py                       # [新增] 业务层·历史记录管理
│   └── settings.py                      # [新增] 业务层·设置管理
│
├── gui.py                              # [废弃] 内容已拆分到各新模块
├── examples/                           # [保留] 示例任务
├── tests/                              # [保留] 测试
└── docs/
    ├── system_design.md                 # [新增] 本文档
    ├── class-diagram.mermaid            # [新增] 类图
    └── sequence-diagram.mermaid         # [新增] 时序图
```

---

## 4. 数据结构设计

### 4.1 录制事件数据格式（AudioRecorder 内部使用）

```python
# 录制过程中，事件以元组列表形式暂存于内存
# 格式: List[Tuple[float, str, Any]]
# 每个元组: (timestamp, event_type, data)

events = [
    (1700000000.123, "click",   (450, 320)),     # 点击坐标
    (1700000001.456, "press",   "enter"),         # 按键
    (1700000002.789, "click",   (600, 500)),
    (1700000004.012, "press",   "ctrl+c"),        # 组合键
]
```

### 4.2 任务配置 JSON Schema（录制生成 & 引擎消费）

```json
{
  "_meta": {
    "name": "string, required — 任务显示名称",
    "created": "string, ISO datetime — 创建时间",
    "modified": "string, ISO datetime — 最后修改时间",
    "version": "string, '3.0' — schema 版本",
    "window": "string, optional — 窗口标题锚定(支持*通配符)",
    "speed": "string, 'normal'|'fast' — 执行速度"
  },
  "Step1": {
    "desc": "string — 步骤描述（日志显示）",
    "action": "string — click|press|type|wait|wait_until|hotkey|move",
    "params": {
      "template": "string — 模板图片名(不含扩展名), click/move/wait_until 用",
      "threshold": "number — 匹配阈值, 默认 0.8",
      "multi_scale": "boolean — 多尺度匹配, 默认 true",
      "key": "string — 按键名, press 用",
      "text": "string — 输入文本, type 用",
      "seconds": "number — 等待秒数, wait 用",
      "timeout": "number — 超时秒数, wait_until 用",
      "keys": "string[] — 组合键, hotkey 用",
      "x": "number — 绝对坐标x(截图锚定时备用)",
      "y": "number — 绝对坐标y(截图锚定时备用)"
    },
    "next": ["Step2"],
    "retry": {"count": 3, "interval": 1.0}
  }
}
```

**关键设计决策**：
- 录制时默认使用 `template` 定位（截图锚定），而非固定坐标
- `params.x` / `params.y` 仅作为模板匹配失败时的 fallback
- 录制时自动为每个 click 生成 60×60 截图作为模板，阈值设为 0.7（容忍 UI 微小变化）

### 4.3 运行历史记录格式

```json
{
  "id": "string — UUID",
  "task_name": "string — 任务名",
  "started_at": "string — ISO datetime",
  "finished_at": "string — ISO datetime",
  "status": "string — success|failed|stopped",
  "stats": {
    "steps": 12,
    "errors": 0,
    "popups_handled": 2
  },
  "checked_steps": ["Step1", "Step2", ...]
}
```

存储位置：`%APPDATA%/SmartRPA/history/YYYY-MM.json`（按月分文件，JSON Lines 格式追加写入）

### 4.4 设置存储格式

通过 QSettings 持久化：

| Key | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `theme` | str | `"light"` | 主题模式 |
| `record/hotkey` | str | `"Key.f6"` | 停止录制快捷键 |
| `global_hotkey` | str | `"<ctrl>+<shift>+r"` | 全局运行/停止快捷键 |
| `speed/fast_mode` | bool | `false` | 极速模式 |
| `popup_detect` | bool | `true` | 弹窗检测 |
| `schedule/enabled` | bool | `false` | 定时任务开关 |
| `schedule/task` | str | `""` | 定时任务名 |
| `schedule/freq` | str | `"每天"` | 定时频率 |
| `schedule/time` | str | `""` | 定时时间 HH:mm |

---

## 5. 任务列表

### T01: 项目基础设施 + 主题系统提取

- **优先级**: P0
- **依赖**: 无
- **源文件**:
  - `smartrpa/ui/__init__.py` [修改] — 导出新模块
  - `smartrpa/ui/theme.py` [新增] — 从 gui.py 提取 Theme 类 + QSS 构建函数
  - `smartrpa/settings.py` [新增] — AppSettings 封装 QSettings
  - `main.py` [修改] — 指向新入口
  - `smartrpa/__init__.py` [修改] — 版本号 → 3.0.0
- **产出**: Theme 和 AppSettings 可独立使用，主入口可运行（空窗口）

### T02: 业务层（TaskManager + HistoryStore）

- **优先级**: P0
- **依赖**: T01
- **源文件**:
  - `smartrpa/task_manager.py` [新增] — 任务扫描、CRUD、排序、重命名、删除
  - `smartrpa/history.py` [新增] — HistoryStore 运行历史记录管理
  - `smartrpa/settings.py` [修改] — 补充（如需要）
- **产出**: TaskManager 和 HistoryStore 可独立测试，能扫描 %APPDATA%/SmartRPA/tasks/ 并管理任务

### T03: UI 骨架 + 首页任务清单页

- **优先级**: P0
- **依赖**: T02
- **源文件**:
  - `smartrpa/ui/main_window.py` [新增] — MainWindow 骨架（侧边栏 + StackedWidget + 状态栏 + 系统托盘 + 调度定时器）
  - `smartrpa/ui/task_page.py` [新增] — 任务清单页（勾选列表 + 录制/运行按钮 + 日志面板 + 模板路径 + 区域选择 + 速度切换）
  - `smartrpa/ui/recorder.py` [新增] — 从 gui.py 提取 ActionRecorder
  - `smartrpa/ui/worker.py` [新增] — 从 gui.py 提取 TaskWorker
  - `smartrpa/ui/theme.py` [修改] — 补充 task_page 用到的样式
- **产出**: 可启动的 v3 主页，任务清单可见，录制功能可用，运行功能可用

### T04: 历史页 + 设置页

- **优先级**: P1
- **依赖**: T03
- **源文件**:
  - `smartrpa/ui/history_page.py` [新增] — 历史记录列表 + 成功/失败统计 + 筛选
  - `smartrpa/ui/settings_page.py` [新增] — 设置页（热键配置 + 速度 + 弹窗开关 + 全局快捷键 + 定时任务）
  - `smartrpa/ui/main_window.py` [修改] — 注册 history/settings 页面到 StackedWidget
- **产出**: 完整的历史记录查看和设置配置能力

### T05: 高级页 + 集成收尾

- **优先级**: P2
- **依赖**: T04
- **源文件**:
  - `smartrpa/ui/advanced_page.py` [新增] — 高级模式页（流程编辑器入口 + 行为树编辑入口 + 隐藏入口设计）
  - `smartrpa/ui/flow_editor.py` [修改，微调] — 适配新的页面嵌入方式
  - `smartrpa/ui/main_window.py` [修改] — 注册高级页
  - `gui.py` [废弃] — 删除旧文件（或保留为备份）
- **产出**: 完整 v3 应用，四个 tab 齐全，高级功能对普通用户隐藏

---

## 6. 依赖包列表

```
opencv-python>=4.8       # 模板匹配、图像处理
numpy>=1.24              # 数组操作（OpenCV 依赖）
mss>=9.0                 # 跨平台高速截图
pydirectinput>=1.0       # DirectInput 键鼠操作（游戏兼容）
PySide6>=6.5             # Qt GUI 框架
pywin32>=306             # Windows API（窗口锚定、句柄操作）
screeninfo>=0.8          # 多显示器信息检测
pynput>=1.8              # 全局键盘监听（录制 + 全局快捷键）
```

**无需新增任何第三方依赖。** v3 完全复用现有依赖栈。

---

## 7. 共享知识

### 7.1 命名约定

| 范畴 | 约定 | 示例 |
|------|------|------|
| 模块文件 | `snake_case` | `task_page.py`, `task_manager.py` |
| 类名 | `PascalCase` | `TaskManager`, `HistoryStore`, `MainWindow` |
| 方法/函数 | `snake_case`，私有以 `_` 开头 | `_scan_tasks()`, `get_task_list()` |
| Qt 信号 | 名词/动词短语 | `task_changed = Signal(str)` |
| 槽函数 | `_on_` 前缀 | `_on_record_clicked()` |
| UI 控件 | `snake_case`，类型后缀可选 | `run_btn`, `task_list`, `log_text` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_HOTKEY`, `TASK_DIR` |
| 数据目录 | `data_dir(subdir)` 函数 | `data_dir("tasks")` |

### 7.2 设计模式

| 模式 | 应用场景 |
|------|----------|
| **Signal-Slot (Observer)** | UI 层所有跨组件通信（PySide6 原生） |
| **Strategy** | TaskEngine vs BTEngine：统一 `run/stop` 接口，`TaskWorker` 透明切换 |
| **Singleton (Module-level)** | `Theme` 全局实例 `T`、`AppSettings` 全局实例 |
| **Repository** | `TaskManager` 封装任务数据访问，UI 层不直接读文件系统 |
| **Template Method** | `TaskEngine._execute_step()` 分发到 `_do_click/_do_press/...`，子步骤可覆盖 |

### 7.3 编码规范

- **UI 与业务分离**：展示层类不直接操作文件系统，通过 TaskManager/HistoryStore/AppSettings 访问
- **线程安全**：所有引擎操作在 QThread 中执行，UI 更新通过 Signal 回到主线程
- **日志格式**：统一使用 `[HH:MM:SS] [LEVEL] message`，日志文件最大 2000 行
- **错误处理**：引擎层异常在 TaskWorker.run() 的 try/except 中捕获，通过 Signal 报告
- **路径处理**：使用 `data_dir()` 函数统一获取用户数据目录（`%APPDATA%/SmartRPA`）
- **模板图片**：统一 PNG 格式，存储在 `{task_dir}/templates/` 下
- **向后兼容**：TaskManager 必须能读取 v0.7.x 的 task.json 格式（flat JSON + _meta）

### 7.4 组件通信流

```
用户点击"录制" 
  → TaskPage._on_record_clicked()
  → ActionRecorder.start()
  → ActionRecorder 通过 Signal 发送 log 到 TaskPage
  → 录制完成 → TaskPage 通过 TaskManager 重新扫描
  → 新任务出现在列表中

用户点击"开始运行"
  → TaskPage._on_run_clicked()
  → 遍历勾选的任务 → 依次创建 TaskWorker
  → TaskWorker 通过 Signal 发送 log/step/finished
  → 单个任务完成 → TaskPage 通过 HistoryStore 写入历史
  → 全部完成 → 恢复窗口
```

---

## 8. 风险与待明确事项

### 8.1 已识别风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| gui.py 拆分时遗漏功能 | 中 | PRD 明确列出 P0 功能，逐项对照。保留旧 gui.py 作为参考直到 v3 稳定 |
| 录制时截图定位漂移（不同分辨率/DPI） | 中 | 录制时使用 0.7 低阈值 + 多尺度匹配。后续可增加录制时的显示器 DPI 记录 |
| 旧版 task.json 兼容性 | 低 | 新旧格式共用 `_meta`，引擎已支持。仅需 TaskManager 正确解析 |
| PySide6 版本升级导致渲染差异 | 低 | 锁定 `>=6.5`，不升级大版本 |

### 8.2 待明确事项

1. **"高级"页入口隐蔽程度**：PRD 说"入口隐蔽"，具体是多隐蔽？建议方案：
   - 侧边栏"高级"按钮默认隐藏，在设置页底部放一个"启用高级模式"开关
   - 或连续点击版本号 5 次触发
   
2. **任务排序**：PRD 提到"支持排序"——是手动拖拽排序还是按名称/时间排序？建议先实现按录制时间倒序（最新在上），手动排序放 P2

3. **多任务并行运行**：PRD 描述"勾选多个任务 → 点开始运行"，是否支持多个任务同时跑？建议 P0 只支持串行（逐个运行），并行放 P2

4. **录制是否支持键盘组合键**：现有录制代码仅捕获单个按键。建议 P0 只支持单键，组合键留给高级模式

5. **最小化到系统托盘**：PRD 说"软件最小化 → 用户操作"。v0.7.6 已有系统托盘实现，确认保留即可

---

## 附录 A：类图

另见 `docs/class-diagram.mermaid`

## 附录 B：时序图

另见 `docs/sequence-diagram.mermaid`
