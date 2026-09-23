# -*- coding: utf-8 -*-
"""探针 v4：静态扫描（3.1 未用导入 / 3.2 行长 / 3.3 静默 except / 3.4 引擎参数签名）。"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"d:\Project\AIGC"
SCAN = [os.path.join(ROOT, "app"), os.path.join(ROOT, "installer"), os.path.join(ROOT, "tools")]


def py_files():
    for base in SCAN:
        for r, dirs, fs in os.walk(base):
            if "__pycache__" in r:
                continue
            for f in fs:
                if f.endswith(".py"):
                    yield os.path.join(r, f)


files = sorted(py_files())
print("扫描 .py 文件: %d 个" % len(files))


# ---------------------------------------------------------------- 3.1
print("\n" + "=" * 68)
print("【3.1】未使用导入（AST）")
print("=" * 68)
unused = []
for fp in files:
    try:
        src = open(fp, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:
        print("  解析失败 %s: %s" % (os.path.basename(fp), e))
        continue
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = (a.asname or a.name).split(".")[0]
                imported[nm] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    continue
                imported[a.asname or a.name] = node.lineno
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            p = node
            while isinstance(p, ast.Attribute):
                p = p.value
            if isinstance(p, ast.Name):
                used.add(p.id)
    # noqa 注释里的名字视为已用
    for nm, ln in sorted(imported.items()):
        if nm in used:
            continue
        if ("noqa" in src.splitlines()[ln - 1]) if ln - 1 < len(src.splitlines()) else False:
            continue
        unused.append((os.path.relpath(fp, ROOT), ln, nm))
print("未使用导入共 %d 处:" % len(unused))
for rel, ln, nm in unused:
    print("   %-46s :%-4d %s" % (rel, ln, nm))


# ---------------------------------------------------------------- 3.2
print("\n" + "=" * 68)
print("【3.2】行长超 80 字符（A9）")
print("=" * 68)
rows = []
total_over = 0
for fp in files:
    lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
    over = [(i, len(l)) for i, l in enumerate(lines, 1) if len(l) > 80]
    if over:
        rows.append((os.path.relpath(fp, ROOT), len(lines), len(over), max(x[1] for x in over)))
        total_over += len(over)
rows.sort(key=lambda r: -r[2])
print("超长行合计 %d 处，涉及 %d 个文件" % (total_over, len(rows)))
print("   %-46s %6s %6s %6s" % ("文件", "总行", "超长", "最长"))
for rel, tot, ov, mx in rows[:16]:
    print("   %-46s %6d %6d %6d" % (rel, tot, ov, mx))


# ---------------------------------------------------------------- 3.3
print("\n" + "=" * 68)
print("【3.3】静默 except（吞异常）")
print("=" * 68)
silent = []
for fp in files:
    lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
    for i, l in enumerate(lines):
        s = l.strip()
        if s in ("pass", "continue") and i > 0:
            prev = lines[i - 1].strip()
            if prev.startswith("except") or prev.startswith("finally"):
                silent.append((os.path.relpath(fp, ROOT), i, prev, s))
print("静默 except 共 %d 处:" % len(silent))
for rel, ln, prev, s in silent:
    print("   %-40s :%-4d %s -> %s" % (rel, ln, prev, s))


# ---------------------------------------------------------------- 3.4
print("\n" + "=" * 68)
print("【3.4】引擎 predict_paragraphs 签名 vs benchmark 传参")
print("=" * 68)
sys.path.insert(0, os.path.join(ROOT, "app"))
import inspect  # noqa: E402

from core.engines.rule_engine import CnkiDiagnoseEngine, RuleRewriteEngine  # noqa: E402

for cls in (RuleRewriteEngine, CnkiDiagnoseEngine):
    sig = inspect.signature(cls.predict_paragraphs)
    print("   %s.predict_paragraphs%s" % (cls.__name__, sig))
print()
print("   benchmark_dialog.py:212 传入 params = dict(cfg.get('params') or {})")
from core.engines import catalog  # noqa: E402

for eid in ("aigc_reduce", "cnki_skill", "raid", "mgtbench"):
    e = catalog.by_id(eid)
    print("   catalog[%s].params = %r" % (eid, e.get("params")))
print()
print("   -> 修复/评测类引擎 params 为空或少字段，predict_paragraphs")
print("      收到的是 {}，CnkiDiagnoseEngine 期待 probs/threshold，规则引擎期待 options")
cp = CnkiDiagnoseEngine(catalog.by_id("cnki_skill"), os.path.join(ROOT, "app"))
try:
    r = cp.predict_paragraphs(["这段文本用于测试参数传递。"], None, **{})
    print("   CnkiDiagnoseEngine.predict_paragraphs(**{}) -> %r" % r)
except Exception as e:
    print("   抛错: %s: %s" % (type(e).__name__, e))
rp = RuleRewriteEngine(catalog.by_id("aigc_reduce"), os.path.join(ROOT, "app"))
try:
    r = rp.predict_paragraphs(["这段文本用于测试参数传递。"], None, **{})
    print("   RuleRewriteEngine.predict_paragraphs(**{}) -> %r" % r)
except Exception as e:
    print("   抛错: %s: %s" % (type(e).__name__, e))
print()
print("   传入不存在的键会怎样:")
for k in ({"threshold": 0.5}, {"probs": [0.9]}):
    try:
        RuleRewriteEngine(catalog.by_id("aigc_reduce"), ROOT).predict_paragraphs(
            ["测试文本内容。"], None, **k)
        print("      RuleRewriteEngine **%r -> 未报错" % k)
    except Exception as e:
        print("      RuleRewriteEngine **%r -> %s: %s" % (k, type(e).__name__, e))
    try:
        CnkiDiagnoseEngine(catalog.by_id("cnki_skill"), ROOT).predict_paragraphs(
            ["测试文本内容。"], None, **k)
        print("      CnkiDiagnoseEngine **%r -> 未报错" % k)
    except Exception as e:
        print("      CnkiDiagnoseEngine **%r -> %s: %s" % (k, type(e).__name__, e))
