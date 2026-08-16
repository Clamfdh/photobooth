"""
相机处理模块
对应架构图：二.3 相机处理模块
gphoto2连接、断线自动重连、参数设置
"""
import time
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

from config import Config
from hardware.camera import create_camera, CameraError


class CameraWorker(QObject):
    """相机管理 Worker"""
    connected = pyqtSignal(bool, str)      # success, message
    disconnected = pyqtSignal()
    capture_done = pyqtSignal(str, str)    # raw_path, photo_id
    capture_failed = pyqtSignal(str)
    status_changed = pyqtSignal(str)       # ready / error / reconnecting

    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.camera = None
        self._running = False
        self._reconnect_timer = None

    def start(self):
        self._running = True
        self._connect_camera()

    def _connect_camera(self):
        """连接相机，失败则启动重连定时器"""
        try:
            force_sim = self.cfg.get("simulation_mode", True)
            self.camera = create_camera(force_simulation=force_sim)
            self.connected.emit(True,
                "模拟相机已连接" if self.camera.simulation else "尼康 Z5 II 已连接")
            self.status_changed.emit("ready")
            self._apply_camera_params()
        except Exception as e:
            self.connected.emit(False, str(e))
            self.status_changed.emit("error")
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        if self._reconnect_timer is None:
            self._reconnect_timer = QTimer()
            self._reconnect_timer.setSingleShot(True)
            self._reconnect_timer.timeout.connect(self._connect_camera)
        self._reconnect_timer.start(5000)

    def _apply_camera_params(self):
        """应用配置中的相机参数"""
        params = self.cfg.get("camera_params", {})
        mapping = {
            "iso": "iso",
            "shutter": "shutterspeed",
            "aperture": "aperture",
            "white_balance": "whitebalance",
        }
        for cfg_key, cam_key in mapping.items():
            val = params.get(cfg_key)
            if val:
                self.camera.set_config(cam_key, val)

    def capture(self, save_path: str, photo_id: str = None):
        """执行拍摄"""
        if not self.camera or not self.camera.is_ready():
            self.capture_failed.emit("相机未就绪")
            self._schedule_reconnect()
            return
        try:
            self.status_changed.emit("capturing")
            path = self.camera.capture(save_path)
            self.capture_done.emit(path, photo_id or "")
            self.status_changed.emit("ready")
        except CameraError as e:
            self.capture_failed.emit(str(e))
            self.status_changed.emit("error")
            self._schedule_reconnect()

    def get_preview(self) -> bytes:
        """获取一帧预览"""
        if not self.camera:
            return b""
        return self.camera.get_preview_frame()

    def set_param(self, key: str, value):
        if self.camera:
            self.camera.set_config(key, value)

    def autofocus(self, x=0.5, y=0.5):
        if self.camera:
            self.camera.autofocus(x, y)

    def stop(self):
        self._running = False
        if self._reconnect_timer:
            self._reconnect_timer.stop()
        if self.camera:
            self.camera.disconnect()
        self.disconnected.emit()
