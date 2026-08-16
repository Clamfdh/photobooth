"""
数据库处理模块
对应架构图：八 数据库处理进程
SQLite 分表：projects / photos / previews
通过 DBWorker 线程串行访问，避免多线程竞争
"""
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, pyqtSignal


class Database:
    """SQLite 直接操作层（仅在 DBWorker 线程内调用）"""

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self.conn = None
        self._connect()
        self._init_tables()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                cover_path TEXT,
                created_at REAL,
                updated_at REAL,
                photo_count INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                raw_path TEXT NOT NULL,
                export_path TEXT,
                filename TEXT,
                created_at REAL,
                has_frame INTEGER DEFAULT 0,
                beauty_level INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS previews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER,
                project_id INTEGER,
                preview_type TEXT NOT NULL,
                cache_path TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                last_access REAL,
                created_at REAL,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_photos_project ON photos(project_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_previews_photo ON previews(photo_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_previews_type ON previews(preview_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_previews_access ON previews(last_access)")
        self.conn.commit()

    # ---------- projects ----------
    def create_project(self, name: str, path: str) -> int:
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO projects (name,path,created_at,updated_at) VALUES (?,?,?,?)",
            (name, path, now, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_project(self, project_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return dict(row) if row else None

    def get_project_by_path(self, path: str) -> dict:
        row = self.conn.execute("SELECT * FROM projects WHERE path=?", (path,)).fetchone()
        return dict(row) if row else None

    def list_projects(self) -> list:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_project_cover(self, project_id: int, cover_path: str):
        self.conn.execute(
            "UPDATE projects SET cover_path=?, updated_at=? WHERE id=?",
            (cover_path, time.time(), project_id)
        )
        self.conn.commit()

    def update_project_count(self, project_id: int):
        self.conn.execute(
            "UPDATE projects SET photo_count=(SELECT COUNT(*) FROM photos WHERE project_id=?), updated_at=? WHERE id=?",
            (project_id, time.time(), project_id)
        )
        self.conn.commit()

    def delete_project(self, project_id: int):
        self.conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        self.conn.commit()

    # ---------- photos ----------
    def add_photo(self, project_id: int, raw_path: str, filename: str) -> int:
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO photos (project_id,raw_path,filename,created_at) VALUES (?,?,?,?)",
            (project_id, raw_path, filename, now)
        )
        self.conn.commit()
        self.update_project_count(project_id)
        return cur.lastrowid

    def get_photo(self, photo_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
        return dict(row) if row else None

    def list_photos(self, project_id: int, limit: int = None) -> list:
        q = "SELECT * FROM photos WHERE project_id=? ORDER BY created_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = self.conn.execute(q, (project_id,)).fetchall()
        return [dict(r) for r in rows]

    def update_photo_export(self, photo_id: int, export_path: str, beauty_level: int, has_frame: int):
        self.conn.execute(
            "UPDATE photos SET export_path=?, beauty_level=?, has_frame=? WHERE id=?",
            (export_path, beauty_level, has_frame, photo_id)
        )
        self.conn.commit()

    def delete_photo(self, photo_id: int):
        row = self.conn.execute("SELECT project_id FROM photos WHERE id=?", (photo_id,)).fetchone()
        pid = row["project_id"] if row else None
        self.conn.execute("DELETE FROM photos WHERE id=?", (photo_id,))
        self.conn.commit()
        if pid:
            self.update_project_count(pid)

    # ---------- previews ----------
    def add_preview(self, photo_id, project_id, preview_type: str,
                    cache_path: str, size_bytes: int = 0) -> int:
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO previews (photo_id,project_id,preview_type,cache_path,size_bytes,last_access,created_at) VALUES (?,?,?,?,?,?,?)",
            (photo_id, project_id, preview_type, cache_path, size_bytes, now, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_preview(self, photo_id, preview_type: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM previews WHERE photo_id=? AND preview_type=? ORDER BY created_at DESC LIMIT 1",
            (photo_id, preview_type)
        ).fetchone()
        if row:
            self.conn.execute("UPDATE previews SET last_access=? WHERE id=?", (time.time(), row["id"]))
            self.conn.commit()
        return dict(row) if row else None

    def get_project_cover(self, project_id: int) -> dict:
        row = self.conn.execute(
            "SELECT * FROM previews WHERE project_id=? AND preview_type='cover' ORDER BY created_at DESC LIMIT 1",
            (project_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_lru_previews(self, limit: int = 100) -> list:
        rows = self.conn.execute(
            "SELECT * FROM previews ORDER BY last_access ASC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def total_cache_size(self) -> int:
        row = self.conn.execute("SELECT COALESCE(SUM(size_bytes),0) as s FROM previews").fetchone()
        return row["s"]

    def delete_preview(self, preview_id: int):
        self.conn.execute("DELETE FROM previews WHERE id=?", (preview_id,))
        self.conn.commit()

    def delete_previews_by_photo(self, photo_id: int):
        self.conn.execute("DELETE FROM previews WHERE photo_id=?", (photo_id,))
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()


class DBWorker(QObject):
    """
    数据库工作线程
    所有 DB 操作通过信号槽串行化
    """
    finished = pyqtSignal(str, object)  # op_name, result
    error = pyqtSignal(str, str)         # op_name, error_msg

    def __init__(self, db_path: Path):
        super().__init__()
        self.db_path = db_path
        self.db = None

    def start(self):
        self.db = Database(self.db_path)

    # 统一入口：通过反射调用 Database 方法
    def execute(self, op_name: str, method: str, *args, **kwargs):
        try:
            if self.db is None:
                self.start()
            func = getattr(self.db, method)
            result = func(*args, **kwargs)
            self.finished.emit(op_name, result)
        except Exception as e:
            self.error.emit(op_name, str(e))

    def shutdown(self):
        if self.db:
            self.db.close()
