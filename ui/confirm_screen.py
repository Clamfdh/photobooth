"""
三 拍摄确认界面
低画质预览｜确认打印｜重拍｜仅保存
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from workers.confirm_worker import ConfirmWorker


class ConfirmScreen(QWidget):
    retake = pyqtSignal()
    saved = pyqtSignal()
    printed = pyqtSignal(int)  # photo_id

    def __init__(self, confirm_worker: ConfirmWorker, parent=None):
        super().__init__(parent)
        self.worker = confirm_worker
        self._current_photo_id = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("✅ 拍摄确认")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 预览区
        self.preview_label = QLabel("加载预览中...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(600, 400)
        self.preview_label.setStyleSheet("background-color: #000; border-radius: 8px;")
        layout.addWidget(self.preview_label, stretch=1)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.retake_btn = QPushButton("🔄 重拍")
        self.retake_btn.setMinimumHeight(50)
        self.retake_btn.clicked.connect(self.retake.emit)

        self.save_btn = QPushButton("💾 仅保存")
        self.save_btn.setMinimumHeight(50)
        self.save_btn.clicked.connect(self._on_save_only)

        self.print_btn = QPushButton("🖨️ 确认打印")
        self.print_btn.setObjectName("primaryBtn")
        self.print_btn.setMinimumHeight(50)
        self.print_btn.clicked.connect(self._on_confirm_print)

        btn_layout.addWidget(self.retake_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.print_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.worker.lowres_ready.connect(self._on_lowres_ready)
        self.worker.print_started.connect(self._on_print_started)
        self.worker.print_done.connect(self._on_print_done)
        self.worker.saved_only.connect(self._on_saved)
        self.worker.error.connect(self._on_error)

    def load_photo(self, photo_id: int, beauty_level: int = 2, frame_path: str = None):
        self._current_photo_id = photo_id
        self._beauty_level = beauty_level
        self._frame_path = frame_path
        self.preview_label.setText("加载预览中...")
        self.progress.setVisible(False)
        self.worker.load_lowres(photo_id)

    def _on_lowres_ready(self, photo_id, path):
        pm = QPixmap(path)
        if not pm.isNull():
            scaled = pm.scaled(self.preview_label.size(),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(scaled)

    def _on_confirm_print(self):
        if not self._current_photo_id:
            return
        self.worker.confirm_print(self._current_photo_id,
                                   getattr(self, "_beauty_level", 2),
                                   getattr(self, "_frame_path", None))

    def _on_save_only(self):
        if self._current_photo_id:
            self.worker.save_only(self._current_photo_id)

    def _on_print_started(self, photo_id):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("正在生成成品并打印...")
        self.print_btn.setEnabled(False)

    def _on_print_done(self, photo_id, print_path):
        self.progress.setVisible(False)
        self.status_label.setText(f"打印完成：{print_path}")
        self.print_btn.setEnabled(True)
        self.printed.emit(photo_id)

    def _on_saved(self, photo_id):
        self.status_label.setText("已保存，返回拍摄")
        self.saved.emit()

    def _on_error(self, msg):
        self.progress.setVisible(False)
        self.print_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", msg)
