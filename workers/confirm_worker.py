"""
确认界面后台
对应架构图：三.1 确认界面后台
加载低画质预览图
"""
import os
from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from database import Database
from workers.thumbnail_gen import ThumbnailWorker
from workers.image_processor import ImageProcessor


class ConfirmWorker(QObject):
    """确认页 Worker"""
    lowres_ready = pyqtSignal(int, str)    # photo_id, preview_path
    print_started = pyqtSignal(int)
    print_done = pyqtSignal(int, str)      # photo_id, print_path
    saved_only = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, thumb_worker: ThumbnailWorker, image_processor: ImageProcessor):
        super().__init__()
        self.cfg = Config()
        self.db = Database(self.cfg.db_path)
        self.thumb_worker = thumb_worker
        self.image_processor = image_processor
        self.image_processor.print_ready.connect(self._on_print_ready)
        self._current_photo_id = None

    def load_lowres(self, photo_id: int):
        """加载低画质预览"""
        try:
            photo = self.db.get_photo(photo_id)
            if not photo:
                self.error.emit("照片不存在")
                return
            # 先查缓存
            cached = self.thumb_worker.get_cached(photo_id, "lowres")
            if cached:
                self.lowres_ready.emit(photo_id, cached)
                return
            # 生成
            path = self.thumb_worker.generate(photo["raw_path"], "lowres", photo_id=photo_id)
            if path:
                self.lowres_ready.emit(photo_id, path)
        except Exception as e:
            self.error.emit(f"加载预览失败: {e}")

    def confirm_print(self, photo_id: int, beauty_level: int = 2, frame_path: str = None):
        """确认打印：生成成品并打印"""
        try:
            self._current_photo_id = photo_id
            photo = self.db.get_photo(photo_id)
            if not photo:
                self.error.emit("照片不存在")
                return
            self.print_started.emit(photo_id)
            project = self.db.get_project(photo["project_id"])
            export_dir = os.path.join(project["path"], "exports") if project else str(self.cfg.export_dir)
            print_size = self.cfg.get("print_size", "2x6")
            self.image_processor.process_for_print(
                photo["raw_path"], export_dir, beauty_level, frame_path, print_size
            )
        except Exception as e:
            self.error.emit(f"打印失败: {e}")

    def save_only(self, photo_id: int):
        """仅保存，不打印"""
        self.saved_only.emit(photo_id)

    def _on_print_ready(self, print_path: str):
        if self._current_photo_id:
            self.print_done.emit(self._current_photo_id, print_path)

    def shutdown(self):
        self.db.close()
