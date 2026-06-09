"""视觉识别层 - 模板匹配 + 颜色识别"""
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
    """视觉识别器"""

    def __init__(self, template_dir: str = None):
        self.template_dir = template_dir
        self._cache: Dict[str, np.ndarray] = {}

    def set_template_dir(self, path: str):
        self.template_dir = path
        self._cache.clear()

    def _load_template(self, name: str) -> Optional[np.ndarray]:
        """加载模板图片（支持懒加载+缓存）"""
        if name in self._cache:
            return self._cache[name]

        # 搜索路径：template_dir + 名称
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

    # ========== 模板匹配（核心） ==========

    def find(self, image: np.ndarray, template_name: str,
             threshold: float = 0.8,
             roi: Tuple[int, int, int, int] = None) -> Found:
        """
        在图像中查找模板

        Args:
            image: 待搜索图像（BGR）
            template_name: 模板名称（不含扩展名）
            threshold: 匹配阈值（0-1，越高越严格）
            roi: 搜索区域 (x, y, w, h)

        Returns:
            Found对象
        """
        tpl = self._load_template(template_name)
        if tpl is None:
            return Found(found=False)

        # 裁剪ROI
        if roi:
            x, y, w, h = roi
            search = image[y:y+h, x:x+w]
            off_x, off_y = x, y
        else:
            search = image
            off_x, off_y = 0, 0

        if search.shape[0] < tpl.shape[0] or search.shape[1] < tpl.shape[1]:
            return Found(found=False)

        # 匹配
        result = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            return Found(
                found=True,
                x=off_x + max_loc[0],
                y=off_y + max_loc[1],
                w=tpl.shape[1],
                h=tpl.shape[0],
                score=float(max_val),
                label=template_name,
            )
        return Found(found=False)

    def find_all(self, image: np.ndarray, template_name: str,
                 threshold: float = 0.8,
                 roi: Tuple[int, int, int, int] = None) -> List[Found]:
        """查找所有匹配位置（用于多个相同元素）"""
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

        result = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        # 非极大值抑制
        found = []
        h_t, w_t = tpl.shape[:2]
        for pt in zip(*locations[::-1]):
            # 检查是否与已有结果重叠
            fx, fy = off_x + pt[0], off_y + pt[1]
            score = float(result[pt[1], pt[0]])

            overlap = False
            for f in found:
                if abs(fx - f.x) < w_t // 2 and abs(fy - f.y) < h_t // 2:
                    overlap = True
                    if score > f.score:
                        f.x, f.y, f.score = fx, fy, score
                    break
            if not overlap:
                found.append(Found(
                    found=True, x=fx, y=fy, w=w_t, h=h_t,
                    score=score, label=template_name
                ))

        return found

    def exists(self, image: np.ndarray, template_name: str,
               threshold: float = 0.8) -> bool:
        """快速检查是否存在（不返回位置）"""
        return self.find(image, template_name, threshold).found

    # ========== 颜色识别 ==========

    def match_color(self, image: np.ndarray,
                    roi: Tuple[int, int, int, int],
                    color_table: Dict[int, Tuple[Tuple[int, int, int],
                                                   Tuple[int, int, int]]]
                    ) -> Optional[int]:
        """
        通过颜色识别数值（2048方块专用）

        Args:
            image: 图像
            roi: 区域
            color_table: {value: ((b_low,g_low,r_low), (b_high,g_high,r_high))}

        Returns:
            匹配到的数值，未匹配返回None
        """
        x, y, w, h = roi
        cell = image[y:y+h, x:x+w]
        if cell.size == 0:
            return None

        avg = tuple(int(np.mean(cell[:, :, c])) for c in range(3))

        best_val = None
        best_dist = float('inf')
        for val, (low, high) in color_table.items():
            center = tuple((l + h) // 2 for l, h in zip(low, high))
            dist = sum((a - b) ** 2 for a, b in zip(avg, center)) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_val = val

        max_dist = 80
        return best_val if best_dist < max_dist else None
