"""
对焦模块
对应架构图：二.4 对焦模块
单点对焦指令下发
"""
from PyQt6.QtCore import QObject, pyqtSignal

from workers.camera_worker import CameraWorker


class FocusWorker(QObject):
    """对焦 Worker"""
    focus_started = pyqtSignal(float, float)  # x, y ratio
    focus_done = pyqtSignal(bool)             # success
    error = pyqtSignal(str)

    def __init__(self, camera_worker: CameraWorker):
        super().__init__()
        self.camera_worker = camera_worker

    def autofocus(self, x_ratio: float = 0.5, y_ratio: float = 0.5):
        """执行单点对焦"""
        try:
            self.focus_started.emit(x_ratio, y_ratio)
            self.camera_worker.autofocus(x_ratio, y_ratio)
            self.focus_done.emit(True)
        except Exception as e:
            self.error.emit(f"对焦失败: {e}")
            self.focus_done.emit(False)
