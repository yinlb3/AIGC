# -*- coding: utf-8 -*-
"""探针 v9：GUI 层真实行为（离屏，不显示窗口，不写项目文件）。"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"d:\Project\AIGC\app")

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
print("=" * 68)
print("【GUI】离屏实例化主窗口 + 真实按钮路径")
print("=" * 68)

from core.i18n import set_lang  # noqa: E402
from core.settings import Settings  # noqa: E402
from ui.main_window import BASE_DIR, MainWindow  # noqa: E402

print("BASE_DIR = %r" % BASE_DIR)
print()

# 用项目外临时目录当 base_dir，避免往项目里写 settings.json
import tempfile  # noqa: E402

tmp_base = tempfile.mkdtemp(prefix="aigc_gui_")
print("离屏主窗口用的 base_dir 先探明: 实际 MainWindow() 内部用 BASE_DIR")
print("为避免写项目 settings.json，先检查是否已存在:")
sp = os.path.join(BASE_DIR, "settings.json")
print("   %s 存在? %s" % (sp, os.path.exists(sp)))
print()

try:
    win = MainWindow()
    print("OK  MainWindow() 构造成功")
    print("    引擎下拉项数 = %d" % win.engine_combo.count())
    print("    下拉内容 = %r" % [win.engine_combo.itemText(i)
                               for i in range(win.engine_combo.count())])
    print("    预设项数 = %d" % win.preset_combo.count())
    print("    阈值滑杆 = %d" % win.thr_slider.value())
    print("    设备标签 = %r" % win.device_label.text()[:60])
    print("    许可标签 = %r" % win.lic_label.text())
    print()
    print("     集群 master 是否已启动 = %r" % win.master.running)
    print("     这让 DISCOVERY_PORT 在程序一启动就被 master 占用")
    print()

    print("--- 3.4 真实 BUG 复核: detect 分片计算 ---")
    from core.detector import _devices

    print("     当前设备 = %r" % _devices({"use_gpu": True, "max_workers": 0}))
    n = 3
    total = 5
    chunk = max(total // n, 1)
    print("     模拟 3 设备 / 5 段: chunk = max(5//3,1) = %d" % chunk)
    splits = []
    for d in range(n):
        start = d * chunk
        end = total if d == n - 1 else (d + 1) * chunk
        splits.append((d, start, end, list(range(start, end))))
    for d, s, e, idx in splits:
        print("        cuda:%d 段范围 [%d,%d) 索引 %r" % (d, s, e, idx))
    covered = [i for _, _, _, idx in splits for i in idx]
    print("     覆盖索引 = %r" % covered)
    print("     实际段落数 = %d" % total)
    missing = [i for i in range(total) if i not in covered]
    dup = len(covered) != len(set(covered))
    print("     漏掉的段落 = %r" % missing)
    print("     有重复? %s" % dup)
    print(">>> %s" % ("BUG 确认：末段被静默丢弃" if missing else "未复现"))

    print()
    print("--- 2.3 真实 BUG 复核: SettingsDialog._save 用离屏真跑 ---")
    from ui.settings_dialog import SettingsDialog

    s2 = Settings(tmp_base)
    print("     保存前 hf_endpoint = %r" % s2.get("download", "hf_endpoint"))
    dlg = SettingsDialog(s2, tmp_base)
    print("     对话框默认选中 国内镜像 = %r" % dlg.rb_mirror.isChecked())
    dlg._save()
    print("     保存后 mirror      = %r" % s2.get("download", "mirror"))
    print("     保存后 hf_endpoint = %r" % s2.get("download", "hf_endpoint"))
    val = s2.get("download", "hf_endpoint")
    print("     含协议头? %s" % ("是" if "://" in str(val) else "否 <-- BUG"))
    print("     写入的 settings.json 路径 = %s" % s2.path)
    print("     [写操作记录] 该文件在项目外临时目录 %s" % tmp_base)

    win.close()
    print()
    print("OK  win.close() 未报错")
except Exception as e:
    import traceback

    print("FAIL %s: %s" % (type(e).__name__, e))
    traceback.print_exc(limit=5)
