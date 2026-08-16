"""
全局单例配置模块
对应架构图：〇 配置模块
所有模块通过 Config.instance() 访问统一参数
"""
import os
import json
from pathlib import Path


class Config:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data = {}
        self._load()

    # ---------- 路径 ----------
    @property
    def base_dir(self) -> Path:
        d = Path(os.environ.get("PHOTOBOOTH_HOME", str(Path.home() / "Photobooth")))
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def projects_dir(self) -> Path:
        d = self.base_dir / "projects"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def cache_dir(self) -> Path:
        d = self.base_dir / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def db_path(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir / "photobooth.db"

    @property
    def export_dir(self) -> Path:
        d = self.base_dir / "exports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def config_path(self) -> Path:
        return self.base_dir / "config.json"

    # ---------- 默认值 ----------
    def _defaults(self) -> dict:
        return {
            "night_mode": False,
            "beauty_level": 2,            # 0-5 磨皮等级预设
            "print_size": "2x6",          # 2x6 / 4x6 / 5x7
            "current_project": None,
            "last_project": None,
            "camera_params": {
                "iso": "Auto",
                "shutter": "1/60",
                "aperture": "f/4",
                "white_balance": "Auto",
            },
            "export_quality": 95,
            "cache_initial_mb": 30,
            "cache_append_mb": 30,
            "cache_max_mb": 500,
            "gallery_max_photos": 9,
            "simulation_mode": True,      # 无 gphoto2 时自动模拟
            "printer_name": "CY02",
            "qr_port": 8765,
            "qr_host": "0.0.0.0",
        }

    def _load(self):
        defaults = self._defaults()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                defaults.update(saved)
            except Exception:
                pass
        self._data = defaults
        self._save()

    def _save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 公开 API ----------
    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self._save()

    def get_camera_param(self, key, default=None):
        return self._data.get("camera_params", {}).get(key, default)

    def set_camera_param(self, key, value):
        self._data.setdefault("camera_params", {})[key] = value
        self._save()

    def to_dict(self) -> dict:
        return dict(self._data)
