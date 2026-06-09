"""2048 AI 自动化 - SmartRPA示例
演示：视觉识别棋盘 → AI决策 → 真人化按键操作
"""
import sys
import os
import numpy as np

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from smartrpa import Controller, Vision, TaskEngine, PopupHandler

# ========== 2048方块颜色表（BGR格式） ==========

TILE_COLORS = {
    0:    ((195, 185, 175), (215, 205, 195)),
    2:    ((210, 210, 195), (245, 235, 225)),
    4:    ((195, 210, 225), (220, 235, 245)),
    8:    ((115, 170, 235), (140, 190, 250)),
    16:   ((90, 145, 240), (115, 165, 250)),
    32:   ((80, 115, 240), (110, 140, 250)),
    64:   ((50, 85, 240), (75, 110, 250)),
    128:  ((105, 200, 230), (130, 215, 245)),
    256:  ((90, 195, 230), (115, 210, 245)),
    512:  ((75, 190, 225), (95, 205, 245)),
    1024: ((55, 185, 220), (80, 200, 240)),
    2048: ((40, 180, 215), (65, 195, 235)),
}


class Board2048:
    """2048棋盘解析器"""

    def __init__(self, region: tuple):
        self.x, self.y, self.w, self.h = region
        self.cell_w = self.w / 4
        self.cell_h = self.h / 4

    def parse(self, screenshot, vision):
        """识别棋盘，返回4x4 numpy数组"""
        board = []
        for row in range(4):
            row_data = []
            for col in range(4):
                cx = int(self.x + col * self.cell_w + 2)
                cy = int(self.y + row * self.cell_h + 2)
                cw = int(self.cell_w - 4)
                ch = int(self.cell_h - 4)

                val = vision.match_color(screenshot, (cx, cy, cw, ch), TILE_COLORS)
                row_data.append(val if val is not None else 0)
            board.append(row_data)
        return np.array(board, dtype=np.int64)


def expectimax_decide(board: np.ndarray) -> str:
    """简单的Expectimax决策 - 选择最优方向"""
    def _move(b, direction):
        """模拟移动，返回(新棋盘, 是否移动)"""
        if direction == "up":
            b = b.T
        elif direction == "down":
            b = np.fliplr(b.T)
        elif direction == "right":
            b = np.fliplr(b)

        moved = False
        new_b = np.zeros_like(b)
        for r in range(4):
            # 提取非零值并合并
            row = [x for x in b[r] if x != 0]
            merged = []
            i = 0
            while i < len(row):
                if i + 1 < len(row) and row[i] == row[i + 1]:
                    merged.append(row[i] * 2)
                    i += 2
                    moved = True
                else:
                    merged.append(row[i])
                    i += 1
            # 补零
            merged += [0] * (4 - len(merged))
            new_b[r] = merged
            if any(row[j] != merged[j] for j in range(4)):
                moved = True

        # 还原方向
        if direction == "up":
            new_b = new_b.T
        elif direction == "down":
            new_b = np.fliplr(new_b.T)
        elif direction == "right":
            new_b = np.fliplr(new_b)

        return new_b, moved

    # 评估函数：空格数 + 角点大数
    def _score(b):
        empty = np.sum(b == 0)
        corner = b[0, 0] + b[0, 3] + b[3, 0] + b[3, 3]
        return empty * 10 + corner * 0.1

    best_dir = "up"
    best_score = -1

    for direction in ["up", "down", "left", "right"]:
        new_board, moved = _move(board.copy(), direction)
        if not moved:
            continue
        s = _score(new_board)
        if s > best_score:
            best_score = s
            best_dir = direction

    return best_dir


def ai_move(engine, params) -> bool:
    """AI决策回调 - 截图→识别→决策→按键"""
    screenshot = engine.controller.screenshot()
    board = engine._board_parser.parse(screenshot, engine.vision)

    if np.sum(board) < 4:
        return False

    # AI决策
    direction = expectimax_decide(board)

    # 执行按键
    engine.controller.press_key(direction)

    # 显示状态
    score = int(np.sum(board))
    max_tile = int(np.max(board))
    flat = ''.join(str(n) if n > 0 else '.' for n in board.flatten())
    print(f"  [{direction}] {flat} | 分={score} 最大={max_tile}")

    return True


def main():
    print("\n" + "=" * 50)
    print("  SmartRPA - 2048 AI 自动化")
    print("=" * 50)

    # 棋盘区域（需要根据实际游戏位置调整）
    # 用截图工具获取棋盘在屏幕上的位置
    board_region = (400, 200, 400, 400)  # (x, y, w, h)
    print(f"\n棋盘区域: {board_region}")
    print("如果游戏位置不同，请修改 run.py 中的 board_region 变量")

    # 初始化组件
    controller = Controller()
    vision = Vision(template_dir="examples/2048/templates")
    popup = PopupHandler(vision, controller)

    engine = TaskEngine(controller, vision, popup)
    engine.on("ai_move", ai_move)

    # 注入棋盘解析器
    engine._board_parser = Board2048(board_region)

    # 加载任务配置
    config_path = os.path.join(os.path.dirname(__file__), "task.json")
    engine.load(config_path)

    print("\n开始运行... (Ctrl+C 停止)")
    print("请确保2048游戏窗口已打开！\n")

    try:
        engine.run("StartGame")
    except KeyboardInterrupt:
        print("\n\n用户停止")
    finally:
        engine.stop()


if __name__ == "__main__":
    main()
