# -*- coding: utf-8 -*-
"""探针 v3：2.8 license / 2.9 i18n 拼接键 / 2.10 report.py 未转义。"""
import io
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"d:\Project\AIGC\app")

RESULT = []


def head(n, t):
    print("\n" + "=" * 68)
    print("【%s】%s" % (n, t))
    print("=" * 68)


def verdict(n, ok, detail):
    RESULT.append((n, ok, detail))
    print(">>> 结论: %s | %s" % ("BUG 确认" if ok else "未复现", detail))


# ---------------------------------------------------------------- 2.8
head("2.8", "license 校验空壳 —— license.py:29-32")
print('    def _validate(self, key):')
print('        return bool(key) and key.startswith("AIGC-PRO-") and len(key) >= 20')
print()
from core.license import License  # noqa: E402


class L(License):
    def __init__(self):
        pass


lic = L()
tests = ["AIGC-PRO-0000000000000000", "AIGC-PRO-" + "x" * 11,
         "AIGC-PRO-AAAAAAAAAAAA", "", "AIGC-PRO-12345678901", "abc"]
for k in tests:
    print("   _validate(%-30r) = %s" % (k, lic._validate(k)))

print()
tmp = tempfile.mkdtemp(prefix="aigc_lic_")
try:
    real = License(tmp)
    print("   初始 current_tier() = %r" % real.current_tier())
    ok2, msg = real.activate("AIGC-PRO-0000000000000000")
    print("   activate('AIGC-PRO-0000000000000000') -> %s / %s" % (ok2, msg))
    print("   之后 current_tier() = %r" % real.current_tier())
    kp = os.path.join(tmp, "license.key")
    print("   license.key 内容 = %r" % open(kp, encoding="utf-8").read())
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print()
print("注: 该文件写入临时目录，已清理")
verdict("2.8", lic._validate("AIGC-PRO-0000000000000000"),
        "任意 AIGC-PRO- 开头且长度>=20 的字符串即通过")


# ---------------------------------------------------------------- 2.9
head("2.9", "i18n 拼接键缺失 —— engine_dialog.py:145 / rewrite_dialog.py:405")
import core.i18n as i18n  # noqa: E402

d = None
for nm in ("DICTS", "_DICTS", "TEXTS", "_TEXTS", "STRINGS"):
    if hasattr(i18n, nm):
        d = getattr(i18n, nm)
        print("词典对象: i18n.%s" % nm)
        break
if d is None:
    print("未找到词典变量名，列出模块级 dict:")
    for k, v in vars(i18n).items():
        if isinstance(v, dict) and len(v) > 50:
            print("   %s (len=%d)" % (k, len(v)))
    d = {"zh": {}, "en": {}}
zh, en = d.get("zh", {}), d.get("en", {})
print("   zh 键数 = %d, en 键数 = %d" % (len(zh), len(en)))
print()
print("枚举代码里字符串拼接出来的 tr() 键:")
combos = [("engine_dialog.py:145", "engine_status_" + s)
          for s in ("builtin", "ready", "missing")]
combos += [("rewrite_dialog.py:405", "rewrite_sev_" + s)
           for s in ("high", "medium", "low")]
missing = []
for src, key in combos:
    got = i18n.tr(key)
    found = got is not None and got != key
    if not found:
        missing.append((src, key))
    print("   %-9s %-26s tr() -> %r   (%s)"
          % ("OK" if found else "MISSING", key, got, src))
print()
print("缺失 %d 个" % len(missing))
for src, key in missing:
    print("   %s 需要 %s" % (src, key))
verdict("2.9", bool(missing), "缺失拼接键: %s" % ([k for _, k in missing] or "无"))


# ---------------------------------------------------------------- 2.10
head("2.10", "report.py 未转义文件名 —— report.py:20")
print('    html = ["<h2>%s</h2>" % file_name, ...]')
print("   file_name 来自 os.path.basename(self.path)，未 escape()")
print("   而 snippet 那行做了 escape()")
print()
from core.report import build_report  # noqa: E402

bad_name = 'a&b<c>d"e".txt'
html = build_report(["这是一段测试文本"], [0.9], 0.9, bad_name, "test", 0.5)
first = html[:120]
print("   build_report(file_name=%r) 前 120 字符:" % bad_name)
print("   %r" % first)
leaked = "<c>" in first or "&b" in first
print()
print("   是否原样泄漏未转义字符: %s" % leaked)
from core.report import escape  # noqa: E402

print("   正确应为: <h2>%s</h2>" % escape(bad_name))
print()
print("   注: Qt 的 setHtml 对未闭合标签会静默吞内容，Win 文件名允许 & 号")
verdict("2.10", leaked, "文件名 %r 未转义直接拼进 HTML" % bad_name)


print("\n" + "#" * 68)
for n, o, d in RESULT:
    print("  [%s] %-5s %s" % ("BUG" if o else "OK ", n, d))
print("确认 bug: %d / %d" % (sum(1 for _, o, _ in RESULT if o), len(RESULT)))
