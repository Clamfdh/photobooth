"""
局域网二维码服务
对应架构图：📶 局域网二维码服务(顾客下载原图)
启动本地 HTTP 服务，生成二维码指向下载链接
"""
import os
import socket
import threading
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

try:
    import qrcode
    HAS_QRCODE = True
except Exception:
    HAS_QRCODE = False


def get_lan_ip() -> str:
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class QRService:
    """二维码下载服务单例"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_ready"):
            return
        self._ready = True
        self.server = None
        self.thread = None
        self.port = 8765
        self.host = "0.0.0.0"
        self.serve_dir = None
        self.active_files = {}  # token -> filepath

    def start(self, port: int = 8765, serve_dir: str = None):
        self.port = port
        if serve_dir:
            self.serve_dir = serve_dir
            os.makedirs(serve_dir, exist_ok=True)
        if self.server:
            return
        handler = self._make_handler()
        self.server = HTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _make_handler(self):
        outer = self

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=outer.serve_dir, **kwargs)

            def log_message(self, fmt, *args):
                pass  # 静默

        return Handler

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None

    def register_file(self, filepath: str, token: str = None) -> str:
        """注册文件，返回下载 URL"""
        import shutil
        import uuid
        if not token:
            token = uuid.uuid4().hex[:8]
        if self.serve_dir:
            dest = Path(self.serve_dir) / f"{token}_{Path(filepath).name}"
            shutil.copy2(filepath, dest)
            filename = dest.name
        else:
            filename = Path(filepath).name
        ip = get_lan_ip()
        return f"http://{ip}:{self.port}/{filename}"

    def generate_qr_image(self, url: str, save_path: str) -> str:
        """生成二维码图片"""
        if HAS_QRCODE:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(save_path)
            return save_path
        else:
            # 无 qrcode 库时生成占位图
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (300, 300), "white")
            draw = ImageDraw.Draw(img)
            draw.text((10, 140), f"QR: {url[:40]}", fill="black")
            img.save(save_path)
            return save_path

    def get_url_for_file(self, filepath: str) -> str:
        """快捷：注册并返回 URL"""
        return self.register_file(filepath)
