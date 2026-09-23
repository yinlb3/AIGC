# -*- coding: utf-8 -*-
"""探针公共工具：输出、路径、结论汇总。

原 15 个探针脚本每个都重复了一遍 sys.stdout 包装、sys.path 注入、
head()/verdict() 定义。这些收敛到本模块，探针函数只管验证逻辑。
"""
import io
import os
import sys

# 项目根：本文件在 tools/probes/ 下，上溯两级
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, "app")

if APP not in sys.path:
    sys.path.insert(0, APP)


class Verdicts(object):
    """收集各探针的结论，供主程序汇总。

    原实现是每个脚本自己一个 RESULT 列表 + 自己打汇总，
    跨脚本无法汇总。这里改为统一收集。
    """

    def __init__(self):
        self.rows = []

    def add(self, tag, ok, detail):
        self.rows.append((tag, ok, detail))
        print(">>> 结论: %s | %s" % ("BUG 确认" if ok else "未复现", detail))

    def table(self):
        print("\n" + "#" * 68)
        for tag, ok, d in self.rows:
            print("  [%s] %-6s %s" % ("BUG" if ok else "OK ", tag, d))
        print("确认 bug: %d / %d"
              % (sum(1 for _, o, _ in self.rows if o), len(self.rows)))

    def bug_count(self):
        return sum(1 for _, o, _ in self.rows if o)


def head(tag, title):
    print("\n" + "=" * 68)
    print("【%s】%s" % (tag, title))
    print("=" * 68)


def setup_stdout():
    """控制台编码不可靠（PowerShell 下中文会乱码），强制 utf-8。"""
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
