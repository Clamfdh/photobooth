"""
缓存块文件管理
对应架构图：📦 缓存块文件
初始30MB，不足追加30MB，上限500MB，LRU淘汰
实际实现为缓存目录 + 数据库索引的 LRU 管理
"""
import os
from pathlib import Path
from config import Config


class CacheManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_ready"):
            return
        self._ready = True
        self.cfg = Config()
        self.cache_dir = self.cfg.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_path(self, preview_type: str, photo_id=None, project_id=None) -> Path:
        """生成缓存文件路径"""
        sub = self.cache_dir / preview_type
        sub.mkdir(parents=True, exist_ok=True)
        if photo_id:
            name = f"photo_{photo_id}_{preview_type}.jpg"
        elif project_id:
            name = f"project_{project_id}_{preview_type}.jpg"
        else:
            import time
            name = f"tmp_{int(time.time()*1000)}_{preview_type}.jpg"
        return sub / name

    def evict_if_needed(self, db, current_size: int = None):
        """LRU 淘汰，确保缓存不超过上限"""
        max_bytes = self.cfg.get("cache_max_mb", 500) * 1024 * 1024
        if current_size is None:
            current_size = db.total_cache_size()
        if current_size <= max_bytes:
            return 0
        evicted = 0
        # 按 last_access 升序删除
        for pv in db.list_lru_previews(200):
            if current_size <= max_bytes:
                break
            try:
                p = Path(pv["cache_path"])
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            current_size -= pv.get("size_bytes", 0)
            db.delete_preview(pv["id"])
            evicted += 1
        return evicted

    def clear_all(self):
        """清空缓存目录"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
