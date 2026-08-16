"""
相机硬件抽象层
对应架构图：📷 尼康Z5 II 联机相机(gphoto2)
优先使用 gphoto2，不可用时自动进入模拟模式
"""
import time
import io
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    import gphoto2 as gp
    HAS_GPHOTO2 = True
except Exception:
    HAS_GPHOTO2 = False


class CameraError(Exception):
    pass


class BaseCamera:
    """相机基类，定义统一接口"""
    connected = False
    simulation = False

    def connect(self): ...
    def disconnect(self): ...
    def capture(self, save_path: str) -> str: ...
    def get_preview_frame(self) -> bytes: ...
    def set_config(self, key: str, value): ...
    def autofocus(self, x_ratio: float = 0.5, y_ratio: float = 0.5): ...
    def is_ready(self) -> bool: ...


class GPhotoCamera(BaseCamera):
    """gphoto2 真实相机驱动"""

    def __init__(self):
        self.camera = None
        self.context = None
        self.simulation = False

    def connect(self):
        try:
            self.context = gp.Context()
            self.camera = gp.Camera()
            self.camera.init(self.context)
            self.connected = True
        except Exception as e:
            self.connected = False
            raise CameraError(f"相机连接失败: {e}")

    def disconnect(self):
        if self.camera:
            try:
                self.camera.exit(self.context)
            except Exception:
                pass
            self.camera = None
        self.connected = False

    def capture(self, save_path: str) -> str:
        if not self.connected:
            raise CameraError("相机未连接")
        try:
            file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE, self.context)
            camera_file = self.camera.file_get(
                file_path.folder, file_path.name,
                gp.GP_FILE_TYPE_NORMAL, self.context
            )
            camera_file.save(save_path)
            # 从相机删除
            try:
                self.camera.file_delete(file_path.folder, file_path.name, self.context)
            except Exception:
                pass
            return save_path
        except Exception as e:
            raise CameraError(f"拍摄失败: {e}")

    def get_preview_frame(self) -> bytes:
        if not self.connected:
            return b""
        try:
            camera_file = self.camera.capture_preview(self.context)
            return camera_file.get_data_and_size()
        except Exception:
            return b""

    def set_config(self, key: str, value):
        if not self.connected:
            return
        try:
            config = self.camera.get_config(self.context)
            child = config.get_child_by_name(key)
            child.set_value(str(value))
            self.camera.set_config(config, self.context)
        except Exception:
            pass

    def autofocus(self, x_ratio=0.5, y_ratio=0.5):
        # gphoto2 通用触发对焦
        self.set_config("autofocusdrive", 1)
        time.sleep(0.1)
        self.set_config("autofocusdrive", 0)

    def is_ready(self) -> bool:
        return self.connected


class SimulatedCamera(BaseCamera):
    """
    模拟相机：无真实硬件时生成测试画面
    支持实时预览流（动态渐变）和拍摄（保存测试图）
    """

    def __init__(self):
        self.simulation = True
        self.connected = False
        self._frame_count = 0

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def _make_test_image(self, width=1280, height=854, text="SIMULATION") -> bytes:
        self._frame_count += 1
        # 动态背景
        t = self._frame_count
        r = int(128 + 127 * np.sin(t * 0.05))
        g = int(128 + 127 * np.sin(t * 0.03 + 2))
        b = int(128 + 127 * np.sin(t * 0.07 + 4))
        img = Image.new("RGB", (width, height), (r, g, b))
        draw = ImageDraw.Draw(img)
        # 网格
        for x in range(0, width, 80):
            draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 80), width=1)
        for y in range(0, height, 80):
            draw.line([(0, y), (width, y)], fill=(255, 255, 255, 80), width=1)
        # 中心对焦框
        cx, cy = width // 2, height // 2
        draw.rectangle([cx - 100, cy - 70, cx + 100, cy + 70],
                       outline=(0, 255, 0), width=3)
        # 文字
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        except Exception:
            font = ImageFont.load_default()
        draw.text((20, 20), f"{text}  Frame:{t}", fill=(255, 255, 255), font=font)
        draw.text((20, height - 60), f"Nikon Z5 II [SIM]", fill=(0, 255, 0), font=font)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()

    def capture(self, save_path: str) -> str:
        if not self.connected:
            raise CameraError("相机未连接")
        time.sleep(0.5)  # 模拟拍摄延迟
        data = self._make_test_image(3000, 2000, "CAPTURED")
        with open(save_path, "wb") as f:
            f.write(data)
        return save_path

    def get_preview_frame(self) -> bytes:
        if not self.connected:
            return b""
        return self._make_test_image(960, 640, "LIVE")

    def set_config(self, key, value):
        pass

    def autofocus(self, x_ratio=0.5, y_ratio=0.5):
        time.sleep(0.2)

    def is_ready(self) -> bool:
        return self.connected


def create_camera(force_simulation: bool = False):
    """工厂方法：优先真实相机，失败回退模拟"""
    if not force_simulation and HAS_GPHOTO2:
        try:
            cam = GPhotoCamera()
            cam.connect()
            return cam
        except Exception:
            pass
    cam = SimulatedCamera()
    cam.connect()
    return cam
