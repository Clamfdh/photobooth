#!/usr/bin/env python3
"""
Photobooth 联机拍摄系统
入口文件

架构：
  全局单例层：Config
  UI主线程：StartScreen / CaptureScreen / ConfirmScreen / GalleryScreen / PreviewWindow
  业务异步线程池：9个 Worker
  底层持久化：SQLite + 缓存块
  硬件：尼康Z5 II(gphoto2) / CY02-RX1打印机 / 局域网二维码
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from main_window import MainWindow


def main():
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Photobooth")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
