"""BD2 自动钓鱼 v2 — 使用 BD2AutoFishing-main 的高质量引擎"""
import os, sys, time, random, math
import numpy as np
import cv2
import pydirectinput
import win32gui
import win32con

# ════════════════════════════════════════════════
#  Part 1 — 配置与模板加载
# ════════════════════════════════════════════════

TEMPLATE_KEYS = {
    "cast":       "cast_icon.png",
    "bite":       "bite_icon.png",
    "result":     "result_screen.png",
    "full_warning": "text_inventory_full.png",
    "pos_error":  "text_position_error.png",
    "btn_sell_mode":  "btn_one_click_sell.png",
    "btn_select_all": "btn_select_all.png",
    "btn_check":  "btn_check_blue.png",
    "btn_confirm":"btn_confirm_sell.png",
}

# QTE 颜色 (HSV)
COLOR_CONFIG = {
    "yellow_lower": (0, 40, 120),  "yellow_upper": (40, 255, 255),
    "cursor_lower": (0, 0, 200),   "cursor_upper": (180, 50, 255),
}

# 游戏参数
CAST_DURATION = 0.35
HIT_COOLDOWN = 0.2
CURSOR_TIMEOUT = 1.0
TEMPLATE_CONFIDENCE = 0.75

_templates = {}
_running = True


def init_templates(tpl_dir):
    """加载所有模板图片"""
    global _templates
    for key, fname in TEMPLATE_KEYS.items():
        path = os.path.join(tpl_dir, fname)
        if os.path.exists(path):
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                if len(img.shape) == 3 and img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                _templates[key] = img


def find_template(key, screenshot, region=None, confidence=None):
    """模板匹配查找"""
    if key not in _templates:
        return None
    if confidence is None:
        confidence = TEMPLATE_CONFIDENCE

    if region:
        x, y, w, h = region
        screen = screenshot[y:y+h, x:x+w]
    else:
        screen = screenshot

    tpl = _templates[key]
    gray_scr = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    gray_tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_scr, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= confidence:
        cx = max_loc[0] + tpl.shape[1] // 2
        cy = max_loc[1] + tpl.shape[0] // 2
        if region:
            cx += region[0]
            cy += region[1]
        return (cx, cy)
    return None


# ════════════════════════════════════════════════
#  Part 2 — 窗口与操作工具
# ════════════════════════════════════════════════

def activate_window(title="BrownDust II"):
    """激活游戏窗口"""
    hwnd = win32gui.FindWindow(None, title)
    if hwnd:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pydirectinput.press('alt')
            win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return hwnd
    return None


def get_window_rect(title):
    """获取窗口坐标"""
    hwnd = win32gui.FindWindow(None, title)
    if hwnd:
        rect = win32gui.GetWindowRect(hwnd)
        return (rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1])
    return None


def human_press(key, duration=None):
    if duration is None:
        duration = random.uniform(0.05, 0.1)
    pydirectinput.keyDown(key)
    time.sleep(duration)
    pydirectinput.keyUp(key)


def human_click(pt, offset=5):
    if not pt:
        return
    dx = int(random.gauss(0, offset/2))
    dy = int(random.gauss(0, offset/2))
    dx = max(-offset, min(offset, dx))
    dy = max(-offset, min(offset, dy))
    pydirectinput.click(pt[0] + dx, pt[1] + dy)


# ════════════════════════════════════════════════
#  Part 3 — QTE 小游戏（轮廓检测版）
# ════════════════════════════════════════════════

def play_minigame(screenshot, region, log):
    """QTE 小游戏 — 用轮廓检测游标 + 黄条"""
    log("🎮 进入小游戏", "INFO")

    y_low = np.array(COLOR_CONFIG["yellow_lower"], dtype=np.uint8)
    y_high = np.array(COLOR_CONFIG["yellow_upper"], dtype=np.uint8)
    c_low = np.array(COLOR_CONFIG["cursor_lower"], dtype=np.uint8)
    c_high = np.array(COLOR_CONFIG["cursor_upper"], dtype=np.uint8)

    x, y, w, h = region
    crop = screenshot[y:y+h, x:x+w]
    if crop.size == 0:
        return

    # HSV 转换
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # 游标
    mask_c = cv2.inRange(hsv, c_low, c_high)
    ctrs_c, _ = cv2.findContours(mask_c, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not ctrs_c:
        log("未检测到游标", "WARN")
        return

    # 黄条
    mask_y = cv2.inRange(hsv, y_low, y_high)
    ctrs_y, _ = cv2.findContours(mask_y, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 最大的游标
    max_c = max(ctrs_c, key=cv2.contourArea)
    cx_, cy_, cw_, ch_ = cv2.boundingRect(max_c)
    if ch_ < 5:
        return

    cursor_center = cx_ + cw_ // 2

    # 找黄条
    hit = False
    for cnt in ctrs_y:
        if cv2.contourArea(cnt) > 20:
            yx, yy, yw, yh = cv2.boundingRect(cnt)
            if yx <= cursor_center <= yx + yw:
                hit = True
                break

    if hit:
        press_dur = random.uniform(0.02, 0.05)
        human_press('space', press_dur)
        log(f"⚡ HIT! {press_dur:.3f}s", "SUCCESS")
    else:
        log("游标未在黄条区域", "INFO")


# ════════════════════════════════════════════════
#  Part 4 — 贩卖流程
# ════════════════════════════════════════════════

def handle_selling(screenshot, log):
    """自动贩卖背包"""
    log("🎒 背包满，尝试贩卖", "INFO")
    human_press('t', 0.1)
    time.sleep(2.5)

    steps = [
        ("btn_sell_mode", "点击贩卖模式", 1.0),
        ("btn_select_all", "点击全选", 0.5),
        ("btn_check", "确认选择", 1.0),
        ("btn_confirm", "确认贩卖", 2.0),
    ]
    for key, desc, delay in steps:
        pt = find_template(key, screenshot)
        if pt:
            log(f"  → {desc}", "INFO")
            human_click(pt)
            time.sleep(delay)
        else:
            if key == "btn_sell_mode":
                log("❌ 未找到贩卖按钮", "WARN")
                human_press('esc')
                return False
    human_press('esc')
    time.sleep(1.5)
    log("✅ 贩卖完成", "SUCCESS")
    return True


# ════════════════════════════════════════════════
#  Part 5 — 主循环
# ════════════════════════════════════════════════

# ROI 配置（相对窗口比例）
ROI_RATIOS = {
    "minigame": (0.51, 0.85, 0.36, 0.06),
    "bite":     (0.61, 0.33, 0.11, 0.16),
    "msg_tips": (0.45, 0.21, 0.42, 0.12),
}


def calc_roi(wx, wy, ww, wh, ratios):
    """从窗口坐标 + 比例算绝对区域"""
    rx, ry, rw, rh = ratios
    return (int(wx + ww*rx), int(wy + wh*ry), int(ww*rw), int(wh*rh))


def callback_bd2_fishing(engine, params):
    """BD2 自动钓鱼主回调"""
    global _running
    if not getattr(engine, '_running', True):
        _running = False
        return False

    log = getattr(engine, '_user_log', lambda m, l: None)

    # 首次加载模板
    if not _templates:
        tpl_dir = getattr(getattr(engine, 'vision', None), 'template_dir', None)
        if tpl_dir and os.path.isdir(tpl_dir):
            init_templates(tpl_dir)
            log(f"已加载 {len(_templates)} 个模板", "INFO")
        else:
            log("templates/ 目录未找到", "WARN")

    # 激活窗口
    win = activate_window("BrownDust II")
    if not win:
        log("未找到游戏窗口", "ERROR")
        return True  # 继续尝试

    wr = get_window_rect("BrownDust II")
    if not wr:
        return True

    screenshot = engine.controller.screenshot()

    # ── 异常检测 ──
    roi_msg = calc_roi(*wr, ROI_RATIOS["msg_tips"])

    # 结算画面
    if find_template("result", screenshot):
        log("结算画面, 按 ESC", "INFO")
        human_press('esc')
        time.sleep(2.0)
        return True

    # 位置错误
    if find_template("pos_error", screenshot, region=roi_msg):
        log("位置错误, 后退", "WARN")
        human_press('s', 0.3)
        time.sleep(1.0)
        return True

    # 背包满
    if find_template("full_warning", screenshot, region=roi_msg):
        handle_selling(screenshot, log)
        return True

    # ── 咬钩检测 ──
    roi_bite = calc_roi(*wr, ROI_RATIOS["bite"])
    if "bite" in _templates and find_template("bite", screenshot, region=roi_bite):
        log("🎣 咬钩! 拉杆!", "SUCCESS")
        human_press('space')

        # 小游戏
        roi_game = calc_roi(*wr, ROI_RATIOS["minigame"])
        # 在 QTE 循环帧内重截图
        game_start = time.time()
        hit_count = 0
        while time.time() - game_start < 20:
            if not getattr(engine, '_running', True):
                return False
            ss = engine.controller.screenshot()
            play_minigame(ss, roi_game, log)
            time.sleep(0.032)  # ~30fps
        return True

    # ── 抛竿 ──
    if "cast" in _templates and find_template("cast", screenshot):
        log("🌊 抛竿", "INFO")
        human_press('space', CAST_DURATION)
        time.sleep(2.0)
        return True

    # 无事发生
    time.sleep(0.1)
    return True
