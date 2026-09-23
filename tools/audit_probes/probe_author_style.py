# -*- coding: utf-8 -*-
"""按 skill 的 A1~A12 检查项，逐项调查**原作者的实际风格**。

目的：不是为了按 skill 改他，而是弄清他的风格，以便我的改动与之一致。
只读 git 已跟踪的文件（排除我新增的 tools/audit_probes/）。
"""
import io
import os
import re
import subprocess
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"d:\Project\AIGC"
os.chdir(ROOT)
OUT = os.path.join(ROOT, "docs", "calibration", "author_style.txt")
log = open(OUT, "w", encoding="utf-8")


def w(s=""):
    log.write(s + "\n")
    log.flush()


tracked = subprocess.check_output(
    ["git", "ls-files", "*.py"], cwd=ROOT, text=True).splitlines()
files = [f for f in tracked if os.path.exists(f)]
srcs = {}
for f in files:
    try:
        srcs[f] = open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        pass

w("=" * 76)
w("原作者代码风格逐项调查（%d 个文件）" % len(srcs))
w("=" * 76)
w("说明：本表目的是弄清原作者风格，供改动时对齐。")
w()


def stat(fn, name, note=""):
    hits = {f: fn(s) for f, s in srcs.items()}
    hits = {f: v for f, v in hits.items() if v}
    tot = sum(hits.values()) if all(isinstance(v, int) for v in hits.values()) else 0
    w("--- %s ---" % name)
    if note:
        w("    skill 要求: %s" % note)
    if not hits:
        w("    原作者: 无（0 个文件）")
    else:
        w("    原作者: %d 处，涉及 %d 个文件" % (tot if tot else len(hits), len(hits)))
        for f, v in sorted(hits.items(), key=lambda x: -x[1])[:6]:
            w("      %-40s %s" % (f, v))
    w()


# A.1 语言策略：注释语言
def count_cn_comment(s):
    n = 0
    for l in s.splitlines():
        st = l.strip()
        if st.startswith("#") and any("\u4e00" <= c <= "\u9fff" for c in st):
            n += 1
    return n


stat(count_cn_comment, "A.1 中文行注释", "skill 要求注释全英文")


# A.1 docstring 语言
def count_cn_docstring(s):
    import ast
    try:
        t = ast.parse(s)
    except SyntaxError:
        return 0
    n = 0
    for node in ast.walk(t):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            d = ast.get_docstring(node)
            if d and any("\u4e00" <= c <= "\u9fff" for c in d):
                n += 1
    return n


stat(count_cn_docstring, "A.1 中文 docstring", "skill 要求 docstring 全英文")


# A.1 异常消息语言
def count_cn_raise(s):
    return len(re.findall(r'raise\s+\w+\([^)]*[\u4e00-\u9fff]', s))


stat(count_cn_raise, "A.1 raise 里的中文异常消息", "skill 要求异常全英文")


# A.2 路径构造方式
stat(lambda s: len(re.findall(r"os\.path\.join\(", s)),
     "A.2 os.path.join() 用量", "skill 强制用 pathlib.Path 的 / 运算符")
stat(lambda s: len(re.findall(r"Path\(__file__\)|from pathlib import", s)),
     "A.2 pathlib 用量", "skill 强制 pathlib")


# A.2 日志：print vs logging
stat(lambda s: len(re.findall(r"\bprint\(", s)), "A.2 print() 用量",
     "skill 要求放弃 logging，统一 print")
stat(lambda s: len(re.findall(r"\blogging\.", s)), "A.2 logging 用量",
     "skill 要求放弃 logging")


# A.2 os.makedirs
stat(lambda s: len(re.findall(r"os\.makedirs\(", s)), "A.2 os.makedirs(exist_ok=)",
     "skill 要求用 os.makedirs(path, exist_ok=True)")


# A.2 列表初始化
stat(lambda s: len(re.findall(r"=\s*\[\]", s)), "A.2 `= []`（空列表字面量）",
     "skill 建议改用 list()")


# A.11 字符串引号
def quote_style(s):
    d = len(re.findall(r'=\s*"', s))
    q = len(re.findall(r"=\s*'", s))
    return d


stat(quote_style, "A.11 赋值用双引号 \" 的次数", "skill 要求单引号")
stat(lambda s: len(re.findall(r"=\s*'", s)), "A.11 赋值用单引号 ' 的次数",
     "skill 要求单引号")


# A.9 行长
stat(lambda s: sum(1 for l in s.splitlines() if len(l) > 80),
     "A.9 行长 > 80", "skill 要求 <= 80")


# A.11 文件行数
stat(lambda s: len(s.splitlines()) if len(s.splitlines()) > 1000 else 0,
     "A.11 文件 > 1000 行", "skill 要求 <= 1000 行")


# A.11 文件头（Founded / @author）
stat(lambda s: 1 if re.search(r"Founded|@author|Modified", s) else 0,
     "A.11 文件头含 Founded/Modified/@author", "skill 要求标注")


# A.12 目录结构
w("--- A.12 目录结构 ---")
w("    skill 要求: 入口脚本在根目录、可复用模块放 src/、配置放 config/")
w("    原作者实际:")
for sub in ("app", "app/core", "app/core/engines", "app/ui", "installer", "tools"):
    n = len([f for f in files if f.startswith(sub + "/")
             and f.count("/") == sub.count("/") + 1])
    w("      %-20s %d 个 .py" % (sub + "/", n))
w("      src/ 目录: %s" % ("存在" if os.path.isdir("src") else "不存在"))
w("      config/ 目录: %s" % ("存在" if os.path.isdir("config") else "不存在"))
w()

# A.10 变量命名：单字母
def single_letter(s):
    import ast
    try:
        t = ast.parse(s)
    except SyntaxError:
        return 0
    n = 0
    for node in ast.walk(t):
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and len(tg.id) == 1:
                    n += 1
    return n


stat(single_letter, "A.10 单字母赋值目标", "skill 禁止单字母（循环变量除外）")


# A.10 变量名 > 20 字符
def long_vars(s):
    import ast
    try:
        t = ast.parse(s)
    except SyntaxError:
        return 0
    n = 0
    for node in ast.walk(t):
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and len(tg.id) > 20:
                    n += 1
    return n


stat(long_vars, "A.10 变量名 > 20 字符", "skill 要求 <= 20 字符")

log.close()
print("written:", OUT)
