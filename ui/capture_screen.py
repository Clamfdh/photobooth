"""
二 拍摄界面
左侧预览｜右上相框选择｜中间快门按钮(绿就绪/红异常)
底部快捷图库(最小预览图)
"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QScrollArea, QGridLayout,
                             QFrame, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QMouseEvent

from workers.preview_stream import PreviewStreamWorker
from workers.shutter_worker import ShutterWorker
from workers.focus_worker import FocusWorker
from workers.thumbnail_gen import ThumbnailWorker
from workers.camera_worker import CameraWorker
from database import Database
from config import Config


class ClickableLabel(QLabel):
    """可点击的预览标签，支持点击对焦"""
    clicked = pyqtSignal(float, float)

    def mousePressEvent(self, ev: QMouseEvent):
        if self.pixmap() and not self.pixmap().isNull():
            x_ratio = ev.position().x() / self.width()
            y_ratio = ev.position().y() / self.height()
            self.clicked.emit(x_ratio, y_ratio)
        super().mousePressEvent(ev)


class CaptureScreen(QWidget):
    capture_confirmed = pyqtSignal(int)   # photo_id -> 跳确认页
    go_gallery = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, camera_worker: CameraWorker,
                 preview_worker: PreviewStreamWorker,
                 shutter_worker: ShutterWorker,
                 focus_worker: FocusWorker,
                 thumb_worker: ThumbnailWorker,
                 parent=None):
        super().__init__(parent)
        self.cfg = Config()
        self.db = Database(self.cfg.db_path)
        self.camera_worker = camera_worker
        self.preview_worker = preview_worker
        self.shutter_worker = shutter_worker
        self.focus_worker = focus_worker
        self.thumb_worker = thumb_worker
        self._current_project_id = None
        self._recent_photos = []

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # ===== 左侧：预览区 =====
        left = QVBoxLayout()
        self.preview_label = ClickableLabel("相机预览加载中...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(640, 480)
        self.preview_label.setStyleSheet("background-color: #000; border-radius: 8px;")
        self.preview_label.setScaledContents(False)
        self.preview_label.clicked.connect(self._on_preview_click)
        left.addWidget(self.preview_label, stretch=1)

        # 底部快捷图库
        left.addWidget(QLabel("📷 最近拍摄："))
        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setWidgetResizable(True)
        self.thumb_scroll.setMaximumHeight(100)
        thumb_widget = QWidget()
        self.thumb_layout = QHBoxLayout(thumb_widget)
        self.thumb_layout.setContentsMargins(4, 4, 4, 4)
        self.thumb_layout.setSpacing(6)
        self.thumb_scroll.setWidget(thumb_widget)
        left.addWidget(self.thumb_scroll)
        main.addLayout(left, stretch=3)

        # ===== 右侧：控制面板 =====
        right = QVBoxLayout()
        right.setSpacing(15)

        # 返回按钮
        back_btn = QPushButton("← 返回首页")
        back_btn.clicked.connect(self.go_back.emit)
        right.addWidget(back_btn)

        # 相框选择
        right.addWidget(QLabel("🖼️ 相框选择："))
        self.frame_combo = QComboBox()
        self.frame_combo.addItem("无相框", None)
        self._load_frames()
        right.addWidget(self.frame_combo)

        # 相机状态
        self.status_label = QLabel("相机状态：检测中...")
        self.status_label.setWordWrap(True)
        right.addWidget(self.status_label)

        # 快门按钮
        self.shutter_btn = QPushButton("📸\n快门")
        self.shutter_btn.setObjectName("shutterReady")
        self.shutter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shutter_btn.clicked.connect(self._on_shutter)
        right.addWidget(self.shutter_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 图库入口
        gallery_btn = QPushButton("🖼️ 进入图库")
        gallery_btn.setObjectName("primaryBtn")
        gallery_btn.clicked.connect(self.go_gallery.emit)
        right.addWidget(gallery_btn)

        right.addStretch()
        main.addLayout(right, stretch=1)

    def _load_frames(self):
        """扫描 assets/frames 目录"""
        frames_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "frames")
        if os.path.exists(frames_dir):
            for f in sorted(os.listdir(frames_dir)):
                if f.lower().endswith((".png", ".jpg")):
                    self.frame_combo.addItem(f.replace(".png", "").replace(".jpg", ""),
                                              os.path.join(frames_dir, f))

    def _connect_signals(self):
        self.preview_worker.frame_ready.connect(self._on_frame)
        self.preview_worker.focus_requested.connect(self.focus_worker.autofocus)
        self.shutter_worker.capture_success.connect(self._on_capture_success)
        self.shutter_worker.capture_failed.connect(self._on_capture_failed)
        self.shutter_worker.status_update.connect(self._on_shutter_status)
        self.camera_worker.connected.connect(self._on_camera_connected)
        self.camera_worker.status_changed.connect(self._on_camera_status)
        self.thumb_worker.preview_ready.connect(self._on_thumb_ready)

    def set_project(self, project_id: int):
        self._current_project_id = project_id
        self._load_recent_thumbs()

    def _load_recent_thumbs(self):
        """加载最近拍摄的缩略图"""
        if not self._current_project_id:
            return
        photos = self.db.list_photos(self._current_project_id, limit=9)
        self._recent_photos = photos
        # 清空
        while self.thumb_layout.count():
            item = self.thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for p in photos:
            cached = self.thumb_worker.get_cached(p["id"], "thumbnail")
            if cached:
                self._add_thumb_widget(p["id"], cached)
            else:
                self.thumb_worker.generate(p["raw_path"], "thumbnail", photo_id=p["id"])

    def _add_thumb_widget(self, photo_id, path):
        lbl = QLabel()
        pm = QPixmap(path)
        if not pm.isNull():
            lbl.setPixmap(pm.scaled(80, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        lbl.setFixedSize(84, 64)
        lbl.setStyleSheet("border: 2px solid #45475a; border-radius: 4px;")
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl.mousePressEvent = lambda e, pid=photo_id: self.capture_confirmed.emit(pid)
        self.thumb_layout.addWidget(lbl)

    def _on_frame(self, pixmap: QPixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(self.preview_label.size(),
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(scaled)

    def _on_preview_click(self, x_ratio, y_ratio):
        self.focus_worker.autofocus(x_ratio, y_ratio)

    def _on_shutter(self):
        if not self._current_project_id:
            QMessageBox.warning(self, "提示", "未选择项目")
            return
        self.shutter_worker.click(self._current_project_id)

    def _on_capture_success(self, raw_path, photo_id):
        # 生成缩略图
        self.thumb_worker.generate(raw_path, "thumbnail", photo_id=photo_id)
        self.thumb_worker.generate(raw_path, "lowres", photo_id=photo_id)
        self._load_recent_thumbs()
        # 跳确认页
        self.capture_confirmed.emit(photo_id)

    def _on_capture_failed(self, msg):
        QMessageBox.warning(self, "拍摄失败", msg)

    def _on_shutter_status(self, status):
        if status == "ready":
            self.shutter_btn.setObjectName("shutterReady")
            self.shutter_btn.setText("📸\n快门")
            self.shutter_btn.setEnabled(True)
        elif status == "busy":
            self.shutter_btn.setObjectName("shutterBusy")
            self.shutter_btn.setText("⏳\n拍摄中")
            self.shutter_btn.setEnabled(False)
        else:
            self.shutter_btn.setObjectName("shutterError")
            self.shutter_btn.setText("⚠️\n异常")
        self.shutter_btn.style().unpolish(self.shutter_btn)
        self.shutter_btn.style().polish(self.shutter_btn)

    def _on_camera_connected(self, success, msg):
        self.status_label.setText(f"相机：{msg}")

    def _on_camera_status(self, status):
        status_map = {"ready": "就绪", "capturing": "拍摄中",
                      "error": "异常", "reconnecting": "重连中"}
        self.status_label.setText(f"相机状态：{status_map.get(status, status)}")

    def _on_thumb_ready(self, preview_type, cache_path, photo_id):
        if preview_type == "thumbnail" and photo_id:
            self._add_thumb_widget(int(photo_id), cache_path)

    def get_current_frame(self):
        return self.frame_combo.currentData()

    def start_preview(self):
        self.preview_worker.start()

    def stop_preview(self):
        self.preview_worker.stop()
