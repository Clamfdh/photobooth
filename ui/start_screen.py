"""
一 开始界面
新建项目 / 打开历史项目
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem,
                             QInputDialog, QMessageBox, QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from workers.start_worker import StartWorker


class StartScreen(QWidget):
    project_opened = pyqtSignal(int)  # project_id

    def __init__(self, start_worker: StartWorker, parent=None):
        super().__init__(parent)
        self.worker = start_worker
        self._projects = []
        self._setup_ui()
        self._connect_signals()
        self.worker.load_projects()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 标题
        title = QLabel("📸 Photobooth 联机拍摄系统")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("选择历史项目或新建项目开始拍摄")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("➕ 新建项目")
        self.new_btn.setObjectName("primaryBtn")
        self.new_btn.setMinimumHeight(50)
        self.new_btn.clicked.connect(self._on_new_project)
        btn_layout.addWidget(self.new_btn)

        self.open_btn = QPushButton("📂 打开选中项目")
        self.open_btn.setMinimumHeight(50)
        self.open_btn.clicked.connect(self._on_open_project)
        btn_layout.addWidget(self.open_btn)
        layout.addLayout(btn_layout)

        # 项目列表
        layout.addWidget(QLabel("历史项目："))
        self.project_list = QListWidget()
        self.project_list.setIconSize(self.project_list.iconSize())
        self.project_list.itemDoubleClicked.connect(lambda _: self._on_open_project())
        layout.addWidget(self.project_list, stretch=1)

        # 底部状态
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.worker.projects_loaded.connect(self._on_projects_loaded)
        self.worker.project_created.connect(self._on_project_created)
        self.worker.project_cover_ready.connect(self._on_cover_ready)
        self.worker.error.connect(self._on_error)

    def _on_projects_loaded(self, projects):
        self._projects = projects
        self.project_list.clear()
        if not projects:
            item = QListWidgetItem("（暂无项目，点击上方新建）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.project_list.addItem(item)
            return
        for p in projects:
            text = f"📁 {p['name']}  |  照片数: {p.get('photo_count', 0)}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.project_list.addItem(item)
        self.status_label.setText(f"共 {len(projects)} 个项目")

    def _on_new_project(self):
        name, ok = QInputDialog.getText(self, "新建项目", "请输入项目名称：")
        if ok and name.strip():
            self.worker.create_project(name.strip())

    def _on_project_created(self, project):
        if project:
            QMessageBox.information(self, "成功", f"项目「{project['name']}」已创建")
            self.project_opened.emit(project["id"])

    def _on_open_project(self):
        item = self.project_list.currentItem()
        if not item:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid is None:
            return
        self.worker.open_project(pid)
        self.project_opened.emit(pid)

    def _on_cover_ready(self, project_id, cover_path):
        # 更新列表项图标
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                pm = QPixmap(cover_path)
                if not pm.isNull():
                    item.setIcon(pm.scaled(60, 45, Qt.AspectRatioMode.KeepAspectRatio))
                break

    def _on_error(self, msg):
        QMessageBox.critical(self, "错误", msg)

    def refresh(self):
        self.worker.load_projects()
