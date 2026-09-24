import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.settings import Settings, base_dir, migrate_legacy_layout
from core.netfix import apply_env_fix

# 系统代理若是 socks（VPN 客户端常见写法），Python 侧一律走直连，否则模型下载必挂
apply_env_fix()

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
# 用户数据根目录 = 安装目录（与安装器写 settings.json 的位置一致）
_BASE_DIR = base_dir()
# 旧布局（用户数据在 app\ 里）搬到安装目录根：只做一次，失败不影响启动
migrate_legacy_layout(_BASE_DIR)
_settings = Settings(_BASE_DIR)
_mirror = _settings.get("download", "hf_endpoint", default="https://hf-mirror.com")
os.environ.setdefault("HF_ENDPOINT", _mirror)

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.glass import apply_design_system


def _asset(*parts):
    """定位 app/assets 下的静态资源；同时兼容源码运行与被 PyInstaller 打包。"""
    for p in (
        os.path.join(getattr(sys, "_MEIPASS", ""), "app", "assets", *parts),
        os.path.join(_APP_DIR, "assets", *parts),
    ):
        if p and os.path.exists(p):
            return p
    return ""


def _set_taskbar_identity():
    """声明进程身份，让任务栏把窗口归到本应用而不是 pythonw.exe。

    不做这一步，任务栏 / Alt-Tab 里显示的是 Python 解释器的图标。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "gxgx3456.AIGCToolkit.1"
        )
    except Exception:
        pass


def _show_selfcheck_problem(parent, level, problems):
    """把自检发现的问题告诉用户，并给出**用户自己能做**的下一步。

    这里刻意不做"一键自动修复"：修复要联网重装几 GB 的包、还可能改动环境，
    放在启动路径上风险太大。引导用户重跑引导器（``启动.cmd``）即可 ——
    那本来就会补装缺失组件，且带完整的进度与失败重试。
    """
    from PySide6.QtWidgets import QMessageBox

    from core.i18n import tr

    text = "\n".join("· " + p for p in problems)
    body = tr("sc_err_body" if level == "error" else "sc_warn_body") % text
    box = QMessageBox(parent)
    box.setWindowTitle(tr("sc_title"))
    box.setIcon(QMessageBox.Critical if level == "error" else QMessageBox.Warning)
    box.setText(body)
    box.exec()


def _selfcheck_async(win):
    """后台跑环境自检，有问题才提示。

    为什么绕这一圈：自检最慢约 3 秒（``import torch``），不能卡住窗口显示；
    而 Qt 控件只能在主线程碰，所以子线程只写结果、主线程轮询取。
    """
    import threading

    from PySide6.QtCore import QTimer

    state = {"done": False, "level": "ok", "problems": []}

    def worker():
        try:
            from core.selfcheck import run_check

            state["level"], state["problems"] = run_check()
        except Exception as e:  # noqa: BLE001
            state["level"], state["problems"] = "error", ["自检异常：%s" % e]
        state["done"] = True

    threading.Thread(target=worker, daemon=True).start()

    timer = QTimer()

    def poll():
        if not state["done"]:
            return
        timer.stop()
        if state["level"] != "ok":
            _show_selfcheck_problem(win, state["level"], state["problems"])

    timer.timeout.connect(poll)
    timer.start(500)


def main():
    _set_taskbar_identity()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # 显式指定中文字体，避免不同系统默认字体导致的渲染异常
    app.setFont(QFont("Microsoft YaHei UI", 9))
    _icon = _asset("icon.ico")
    if _icon:
        app.setWindowIcon(QIcon(_icon))
    apply_design_system(app)
    win = MainWindow()
    win.show()
    # 窗口先显示，自检在后台跑（有问题才弹提示）
    _selfcheck_async(win)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()