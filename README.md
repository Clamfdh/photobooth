# Photobooth 联机拍摄系统

基于 PyQt6 + gphoto2 的婚礼/活动联机拍摄软件，支持尼康 Z5 II 相机实时预览、拍摄、磨皮、相框合成、打印及顾客二维码交付。

## 架构

```
全局单例层：Config（配置模块）
UI主线程：StartScreen / CaptureScreen / ConfirmScreen / GalleryScreen / PreviewWindow
业务异步线程池：
  - StartWorker（项目遍历+封面）
  - PreviewStreamWorker（实时预览流）
  - ShutterWorker（快门逻辑）
  - CameraWorker（相机连接/重连/参数）
  - FocusWorker（单点对焦）
  - ConfirmWorker（确认页后台）
  - PreviewWindowWorker（预览弹窗业务+成品交付）
  - ImageProcessor（磨皮+相框合成）
  - ThumbnailWorker（5类预览图生成+LRU缓存）
底层持久化：SQLite(projects/photos/previews分表) + 缓存块(LRU)
硬件：尼康Z5 II(gphoto2) / CY02-RX1打印机 / 局域网二维码下载
```

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

无真实相机时自动进入**模拟模式**，生成测试画面用于调试。

## 目录结构

```
photobooth/
├── main.py              # 入口
├── main_window.py       # 主窗口+线程编排
├── config.py            # 全局配置单例
├── database.py          # SQLite + DBWorker
├── cache.py             # 缓存块LRU管理
├── requirements.txt
├── ui/                  # UI 5个界面
│   ├── start_screen.py
│   ├── capture_screen.py
│   ├── confirm_screen.py
│   ├── gallery_screen.py
│   ├── preview_window.py
│   └── styles.py
├── workers/             # 9个异步Worker
│   ├── camera_worker.py
│   ├── preview_stream.py
│   ├── shutter_worker.py
│   ├── focus_worker.py
│   ├── start_worker.py
│   ├── confirm_worker.py
│   ├── preview_window_worker.py
│   ├── image_processor.py
│   └── thumbnail_gen.py
├── hardware/            # 硬件抽象
│   ├── camera.py        # gphoto2 + 模拟回退
│   ├── printer.py       # CUPS lp + 模拟回退
│   └── qr_service.py    # 局域网HTTP+二维码
└── assets/
    └── frames/          # 相框PNG放这里
```

## 核心功能

1. **实时预览**：gphoto2 预览流，点击画面对焦
2. **拍摄**：状态校验→下发指令→保存原图→自动跳转确认页
3. **磨皮**：OpenCV双边滤波+肤色检测，0-5级可调
4. **相框**：PNG透明叠加，assets/frames 目录扫描
5. **打印**：2x6/4x6/5x7 尺寸，CY02/RX1 打印机
6. **成品交付**：生成高清成品→局域网HTTP→二维码扫码下载
7. **图库**：宫格展示，最多9张，预览弹窗缩放/删除
8. **缓存**：5类预览图统一管理，LRU淘汰，上限500MB
