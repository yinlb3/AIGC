# -*- coding: utf-8 -*-
"""探针 v2b：2.6 死循环隐患 / 2.7 参数覆盖顺序。"""
import io
import sys

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


# ---------------------------------------------------------------- 2.6
head("2.6", "死循环隐患 —— therapy.py:243-248 / 152-168")
from core.aigc_rules import (  # noqa: E402
    COLLOQUIAL_FIXES,
    NUMBERED_MARKERS,
    SEQ_MARKERS,
)

print("A) _style_fix:")
print("     for word, repl in COLLOQUIAL_FIXES.items():")
print("         while word in text:")
print("             text = text.replace(word, repl, 1)")
print("   若 repl 里含 word -> 替换后仍命中 -> 无限循环")
bad_style = [(w, r) for w, r in COLLOQUIAL_FIXES.items() if w in r]
print("   COLLOQUIAL_FIXES 共 %d 条，自激 %d 条" % (len(COLLOQUIAL_FIXES), len(bad_style)))
for w, r in bad_style:
    print("      BAD %r -> %r" % (w, r))
print("   前 8 条规则样本:")
for w, r in list(COLLOQUIAL_FIXES.items())[:8]:
    print("      %r -> %r" % (w, r))

print()
print("B) _break_parallel:")
print("     while True:")
print("         m = pattern.search(text)")
print("         if not m: break")
print("         text = text[:m.start()] + repl + text[m.end():]")
print("   若 repl 被 pattern 命中 -> 无限循环")
bad_par = []
for nm, tbl in (("NUMBERED_MARKERS", NUMBERED_MARKERS), ("SEQ_MARKERS", SEQ_MARKERS)):
    for pattern, repl in tbl:
        if pattern.search(repl):
            bad_par.append((nm, pattern.pattern, repl))
print("   NUMBERED=%d 条, SEQ=%d 条, 自激 %d 条"
      % (len(NUMBERED_MARKERS), len(SEQ_MARKERS), len(bad_par)))
for nm, p, r in bad_par:
    print("      BAD [%s] pattern=%r repl=%r" % (nm, p, r))

print()
print("实测调用（当前规则表）:")
from core import therapy  # noqa: E402

probe = [
    "首先，要重视这一问题。其次，要落实到行动。最后，要总结经验。",
    "说白了，这个方案真的强。总的来说，值得推广。",
    "一方面要抓效率，另一方面要抓质量，总的来说要两手抓。",
]
for t in probe:
    c1, c2 = [], []
    therapy._style_fix(t, c1)
    therapy._break_parallel(t, c2)
    print("   输入 %r -> style %d 处, parallel %d 处" % (t[:22], len(c1), len(c2)))
verdict("2.6", bool(bad_style) or bool(bad_par),
        "口语化自激 %d 条，模板自激 %d 条；当前规则表未触发实测卡死"
        % (len(bad_style), len(bad_par)))


# ---------------------------------------------------------------- 2.7
head("2.7", "引擎清单参数覆盖用户参数 —— main_window.py:86-90")
print('    eparams = dict(cfg.get("params", {}))')
print('    if "max_len" in self.params:')
print('        eparams["max_len"] = self.params["max_len"]')
print("    run_params = dict(self.params)")
print('    run_params.update(eparams)')
print()
cfg = {"params": {"threshold": 0.3, "ppl_high": 25.0}}
user = {"threshold": 0.7, "min_para_len": 20, "use_gpu": True}
ep = dict(cfg.get("params", {}))
if "max_len" in user:
    ep["max_len"] = user["max_len"]
rp = dict(user)
rp.update(ep)
print("清单默认 threshold=0.3，用户界面设 0.7")
print("   合并后 run_params['threshold'] = %r" % rp["threshold"])
print("   完整 run_params = %r" % rp)
print()
extra = [k for k in rp if k in ("engine", "min_para_len", "use_cluster",
                                "rewrite", "suggest_threshold", "use_gpu")]
print("非引擎参数也会 ** 展开进 predict_paragraphs(): %r" % extra)
print("引擎签名以 **kwargs 兜底，不会 TypeError，但语义混乱")
verdict("2.7", rp["threshold"] != user["threshold"],
        "用户 threshold=0.7 被清单覆盖为 %r" % rp["threshold"])


print("\n" + "#" * 68)
for n, o, d in RESULT:
    print("  [%s] %-5s %s" % ("BUG" if o else "OK ", n, d))
print("确认 bug: %d / %d" % (sum(1 for _, o, _ in RESULT if o), len(RESULT)))
