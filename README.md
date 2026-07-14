<div align="center">

# SmartRPA

<br>
<div>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.13-%233776AB?logo=python">
    <img alt="platform" src="https://img.shields.io/badge/platform-Windows-blueviolet">
    <img alt="license" src="https://img.shields.io/badge/license-AGPL--3.0-green">
</div>
<br>

一款桌面自动化工具

基于图像识别与行为树引擎，零代码搭建你的自动化任务！

</div>

## 下载与安装

```bash
# 克隆仓库
git clone https://github.com/virmuran/SmartRPA.git
cd SmartRPA

# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 启动
python main.py
```

> 需要 **Windows** 系统，Python 3.13+。

## 亮点功能

- **MAA 风格步骤编辑器** — 框选 ROI + 截取模板，线性步骤编排，所见即所得
- **行为树引擎** — 支持 Sequence / Selector / Retry / Timeout / ForEach / Parallel 等节点，灵活编排复杂流程
- **窗口锚定** — 自动识别目标窗口，基于 Client Area 坐标系，窗口放哪都能跑
- **BitBlt 高速截屏** — 使用 win32gui 直接读取显存缓冲区，比传统截屏快 3~5 倍
- **窗口位置记忆** — 记录编辑时的窗口位置与大小，运行时自动恢复
- **循环节点** — 内置 ForEach 网格遍历，展开一个 9×5 网格只需 7 行 JSON
- **模板匹配 + ROI 约束** — OpenCV 模板匹配限定搜索区域，精准快速
- **真人模拟点击** — 带随机偏移的鼠标点击，降低被检测风险
- **弹窗自动处理** — 运行时检测并关闭弹出的通知窗口
- **任务文件管理** — 导入 / 导出 ZIP，随时备份和迁移任务

## 使用说明

### 自动化任务页

在「自动化任务」页选择已有任务或新建任务，点击运行即可。

### MAA 模式编辑器

1. 选择目标窗口（自动扫描当前打开的所有窗口）
2. 点击「截图」框选屏幕区域，生成模板图片
3. 点击「框选ROI」限定模板搜索范围
4. 设置匹配阈值（默认 0.8）
5. 选择动作类型（click / find / wait_until 等）
6. 保存任务文件，一键运行

所有坐标基于窗口内容区（Client Area），切换电脑、改变窗口位置均不影响使用。

### 循环与网格扫描

使用 `for_each` 节点轻松遍历网格：

```json
{
  "type": "for_each",
  "x_list": [128, 284, 439, 595, 751],
  "y_list": [196, 363, 530, 697, 819],
  "child": { "type": "click", "params": { "x": "$x", "y": "$y" } }
}
```

任务文件使用 JSON 格式，完整语法请参阅 [NODE_REFERENCE.md](smartrpa/NODE_REFERENCE.md)。

## 项目结构

```
SmartRPA/
├── main.py                 # 入口
├── smartrpa/
│   ├── core/               # 核心引擎
│   │   ├── controller.py   # BitBlt 截屏 + 键鼠操作
│   │   ├── vision.py       # 模板匹配 + OCR 识别
│   │   ├── behavior_tree.py # 行为树引擎（节点调度）
│   │   └── engine.py       # 经典状态机引擎
│   └── ui/                 # PySide6 界面
│       ├── main_window.py  # 主窗口 + 侧边栏
│       ├── task_page.py    # 任务运行页面
│       ├── maa_editor.py   # MAA 风格步骤编辑器
│       ├── flow_editor.py  # 流程编辑器
│       └── settings_page.py # 系统设置 + 高级工具
└── tasks/                  # 任务文件目录
```

## 加入我们

### 任务示例

| 任务 | 说明 |
|------|------|
| `tasks/baidu_sign/` | 百度贴吧自动签到 |
| `tasks/bing_points/` | Bing 积分自动领取 |
| `tasks/endfield_essence/` | 终末地·基质识别扫描 |

### 致谢

- 图像识别：[OpenCV](https://github.com/opencv/opencv)
- 界面框架：[PySide6](https://pypi.org/project/PySide6/)
- 致敬项目：[MAA (MaaAssistantArknights)](https://github.com/MaaAssistantArknights/MaaAssistantArknights)
- 仿照参考：[endfield-essence-recognizer](https://github.com/Logical-Byte/endfield-essence-recognizer)

### 参与开发

欢迎提交 Issue 和 Pull Request。

## 声明

- 本软件使用 [GNU Affero General Public License v3.0](https://spdx.org/licenses/AGPL-3.0-only.html) 开源。
- 本软件开源、免费，仅供学习交流使用。若您遇到商家使用本软件进行代练并收费，产生的问题及后果与本软件无关。
