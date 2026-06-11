"""2048 AI 回调 — Tesseract OCR 数字识别（不依赖颜色，适配任何主题）"""
import os
import shutil
import numpy as np
import cv2
import pytesseract


def _find_tesseract():
    """自动检测 Tesseract OCR 安装路径"""
    # 1) 环境变量
    env_path = os.environ.get("TESSERACT_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2) 系统 PATH
    which = shutil.which("tesseract")
    if which:
        return which

    # 3) 常见安装路径
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

    # 4) 都没找到 → 抛出可操作的错误提示
    raise RuntimeError(
        "未找到 Tesseract OCR。请执行以下任一操作：\n"
        "  1. 安装 Tesseract: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "  2. 设置环境变量: set TESSERACT_PATH=C:\\Path\\To\\tesseract.exe\n"
        "  3. 将 tesseract 所在目录添加到系统 PATH 中"
    )


pytesseract.pytesseract.tesseract_cmd = _find_tesseract()

TESSER_CONF = "--psm 7 -c tessedit_char_whitelist=0123456789"


def callback_2048(engine, params):
    """每帧: OCR识别棋盘 → AI决策 → 按键"""
    region = getattr(engine, 'region', (0,0,1920,1080))
    rx, ry, rw, rh = region
    cw, ch = rw/4, rh/4
    screenshot = engine.controller.screenshot()
    log = getattr(engine, '_user_log', lambda m,l: None)

    board = []
    for row in range(4):
        r = []
        for col in range(4):
            x1 = int(rx + col*cw)
            y1 = int(ry + row*ch)
            x2 = int(rx + (col+1)*cw)
            y2 = int(ry + (row+1)*ch)

            if x2<=x1 or y2<=y1:
                r.append(0)
                continue

            cell = screenshot[y1:y2, x1:x2]
            if cell.size == 0:
                r.append(0)
                continue

            # 裁剪中间60%区域(去掉边框)
            h, w = cell.shape[:2]
            crop = cell[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]

            # 识别数字
            val = _ocr_digit(crop)
            r.append(val)
        board.append(r)

    board = np.array(board, dtype=np.int64)

    # 日志
    lines = [' '.join(f'{board[r][c]:>4}' for c in range(4)) for r in range(4)]
    for l in lines:
        log(f"  {l}", "INFO")

    # 游戏结束
    if np.all(board > 0):
        can = False
        for r in range(4):
            for c in range(3):
                if board[r,c]==board[r,c+1] or (r<3 and board[r,c]==board[r+1,c]):
                    can = True
        if not can:
            log("游戏结束", "SUCCESS")
            return True

    # AI决策
    def sim(b, d):
        nb=b.copy()
        if d=="up": nb=nb.T
        elif d=="down": nb=np.fliplr(nb.T)
        elif d=="right": nb=np.fliplr(nb)
        moved=False; new=np.zeros_like(nb)
        for r in range(4):
            row=[x for x in nb[r] if x!=0]; mgd,i=[],0
            while i<len(row):
                if i+1<len(row) and row[i]==row[i+1]: mgd.append(row[i]*2); i+=2; moved=True
                else: mgd.append(row[i]); i+=1
            mgd+=[0]*(4-len(mgd)); new[r]=mgd
            if any(nb[r][j]!=mgd[j] for j in range(4)): moved=True
        if d=="up": new=new.T
        elif d=="down": new=np.fliplr(new.T)
        elif d=="right": np.fliplr(new)
        return new,moved

    bd,bs="up",-1
    for d in ["up","down","left","right"]:
        nb,m=sim(board,d)
        if not m: continue
        s=np.sum(nb==0)*100+np.max(nb)*0.1
        if s>bs: bs,bd=s,d
    if bs==-1:
        log("无法移动", "SUCCESS"); return True

    engine.controller.press_key(bd)
    log(f"{bd:>5} | 分数={int(np.sum(board)):>6} 最大={int(np.max(board)):>5}", "INFO")
    engine.controller.random_delay("think")
    return True


def _ocr_digit(cell):
    """OCR识别单个格子的数字"""
    if cell.size == 0:
        return 0

    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)

    # 二值化: 提取亮色数字 (白色文字)
    # 用OTSU自适应阈值
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 判断是白底黑字还是深色底白字
    white_px = np.sum(binary == 255)
    black_px = np.sum(binary == 0)
    if white_px > black_px:
        # 白底黑字 → 反转
        binary = cv2.bitwise_not(binary)

    # 如果白色像素太少（接近纯色），说明是空格
    total = binary.shape[0] * binary.shape[1]
    if np.sum(binary == 255) < total * 0.02:
        return 0

    # 膨胀使数字更粗，更容易识别
    kernel = np.ones((2,2), np.uint8)
    binary = cv2.dilate(binary, kernel, iterations=1)

    # OCR
    text = pytesseract.image_to_string(binary, config=TESSER_CONF).strip()
    try:
        return int(text)
    except ValueError:
        return 0
