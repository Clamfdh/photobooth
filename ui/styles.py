"""全局样式表"""

DARK_QSS = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 14px;
}
QMainWindow { background-color: #1e1e2e; }
QPushButton {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 15px;
    font-weight: bold;
}
QPushButton:hover { background-color: #585b70; }
QPushButton:pressed { background-color: #313244; }
QPushButton#primaryBtn {
    background-color: #89b4fa;
    color: #1e1e2e;
}
QPushButton#primaryBtn:hover { background-color: #b4befe; }
QPushButton#dangerBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#dangerBtn:hover { background-color: #eba0ac; }
QPushButton#shutterReady {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border-radius: 50px;
    min-width: 100px;
    min-height: 100px;
    font-size: 18px;
}
QPushButton#shutterBusy {
    background-color: #f9e2af;
    color: #1e1e2e;
    border-radius: 50px;
    min-width: 100px;
    min-height: 100px;
    font-size: 18px;
}
QPushButton#shutterError {
    background-color: #f38ba8;
    color: #1e1e2e;
    border-radius: 50px;
    min-width: 100px;
    min-height: 100px;
    font-size: 18px;
}
QLabel { background: transparent; }
QLabel#titleLabel {
    font-size: 28px;
    font-weight: bold;
    color: #89b4fa;
}
QLabel#subtitleLabel {
    font-size: 16px;
    color: #a6adc8;
}
QListWidget, QListView {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px;
}
QListWidget::item {
    padding: 12px;
    border-radius: 6px;
    margin: 2px;
}
QListWidget::item:selected {
    background-color: #45475a;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #313244;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #585b70;
    border-radius: 4px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #45475a;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #89b4fa;
    width: 18px;
    margin: -6px 0;
    border-radius: 9px;
}
QComboBox {
    background-color: #45475a;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
}
QProgressBar {
    background-color: #313244;
    border-radius: 4px;
    text-align: center;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
"""

LIGHT_QSS = """
QWidget {
    background-color: #f5f5f7;
    color: #1d1d1f;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 14px;
}
QPushButton {
    background-color: #e8e8ed;
    color: #1d1d1f;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 15px;
    font-weight: bold;
}
QPushButton:hover { background-color: #d2d2d7; }
QPushButton#primaryBtn {
    background-color: #0071e3;
    color: white;
}
QPushButton#primaryBtn:hover { background-color: #0077ed; }
QPushButton#shutterReady {
    background-color: #34c759;
    color: white;
    border-radius: 50px;
    min-width: 100px;
    min-height: 100px;
}
QPushButton#shutterError {
    background-color: #ff3b30;
    color: white;
    border-radius: 50px;
    min-width: 100px;
    min-height: 100px;
}
QLabel#titleLabel { font-size: 28px; font-weight: bold; color: #0071e3; }
"""
