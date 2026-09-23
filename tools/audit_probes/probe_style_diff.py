# -*- coding: utf-8 -*-
"""核对我的改动是否混入了与原作者不一致的风格。"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"d:\Project\AIGC"
os.chdir(ROOT)

OUT = os.path.join(ROOT, "docs", "calibration", "style_diff.txt")
log = open(OUT, "w", encoding="utf-8")


def w(s=""):
    log.write(s + "\n")
    log.flush()


# 我改过的文件
changed = subprocess.check_output(
    ["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines()

w("=" * 74)
w("我改动过的文件的风格一致性核对")
w("=" * 74)
w()

for rel in changed:
    if not rel.endswith(".py"):
        continue
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    src = open(p, encoding="utf-8", errors="replace").read()
    lines = src.splitlines()
    has_nonascii = any(ord(c) > 127 for c in src)
    head = "\n".join(lines[:2])
    coding = "coding" in head or "-*-" in head

    # 我新增/改动的行（从 diff 里取）
    diff = subprocess.check_output(
        ["git", "diff", "-U0", "--", rel], cwd=ROOT, text=True,
        errors="replace")
    added = []
    for ln in diff.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            body = ln[1:]
            if body.strip():
                added.append(body)

    over79 = sum(1 for l in added if len(l) > 79)
    over100 = sum(1 for l in added if len(l) > 100)
    mx = max((len(l) for l in added), default=0)

    w("%-44s" % rel)
    w("   编码声明: %-4s (文件含中文: %s)" % ("有" if coding else "无", has_nonascii))
    w("   我新增行: %d 行" % len(added))
    w("   其中 >79: %d 行, >100: %d 行, 最长 %d" % (over79, over100, mx))

    # 原作者该文件原有行的行长概况
    orig = subprocess.check_output(
        ["git", "show", "HEAD:" + rel], cwd=ROOT, text=True, errors="replace")
    orig_lines = [l for l in orig.splitlines() if l.strip()]
    o79 = sum(1 for l in orig_lines if len(l) > 79)
    w("   原作者原版: %d 行, 其中 >79: %d 行 (%.0f%%)"
      % (len(orig_lines), o79, o79 * 100.0 / max(len(orig_lines), 1)))
    w()

log.close()
print("written:", OUT)
