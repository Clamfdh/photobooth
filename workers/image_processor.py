"""
磨皮合成模块
对应架构图：六 磨皮合成模块
人像磨皮｜相框叠加
输出：预览处理图 + 高清成品交付图
"""
import os
import time
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from PyQt6.QtCore import QObject, pyqtSignal

from config import Config


class ImageProcessor(QObject):
    """图像处理 Worker（磨皮 + 相框合成）"""
    progress = pyqtSignal(int, str)       # percent, message
    preview_done = pyqtSignal(str)        # preview_path
    final_done = pyqtSignal(str, str)     # final_path, photo_id
    print_ready = pyqtSignal(str)         # printable_path
    error = pyqtSignal(str)

    # 磨皮等级参数：(双边滤波直径, 双边滤波色sigma, 双边滤波空间sigma, 锐化程度)
    BEAUTY_PRESETS = {
        0: (0, 0, 0, 0),         # 关闭
        1: (5, 20, 20, 0.3),     # 轻微
        2: (9, 40, 40, 0.5),     # 自然
        3: (13, 60, 60, 0.7),    # 标准
        4: (17, 80, 80, 0.9),    # 较强
        5: (21, 100, 100, 1.0),  # 最强
    }

    def __init__(self):
        super().__init__()
        self.cfg = Config()

    def _beautify(self, img: Image.Image, level: int) -> Image.Image:
        """人像磨皮：双边滤波 + 锐化恢复细节"""
        if level <= 0:
            return img
        preset = self.BEAUTY_PRESETS.get(level, self.BEAUTY_PRESETS[2])
        d, sigma_color, sigma_space, sharpen = preset

        arr = np.array(img)
        try:
            import cv2
            # OpenCV 双边滤波（效果最好）
            smoothed = cv2.bilateralFilter(arr, d, sigma_color, sigma_space)
            # 肤色区域检测（简单的 YCrCb 肤色模型）
            ycrcb = cv2.cvtColor(arr, cv2.COLOR_RGB2YCrCb)
            lower = np.array([0, 133, 77])
            upper = np.array([255, 173, 127])
            skin_mask = cv2.inRange(ycrcb, lower, upper)
            skin_mask = cv2.GaussianBlur(skin_mask, (15, 15), 0)
            mask_3ch = cv2.cvtColor(skin_mask, cv2.COLOR_GRAY2RGB) / 255.0
            # 仅在肤色区域融合磨皮效果
            result = (arr * (1 - mask_3ch) + smoothed * mask_3ch).astype(np.uint8)
            # USM 锐化恢复
            if sharpen > 0:
                blur = cv2.GaussianBlur(result, (0, 0), 3)
                result = cv2.addWeighted(result, 1 + sharpen, blur, -sharpen, 0)
            return Image.fromarray(result)
        except Exception:
            # 无 OpenCV 时用 PIL 回退
            smoothed = img.filter(ImageFilter.SMOOTH_MORE)
            blended = Image.blend(img, smoothed, 0.3 + level * 0.1)
            return blended

    def _apply_frame(self, img: Image.Image, frame_path: str = None) -> Image.Image:
        """叠加相框 PNG"""
        if not frame_path or not os.path.exists(frame_path):
            return img
        try:
            frame = Image.open(frame_path).convert("RGBA")
            frame = frame.resize(img.size, Image.LANCZOS)
            base = img.convert("RGBA")
            base.paste(frame, (0, 0), frame)
            return base.convert("RGB")
        except Exception:
            return img

    def process(self, source_path: str, output_dir: str,
                beauty_level: int = 2, frame_path: str = None,
                photo_id: str = None, generate_preview: bool = True) -> str:
        """
        完整处理流程：磨皮 → 相框 → 保存高清成品
        返回成品图路径
        """
        try:
            self.progress.emit(10, "加载原图")
            img = Image.open(source_path)
            if img.mode != "RGB":
                img = img.convert("RGB")

            self.progress.emit(30, "人像磨皮中")
            img = self._beautify(img, beauty_level)

            self.progress.emit(60, "叠加相框")
            img = self._apply_frame(img, frame_path)

            self.progress.emit(80, "保存高清成品")
            os.makedirs(output_dir, exist_ok=True)
            stem = Path(source_path).stem
            final_path = os.path.join(output_dir, f"{stem}_final.jpg")
            quality = self.cfg.get("export_quality", 95)
            img.save(final_path, "JPEG", quality=quality)

            self.progress.emit(100, "完成")
            self.final_done.emit(final_path, str(photo_id) if photo_id else "")
            self.print_ready.emit(final_path)

            # 生成预览图
            if generate_preview:
                prev = img.copy()
                prev.thumbnail((1024, 1024), Image.LANCZOS)
                preview_path = os.path.join(output_dir, f"{stem}_preview.jpg")
                prev.save(preview_path, "JPEG", quality=80)
                self.preview_done.emit(preview_path)

            return final_path
        except Exception as e:
            self.error.emit(f"图像处理失败: {e}")
            return ""

    def process_for_print(self, source_path: str, output_dir: str,
                          beauty_level: int = 2, frame_path: str = None,
                          print_size: str = "2x6") -> str:
        """打印专用：按打印尺寸拼图"""
        final_path = self.process(source_path, output_dir, beauty_level,
                                   frame_path, generate_preview=False)
        if not final_path:
            return ""
        # 根据打印尺寸做拼图
        try:
            img = Image.open(final_path)
            if print_size == "2x6":
                # 2x6 英寸通常是两张 2x3 竖图拼接
                w, h = img.size
                strip_h = h // 2
                top = img.crop((0, 0, w, strip_h))
                bottom = img.crop((0, strip_h, w, h))
                canvas = Image.new("RGB", (w, strip_h * 2), "white")
                canvas.paste(top, (0, 0))
                canvas.paste(bottom, (0, strip_h))
                print_path = os.path.join(output_dir, f"{Path(final_path).stem}_print.jpg")
                canvas.save(print_path, "JPEG", quality=95)
                return print_path
            return final_path
        except Exception:
            return final_path
