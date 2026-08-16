"""
五 图库预览弹窗
磨皮调节｜打印｜删除｜缩放
【新增：生成成品+交付顾客按钮】
"""
import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QScrollArea, QProgressBar,
                             QMessageBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from workers.preview_window_worker import PreviewWindowWorker


class PreviewWindow(QDialog):
    photo_deleted = pyqtSignal(int)

    def __init__(self, worker: PreviewWindowWorker, photo_id: int, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.photo_id = photo_id
        self._current_pixmap = None
        self._zoom_level = 1.0
        self._final_path = None
        self._qr_path = None
        self._beauty_level = 2
        self._frame_path = None

        self.setWindowTitle(f"照片预览 #{photo_id}")
        self.setMinimumSize(900, 700)
        self._setup_ui()
        self._connect_signals()
        self.worker.load_hires(photo_id)

    def _setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(15, 15, 15, 15)
        main.setSpacing(15)

        # ===== 左侧：图片预览 =====
        left = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #000; border-radius: 8px;")
        self.img_label = QLabel("加载中...")
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setMinimumSize(600, 450)
        self.scroll.setWidget(self.img_label)
        left.addWidget(self.scroll, stretch=1)

        # 缩放控制
        zoom_bar = QHBoxLayout()
        zoom_out = QPushButton("➖")
        zoom_out.setFixedWidth(40)
        zoom_out.clicked.connect(lambda: self._set_zoom(self._zoom_level - 0.2))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_in = QPushButton("➕")
        zoom_in.setFixedWidth(40)
        zoom_in.clicked.connect(lambda: self._set_zoom(self._zoom_level + 0.2))
        reset_zoom = QPushButton("重置")
        reset_zoom.clicked.connect(lambda: self._set_zoom(1.0))
        zoom_bar.addWidget(zoom_out)
        zoom_bar.addWidget(self.zoom_label)
        zoom_bar.addWidget(zoom_in)
        zoom_bar.addWidget(reset_zoom)
        left.addLayout(zoom_bar)
        main.addLayout(left, stretch=3)

        # ===== 右侧：操作面板 =====
        right = QVBoxLayout()
        right.setSpacing(12)

        # 磨皮调节
        right.addWidget(QLabel("✨ 磨皮等级："))
        self.beauty_slider = QSlider(Qt.Orientation.Horizontal)
        self.beauty_slider.setRange(0, 5)
        self.beauty_slider.setValue(2)
        self.beauty_slider.valueChanged.connect(self._on_beauty_changed)
        right.addWidget(self.beauty_slider)
        self.beauty_label = QLabel("自然 (2)")
        self.beauty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.beauty_label)

        self.apply_beauty_btn = QPushButton("🎨 应用磨皮预览")
        self.apply_beauty_btn.clicked.connect(self._on_apply_beauty)
        right.addWidget(self.apply_beauty_btn)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        right.addWidget(line)

        # 【新增】成品交付
        right.addWidget(QLabel("📦 成品交付："))
        self.generate_btn = QPushButton("⚙️ 生成高清成品")
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.clicked.connect(self._on_generate_final)
        right.addWidget(self.generate_btn)

        self.deliver_btn = QPushButton("📲 交付顾客（二维码）")
        self.deliver_btn.setObjectName("primaryBtn")
        self.deliver_btn.setEnabled(False)
        self.deliver_btn.clicked.connect(self._on_deliver)
        right.addWidget(self.deliver_btn)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(160)
        right.addWidget(self.qr_label)

        self.url_label = QLabel("")
        self.url_label.setWordWrap(True)
        self.url_label.setStyleSheet("color: #89b4fa; font-size: 11px;")
        right.addWidget(self.url_label)

        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        right.addWidget(line2)

        # 打印
        self.print_btn = QPushButton("🖨️ 打印")
        self.print_btn.clicked.connect(self._on_print)
        right.addWidget(self.print_btn)

        # 进度
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        right.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        right.addWidget(self.status_label)

        right.addStretch()

        # 删除
        self.delete_btn = QPushButton("🗑️ 删除照片")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self._on_delete)
        right.addWidget(self.delete_btn)

        # 关闭
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        right.addWidget(close_btn)

        main.addLayout(right, stretch=1)

    def _connect_signals(self):
        self.worker.hires_ready.connect(self._on_hires_ready)
        self.worker.beauty_preview_ready.connect(self._on_beauty_preview)
        self.worker.final_generated.connect(self._on_final_generated)
        self.worker.print_done.connect(self._on_print_done)
        self.worker.delete_done.connect(self._on_delete_done)
        self.worker.qr_ready.connect(self._on_qr_ready)
        self.worker.deliver_ready.connect(self._on_deliver_ready)
        self.worker.error.connect(self._on_error)

    def _on_hires_ready(self, photo_id, path):
        if photo_id == self.photo_id:
            self._current_pixmap = QPixmap(path)
            self._update_display()

    def _on_beauty_changed(self, val):
        names = ["关闭", "轻微", "自然", "标准", "较强", "最强"]
        self.beauty_label.setText(f"{names[val]} ({val})")
        self._beauty_level = val

    def _on_apply_beauty(self):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("生成磨皮预览中...")
        self.worker.preview_beauty(self.photo_id, self._beauty_level, self._frame_path)

    def _on_beauty_preview(self, photo_id, path):
        if photo_id == self.photo_id:
            self._current_pixmap = QPixmap(path)
            self._update_display()
            self.progress.setVisible(False)
            self.status_label.setText("磨皮预览已更新")

    def _on_generate_final(self):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("正在生成高清成品...")
        self.generate_btn.setEnabled(False)
        self.worker.generate_final(self.photo_id, self._beauty_level, self._frame_path)

    def _on_final_generated(self, photo_id, final_path, preview_path):
        if photo_id == self.photo_id:
            self._final_path = final_path
            self.progress.setVisible(False)
            self.status_label.setText(f"成品已生成：{os.path.basename(final_path)}")
            self.deliver_btn.setEnabled(True)
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("✅ 已生成（可重新生成）")
            if preview_path:
                self._current_pixmap = QPixmap(preview_path)
                self._update_display()

    def _on_deliver(self):
        if not self._final_path:
            QMessageBox.warning(self, "提示", "请先生成高清成品")
            return
        self.status_label.setText("生成交付二维码中...")
        self.worker.deliver_to_customer(self.photo_id, self._final_path)

    def _on_qr_ready(self, photo_id, qr_path, url):
        if photo_id == self.photo_id:
            pm = QPixmap(qr_path)
            if not pm.isNull():
                self.qr_label.setPixmap(pm.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio))
            self.url_label.setText(f"下载链接：{url}")
            self.status_label.setText("请顾客扫码下载原图")

    def _on_deliver_ready(self, photo_id, final_path, qr_path):
        pass  # 已在 qr_ready 处理

    def _on_print(self):
        path = self._final_path
        if not path:
            # 没有成品则直接打原图
            self.status_label.setText("未生成成品，将打印原图")
        self.worker.print_photo(self.photo_id, path)
        self.status_label.setText("打印任务已发送...")

    def _on_print_done(self, photo_id, success, msg):
        if photo_id == self.photo_id:
            self.status_label.setText(msg)
            if not success:
                QMessageBox.warning(self, "打印", msg)

    def _on_delete(self):
        reply = QMessageBox.question(self, "确认删除",
                                      "确定要删除这张照片吗？此操作不可恢复。",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.worker.delete_photo(self.photo_id)

    def _on_delete_done(self, photo_id):
        if photo_id == self.photo_id:
            self.photo_deleted.emit(photo_id)
            self.accept()

    def _on_error(self, msg):
        self.progress.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.status_label.setText(f"错误：{msg}")
        QMessageBox.critical(self, "错误", msg)

    def _set_zoom(self, level):
        self._zoom_level = max(0.2, min(5.0, level))
        self.zoom_label.setText(f"{int(self._zoom_level * 100)}%")
        self._update_display()

    def _update_display(self):
        if self._current_pixmap and not self._current_pixmap.isNull():
            if self._zoom_level != 1.0:
                w = int(self._current_pixmap.width() * self._zoom_level)
                h = int(self._current_pixmap.height() * self._zoom_level)
                scaled = self._current_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation)
                self.img_label.setPixmap(scaled)
                self.img_label.resize(scaled.size())
            else:
                self.img_label.setPixmap(self._current_pixmap)
                self.img_label.adjustSize()
