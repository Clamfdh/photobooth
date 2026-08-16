"""
四 图库界面
照片宫格(最多9张)
选中启用拼图/删除｜常驻拍摄入口
"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QGridLayout, QScrollArea,
                             QFrame, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from config import Config
from database import Database
from workers.thumbnail_gen import ThumbnailWorker


class PhotoTile(QFrame):
    """宫格中的单个照片块"""
    clicked = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, photo_id: int, parent=None):
        super().__init__(parent)
        self.photo_id = photo_id
        self.setFixedSize(180, 140)
        self.setStyleSheet("QFrame { border: 2px solid #45475a; border-radius: 8px; }"
                           "QFrame:hover { border-color: #89b4fa; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setMinimumSize(160, 100)
        layout.addWidget(self.img_label)
        self.id_label = QLabel(f"#{photo_id}")
        self.id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.id_label.setStyleSheet("font-size: 11px; color: #a6adc8;")
        layout.addWidget(self.id_label)

    def set_image(self, path):
        pm = QPixmap(path)
        if not pm.isNull():
            self.img_label.setPixmap(pm.scaled(160, 100,
                                                Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, ev):
        self.clicked.emit(self.photo_id)


class GalleryScreen(QWidget):
    photo_selected = pyqtSignal(int)   # 打开预览弹窗
    go_capture = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, thumb_worker: ThumbnailWorker, parent=None):
        super().__init__(parent)
        self.cfg = Config()
        self.db = Database(self.cfg.db_path)
        self.thumb_worker = thumb_worker
        self._current_project_id = None
        self._tiles = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 顶部栏
        top = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.clicked.connect(self.go_back.emit)
        top.addWidget(back_btn)

        title = QLabel("🖼️ 图库")
        title.setObjectName("titleLabel")
        top.addWidget(title)
        top.addStretch()

        self.count_label = QLabel("")
        top.addWidget(self.count_label)

        capture_btn = QPushButton("📸 去拍摄")
        capture_btn.setObjectName("primaryBtn")
        capture_btn.clicked.connect(self.go_capture.emit)
        top.addWidget(capture_btn)
        layout.addLayout(top)

        # 宫格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(12)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

    def _connect_signals(self):
        self.thumb_worker.preview_ready.connect(self._on_thumb_ready)

    def set_project(self, project_id: int):
        self._current_project_id = project_id
        self.refresh()

    def refresh(self):
        if not self._current_project_id:
            return
        # 清空
        for tile in self._tiles.values():
            tile.deleteLater()
        self._tiles.clear()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        max_photos = self.cfg.get("gallery_max_photos", 9)
        photos = self.db.list_photos(self._current_project_id, limit=max_photos)
        self.count_label.setText(f"共 {len(photos)} 张（最多显示{max_photos}张）")

        for i, p in enumerate(photos):
            tile = PhotoTile(p["id"])
            tile.clicked.connect(self.photo_selected.emit)
            self.grid.addWidget(tile, i // 3, i % 3)
            self._tiles[p["id"]] = tile
            # 加载缩略图
            cached = self.thumb_worker.get_cached(p["id"], "thumbnail")
            if cached:
                tile.set_image(cached)
            else:
                self.thumb_worker.generate(p["raw_path"], "thumbnail", photo_id=p["id"])

    def _on_thumb_ready(self, preview_type, cache_path, photo_id):
        if preview_type == "thumbnail" and photo_id:
            pid = int(photo_id)
            if pid in self._tiles:
                self._tiles[pid].set_image(cache_path)
