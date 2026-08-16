"""
预览图生成后台进程
对应架构图：七 预览图生成后台进程
5类图像生成：
  ①极小缩略图(图库宫格)  thumbnail
  ②低画质预览(确认页)    lowres
  ③无损预览(大图弹窗)    hires
  ④项目封面图(首页)      cover
  ⑤成品效果图预览        final_preview
统一写入缓存块，LRU容量管控
"""
import os
import time
from pathlib import Path
from PIL import Image
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from config import Config
from cache import CacheManager
from database import Database


PREVIEW_TYPES = {
    "thumbnail": (200, 200),      # 极小缩略图
    "lowres": (800, 600),         # 低画质预览
    "hires": (1600, 1200),        # 无损预览
    "cover": (400, 300),          # 项目封面
    "final_preview": (1024, 768), # 成品效果图预览
}


class ThumbnailWorker(QObject):
    """缩略图生成 Worker（运行在独立线程）"""
    preview_ready = pyqtSignal(str, str, str)   # preview_type, cache_path, photo_id
    cover_ready = pyqtSignal(int, str)           # project_id, cover_path
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.cache_mgr = CacheManager()
        self.db = Database(self.cfg.db_path)

    def generate(self, source_path: str, preview_type: str,
                 photo_id=None, project_id=None) -> str:
        """生成指定类型预览图，返回缓存路径"""
        try:
            if preview_type not in PREVIEW_TYPES:
                raise ValueError(f"未知预览类型: {preview_type}")

            # 检查缓存是否已存在
            if photo_id:
                existing = self.db.get_preview(photo_id, preview_type)
                if existing and os.path.exists(existing["cache_path"]):
                    self.preview_ready.emit(preview_type, existing["cache_path"], str(photo_id))
                    return existing["cache_path"]

            target_w, target_h = PREVIEW_TYPES[preview_type]
            cache_path = self.cache_mgr.get_path(preview_type, photo_id, project_id)

            # 打开并缩放
            img = Image.open(source_path)
            img.thumbnail((target_w, target_h), Image.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(str(cache_path), "JPEG", quality=85)

            size_bytes = os.path.getsize(str(cache_path))
            pid = self.db.add_preview(photo_id, project_id, preview_type,
                                       str(cache_path), size_bytes)

            # LRU 淘汰
            self.cache_mgr.evict_if_needed(self.db)

            if preview_type == "cover" and project_id:
                self.db.update_project_cover(project_id, str(cache_path))
                self.cover_ready.emit(project_id, str(cache_path))
            else:
                self.preview_ready.emit(preview_type, str(cache_path),
                                         str(photo_id) if photo_id else "")
            return str(cache_path)
        except Exception as e:
            self.error.emit(f"缩略图生成失败: {e}")
            return ""

    def generate_batch(self, source_path: str, types: list,
                       photo_id=None, project_id=None) -> dict:
        """批量生成多种预览"""
        results = {}
        for t in types:
            p = self.generate(source_path, t, photo_id, project_id)
            results[t] = p
        return results

    def get_cached(self, photo_id: int, preview_type: str) -> str:
        """获取已缓存预览路径"""
        pv = self.db.get_preview(photo_id, preview_type)
        if pv and os.path.exists(pv["cache_path"]):
            return pv["cache_path"]
        return ""

    def shutdown(self):
        self.db.close()
