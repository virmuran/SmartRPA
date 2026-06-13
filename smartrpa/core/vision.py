"""视觉识别层 - 多尺度/多角度模板匹配 + 颜色识别"""
import os
import cv2
import numpy as np
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass


@dataclass
class Found:
    """识别结果"""
    found: bool
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    score: float = 0.0
    label: str = ""

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    def __bool__(self):
        return self.found


class Vision:
    """视觉识别器（多尺度+多角度匹配、颜色触发检测）"""

    DEFAULT_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]
    DEFAULT_ANGLES = [-10, -5, 0, 5, 10]

    def __init__(self, template_dir: str = None):
        self.template_dir = template_dir
        self._cache: Dict[str, np.ndarray] = {}

    def set_template_dir(self, path: str):
        self.template_dir = path
        self._cache.clear()

    def _load_template(self, name: str) -> Optional[np.ndarray]:
        if name in self._cache:
            return self._cache[name]
        search_paths = []
        if self.template_dir:
            for ext in ('.png', '.jpg', '.jpeg'):
                search_paths.append(os.path.join(self.template_dir, name + ext))
        for path in search_paths:
            if os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    self._cache[name] = img
                    return img
        return None

    @staticmethod
    def _rotate_bound(image: np.ndarray, angle: float) -> np.ndarray:
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos = abs(M[0, 0]); sin = abs(M[0, 1])
        nw = int((h * sin) + (w * cos))
        nh = int((h * cos) + (w * sin))
        M[0, 2] += (nw / 2) - center[0]
        M[1, 2] += (nh / 2) - center[1]
        return cv2.warpAffine(image, M, (nw, nh), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # ========== 多尺度多角度模板匹配 ==========

    def find(self, image: np.ndarray, template_name: str,
             threshold: float = 0.8,
             roi: Tuple[int, int, int, int] = None,
             use_multi_scale: bool = True,
             use_multi_angle: bool = False) -> Found:
        """
        多尺度/多角度模板匹配。默认只开多尺度（快），多角度需手动开启（慢）。

        Args:
            image: 待搜索图像（BGR）
            template_name: 模板名称
            threshold: 匹配阈值
            roi: 搜索区域 (x, y, w, h)
            use_multi_scale: 启用多尺度搜索（默认开）
            use_multi_angle: 启用多角度搜索（默认关，性能开销大）
        """
        tpl = self._load_template(template_name)
        if tpl is None:
            return Found(found=False)

        if roi:
            x, y, w, h = roi
            search = image[y:y+h, x:x+w]
            off_x, off_y = x, y
        else:
            search = image
            off_x, off_y = 0, 0

        if search.shape[0] < 2 or search.shape[1] < 2:
            return Found(found=False)

        tpl_h, tpl_w = tpl.shape[:2]
        best = None
        scales = self.DEFAULT_SCALES if use_multi_scale else [1.0]
        angles = self.DEFAULT_ANGLES if use_multi_angle else [0]

        for scale in scales:
            sw = max(int(tpl_w * scale), 2)
            sh = max(int(tpl_h * scale), 2)
            scaled = cv2.resize(tpl, (sw, sh), interpolation=cv2.INTER_LINEAR)

            for angle in angles:
                rot = self._rotate_bound(scaled, angle) if angle else scaled
                if search.shape[0] < rot.shape[0] or search.shape[1] < rot.shape[1]:
                    continue

                res = cv2.matchTemplate(search, rot, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val >= threshold and (best is None or max_val > best.score):
                    if angle and abs(angle) > 0.1:
                        cx = max_loc[0] + rot.shape[1] // 2
                        cy = max_loc[1] + rot.shape[0] // 2
                        best = Found(found=True, x=cx - sw//2 + off_x, y=cy - sh//2 + off_y,
                                     w=sw, h=sh, score=float(max_val), label=template_name)
                    else:
                        best = Found(found=True, x=max_loc[0] + off_x, y=max_loc[1] + off_y,
                                     w=sw, h=sh, score=float(max_val), label=template_name)
        return best if best else Found(found=False)

    def find_all(self, image: np.ndarray, template_name: str,
                 threshold: float = 0.8,
                 roi: Tuple[int, int, int, int] = None) -> List[Found]:
        """查找所有匹配位置"""
        tpl = self._load_template(template_name)
        if tpl is None:
            return []
        if roi:
            x, y, w, h = roi
            search = image[y:y+h, x:x+w]
            off_x, off_y = x, y
        else:
            search = image
            off_x, off_y = 0, 0
        res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        locs = np.where(res >= threshold)
        found, ht, wt = [], tpl.shape[0], tpl.shape[1]
        for pt in zip(*locs[::-1]):
            fx, fy = off_x + pt[0], off_y + pt[1]
            sc = float(res[pt[1], pt[0]])
            overlap = False
            for f in found:
                if abs(fx - f.x) < wt // 2 and abs(fy - f.y) < ht // 2:
                    overlap = True
                    if sc > f.score:
                        f.x, f.y, f.score = fx, fy, sc
                    break
            if not overlap:
                found.append(Found(found=True, x=fx, y=fy, w=wt, h=ht, score=sc, label=template_name))
        return found

    def exists(self, image: np.ndarray, template_name: str,
               threshold: float = 0.8) -> bool:
        return self.find(image, template_name, threshold).found

    # ========== 颜色识别（原有2048专用） ==========

    def match_color(self, image: np.ndarray,
                    roi: Tuple[int, int, int, int],
                    color_table: Dict[int, Tuple[Tuple[int, int, int], Tuple[int, int, int]]]
                    ) -> Optional[int]:
        x, y, w, h = roi
        cell = image[y:y+h, x:x+w]
        if cell.size == 0:
            return None
        avg = tuple(int(np.mean(cell[:, :, c])) for c in range(3))
        best_val, best_dist = None, float('inf')
        for val, (low, high) in color_table.items():
            center = tuple((l + h) // 2 for l, h in zip(low, high))
            dist = sum((a - b) ** 2 for a, b in zip(avg, center)) ** 0.5
            if dist < best_dist:
                best_dist, best_val = dist, val
        return best_val if best_dist < 80 else None

    # ========== 颜色触发检测（OS-Bot-COLOR 思路） ==========

    def find_color_region(self, image: np.ndarray,
                          target_color: Tuple[int, int, int],
                          tolerance: int = 40,
                          min_pct: float = 0.15,
                          roi: Tuple[int, int, int, int] = None) -> Found:
        """
        在图像中查找包含目标颜色的区域。
        用于检测特定颜色按钮、状态指示器等，无需模板图片。
        """
        if roi:
            x, y, w, h = roi
            search = image[y:y+h, x:x+w]
            off_x, off_y = x, y
        else:
            search = image
            off_x, off_y = 0, 0
        if search.size == 0:
            return Found(found=False)
        lower = np.array([max(0, c - tolerance) for c in target_color], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in target_color], dtype=np.uint8)
        mask = cv2.inRange(search, lower, upper)
        pct = np.sum(mask > 0) / mask.size
        if pct >= min_pct:
            ys, xs = np.where(mask > 0)
            return Found(found=True, x=off_x + int(xs.mean()) - 20, y=off_y + int(ys.mean()) - 20,
                         w=40, h=40, score=float(pct), label=f"color_{target_color}")
        return Found(found=False)

    def detect_overlay(self, image: np.ndarray,
                       roi: Tuple[int, int, int, int] = None) -> Found:
        """
        检测屏幕是否有半透明弹窗遮罩层。
        原理：遮罩层使屏幕均匀变暗。亮度低 + 标准差小 = 可能是遮罩。
        """
        if roi:
            x, y, w, h = roi
            search = image[y:y+h, x:x+w]
        else:
            search = image
        if search.size == 0:
            return Found(found=False)
        gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
        mean_b = float(np.mean(gray))
        std_b = float(np.std(gray))
        if mean_b < 100 and std_b < 40:
            return Found(found=True, score=float(mean_b), label="overlay")
        return Found(found=False)
