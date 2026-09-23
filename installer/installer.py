"""AI 检测工具箱 安装器（不打包 AI 环境，运行时下载）。

架构：安装器只负责
  1) Python 便携运行时（官方 embeddable zip：解压即用，无注册表 / 无 UAC）
  2) 程序本体 + 卸载注册 + 桌面快捷方式
PyTorch / PySide6 等重依赖由首次启动引导器 first_run_gui.exe 按需下载。

安装逻辑全部落在模块级函数（perform_install / install_embed_runtime）里，
GUI 只是薄薄一层壳 —— 这样既可以用 `installer.py --cli D:\\目标` 无界面安装
（也方便自测），又避免"把逻辑写在 Tk 回调里没法验证"的老问题。
"""

import os
import queue
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile

try:  # 无 tkinter 的精简解释器下，CLI 模式（--cli）依然要能用
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # pragma: no cover
    tk = filedialog = messagebox = ttk = None

APP_NAME = "AI 检测工具箱"
APP_VER = "1.3.0"
PY_VER = "3.12.10"
PY_EMBED_NAME = "python-%s-embed-amd64.zip" % PY_VER
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AIGC_Toolkit"
# embeddable 便携包：解压即用，无安装器 / 无注册表 / 无 UAC —— 从根上规避官方 exe 安装器的
# MSI 孤儿注册问题（用户删目录后重装：静默安装被"已注册"骗过返回 0、卸载/修复全 1603）。
# 国内镜像优先（无需 VPN，均已实测可下），官方源排最后兜底
PY_EMBED_URLS = [
    "https://registry.npmmirror.com/-/binary/python/%s/%s" % (PY_VER, PY_EMBED_NAME),
    "https://mirrors.huaweicloud.com/python/%s/%s" % (PY_VER, PY_EMBED_NAME),
    "https://www.python.org/ftp/python/%s/%s" % (PY_VER, PY_EMBED_NAME),
]
GET_PIP_URLS = [
    "https://bootstrap.pypa.io/get-pip.py",
    "https://mirrors.aliyun.com/pypi/get-pip.py",
]
PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
MIN_DL_SIZE = 2 * 1024 * 1024   # Python 便携包 ~11MB
GETPIP_MIN_SIZE = 200 * 1024    # get-pip.py 各镜像 1.9~2.3MB，下限放宽
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
AUTHOR_EMAIL = "gxgx3456@qq.com"
PY_NAME = ("Python 便携包 (*.zip)", "*.zip")

# 卸载器由安装器生成到安装目录；自删用延迟 rd，避开运行中 python.exe 的文件锁
UNINSTALLER_TEMPLATE = '''# -*- coding: utf-8 -*-
"""AI 检测工具箱 卸载器（由安装器自动生成，勿手改）。

清理策略（**三个勾默认都不打**）
--------------------------------
默认只删"软件的壳"：注册表卸载项、桌面快捷方式、程序本体 ``app\\\\``、
以及 settings.json / 启动.cmd / 诊断.cmd。运行环境与模型**默认保留** ——
前者重装能复用（省几 GB 下载），后者是用户花时间下的东西。

三个勾对应三类**性质完全不同**的东西：
    下载缓存与日志 —— 软件自己产生的，删了零损失
    Python 运行环境 —— 软件装的，删了重装要重下，慢但不丢东西
    已下载的模型   —— 用户花时间下的资产，删了要重下（10GB 的可能几小时）

合并成一个勾是危险的：用户想"清个缓存"，会顺手把 10GB 模型删掉且不可恢复。

模型目录可能被设置指到别的盘（settings.json 的 download.models_dir），
所以只删**我们自己的那几个子目录**，绝不整删 models_dir —— 用户可能把
别的软件也指向同一个目录。
"""
import json
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox

TARGET = r"@TARGET@"
RUNTIME_DIR = r"@RUNTIME_DIR@"
EMAIL = "@EMAIL@"
APP_NAME = "AI 检测工具箱"
CREATE_NO_WINDOW = 0x08000000

# 有模型的引擎 id —— 即 models 下属于我们的子目录名，与
# app/core/engines/catalog.py 的 id 对应。卸载器没法 import catalog
# （此时 app\\ 可能已被删），故在此列一份，**新增引擎时记得同步**。
_ENGINE_DIRS = ("simpleai", "gltr", "zh_perplexity", "binoculars",
                "detectgpt", "fastdetectgpt")


def _human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


def _dir_size(path):
    total = 0
    for root_dir, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root_dir, f))
            except OSError:
                pass
    return total


def _models_dir():
    """模型目录：默认 <TARGET>\\\\models；设置里可指到别的盘。"""
    try:
        p = os.path.join(TARGET, "settings.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            md = ((d.get("download") or {}).get("models_dir") or "").strip()
            if md and os.path.isdir(md):
                return md
    except Exception:
        pass
    d = os.path.join(TARGET, "models")
    return d if os.path.isdir(d) else ""


def _rm(path):
    """删文件或目录，失败不抛（尽力而为）。"""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def main():
    root = tk.Tk()
    root.title("卸载 " + APP_NAME)
    root.geometry("580x390")
    root.resizable(False, False)

    run_dir = RUNTIME_DIR or os.path.join(TARGET, "runtime", "python")
    cache_dirs = [os.path.join(TARGET, "_downloads"),
                  os.path.join(TARGET, "_pipcache"),
                  os.path.join(TARGET, "logs")]
    models_dir = _models_dir()

    cache_size = sum(_dir_size(p) for p in cache_dirs if os.path.isdir(p))
    run_size = _dir_size(run_dir) if os.path.isdir(run_dir) else 0
    mdl_size = (sum(_dir_size(os.path.join(models_dir, n))
                    for n in _ENGINE_DIRS) if models_dir else 0)

    tk.Label(root, text="卸载 " + APP_NAME,
             font=("Microsoft YaHei UI", 14, "bold")).pack(
        anchor="w", padx=18, pady=(16, 4))
    tk.Label(root, justify="left", fg="#475569", wraplength=540,
             text="将删除：卸载注册项、桌面快捷方式、程序本体。\\\n"
                  "运行环境与模型默认保留（重装可复用，省几 GB 下载）。"
             ).pack(anchor="w", padx=18, pady=(0, 10))

    chk_cache = tk.BooleanVar(value=False)
    chk_run = tk.BooleanVar(value=False)
    chk_models = tk.BooleanVar(value=False)

    def add_chk(var, prefix, size, suffix, enabled=True):
        cb = tk.Checkbutton(root, variable=var, anchor="w", justify="left",
                            wraplength=540,
                            text=prefix + _human(size) + suffix)
        cb.pack(fill="x", padx=18, pady=2)
        if not enabled:
            cb.config(state="disabled")

    add_chk(chk_cache, "同时清理下载缓存与日志（可释放 ", cache_size, "）")
    add_chk(chk_run, "同时删除 Python 运行环境（", run_size,
            "，删后重装需重新下载）")
    add_chk(chk_models, "同时删除已下载的模型（", mdl_size, "，删后需重新下载）")

    if models_dir and os.path.abspath(models_dir) != os.path.join(
            os.path.abspath(TARGET), "models"):
        tk.Label(root, fg="#475569", justify="left", wraplength=540,
                 text="模型目录（设置里指定的位置）：%s" % models_dir
                 ).pack(anchor="w", padx=18, pady=(6, 0))

    tk.Label(root, fg="#475569", justify="left", wraplength=540,
             text="遇到 Bug？欢迎先邮件反馈，很多问题都能修：\\\n" + EMAIL
             ).pack(anchor="w", padx=18, pady=(10, 0))

    def do_uninstall():
        if not messagebox.askyesno(
            "确认卸载",
            "确定要卸载 %s 吗？\\n\\n卸载器不会修改你系统里已安装的 Python 环境。"
            % APP_NAME, parent=root,
        ):
            return

        # 1) 注册表卸载项
        try:
            import winreg

            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             r"Software\\Microsoft\\Windows\\CurrentVersion"
                             r"\\Uninstall\\AIGC_Toolkit")
        except OSError:
            pass
        # 2) 桌面快捷方式
        try:
            lnk = os.path.join(os.path.expanduser("~"), "Desktop",
                               APP_NAME + ".lnk")
            if os.path.exists(lnk):
                os.remove(lnk)
        except OSError:
            pass
        # 3) 程序本体与配置 —— 这两样**总是删**（它们是"软件的壳"）
        _rm(os.path.join(TARGET, "app"))
        _rm(os.path.join(TARGET, "settings.json"))
        _rm(os.path.join(TARGET, "启动.cmd"))
        _rm(os.path.join(TARGET, "诊断.cmd"))

        # 4) 三个勾选项
        if chk_cache.get():
            for p in cache_dirs:
                _rm(p)
        if chk_models.get() and models_dir:
            for n in _ENGINE_DIRS:
                _rm(os.path.join(models_dir, n))

        msg = "已卸载，感谢使用。"
        if chk_run.get():
            # 环境目录里有正在运行的 pythonw.exe，必须等本进程退出后再删，
            # 故交给 cmd 延迟执行。
            #
            # **只删用户选定的那个环境目录本身**，绝不删它的父目录 ——
            # 自选路径时父目录里可能是用户自己的东西。
            cmds = ['rd /s /q "%s"' % run_dir]
            default_parent = os.path.join(TARGET, "runtime")
            if os.path.normcase(os.path.dirname(run_dir)) == os.path.normcase(
                    default_parent):
                # 默认布局下这个父目录只装着我们这份环境，空了顺手删掉
                cmds.append('rd "%s"' % default_parent)
            cmds.append('rd "%s"' % TARGET)     # 空的安装目录（非空时自动失败）
            subprocess.Popen(
                'cmd /c ping 127.0.0.1 -n 4 > nul & ' + " & ".join(cmds),
                creationflags=CREATE_NO_WINDOW,
            )
            msg += "\\n\\n运行环境将在几秒后删除。"
        else:
            msg += ("\\n\\n运行环境与模型仍保留在：\\n%s\\n"
                    "（如需彻底删除，请再次运行卸载器并勾选对应项）" % TARGET)
        msg += "\\n\\n遇到 Bug 或建议随时邮件：\\n" + EMAIL
        messagebox.showinfo("完成 / Done", msg)
        root.destroy()

    btns = tk.Frame(root)
    btns.pack(fill="x", padx=18, pady=(14, 16), side="bottom")
    tk.Button(btns, text="卸载", width=10,
              command=do_uninstall).pack(side="right")
    tk.Button(btns, text="取消", width=10,
              command=root.destroy).pack(side="right", padx=6)

    root.mainloop()


main()
'''



class Cancelled(RuntimeError):
    """用户点了取消 —— 单独一个类型，避免被下载兜底逻辑当成"换个源再试"。"""


# 写进便携运行时的 Lib\site-packages\sitecustomize.py：解释器一启动就生效，
# 这样哪怕用户/别的工具手动用 runtime python 跑 pip，也不会被 socks 系统代理坑死。
# 逻辑与 app/core/netfix.py 保持一致（那边是源码侧的唯一真源）。
SITECUSTOMIZE = '''# -*- coding: utf-8 -*-
"""安装器自动写入，勿手改。让便携 Python 绕开"socks 系统代理"。

VPN / 加速器常把 Windows 系统代理写成 socks://127.0.0.1:66，而 Python 的
urllib / requests / pip 都不支持 socks（除非另装 PySocks），于是报
BadStatusLine 或 "Missing dependencies for SOCKS support"，下载全挂。
对应的源码侧实现：app/core/netfix.py
"""
import os

_VARS = ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
         "HTTPS_PROXY", "https_proxy")
_KEY = r"Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"


def _is_socks(value):
    if not value:
        return False
    scheme = value.split("=")[-1].split(":", 1)[0].strip().lower()
    return scheme in ("socks", "socks4", "socks5", "socks5h")


def _apply():
    bad = None
    for name in _VARS:
        if _is_socks(os.environ.get(name)):
            os.environ.pop(name, None)
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as key:
                if winreg.QueryValueEx(key, "ProxyEnable")[0]:
                    server = winreg.QueryValueEx(key, "ProxyServer")[0] or ""
                    if _is_socks(server):
                        bad = server
        except OSError:
            pass
    if bad:
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"


_apply()
'''


# --------------------------------------------------------------------------
# 路径 / i18n
# --------------------------------------------------------------------------
def app_source_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "app")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")


def _i18n_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "app", "core")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "core")


sys.path.insert(0, _i18n_dir())
from i18n import get_lang, set_lang, tr  # noqa: E402
from netfix import apply_env_fix, sanitize_env, unusable_system_proxy  # noqa: E402
from gpuinfo import detect as gpu_detect  # noqa: E402


# --------------------------------------------------------------------------
# 运行环境路径校验（「新建」模式）
# --------------------------------------------------------------------------
# Windows 文件名非法字符 —— **不含 \ 和 /**（它们在路径里是分隔符），
# 也**不含盘符那个冒号**：``D:\...`` 里的 ``:` 合法，故查之前先把盘符剥掉。
_BAD_PATH_CHARS = '<>:"|?*'
# Windows 保留设备名：这些名字做目录会创建失败或行为诡异
_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + ["COM%d" % i for i in range(1, 10)]
    + ["LPT%d" % i for i in range(1, 10)]
)
# 长度上限留余量给 site-packages 的深层嵌套（Windows 路径上限 260）
_MAX_PATH_LEN = 200


def _danger_reason(norm):
    """危险位置判据：命中返回原因文案，否则空串。

    拒绝的都是"一旦按覆盖逻辑清空、后果不可挽回"的位置：盘根、Windows 目录、
    用户主目录或桌面**本身**、Program Files / ProgramData。
    **不拒绝**它们的子目录（如 ``C:\\Users\\me\\AIGC`` 是允许的）。
    """
    low = norm.lower().rstrip("\\")
    if len(low) <= 3 and low.endswith(":"):
        return tr("inst_rt_danger_root")
    sysroot = os.environ.get("SystemRoot", r"C:\Windows").lower().rstrip("\\")
    home = os.path.expanduser("~").lower().rstrip("\\")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop").lower().rstrip("\\")
    for p, key in ((sysroot, "inst_rt_danger_system"),
                   (home, "inst_rt_danger_home"),
                   (desktop, "inst_rt_danger_desktop")):
        if low == p:
            return tr(key)
    drive = sysroot[:2]
    for frag in ("\\program files", "\\program files (x86)", "\\programdata"):
        if low.startswith(drive + frag):
            return tr("inst_rt_danger_programs")
    return ""


def check_runtime_path(path):
    """检查「新建运行环境」的目标路径是否可用。

    顺序即优先级：**先挑出必须改的（error），再看能不能带警告继续（warn）**，
    最后才是干净可用（ok）。一次只报第一个问题 —— 用户改完再点检测。

    :param path: 用户输入的原始路径
    :return: ``(level, msg)``；``level`` ∈ ``{"ok", "warn", "error"}``
    """
    raw = (path or "").strip()
    if not raw:
        return "error", tr("inst_rt_err_empty")

    # 盘符里的冒号是合法的（``D:\...``），先剥掉盘符再查非法字符 ——
    # 否则每个正常路径都会被判成"含非法字符 :"（实测踩过这个坑）
    body = raw[2:] if (len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha()) else raw
    bad = [c for c in _BAD_PATH_CHARS if c in body]
    if bad:
        return "error", tr("inst_rt_err_char") % bad[0]

    if len(raw) > _MAX_PATH_LEN:
        return "error", tr("inst_rt_err_long") % _MAX_PATH_LEN

    if raw.endswith(".") or raw.endswith(" "):
        return "error", tr("inst_rt_err_tail")

    # 保留名：逐个路径分量比对（去掉扩展名后的主体，如 "con.txt" 也是保留的）
    for part in raw.replace("/", "\\").split("\\"):
        if part.split(".")[0].upper() in _RESERVED_NAMES:
            return "error", tr("inst_rt_err_reserved") % part

    drive, _rest = os.path.splitdrive(raw)
    if drive:
        if not os.path.exists(drive + "\\"):
            return "error", tr("inst_rt_err_drive") % drive
    elif not raw.startswith("\\\\"):
        # 既没有盘符也不是 UNC（\\server\share）—— 相对路径不能用来装环境
        return "error", tr("inst_rt_err_absolute")

    norm = os.path.normpath(raw)
    danger = _danger_reason(norm)
    if danger:
        return "error", tr("inst_rt_err_danger") % danger

    if os.path.isdir(norm):
        try:
            n = len(os.listdir(norm))
        except OSError:
            n = 0
        if n:
            return "warn", tr("inst_rt_warn_not_empty") % n
    elif os.path.exists(norm):
        return "warn", tr("inst_rt_warn_is_file")

    if any(ord(c) > 127 for c in raw) or " " in raw:
        return "warn", tr("inst_rt_warn_nonascii")
    return "ok", tr("inst_rt_ok")


# --------------------------------------------------------------------------
# 下载（urllib -> 系统 curl 兜底 -> 多镜像 -> 手动选包）
# --------------------------------------------------------------------------
def _err_text(e):
    """异常转成纯 ASCII，避免个别网络库抛出的非 UTF-8 消息在界面上显示成乱码（如 'ÿ'）。"""
    return ("%s: %s" % (type(e).__name__, e)).encode("ascii", "replace").decode("ascii")


def _cleanup_partial(dest):
    for p in (dest + ".part", dest):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def _validate_dl(dest, minimum=MIN_DL_SIZE, magic=None):
    """体积 + 文件头校验，防止把错误页 / 半截包当成安装包。"""
    if not os.path.exists(dest) or os.path.getsize(dest) < minimum:
        raise RuntimeError(tr("inst_size_bad"))
    if magic:
        with open(dest, "rb") as f:
            head = f.read(len(magic))
        if head != magic:
            raise RuntimeError(tr("inst_size_bad"))


def _fetch_urllib(url, dest, log, status, cancelled, direct=False):
    log(tr("inst_download_log") % url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = dest + ".part"
    # 系统代理是 socks（VPN 常见）时直接用无代理 opener —— 否则 urllib 会把它当
    # HTTP 代理用，报 BadStatusLine；normalize 完仍失败则由调用方改用直连/curl
    if direct or unusable_system_proxy():
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    else:
        opener = urllib.request.build_opener()
    with opener.open(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = 5 + int(15 * done / total)
                    status(tr("inst_download_python_pct") % pct, pct)
                if cancelled():
                    raise Cancelled(tr("inst_cancelled"))
    os.replace(tmp, dest)


def _fetch_curl(url, dest, log, status, cancelled):
    """系统 curl 兜底（Win10 自带）：独立网络栈，能绕开 Python 网络层的问题。"""
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError(tr("inst_no_curl"))
    log(tr("inst_download_curl") % url)
    tmp = dest + ".part"
    status(tr("inst_download_curl_run"), 4)
    rc = subprocess.call(
        [curl, "-L", "--fail", "-sS", "--retry", "2",
         "--connect-timeout", "15", "--speed-time", "30",
         "--speed-limit", "1024", "-o", tmp, url],
        creationflags=CREATE_NO_WINDOW,
    )
    if rc != 0:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise RuntimeError(tr("inst_curl_rc") % rc)
    os.replace(tmp, dest)


def fetch_url(url, dest, log, status, cancelled, minimum=MIN_DL_SIZE, magic=None):
    """单个源：urllib -> 直连 urllib（绕开系统代理）-> 系统 curl，最后做体积校验。"""
    try:
        _fetch_urllib(url, dest, log, status, cancelled)
    except Cancelled:
        raise
    except Exception as e1:
        log(tr("inst_python_dl_fail") % _err_text(e1))
        _cleanup_partial(dest)
        if not unusable_system_proxy():
            try:
                log(tr("inst_proxy_bypass"))
                _fetch_urllib(url, dest, log, status, cancelled, direct=True)
                _validate_dl(dest, minimum, magic)
                return dest
            except Cancelled:
                raise
            except Exception as e2:
                log(tr("inst_python_dl_fail") % _err_text(e2))
                _cleanup_partial(dest)
        _fetch_curl(url, dest, log, status, cancelled)
    _validate_dl(dest, minimum, magic)


def download_with_mirrors(urls, dest, log, status, cancelled,
                          ask_manual=None, minimum=MIN_DL_SIZE, magic=None):
    """多镜像依次尝试；全挂则（可选的）让用户指一个本地已下好的包。"""
    err = None
    for u in urls:
        try:
            fetch_url(u, dest, log, status, cancelled, minimum, magic)
            return dest
        except Cancelled:
            raise
        except Exception as e:
            err = e
            log(tr("inst_python_dl_fail") % _err_text(e))
            _cleanup_partial(dest)
    if err is not None:
        log(tr("inst_all_dl_fail") % _err_text(err))
    if ask_manual:
        manual = ask_manual()
        if manual:
            log(tr("inst_manual_using") % manual)
            shutil.copyfile(manual, dest)
            _validate_dl(dest, minimum, magic)
            return dest
    raise RuntimeError(tr("inst_python_dl_err") % _err_text(err))


def run_stream(args, log, cwd=None, env=None):
    """跑一个子进程，逐行把输出喂给 log，返回退出码。"""
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=sanitize_env(env) if env is None else env,
        creationflags=CREATE_NO_WINDOW,
    )
    for line in proc.stdout:
        line = line.strip()
        if line:
            log(line)
    return proc.wait()


# --------------------------------------------------------------------------
# Python 便携运行时（embeddable）
# --------------------------------------------------------------------------
def python_ok(exe):
    """验证 Python 能完整初始化（标准库 encodings 可用）。"""
    if not os.path.exists(exe):
        return False
    try:
        out = subprocess.run(
            [exe, "-c", "import encodings, sys; print(sys.prefix)"],
            capture_output=True, text=True, timeout=60,
            creationflags=CREATE_NO_WINDOW,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False


def pip_ok(pyexe):
    if not os.path.exists(pyexe):
        return False
    try:
        out = subprocess.run(
            [pyexe, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=90,
            creationflags=CREATE_NO_WINDOW,
        )
        return out.returncode == 0 and "pip" in (out.stdout or "").lower()
    except Exception:
        return False


def patch_embed_pth(pydir, log=print):
    """修补 embeddable 的 `python3xx._pth`。

    这个文件把 sys.path 完全写死（并且默认注释掉 `import site`），不改它的话
    pip 装进 Lib\\site-packages 的包 import 不到 —— 这是 embeddable 最经典的坑：
      1) 放开 `import site`，让 site.py 把 Lib\\site-packages 挂进 sys.path
      2) 补一行 `.`，保证安装目录本身可见
    """
    pth = None
    for name in sorted(os.listdir(pydir)):
        if name.endswith("._pth"):
            pth = os.path.join(pydir, name)
            break
    if not pth:
        raise RuntimeError(tr("inst_pth_missing"))
    with open(pth, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    out = []
    for ln in lines:
        # `#import site` / `import site` 统一成生效的那一行
        out.append("import site" if ln.strip().lstrip("#").strip() == "import site" else ln)
    if not any(l.strip() == "import site" for l in out):
        out.append("import site")
    if not any(l.strip() == "." for l in out):
        out.append(".")
    with open(pth, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    log(tr("inst_pth_patched") % os.path.basename(pth))
    return pth


def write_sitecustomize(pydir, log=None):
    """给便携运行时装一份网络自愈脚本（解释器启动即生效）。"""
    sp = os.path.join(pydir, "Lib", "site-packages")
    os.makedirs(sp, exist_ok=True)
    path = os.path.join(sp, "sitecustomize.py")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(SITECUSTOMIZE)
    if log:
        log(tr("inst_netfix_installed"))
    return path


def install_embed_runtime(pydir, dl, log=print, status=None, cancelled=None, ask_manual=None):
    """保证 pydir 下有一份带 pip 的可用 Python（便携版），返回 python.exe 路径。"""
    log = log or (lambda m: None)
    status = status or (lambda m, p=None: None)
    cancelled = cancelled or (lambda: False)
    pyexe = os.path.join(pydir, "python.exe")

    if python_ok(pyexe) and pip_ok(pyexe):
        log(tr("inst_runtime_reuse"))
        status(tr("inst_python_installed"), 25)
        write_sitecustomize(pydir, log)
        return pyexe

    # 坏的旧运行时一律清掉，避免半成品干扰（含旧版本遗留的 venv）
    if os.path.exists(pydir):
        log(tr("inst_runtime_purge"))
        shutil.rmtree(pydir, ignore_errors=True)
    shutil.rmtree(os.path.join(os.path.dirname(pydir), "venv"), ignore_errors=True)

    # 1. 便携包 zip
    zpath = os.path.join(dl, PY_EMBED_NAME)
    if os.path.exists(zpath) and os.path.getsize(zpath) >= MIN_DL_SIZE:
        status(tr("inst_python_downloaded"), 15)
    else:
        status(tr("inst_download_python"), 3)
        download_with_mirrors(PY_EMBED_URLS, zpath, log, status, cancelled,
                              ask_manual, MIN_DL_SIZE, b"PK")

    # 2. 解压 + 修补 ._pth
    status(tr("inst_extract_python"), 20)
    log(tr("inst_unzip_log") % (PY_EMBED_NAME, pydir))
    os.makedirs(pydir, exist_ok=True)
    try:
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(pydir)
    except zipfile.BadZipFile:
        _cleanup_partial(zpath)
        raise RuntimeError(tr("inst_unzip_bad"))
    patch_embed_pth(pydir, log)
    write_sitecustomize(pydir, log)

    if not python_ok(pyexe):
        raise RuntimeError(tr("inst_python_inst_err") % 0)

    # 3. 引导 pip（embeddable 不自带 ensurepip）
    status(tr("inst_install_pip"), 30)
    getpip = os.path.join(dl, "get-pip.py")
    if not (os.path.exists(getpip) and os.path.getsize(getpip) >= GETPIP_MIN_SIZE):
        download_with_mirrors(GET_PIP_URLS, getpip, log, status, cancelled,
                              None, GETPIP_MIN_SIZE)
    rc = run_stream([pyexe, getpip, "--no-warn-script-location", "-i", PYPI_MIRROR], log)
    log("get-pip 退出码: %d" % rc)
    if rc != 0 or not pip_ok(pyexe):
        raise RuntimeError(tr("inst_pip_err") % rc)
    log(tr("inst_pip_ready"))
    return pyexe


# --------------------------------------------------------------------------
# 程序本体 / 快捷方式 / 卸载注册
# --------------------------------------------------------------------------
def launcher_cmd(appdir, pydir):
    """返回 (可执行文件, 参数或 None)。

    引导器是独立 exe（自带 tkinter，因为 embeddable 没有 tkinter），直接运行即可 ——
    注意不能用 `pythonw.exe first_run_gui.exe`（那是把 exe 当脚本喂给解释器，必错）。
    """
    fr_exe = os.path.join(appdir, "first_run_gui.exe")
    if os.path.exists(fr_exe):
        return fr_exe, None
    return os.path.join(pydir, "pythonw.exe"), os.path.join(appdir, "first_run.py")


def _write_launchers(target, appdir, pydir, log):
    """写两个便捷脚本：启动.cmd（日常启动）、诊断.cmd（出问题时收集信息）。"""
    try:
        exe, args = launcher_cmd(appdir, pydir)
        cmdline = '"%s"' % exe if not args else '"%s" "%s"' % (exe, args)
        with open(os.path.join(target, "启动.cmd"), "w", encoding="ascii") as f:
            f.write('@echo off\r\nstart "" %s\r\n' % cmdline)
        py_exe = os.path.join(pydir, "python.exe")
        with open(os.path.join(target, "诊断.cmd"), "w", encoding="utf-8") as f:
            f.write(
                '@echo off\r\nchcp 65001 >nul\r\ncd /d "%s"\r\n'
                '"%s" diag_startup.py\r\necho.\r\n'
                "echo ============================\r\n"
                "echo 诊断完成，按任意键关闭窗口...\r\npause >nul\r\n"
                % (appdir, py_exe)
            )
    except Exception as e:
        log("启动脚本写入失败(不影响使用): %s" % e)


def app_icon(appdir):
    """程序图标路径（安装目录 app/assets/icon.ico）；没有就返回空串。"""
    p = os.path.join(appdir, "assets", "icon.ico")
    return p if os.path.exists(p) else ""


def make_shortcut(target, args, workdir, log=print, icon=""):
    """在桌面创建快捷方式（args 为 None 时不带参数）。

    注意：`CreateShortcut` 会**加载已存在的 .lnk**，脚本里没赋值的字段会保留旧值 ——
    比如从 pythonw+脚本 的旧快捷方式升级上来时，旧的 Arguments 会残留。
    所以 Arguments 必须无条件写入（空字符串也要写）。
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    lnk = os.path.join(desktop, "%s.lnk" % APP_NAME)
    ps = (
        "$ws = New-Object -ComObject WScript.Shell;"
        "$s = $ws.CreateShortcut('%s');"
        "$s.TargetPath = '%s';"
        "$s.Arguments = '%s';"
        "$s.WorkingDirectory = '%s';"
        "$s.IconLocation = '%s';"
        "$s.Save()" % (
            lnk, target,
            args if args else "",
            workdir,
            icon if icon else target,
        )
    )
    subprocess.call(
        ["powershell", "-NoProfile", "-Command", ps],
        creationflags=CREATE_NO_WINDOW,
    )
    log(tr("inst_shortcut_done") % lnk)


def register_uninstall(target, pythonw_runtime, runtime_dir, log=print):
    """写入卸载器并注册到 Windows「设置 > 应用 / 控制面板卸载程序」。

    ``runtime_dir`` 必须是**用户实际选定的那个环境目录**（不是从 pythonw.exe
    反推出来的父目录）—— 反推是错的：用户若选 ``D:\\myenv``（只一层），反推会
    得到 ``D:\\``，卸载时 ``rd /s /q`` 就把磁盘根删了。
    """
    unw = os.path.join(target, "uninstall.pyw")
    try:
        with open(unw, "w", encoding="utf-8") as f:
            f.write(
                UNINSTALLER_TEMPLATE
                .replace("@TARGET@", target)
                .replace("@RUNTIME_DIR@", runtime_dir)
                .replace("@EMAIL@", AUTHOR_EMAIL)
            )
    except OSError as e:
        log("写入卸载器失败: %s" % e)
        return
    try:
        import winreg

        # 卸载项图标也用程序自己的图标（原来是 pythonw.exe 的 Python 图标，很难看）
        _ico = os.path.join(target, "app", "assets", "icon.ico")
        display_icon = _ico if os.path.exists(_ico) else pythonw_runtime

        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        vals = [
            ("DisplayName", APP_NAME),
            ("DisplayVersion", APP_VER),
            ("Publisher", "gxgx3456"),
            ("DisplayIcon", display_icon),
            ("InstallLocation", target),
            ("UninstallString", '"%s" "%s"' % (pythonw_runtime, unw)),
            ("HelpLink", "mailto:%s" % AUTHOR_EMAIL),
            ("Contact", AUTHOR_EMAIL),
            ("Comments", "遇到 Bug 请邮件反馈 / Report bugs: %s" % AUTHOR_EMAIL),
            ("NoModify", 1),
            ("NoRepair", 1),
        ]
        for name, value in vals:
            if isinstance(value, int):
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
            else:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        log(tr("inst_uninstall_registered"))
    except OSError as e:
        log(tr("inst_uninstall_reg_fail") % e)


def perform_install(target, log=None, status=None, cancelled=None, ask_manual=None,
                    opt_shortcut=True, opt_launch=True, lang=None, runtime_dir=None):
    """完整安装流程（GUI / CLI 共用）：Python 便携运行时 -> 程序本体 -> 注册卸载 -> 快捷方式。

    ``runtime_dir`` 是运行环境的落地目录（用户安装时可自选，默认
    ``<target>\\runtime\\python``）—— 环境约 4.8GB，允许放到别的盘。
    """
    log = log or (lambda m: None)
    status = status or (lambda m, p=None: None)
    cancelled = cancelled or (lambda: False)

    dl = os.path.join(target, "_downloads")
    pydir = runtime_dir or os.path.join(target, "runtime", "python")
    appdir = os.path.join(target, "app")
    os.makedirs(dl, exist_ok=True)

    apply_env_fix(log)  # 系统代理是 socks（VPN）时改为直连，否则 urllib / pip 全挂

    # 1. Python 便携运行时
    pyexe = install_embed_runtime(pydir, dl, log, status, cancelled, ask_manual)
    log("运行时 Python 就绪: %s" % pyexe)

    # 2. 复制程序本体（PyTorch / PySide6 等组件由首次启动引导器下载）
    status(tr("inst_copy_app"), 80)
    src = app_source_dir()
    # logs / __pycache__ 不复制：一是避免把旧日志带过去，二是软件运行时 app.log
    # 会被占用（Windows 下删不掉），复制它会让"正在用的软件上重装"直接失败
    ignore = shutil.ignore_patterns("logs", "__pycache__", "*.pyc")
    if os.path.exists(appdir):
        try:
            shutil.rmtree(appdir)
        except OSError as e:
            log(tr("inst_appdir_busy") % _err_text(e))
    try:
        shutil.copytree(src, appdir, dirs_exist_ok=True, ignore=ignore)
    except OSError as e:
        raise RuntimeError(tr("inst_appdir_locked") % _err_text(e))

    # 3. 配置 + 便捷脚本
    with open(os.path.join(target, "settings.json"), "w", encoding="utf-8") as f:
        f.write(
            '{"app": {"install_dir": "%s"}, "ui": {"language": "%s"}}'
            % (target.replace("\\", "\\\\"), lang or get_lang())
        )
    _write_launchers(target, appdir, pydir, log)

    # 4. 卸载入口
    status(tr("inst_register_uninstall"), 90)
    register_uninstall(target, os.path.join(pydir, "pythonw.exe"), pydir, log)

    # 5. 快捷方式 + 启动
    status(tr("inst_create_shortcut"), 94)
    launch_target, launch_args = launcher_cmd(appdir, pydir)
    if opt_shortcut:
        make_shortcut(
            launch_target, launch_args, appdir, log,
            icon=app_icon(appdir) or launch_target,
        )
    else:
        log(tr("inst_skip_shortcut"))

    if opt_launch:
        try:
            subprocess.Popen(
                [launch_target] + ([launch_args] if launch_args else []),
                cwd=appdir, creationflags=CREATE_NO_WINDOW,
            )
            log(tr("inst_launching"))
        except Exception as e:
            log(tr("inst_launch_fail") % e)

    status(tr("inst_done"), 100)
    log(tr("inst_done_log") % APP_NAME)
    return target


# --------------------------------------------------------------------------
# 运行环境选择对话框（「新建」模式）
# --------------------------------------------------------------------------
class RuntimeDialog(tk.Toplevel if tk else object):
    """让用户选「新建运行环境」的目标路径。

    为什么单独弹一个框
    ------------------
    环境路径和"安装目录"是两件事：默认在安装目录下，但用户可以放到别的盘
    （环境 4.8GB + 模型若干，系统盘吃紧时很需要）。单独一个框才有地方放
    「检测」按钮和逐条校验结果。

    交互约定
    --------
    * 打开即先检测一次（不用用户先点一下才知道行不行）
    * 点「检测」重跑校验，结果显示在提示行并按等级着色
    * 点「确定」时若等级是 ``error`` 则**不关闭**（弹提示说明为什么按不动）；
      若是 ``warn``（文件夹非空等）再弹一次确认 —— 不可恢复的操作必须二次确认
    """

    def __init__(self, parent, default_path):
        super().__init__(parent)
        self.title(tr("inst_rt_title"))
        self.resizable(False, False)
        self.result = None          # 点「确定」后写入最终路径
        self.level = "ok"

        tk.Label(self, text=tr("inst_rt_title"),
                 font=("Microsoft YaHei UI", 13, "bold")).pack(
            anchor="w", padx=18, pady=(16, 2))
        tk.Label(self, text=tr("inst_rt_note"), justify="left", fg="#475569",
                 wraplength=540, anchor="w").pack(fill="x", padx=18, pady=(0, 6))

        # 显卡探测：提前告诉用户会装 GPU 版还是 CPU 版，以及"为什么只能用 CPU"
        # （没 N 卡 / 驱动太旧）。这直接决定首次启动下载 2.6GB 还是 200MB，
        # 也解释得清后面检测为什么慢 —— 别让用户装完才发现走了 CPU。
        try:
            gpu_text = gpu_detect()["reason"]
        except Exception as e:  # noqa: BLE001
            gpu_text = "显卡探测失败：%s" % e
        tk.Label(self, text=gpu_text, justify="left", fg="#475569",
                 wraplength=540, anchor="w").pack(
            fill="x", padx=18, pady=(0, 6))

        row = tk.Frame(self)
        row.pack(fill="x", padx=18, pady=6)
        tk.Label(row, text=tr("inst_rt_path_label")).pack(side="left")
        self.path_var = tk.StringVar(value=default_path)
        self.entry = tk.Entry(row, textvariable=self.path_var, width=50)
        self.entry.pack(side="left", fill="x", expand=True, padx=6)
        self.btn_browse = tk.Button(row, command=self.browse, width=8)
        self.btn_browse.pack(side="left")

        self.msg_var = tk.StringVar(value="")
        self.msg_label = tk.Label(self, textvariable=self.msg_var, justify="left",
                                  fg="#475569", wraplength=560, anchor="w")
        self.msg_label.pack(fill="x", padx=18, pady=(4, 10))

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=18, pady=(0, 16))
        self.btn_ok = tk.Button(btns, command=self.on_ok, width=10)
        self.btn_ok.pack(side="right")
        # 左「检测」右「确定」（按约定的布局）
        self.btn_check = tk.Button(btns, command=self.on_check, width=10)
        self.btn_check.pack(side="right", padx=6)

        self.btn_browse.config(text=tr("inst_rt_browse"))
        self.btn_check.config(text=tr("inst_rt_detect"))
        self.btn_ok.config(text=tr("inst_rt_ok_btn"))

        self.update_idletasks()
        self._center(parent)
        self.transient(parent)
        self.grab_set()
        self.entry.focus_set()
        self.after(120, self.on_check)   # 打开就检测一次

    def _center(self, parent):
        try:
            x = parent.winfo_rootx() + max(
                0, (parent.winfo_width() - self.winfo_width()) // 2)
            y = parent.winfo_rooty() + max(
                0, (parent.winfo_height() - self.winfo_height()) // 3)
            self.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.path_var.get() or "D:\\")
        if d:
            self.path_var.set(os.path.normpath(d))
            self.on_check()

    def on_check(self):
        """跑一遍校验并把结果写到提示行；返回等级（供「确定」判断）。"""
        self.level, msg = check_runtime_path(self.path_var.get())
        self.msg_var.set(msg)
        self.msg_label.config(fg={"ok": "#15803d", "warn": "#b45309",
                                  "error": "#b91c1c"}.get(self.level, "#475569"))
        return self.level

    def on_ok(self):
        level = self.on_check()
        path = os.path.normpath(self.path_var.get().strip())
        if level == "error":
            # 不许带着错误继续；说明原因，别让用户以为按钮坏了
            messagebox.showwarning(tr("inst_rt_title"), tr("inst_rt_cannot_ok"),
                                   parent=self)
            return
        if level == "warn":
            # 非空目录/同名文件都会走"清空后新建"，不可恢复 -> 二次确认
            if not messagebox.askyesno(tr("inst_rt_confirm_title"),
                                       tr("inst_rt_confirm_clear") % path,
                                       parent=self):
                return
        self.result = path
        self.destroy()


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class Installer(tk.Tk if tk else object):
    def __init__(self):
        super().__init__()
        self.title(tr("inst_title"))
        self.geometry("620x520")
        self.resizable(False, False)
        self.cancel_flag = False
        self.ui_q = queue.Queue()
        self.after(50, self._drain_ui)

        pad = {"padx": 18, "pady": 6}
        # 右上角全屏切换（系统按钮风格，安装/下载日志较长时方便查看）
        top_row = tk.Frame(self)
        top_row.pack(fill="x")
        self.btn_full = tk.Button(
            top_row, command=self.toggle_fullscreen,
            relief="flat", bd=0, fg="#475569",
            activeforeground="#1d4ed8", cursor="hand2",
            font=("Microsoft YaHei UI", 9),
        )
        self.btn_full.pack(side="right", padx=14, pady=(8, 0))
        self.btn_full.config(text=tr("inst_fullscreen"))
        self.bind("<Escape>", self._exit_fullscreen)
        self.title_label = tk.Label(self, font=("Microsoft YaHei UI", 16, "bold"))
        self.title_label.pack(anchor="w", **pad)
        self.desc_label = tk.Label(self, justify="left", fg="#475569")
        self.desc_label.pack(anchor="w", **pad)

        row = tk.Frame(self)
        row.pack(fill="x", **pad)
        self.dir_label = tk.Label(row)
        self.dir_label.pack(side="left")
        self.dir_var = tk.StringVar(value=r"D:\AIGC_Detector")
        self.dir_entry = tk.Entry(row, textvariable=self.dir_var)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.btn_browse = tk.Button(row, command=self.browse)
        self.btn_browse.pack(side="left")

        # 安装选项（均默认勾选）
        opt_row = tk.Frame(self)
        opt_row.pack(fill="x", **pad)
        self.chk_shortcut = tk.BooleanVar(value=True)
        self.chk_launch = tk.BooleanVar(value=True)
        self.cb_shortcut = tk.Checkbutton(opt_row, variable=self.chk_shortcut)
        self.cb_shortcut.pack(side="left")
        self.cb_launch = tk.Checkbutton(opt_row, variable=self.chk_launch)
        self.cb_launch.pack(side="left", padx=(14, 0))

        self.progress = ttk.Progressbar(self, maximum=100, length=560)
        self.progress.pack(fill="x", **pad)
        self.status = tk.StringVar()
        tk.Label(self, textvariable=self.status, fg="#1d4ed8").pack(anchor="w", **pad)

        self.log = tk.Text(self, height=10, state="disabled")
        self.log.pack(fill="both", expand=True, **pad)

        btns = tk.Frame(self)
        btns.pack(fill="x", **pad)
        self.btn_start = tk.Button(btns, command=self.start, width=14)
        self.btn_start.pack(side="right")
        self.btn_cancel = tk.Button(btns, command=self.cancel, width=10, state="disabled")
        self.btn_cancel.pack(side="right", padx=6)
        self.btn_lang = tk.Button(btns, command=self.toggle_lang, width=6)
        self.btn_lang.pack(side="left")
        self.author_label = tk.Label(self, fg="#94a3b8", anchor="w")
        self.author_label.pack(
            fill="x", padx=18, pady=(0, 10)
        )
        self._apply_lang()

    def _apply_lang(self):
        self.title(tr("inst_title"))
        self.title_label.config(text=tr("inst_heading") % (APP_NAME, APP_VER))
        self.desc_label.config(text=tr("inst_desc"))
        self.dir_label.config(text=tr("inst_dir_label"))
        self.cb_shortcut.config(text=tr("inst_opt_shortcut"))
        self.cb_launch.config(text=tr("inst_opt_launch"))
        self.btn_browse.config(text=tr("inst_browse"))
        self.btn_start.config(text=tr("inst_start"))
        self.btn_cancel.config(text=tr("inst_cancel"))
        self.btn_lang.config(text="EN" if get_lang() == "zh" else "中文")
        self.author_label.config(text=tr("inst_author_email") % AUTHOR_EMAIL)
        if not self.status.get():
            self.status.set(tr("inst_ready"))

    def toggle_lang(self):
        set_lang("en" if get_lang() == "zh" else "zh")
        self._apply_lang()

    def toggle_fullscreen(self):
        fs = not self.attributes("-fullscreen")
        self.attributes("-fullscreen", fs)
        self.btn_full.config(text=tr("inst_fullscreen_exit") if fs else tr("inst_fullscreen"))

    def _exit_fullscreen(self, event=None):
        if self.attributes("-fullscreen"):
            self.attributes("-fullscreen", False)
            self.btn_full.config(text=tr("inst_fullscreen"))

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or "D:\\")
        if d:
            self.dir_var.set(d)

    def _drain_ui(self):
        try:
            while True:
                fn, args = self.ui_q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(50, self._drain_ui)

    def _ui(self, fn, *args):
        self.ui_q.put((fn, args))

    def log_msg(self, msg):
        self._ui(self._log_impl, msg)

    def _log_impl(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def set_status(self, msg, pct=None):
        self._ui(self._status_impl, msg, pct)

    def _status_impl(self, msg, pct):
        self.status.set(msg)
        if pct is not None:
            self.progress["value"] = pct

    def cancel(self):
        self.cancel_flag = True
        self.set_status(tr("inst_cancelling"))

    def ask_manual_file(self):
        """所有源下载失败时，让用户选择本地已下载的 Python 便携包。"""
        box = {"path": None}
        ev = threading.Event()

        def ask():
            p, _ = filedialog.askopenfilename(
                title=tr("inst_manual_pick_title"),
                filetypes=[PY_NAME, ("所有文件", "*.*")],
            )
            box["path"] = p or None
            ev.set()

        self._ui(ask)
        while not ev.wait(0.2):
            if self.cancel_flag:
                return None
        return box["path"]

    def default_runtime_dir(self):
        """环境路径默认值：``<安装目录>\\runtime\\python``。

        **实时读安装目录**（用户改了目录再点开始，默认值得跟着变），
        不缓存上次的选择 —— 缓存会让两者不一致。
        """
        target = self.dir_var.get().strip() or r"D:\AIGC_Detector"
        return os.path.join(target, "runtime", "python")

    def start(self):
        # 先在主线程弹「运行环境」对话框（tkinter 不能在子线程弹窗）；
        # 用户直接关掉对话框 = 取消安装，不往下走
        dlg = RuntimeDialog(self, self.default_runtime_dir())
        self.wait_window(dlg)
        if not dlg.result:
            return
        self.runtime_dir = dlg.result

        self.cancel_flag = False
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        threading.Thread(target=self.run_install, daemon=True).start()

    def run_install(self):
        try:
            target = self.dir_var.get().strip() or r"D:\AIGC_Detector"
            perform_install(
                target,
                log=self.log_msg,
                status=self.set_status,
                cancelled=lambda: self.cancel_flag,
                ask_manual=self.ask_manual_file,
                opt_shortcut=self.chk_shortcut.get(),
                opt_launch=self.chk_launch.get(),
                lang=get_lang(),
                runtime_dir=getattr(self, "runtime_dir", None),
            )
            self._ui(
                lambda: messagebox.showinfo(
                    tr("inst_done_title"),
                    tr("inst_done_box") % APP_NAME,
                )
            )
        except Exception as e:
            self.set_status(tr("inst_failed_prefix") % e)
            self.log_msg(tr("inst_fail_log") % e)
            self._ui(lambda: messagebox.showerror(tr("inst_fail_title"), str(e)))
        finally:
            self.btn_start.config(state="normal")
            self.btn_cancel.config(state="disabled")


def _cli(argv):
    """无界面安装：python installer.py --cli [目标目录]。自测 / 静默部署用。"""
    target = None
    for i, a in enumerate(argv):
        if a in ("--cli", "--install-cli") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            target = argv[i + 1]
    target = target or r"D:\AIGC_Detector"
    print("[CLI] 安装目标: %s" % target)
    try:
        perform_install(
            target,
            log=lambda m: print("  " + str(m), flush=True),
            status=lambda m, p=None: print("[状态] %s%s" % (m, "" if p is None else " (%d%%)" % p), flush=True),
            opt_shortcut="--no-shortcut" not in argv,
            opt_launch=False,
        )
    except Exception as e:
        print("[CLI] 安装失败: %s" % e)
        return 1
    print("[CLI] 安装完成: %s" % target)
    return 0


if __name__ == "__main__":
    if "--cli" in sys.argv or "--install-cli" in sys.argv:
        sys.exit(_cli(sys.argv[1:]))
    if tk is None:
        print("当前解释器缺少 tkinter，无法显示安装界面。请直接双击安装器 exe，"
              "或使用命令行：installer.exe --cli <目标目录>")
        sys.exit(2)
    Installer().mainloop()
