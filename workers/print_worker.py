"""
打印工作线程
对应架构图：五.3 打印工作线程
集成打印机硬件、图像处理、成品交付的完整业务流
"""
import os
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from config import Config
from database import Database
from hardware.printer import create_printer, PrinterError
from hardware.qr_service import QRService
from workers.image_processor import ImageProcessor


class PrintWorker(QObject):
    """打印业务 Worker"""
    print_progress = pyqtSignal(int, str)        # percent, message
    print_success = pyqtSignal(int, str)         # photo_id, final_path
    print_failed = pyqtSignal(int, str)          # photo_id, error_msg
    qr_generated = pyqtSignal(int, str, str)     # photo_id, qr_image_path, download_url
    
    def __init__(self, image_processor: ImageProcessor):
        super().__init__()
        self.cfg = Config()
        self.db = Database(self.cfg.db_path)
        self.image_processor = image_processor
        self.printer = create_printer(self.cfg.get("printer_name", "CY02"))
        self.qr_service = QRService()
        self._current_photo_id = None
        
    def start_qr_service(self):
        """启动二维码服务"""
        try:
            port = self.cfg.get("qr_port", 8765)
            serve_dir = str(self.cfg.export_dir)
            self.qr_service.start(port=port, serve_dir=serve_dir)
        except Exception as e:
            print(f"QR 服务启动失败: {e}")
    
    def print_photo(self, photo_id: int, beauty_level: int = 2, 
                   frame_path: str = None, copies: int = 1):
        """
        完整打印流程：
        1. 获取原图
        2. 磨皮 + 相框处理
        3. 调用打印机
        4. 生成成品二维码
        """
        try:
            self._current_photo_id = photo_id
            photo = self.db.get_photo(photo_id)
            if not photo:
                self.print_failed.emit(photo_id, "照片不存在")
                return
            
            project = self.db.get_project(photo["project_id"])
            if not project:
                self.print_failed.emit(photo_id, "项目不存在")
                return
            
            self.print_progress.emit(10, "准备打印")
            
            # 生成成品高清图
            export_dir = os.path.join(project["path"], "exports")
            os.makedirs(export_dir, exist_ok=True)
            
            self.print_progress.emit(30, "磨皮处理中")
            print_size = self.cfg.get("print_size", "2x6")
            final_path = self.image_processor.process_for_print(
                photo["raw_path"], 
                export_dir,
                beauty_level=beauty_level,
                frame_path=frame_path,
                print_size=print_size
            )
            
            if not final_path or not os.path.exists(final_path):
                self.print_failed.emit(photo_id, "图像处理失败")
                return
            
            # 更新数据库
            self.db.update_photo_export(
                photo_id, 
                final_path,
                beauty_level,
                has_frame=1 if frame_path else 0
            )
            
            # 调用打印机
            self.print_progress.emit(60, f"打印中（{copies}张）")
            try:
                self.printer.print_image(final_path, copies=copies)
                self.print_progress.emit(80, "打印完成，生成二维码")
            except PrinterError as e:
                # 打印失败但继续生成成品
                self.print_progress.emit(80, f"打印跳过: {e}")
            
            # 生成成品交付二维码
            self.print_progress.emit(90, "生成下载二维码")
            qr_path, download_url = self._generate_delivery_qr(final_path, photo_id)
            
            self.print_progress.emit(100, "完成")
            self.print_success.emit(photo_id, final_path)
            self.qr_generated.emit(photo_id, qr_path, download_url)
            
        except Exception as e:
            self.print_failed.emit(photo_id, f"打印失败: {str(e)}")
    
    def _generate_delivery_qr(self, final_path: str, photo_id: int) -> tuple:
        """
        生成成品交付二维码
        返回: (qr_image_path, download_url)
        """
        try:
            # 注册文件到 QR 服务
            download_url = self.qr_service.get_url_for_file(final_path)
            
            # 生成二维码图片
            qr_path = os.path.join(
                self.cfg.export_dir, 
                f"qr_{photo_id}_{int(time.time())}.png"
            )
            self.qr_service.generate_qr_image(download_url, qr_path)
            
            return qr_path, download_url
        except Exception as e:
            print(f"二维码生成失败: {e}")
            return "", ""
    
    def get_printer_status(self) -> str:
        """获取打印机状态"""
        try:
            return self.printer.get_status()
        except Exception:
            return "offline"
    
    def shutdown(self):
        """关闭服务"""
        self.qr_service.stop()
        self.db.close()
