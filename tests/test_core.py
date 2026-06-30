import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from smartrpa.core.human import generate_bezier_path
from smartrpa.core.vision import Vision
from smartrpa.core.engine import TaskEngine
from smartrpa.core.controller import Controller
from smartrpa.core.popup import PopupHandler


def test_bezier_path():
    """测试贝塞尔曲线生成"""
    path = generate_bezier_path((0, 0), (100, 100), steps=20)
    assert len(path) == 21  # steps+1个点
    assert path[0] == (0, 0) or abs(path[0][0]) + abs(path[0][1]) < 2
    assert path[-1][0] > 80 and path[-1][1] > 80
    print("  ✓ 贝塞尔曲线路径生成")


def test_color_match():
    """测试颜色识别"""
    vision = Vision()
    # 创建一个模拟的2048方块（8号=橙色）
    # BGR of #F2B179 ≈ (121, 177, 242)
    tile = np.full((50, 50, 3), [121, 177, 242], dtype=np.uint8)
    TILE_COLORS = {
        8: ((110, 165, 230), (135, 190, 250)),
        0: ((185, 180, 165), (215, 210, 195)),
    }
    result = vision.match_color(tile, (0, 0, 50, 50), TILE_COLORS)
    assert result == 8, f"Expected 8, got {result}"
    print("  ✓ 颜色识别")


def test_template_match():
    """测试模板匹配"""
    vision = Vision()
    # 创建模拟的模板和搜索图像
    template = np.full((30, 30, 3), [0, 0, 255], dtype=np.uint8)  # 红色方块
    search = np.full((100, 100, 3), [128, 128, 128], dtype=np.uint8)  # 灰色背景
    search[35:65, 35:65] = [0, 0, 255]  # 放入红色方块

    # 直接调用cv2
    import cv2
    result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    assert max_val > 0.9, f"Match score too low: {max_val}"
    print(f"  ✓ 模板匹配 (score={max_val:.2f}, pos={max_loc})")


def test_controller():
    """测试控制器接口"""
    ctrl = Controller()
    assert ctrl.screen_size[0] > 0
    assert ctrl.human is not None
    print(f"  ✓ 控制器 (屏幕={ctrl.screen_size})")


def test_task_engine():
    """测试任务引擎"""
    engine = TaskEngine()

    # 注册测试任务
    engine._tasks = {
        "Start": {
            "desc": "入口",
            "action": "wait",
            "params": {"seconds": 0.01},
            "next": ["End"]
        },
        "End": {
            "desc": "结束",
            "action": "wait",
            "params": {"seconds": 0.01},
            "next": None
        }
    }

    engine.run("Start", max_steps=5)
    assert engine._stats["steps"] == 2
    print(f"  ✓ 任务引擎 ({engine._stats['steps']}步)")


def test_popup_handler():
    """测试弹窗处理器"""
    vision = Vision()
    ctrl = Controller()
    popup = PopupHandler(vision, ctrl)

    # 禁用实际点击，只测试检测逻辑
    popup._enabled = False

    test_img = np.full((200, 200, 3), [128, 128, 128], dtype=np.uint8)
    result = popup.detect(test_img)
    assert result is None  # 没有弹窗
    print("  ✓ 弹窗检测")


def run_all():
    print("\n" + "=" * 50)
    print("  SmartRPA 单元测试")
    print("=" * 50)

    tests = [
        ("贝塞尔曲线", test_bezier_path),
        ("颜色识别", test_color_match),
        ("模板匹配", test_template_match),
        ("控制器", test_controller),
        ("任务引擎", test_task_engine),
        ("弹窗检测", test_popup_handler),
    ]

    for name, func in tests:
        try:
            func()
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    print("\n" + "=" * 50)
    print("  测试完成")
    print("=" * 50)


if __name__ == "__main__":
    run_all()
