"""
开始界面后台任务
对应架构图：一.1 开始界面后台任务
遍历项目、拉取封面预览
"""
import os
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from database import Database
from workers.thumbnail_gen import ThumbnailWorker


class StartWorker(QObject):
    """开始页 Worker"""
    projects_loaded = pyqtSignal(list)        # list of project dicts
    project_cover_ready = pyqtSignal(int, str)  # project_id, cover_path
    project_created = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, thumb_worker: ThumbnailWorker):
        super().__init__()
        self.cfg = Config()
        self.db = Database(self.cfg.db_path)
        self.thumb_worker = thumb_worker

    def load_projects(self):
        """加载所有项目列表"""
        try:
            projects = self.db.list_projects()
            self.projects_loaded.emit(projects)
            # 异步生成封面
            for p in projects:
                if not p.get("cover_path"):
                    photos = self.db.list_photos(p["id"], limit=1)
                    if photos:
                        self.thumb_worker.generate(
                            photos[0]["raw_path"], "cover",
                            project_id=p["id"]
                        )
        except Exception as e:
            self.error.emit(f"加载项目失败: {e}")

    def create_project(self, name: str) -> dict:
        """新建项目"""
        try:
            import time
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-")
            project_dir = self.cfg.projects_dir / f"{int(time.time())}_{safe_name}"
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "raw").mkdir(exist_ok=True)
            (project_dir / "exports").mkdir(exist_ok=True)
            pid = self.db.create_project(name, str(project_dir))
            project = self.db.get_project(pid)
            self.cfg.set("current_project", pid)
            self.cfg.set("last_project", pid)
            self.project_created.emit(project)
            return project
        except Exception as e:
            self.error.emit(f"创建项目失败: {e}")
            return None

    def open_project(self, project_id: int) -> dict:
        """打开项目"""
        project = self.db.get_project(project_id)
        if project:
            self.cfg.set("current_project", project_id)
            self.cfg.set("last_project", project_id)
        return project

    def shutdown(self):
        self.db.close()
