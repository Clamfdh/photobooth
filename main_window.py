"""
主窗口：管理所有 Worker 线程与 UI 页面切换
对应架构图整体编排
"""
import sys
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PyQt6.QtCore import QThread, Qt

from config import Config
from ui.styles import DARK_QSS, LIGHT_QSS
from ui.start_screen import StartScreen
from ui.capture_screen import CaptureScreen
from ui.confirm_screen import ConfirmScreen
from ui.gallery_screen import GalleryScreen
from ui.preview_window import PreviewWindow

from workers.camera_worker import CameraWorker
from workers.preview_stream import PreviewStreamWorker
from workers.shutter_worker import ShutterWorker
from workers.focus_worker import FocusWorker
from workers.start_worker import StartWorker
from workers.confirm_worker import ConfirmWorker
from workers.preview_window_worker import PreviewWindowWorker
from workers.image_processor import ImageProcessor
from workers.thumbnail_gen import ThumbnailWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.setWindowTitle("Photobooth 联机拍摄系统")
        self.resize(1280, 800)

        # 应用样式
        self.setStyleSheet(DARK_QSS if self.cfg.get("night_mode", False) else LIGHT_QSS)

        # ===== 创建所有 Worker =====
        self._init_workers()

        # ===== 创建 UI 页面 =====
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.start_screen = StartScreen(self.start_worker)
        self.capture_screen = CaptureScreen(
            self.camera_worker, self.preview_worker,
            self.shutter_worker, self.focus_worker, self.thumb_worker
        )
        self.confirm_screen = ConfirmScreen(self.confirm_worker)
        self.gallery_screen = GalleryScreen(self.thumb_worker)

        self.stack.addWidget(self.start_screen)    # index 0
        self.stack.addWidget(self.capture_screen)  # index 1
        self.stack.addWidget(self.confirm_screen)  # index 2
        self.stack.addWidget(self.gallery_screen)  # index 3

        # ===== 连接页面导航 =====
        self.start_screen.project_opened.connect(self._enter_capture)
        self.capture_screen.capture_confirmed.connect(self._enter_confirm)
        self.capture_screen.go_gallery.connect(self._enter_gallery)
        self.capture_screen.go_back.connect(self._go_start)
        self.confirm_screen.retake.connect(self._enter_capture_from_confirm)
        self.confirm_screen.saved.connect(self._enter_capture_from_confirm)
        self.confirm_screen.printed.connect(lambda pid: self._enter_capture_from_confirm())
        self.gallery_screen.photo_selected.connect(self._open_preview)
        self.gallery_screen.go_capture.connect(self._enter_capture_from_gallery)
        self.gallery_screen.go_back.connect(self._go_start)

        # 启动相机线程
        self.camera_thread.start()

    def _init_workers(self):
        """初始化所有 Worker 及其线程"""
        # 缩略图生成（独立线程）
        self.thumb_thread = QThread()
        self.thumb_worker = ThumbnailWorker()
        self.thumb_worker.moveToThread(self.thumb_thread)
        self.thumb_thread.start()

        # 图像处理（独立线程）
        self.image_thread = QThread()
        self.image_processor = ImageProcessor()
        self.image_processor.moveToThread(self.image_thread)
        self.image_thread.start()

        # 相机（独立线程）
        self.camera_thread = QThread()
        self.camera_worker = CameraWorker()
        self.camera_worker.moveToThread(self.camera_thread)
        self.camera_thread.started.connect(self.camera_worker.start)
        # 注意：不在这里 start，等 UI 就绪

        # 预览流（独立线程）
        self.preview_thread = QThread()
        self.preview_worker = PreviewStreamWorker(self.camera_worker)
        self.preview_worker.moveToThread(self.preview_thread)
        self.preview_thread.start()

        # 快门（独立线程）
        self.shutter_thread = QThread()
        self.shutter_worker = ShutterWorker(self.camera_worker)
        self.shutter_worker.moveToThread(self.shutter_thread)
        self.shutter_thread.start()

        # 对焦（独立线程）
        self.focus_thread = QThread()
        self.focus_worker = FocusWorker(self.camera_worker)
        self.focus_worker.moveToThread(self.focus_thread)
        self.focus_thread.start()

        # 开始页（独立线程）
        self.start_thread = QThread()
        self.start_worker = StartWorker(self.thumb_worker)
        self.start_worker.moveToThread(self.start_thread)
        self.start_thread.start()

        # 确认页（独立线程）
        self.confirm_thread = QThread()
        self.confirm_worker = ConfirmWorker(self.thumb_worker, self.image_processor)
        self.confirm_worker.moveToThread(self.confirm_thread)
        self.confirm_thread.start()

        # 预览弹窗（独立线程）
        self.preview_win_thread = QThread()
        self.preview_win_worker = PreviewWindowWorker(self.thumb_worker, self.image_processor)
        self.preview_win_worker.moveToThread(self.preview_win_thread)
        self.preview_win_thread.start()

    # ===== 页面导航 =====
    def _enter_capture(self, project_id):
        self.capture_screen.set_project(project_id)
        self.stack.setCurrentIndex(1)
        self.capture_screen.start_preview()

    def _enter_capture_from_confirm(self):
        self.capture_screen.stop_preview()
        self.capture_screen.start_preview()
        self.stack.setCurrentIndex(1)

    def _enter_capture_from_gallery(self):
        self.stack.setCurrentIndex(1)
        self.capture_screen.start_preview()

    def _enter_confirm(self, photo_id):
        self.capture_screen.stop_preview()
        frame = self.capture_screen.get_current_frame()
        self.confirm_screen.load_photo(photo_id,
                                        beauty_level=self.cfg.get("beauty_level", 2),
                                        frame_path=frame)
        self.stack.setCurrentIndex(2)

    def _enter_gallery(self):
        self.capture_screen.stop_preview()
        pid = self.cfg.get("current_project")
        if pid:
            self.gallery_screen.set_project(pid)
        self.stack.setCurrentIndex(3)

    def _go_start(self):
        self.capture_screen.stop_preview()
        self.start_screen.refresh()
        self.stack.setCurrentIndex(0)

    def _open_preview(self, photo_id):
        dlg = PreviewWindow(self.preview_win_worker, photo_id, self)
        dlg.photo_deleted.connect(lambda pid: self.gallery_screen.refresh())
        dlg.exec()

    def closeEvent(self, event):
        """关闭时清理所有线程"""
        self.capture_screen.stop_preview()
        self.camera_worker.stop()
        for thread in [self.thumb_thread, self.image_thread, self.camera_thread,
                       self.preview_thread, self.shutter_thread, self.focus_thread,
                       self.start_thread, self.confirm_thread, self.preview_win_thread]:
            thread.quit()
            thread.wait(2000)
        event.accept()
