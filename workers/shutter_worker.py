"""
拍摄按钮逻辑
对应架构图：二.2 拍摄按钮逻辑
状态校验、下发拍摄指令
"""
import os
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from workers.camera_worker import CameraWorker
from database import Database


class ShutterWorker(QObject):
    """快门 Worker"""
    shutter_clicked = pyqtSignal()
    capture_started = pyqtSignal()
    capture_success = pyqtSignal(str, int)  # raw_path, photo_id
    capture_failed = pyqtSignal(str)
    status_update = pyqtSignal(str)         # ready / busy / error

    def __init__(self, camera_worker: CameraWorker):
        super().__init__()
        self.cfg = Config()
        self.camera_worker = camera_worker
        self.db = Database(self.cfg.db_path)
        self._busy = False

        # 连接相机结果
        self.camera_worker.capture_done.connect(self._on_capture_done)
        self.camera_worker.capture_failed.connect(self._on_capture_failed)
        self.camera_worker.status_changed.connect(self._on_camera_status)

    def click(self, project_id: int):
        """按下快门"""
        if self._busy:
            self.capture_failed.emit("正在拍摄中，请稍候")
            return
        project = self.db.get_project(project_id)
        if not project:
            self.capture_failed.emit("项目不存在")
            return

        self._busy = True
        self.capture_started.emit()
        self.status_update.emit("busy")

        # 生成保存路径
        raw_dir = Path(project["path"]) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"IMG_{timestamp}.jpg"
        save_path = str(raw_dir / filename)

        # 先在 DB 注册照片（获得 photo_id）
        photo_id = self.db.add_photo(project_id, save_path, filename)
        self.camera_worker.capture(save_path, str(photo_id))

    def _on_capture_done(self, raw_path: str, photo_id: str):
        self._busy = False
        self.status_update.emit("ready")
        pid = int(photo_id) if photo_id else 0
        self.capture_success.emit(raw_path, pid)

    def _on_capture_failed(self, msg: str):
        self._busy = False
        self.status_update.emit("error")
        self.capture_failed.emit(msg)

    def _on_camera_status(self, status: str):
        if status == "ready" and not self._busy:
            self.status_update.emit("ready")
        elif status == "error":
            self.status_update.emit("error")

    def shutdown(self):
        self.db.close()
