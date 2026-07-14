"""生成终结地基质识别完整任务JSON（9列×5行扫描网格）"""
import json
import numpy as np

# Resolution1080p coordinates
X_LIST = np.linspace(128, 1374, 9).astype(int).tolist()
Y_LIST = np.linspace(196, 819, 5).astype(int).tolist()

# All attribute template names
ATTR_TEMPLATES = [
    "gat_passive_attr_atk", "gat_passive_attr_hp", "gat_passive_attr_agi",
    "gat_passive_attr_str", "gat_passive_attr_will", "gat_passive_attr_wisd",
    "gat_passive_attr_crirate", "gat_passive_attr_heal",
    "gat_passive_attr_firedam", "gat_passive_attr_icedam", "gat_passive_attr_phydam",
    "gat_passive_attr_magicdam", "gat_passive_attr_naturaldam", "gat_passive_attr_pulsedam",
    "gat_passive_attr_physpell", "gat_passive_attr_usp", "gat_passive_attr_main",
]

children = []

# Step 1: Wait until we're on the inventory screen
children.append({
    "name": "等待进入背包界面",
    "type": "wait_until",
    "params": {
        "template": "武器基质",
        "roi": [38, 66, 105, 40],
        "threshold": 0.85,
        "timeout": 15
    }
})

# Step 2: Scan each grid cell
for col, x in enumerate(X_LIST):
    for row, y in enumerate(Y_LIST):
        cell_step = {
            "name": f"扫描基质[列{col+1}行{row+1}]",
            "type": "sequence",
            "children": [
                {
                    "name": f"点击基质({x},{y})",
                    "type": "click",
                    "params": {"x": x, "y": y}
                },
                {
                    "name": "等待详情加载",
                    "type": "wait",
                    "params": {"seconds": 0.8}
                },
                {
                    "name": "截图记录当前基质",
                    "type": "wait",
                    "params": {"seconds": 0.1}
                },
            ]
        }
        children.append(cell_step)

task = {
    "_meta": {
        "name": "终末地·基质扫描(完整9×5)",
        "window": "Endfield",
        "fix_window": [0, 0, 1920, 1080],
        "resolution": "1080p (1920×1080)",
        "created": "2026-07-14T10:00:00",
        "modified": "2026-07-14T10:00:00",
    },
    "root": {
        "type": "sequence",
        "name": "基质扫描主流程",
        "children": children
    }
}

path = r"C:\Users\Administrator\Desktop\SmartRPA\tasks\endfield_essence\task_full.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(task, f, ensure_ascii=False, indent=2)

print(f"Generated full grid task: {len(children)} steps (1 wait + {len(X_LIST)*len(Y_LIST)} scans)")
print(f"Saved to: {path}")
