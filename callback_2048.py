"""2048 AI 回调 — Tesseract OCR 数字识别（适配默认主题）"""
import os
import shutil
import time
import numpy as np
import cv2
import pytesseract


def _find_tesseract():
    env_path = os.environ.get("TESSERACT_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    which = shutil.which("tesseract")
    if which:
        return which
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    raise RuntimeError("未找到 Tesseract OCR")


pytesseract.pytesseract.tesseract_cmd = _find_tesseract()
TESSER_CONF = "--psm 7 -c tessedit_char_whitelist=0123456789"

# 2048 默认主题典型颜色（BGR）
EMPTY_LOW = np.array([190, 190, 200])
EMPTY_HIGH = np.array([220, 215, 225])


def _is_empty_cell(cell):
    """用颜色判断空格"""
    if cell.size == 0:
        return True
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    return np.mean(gray) > 195


def _ocr_digit(cell):
    """OCR识别单个格子的数字（针对深色底白字优化）"""
    if cell.size == 0:
        return 0

    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray)

def _ocr_digit(cell):
    """OCR识别单个格子的数字（适配2048浅色/深色底色）"""
    if cell.size == 0:
        return 0
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray)
    # 空格
    if mean > 195:
        return 0
    # 根据底色深浅选择二值化方向
    if mean > 160:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = cv2.bitwise_not(binary)  # 深色文字 → 白字
    else:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # 白色像素太少 → 空格
    if np.sum(binary == 255) < binary.size * 0.005:
        return 0
    # 膨胀
    binary = cv2.dilate(binary, np.ones((2, 2), np.uint8), iterations=1)
    text = pytesseract.image_to_string(binary, config=TESSER_CONF).strip()
    try:
        return int(text)
    except ValueError:
        return 0


def callback_2048(engine, params):
    """每帧: 颜色/OCR识别棋盘 → AI决策 → 按键"""
    # 停止检测
    if not getattr(engine, '_running', True):
        return False

    region = getattr(engine, 'region', None)
    if region is None or region[2] < 10 or region[3] < 10:
        log = getattr(engine, '_user_log', lambda m, l: None)
        log("请先框选棋盘区域", "ERROR")
        return False

    rx, ry, rw, rh = region
    cw, ch = rw / 4, rh / 4
    log = getattr(engine, '_user_log', lambda m, l: None)

    try:
        screenshot = engine.controller.screenshot()
    except Exception:
        return False

    # ── 1. OCR 识别棋盘 ──
    board = [[0] * 4 for _ in range(4)]
    for row in range(4):
        for col in range(4):
            x1 = int(rx + col * cw)
            y1 = int(ry + row * ch)
            x2 = int(rx + (col + 1) * cw)
            y2 = int(ry + (row + 1) * ch)
            if x2 <= x1 or y2 <= y1:
                continue
            cell = screenshot[y1:y2, x1:x2]
            if cell.size == 0:
                continue
            if _is_empty_cell(cell):
                continue
            crop = cell[int(ch * 0.15):int(ch * 0.85), int(cw * 0.15):int(cw * 0.85)]
            board[row][col] = _ocr_digit(crop)

    board = np.array(board, dtype=np.int64)

    # 日志
    lines = [' '.join(f'{board[r][c]:>4}' for c in range(4)) for r in range(4)]
    for l in lines:
        log(f"  {l}", "INFO")

    # ── 2. 游戏结束检测 ──
    if np.all(board > 0):
        can = False
        for r in range(4):
            for c in range(3):
                if board[r, c] == board[r, c + 1]:
                    can = True
                if r < 3 and board[r, c] == board[r + 1, c]:
                    can = True
        if not can:
            log("游戏结束", "SUCCESS")
            return False  # 返回 False 让引擎停止循环

    # ── 3. AI 决策（带随机探索） ──
    def sim(b, d):
        """模拟一次移动，返回移动后的棋盘和是否发生移动"""
        nb = b.copy()
        if d == "up":
            nb = nb.T
        elif d == "down":
            nb = np.fliplr(nb.T)
        elif d == "right":
            nb = np.fliplr(nb)
        # left: 保持原样

        moved = False
        new = np.zeros_like(nb)
        for r in range(4):
            row = [x for x in nb[r] if x != 0]
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
            merged += [0] * (4 - len(merged))
            new[r] = merged
            if any(nb[r][j] != merged[j] for j in range(4)):
                moved = True

        if d == "up":
            new = new.T
        elif d == "down":
            new = np.fliplr(new.T)
        elif d == "right":
            new = np.fliplr(new)
        return new, moved

    directions = ["up", "down", "left", "right"]

    # 用期望值（最大化空位 + 合并分数 + 角落偏好）评分
    best_dir, best_score = "up", -1
    for d in directions:
        nb, moved = sim(board, d)
        if not moved:
            continue
        empty = np.sum(nb == 0)
        merge_score = np.sum(nb[nb > 0]) * 0.05
        # 大数字在角落有奖励
        corner_bonus = 0
        corners = [(0, 0), (0, 3), (3, 0), (3, 3)]
        max_val = np.max(nb)
        for cr, cc in corners:
            if nb[cr, cc] == max_val:
                corner_bonus = 50
                break
        # 单调性奖励：行列有序度
        mono = 0
        for r in range(4):
            for c in range(3):
                if nb[r, c] >= nb[r, c + 1] and nb[r, c] > 0:
                    mono += 5
        for c in range(4):
            for r in range(3):
                if nb[r, c] >= nb[r + 1, c] and nb[r, c] > 0:
                    mono += 5
        # 小随机扰动，避免重复走同一条路
        random_bonus = np.random.uniform(0, 2)
        score = empty * 100 + merge_score + corner_bonus + mono + random_bonus
        if score > best_score:
            best_score, best_dir = score, d

    if best_score == -1:
        log("无法移动", "SUCCESS")
        return False

    # ── 4. 按键 ──
    key_map = {"up": "up", "down": "down", "left": "left", "right": "right"}
    engine.controller.press_key(key_map[best_dir])
    log(f"{best_dir:>5} | 分数={int(np.sum(board)):>6} 最大={int(np.max(board)):>5}", "INFO")
    engine.controller.random_delay("think")
    return True
