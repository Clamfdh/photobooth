"""
打印机硬件抽象层
对应架构图：🖨️ CY02/RX1照片打印机
优先使用系统打印，不可用时模拟
"""
import os
import subprocess
from pathlib import Path


class PrinterError(Exception):
    pass


class BasePrinter:
    available = False
    simulation = False

    def print_image(self, image_path: str, copies: int = 1): ...
    def get_status(self) -> str: ...


class SystemPrinter(BasePrinter):
    """通过 lp 命令调用系统打印机（CUPS）"""

    def __init__(self, printer_name: str = "CY02"):
        self.printer_name = printer_name
        self.simulation = False
        self._check()

    def _check(self):
        try:
            r = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=3)
            if self.printer_name in r.stdout or r.stdout.strip():
                self.available = True
                if self.printer_name not in r.stdout:
                    # 取第一个可用打印机
                    for line in r.stdout.splitlines():
                        if line.startswith("printer"):
                            self.printer_name = line.split()[1]
                            break
            else:
                self.available = False
        except Exception:
            self.available = False

    def print_image(self, image_path: str, copies: int = 1):
        if not self.available:
            raise PrinterError("无可用打印机")
        if not os.path.exists(image_path):
            raise PrinterError(f"图片不存在: {image_path}")
        try:
            cmd = ["lp", "-d", self.printer_name, "-n", str(copies), image_path]
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        except subprocess.CalledProcessError as e:
            raise PrinterError(f"打印失败: {e.stderr.decode() if e.stderr else str(e)}")

    def get_status(self) -> str:
        return "ready" if self.available else "offline"


class SimulatedPrinter(BasePrinter):
    """模拟打印机：记录打印日志"""

    def __init__(self):
        self.simulation = True
        self.available = True
        self.log = []

    def print_image(self, image_path: str, copies: int = 1):
        if not os.path.exists(image_path):
            raise PrinterError(f"图片不存在: {image_path}")
        entry = f"[SIM PRINT] {image_path} x{copies}"
        self.log.append(entry)
        print(entry)
        # 模拟打印耗时
        import time
        time.sleep(1.0)

    def get_status(self) -> str:
        return "simulation-ready"


def create_printer(printer_name: str = "CY02"):
    p = SystemPrinter(printer_name)
    if p.available:
        return p
    return SimulatedPrinter()
