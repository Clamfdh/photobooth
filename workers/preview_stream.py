"""
拍摄实时预览模块
对应架构图：二.1 拍摄实时预览模块
接收画面、转发点击对焦坐标
"""
import time
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage

from workers.camera_worker import CameraWorker


class PreviewStreamWorker(QObject):
    """实时预览流 Worker"""
    frame_ready = pyqtSignal(QPixmap)
    focus_requested = pyqtSignal(float, float)  # x_ratio, y_ratio
    error = pyqtSignal(str)

    def __init__(self, camera_worker: CameraWorker):
        super().__init__()
        self.camera_worker = camera_worker
        self._timer = None
        self._running = False
        self._fps = 15  # 预览帧率

    def start(self):
        self._running = True
        self._timer = QTimer()
        self._timer.timeout.connect(self._grab_frame)
        self._timer.start(int(1000 / self._fps))

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _grab_frame(self):
        if not self._running:
            return
        try:
            data = self.camera_worker.get_preview()
            if not data:
                return
            img = QImage.fromData(data, "JPEG")
            if img.isNull():
                return
            self.frame_ready.emit(QPixmap.fromImage(img))
        except Exception as e:
            self.error.emit(f"预览获取失败: {e}")

    def request_focus(self, x_ratio: float, y_ratio: float):
        """转发对焦坐标"""
        self.focus_requested.emit(x_ratio, y_ratio)
