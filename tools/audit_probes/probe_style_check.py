# -*- coding: utf-8 -*-
"""检查原作者代码的格式问题。

只检查 git 已跟踪的 .py（排除我新增的 tools/audit_probes/）。
输出：docs/calibration/style_check.txt
"""
import ast
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"d:\Project\AIGC"
OUT = os.path.join(ROOT, "docs", "calibration", "style_check.txt")
log = open(OUT, "w", encoding="utf-8")


def w(s=""):
    log.write(s + "\n")
    log.flush()


# 只取原作者的文件
tracked = subprocess.check_output(
    ["git", "ls-files", "*.py"], cwd=ROOT, text=True).splitlines()
files = [os.path.join(ROOT, f) for f in tracked if os.path.exists(
    os.path.join(ROOT, f))]
w("=" * 74)
w("原作者代码格式检查（git 已跟踪的 %d 个 .py）" % len(files))
w("=" * 74)

long_lines = []
long_lines_pct = []
tab_indent = []
trailing_ws = []
mixed_issue = []
no_encoding = []
bare_except = []
mutable_default = []
eq_none = []
not_in = []
broad_short = []       # 单字母变量名
todo = []


def read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


for path in files:
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    src = read(path)
    lines = src.splitlines()

    # 1) 行长 > 100（宽松阈值，PEP8 是 79）
    over100 = [(i, len(l)) for i, l in enumerate(lines, 1) if len(l) > 100]
    if over100:
        long_lines.append((rel, len(over100), max(n for _, n in over100)))
    # 1b) 行长 > 79
    over79 = [i for i, l in enumerate(lines, 1) if len(l) > 79]
    if over79:
        long_lines_pct.append((rel, len(over79), len(lines)))

    # 2) 制表符缩进
    for i, l in enumerate(lines, 1):
        if l.startswith("\t") or re.match(r"^ +\t", l):
            tab_indent.append((rel, i))
            break

    # 3) 行尾空白
    n_tw = sum(1 for l in lines if l != l.rstrip() and l.strip())
    if n_tw:
        trailing_ws.append((rel, n_tw))

    # 4) 无编码声明（非 ASCII 且首两行无 coding）
    has_nonascii = any(ord(c) > 127 for c in src)
    head = "\n".join(lines[:2])
    if has_nonascii and "coding" not in head and "-*-" not in head:
        no_encoding.append(rel)

    # 5) 语法级检查
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        mixed_issue.append((rel, "SyntaxError: %s" % e))
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            bare_except.append((rel, node.lineno))
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if isinstance(op, (ast.Is, ast.IsNot)):
                    continue
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    if isinstance(comp, ast.Constant) and comp.value is None:
                        eq_none.append((rel, node.lineno,
                                        "== None" if isinstance(op, ast.Eq) else "!= None"))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.args.defaults + node.args.kw_defaults:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    mutable_default.append((rel, node.lineno, node.name))
        if isinstance(node, ast.Name) and len(node.id) == 1 and \
                node.id not in ("i", "j", "k", "n", "p", "s", "t", "e", "x", "y", "f", "v"):
            pass

    # 6) print 调试残留
    for i, l in enumerate(lines, 1):
        st = l.strip()
        if st.startswith("print(") and rel.startswith("app/core/engines"):
            broad_short.append((rel, i, st[:50]))

    # 7) TODO/FIXME
    for i, l in enumerate(lines, 1):
        if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", l):
            todo.append((rel, i, l.strip()[:60]))

# ---- 输出 ----
w()
w("【1】行长 > 100 字符（PEP8 上限 79，这里用宽松阈值）")
if long_lines:
    long_lines.sort(key=lambda x: -x[1])
    for rel, n, mx in long_lines:
        w("   %-44s %4d 处，最长 %d" % (rel, n, mx))
else:
    w("   无")
w()
w("【2】行长 > 79 字符（PEP8 标准）—— 仅列前 12 个文件")
if long_lines_pct:
    long_lines_pct.sort(key=lambda x: -x[1])
    tot = sum(n for _, n, _ in long_lines_pct)
    w("   合计 %d 处，涉及 %d 个文件" % (tot, len(long_lines_pct)))
    for rel, n, ln in long_lines_pct[:12]:
        w("   %-44s %4d / %4d 行 (%.0f%%)" % (rel, n, ln, n * 100.0 / ln))
else:
    w("   无")
w()
w("【3】制表符缩进（应为空格）")
w("   %s" % ("；".join("%s:%d" % x for x in tab_indent) if tab_indent else "无"))
w()
w("【4】行尾空白")
if trailing_ws:
    trailing_ws.sort(key=lambda x: -x[1])
    for rel, n in trailing_ws:
        w("   %-44s %4d 行" % (rel, n))
else:
    w("   无")
w()
w("【5】缺少编码声明（文件含非 ASCII 但首两行无 coding）")
w("   %s" % (("、".join(no_encoding)) if no_encoding else "无"))
w()
w("【6】裸 except（`except:` 不带异常类型）")
if bare_except:
    for rel, ln in bare_except:
        w("   %s:%d" % (rel, ln))
else:
    w("   无")
w()
w("【7】`== None` / `!= None`（应写 is None / is not None）")
if eq_none:
    for rel, ln, txt in eq_none:
        w("   %s:%d  %s" % (rel, ln, txt))
else:
    w("   无")
w()
w("【8】可变类型作默认参数（def f(x=[]) 之类）")
if mutable_default:
    for rel, ln, name in mutable_default:
        w("   %s:%d  函数 %s" % (rel, ln, name))
else:
    w("   无")
w()
w("【9】引擎模块里的 print(（应为日志）")
if broad_short:
    for rel, ln, txt in broad_short:
        w("   %s:%d  %s" % (rel, ln, txt))
else:
    w("   无")
w()
w("【10】TODO / FIXME / XXX / HACK 注释")
if todo:
    for rel, ln, txt in todo:
        w("   %s:%d  %s" % (rel, ln, txt))
else:
    w("   无")
w()

log.close()
print("written:", OUT)
