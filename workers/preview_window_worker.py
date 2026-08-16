"""
预览弹窗业务处理器
对应架构图：五.1 预览弹窗业务处理器
磨皮预览、打印任务、成品导出流程、【新增：生成成品+交付顾客】
"""
import os
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from database import Database
from workers.thumbnail_gen import ThumbnailWorker
from workers.image_processor import ImageProcessor
from hardware.printer import create_printer
from hardware.qr_service import QRService


class PreviewWindowWorker(QObject):
    """预览弹窗业务 Worker"""
    hires_ready = pyqtSignal(int, str)          # photo_id, hires_path
    beauty_preview_ready = pyqtSignal(int, str) # photo_id, preview_path
    final_generated = pyqtSignal(int, str, str) # photo_id, final_path, preview_path
    print_done = pyqtSignal(int, bool, str)     # photo_id, success, msg
    delete_done = pyqtSignal(int)               # photo_id
    qr_ready = pyqtSignal(int, str, str)        # photo_id, qr_path, download_url
    deliver_ready = pyqtSignal(int, str, str)   # photo_id, final_path, qr_path
    error = pyqtSignal(str)

    def __init__(self, thumb_worker: ThumbnailWorker, image_processor: ImageProcessor):
        super().__init__()
        self.cfg = Config()
        self.db = Database(self.cfg.db_path)
        self.thumb_worker = thumb_worker
        self.image_processor = image_processor
        self.printer = create_printer(self.cfg.get("printer_name", "CY02"))
        self.qr_service = QRService()
        # 启动二维码服务
        try:
            self.qr_service.start(self.cfg.get("qr_port", 8765),
                                   str(self.cfg.export_dir))
        except Exception:
            pass

        self.image_processor.final_done.connect(self._on_final_done)
        self.image_processor.preview_done.connect(self._on_preview_done)

    def load_hires(self, photo_id: int):
        """加载无损预览图"""
        try:
            photo = self.db.get_photo(photo_id)
            if not photo:
                self.error.emit("照片不存在")
                return
            cached = self.thumb_worker.get_cached(photo_id, "hires")
            if cached:
                self.hires_ready.emit(photo_id, cached)
                return
            path = self.thumb_worker.generate(photo["raw_path"], "hires", photo_id=photo_id)
            if path:
                self.hires_ready.emit(photo_id, path)
        except Exception as e:
            self.error.emit(f"加载高清预览失败: {e}")

    def preview_beauty(self, photo_id: int, beauty_level: int, frame_path: str = None):
        """磨皮预览（低分辨率快速预览）"""
        try:
            photo = self.db.get_photo(photo_id)
            if not photo:
                return
            # 用 hires 或 lowres 作为源加速
            src = self.thumb_worker.get_cached(photo_id, "lowres") or photo["raw_path"]
            project = self.db.get_project(photo["project_id"])
            export_dir = os.path.join(project["path"], "exports") if project else str(self.cfg.export_dir)
            self.image_processor.process(src, export_dir, beauty_level, frame_path,
                                          photo_id=str(photo_id), generate_preview=True)
        except Exception as e:
            self.error.emit(f"磨皮预览失败: {e}")

    def generate_final(self, photo_id: int, beauty_level: int, frame_path: str = None):
        """【新增】生成高清成品图用于交付顾客"""
        try:
            photo = self.db.get_photo(photo_id)
            if not photo:
                self.error.emit("照片不存在")
                return
            project = self.db.get_project(photo["project_id"])
            export_dir = os.path.join(project["path"], "exports") if project else str(self.cfg.export_dir)
            self._pending_photo_id = photo_id
            self._pending_beauty = beauty_level
            self._pending_frame = frame_path
            self.image_processor.process(
                photo["raw_path"], export_dir, beauty_level, frame_path,
                photo_id=str(photo_id), generate_preview=True
            )
        except Exception as e:
            self.error.emit(f"生成成品失败: {e}")

    def _on_final_done(self, final_path: str, photo_id: str):
        pid = int(photo_id) if photo_id else 0
        if pid:
            self.db.update_photo_export(pid, final_path,
                                         getattr(self, "_pending_beauty", 2),
                                         1 if getattr(self, "_pending_frame", None) else 0)
            # 生成成品预览缩略图
            self.thumb_worker.generate(final_path, "final_preview", photo_id=pid)

    def _on_preview_done(self, preview_path: str):
        pid = getattr(self, "_pending_photo_id", None)
        if pid:
            self.beauty_preview_ready.emit(pid, preview_path)

    def print_photo(self, photo_id: int, final_path: str = None, copies: int = 1):
        """打印照片"""
        try:
            if not final_path:
                photo = self.db.get_photo(photo_id)
                final_path = photo.get("export_path") if photo else None
            if not final_path or not os.path.exists(final_path):
                self.print_done.emit(photo_id, False, "成品图不存在，请先生成")
                return
            self.printer.print_image(final_path, copies)
            self.print_done.emit(photo_id, True, "打印任务已发送")
        except Exception as e:
            self.print_done.emit(photo_id, False, str(e))

    def deliver_to_customer(self, photo_id: int, final_path: str):
        """【新增核心】交付顾客：生成二维码 + 提供下载"""
        try:
            # 注册文件到 HTTP 服务
            url = self.qr_service.get_url_for_file(final_path)
            # 生成二维码图片
            qr_path = os.path.join(self.cfg.cache_dir, f"qr_{photo_id}.png")
            self.qr_service.generate_qr_image(url, qr_path)
            self.qr_ready.emit(photo_id, qr_path, url)
            self.deliver_ready.emit(photo_id, final_path, qr_path)
        except Exception as e:
            self.error.emit(f"生成交付二维码失败: {e}")

    def delete_photo(self, photo_id: int):
        """删除照片（原图+缓存+数据库）"""
        try:
            photo = self.db.get_photo(photo_id)
            if not photo:
                self.error.emit("照片不存在")
                return
            # 删除原图
            try:
                if os.path.exists(photo["raw_path"]):
                    os.remove(photo["raw_path"])
            except Exception:
                pass
            # 删除成品
            try:
                if photo.get("export_path") and os.path.exists(photo["export_path"]):
                    os.remove(photo["export_path"])
            except Exception:
                pass
            # 删除预览缓存记录（文件由缓存管理器统一处理）
            self.db.delete_previews_by_photo(photo_id)
            self.db.delete_photo(photo_id)
            self.delete_done.emit(photo_id)
        except Exception as e:
            self.error.emit(f"删除失败: {e}")

    def shutdown(self):
        self.db.close()
        self.qr_service.stop()
