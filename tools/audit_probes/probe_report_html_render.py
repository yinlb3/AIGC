# -*- coding: utf-8 -*-
"""探针 v7：2.10 未转义文件名的真实危害（离屏 Qt 渲染验证）。"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"d:\Project\AIGC\app")

print("=" * 68)
print("【2.10b】未转义文件名的真实危害（Qt 离屏渲染）")
print("=" * 68)
print("QT_QPA_PLATFORM = offscreen（不显示窗口）")
print()

from PySide6.QtWidgets import QApplication, QTextEdit  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from core.report import build_report  # noqa: E402

probes = [
    ("普通文件名", "论文初稿.docx"),
    ("含 & （Windows 允许做文件名）", "A&B研究.docx"),
    ("含 < > （Windows 不允许，但路径可经 API 构造）", "a<b>c.docx"),
    ("含引号", 'a"b"c.docx'),
]
for label, name in probes:
    html = build_report(["这是一段用于验证的测试文本内容。"], [0.9], 0.9,
                        name, "testengine", 0.5)
    w = QTextEdit()
    w.setHtml(html)
    plain = w.toPlainText()
    head = plain.split("\n")[0] if plain else ""
    expect_start = name
    ok = head.startswith(expect_start)
    print("%-34s 文件名=%r" % (label, name))
    print("   HTML 片段  : %r" % html[:60])
    print("   Qt 渲染首行: %r" % head[:60])
    print("   标题正确?  : %s" % ("是" if ok else "否 <-- 被 HTML 解析破坏"))
    print()

print("对照: 转义后")
from html import escape  # noqa: E402

name = "a<b>c.docx"
html_fixed = build_report(["测试文本内容用于验证。"], [0.9], 0.9,
                          escape(name), "testengine", 0.5)
w = QTextEdit()
w.setHtml(html_fixed)
print("   escape 后 Qt 渲染首行: %r" % (w.toPlainText().split("\n")[0][:60]))
print()
print("结论: 文件名里的 & 与 < > 会破坏 <h2> 标题渲染，")
print("      用户报告里显示的文件名会缺字符或错乱。")
