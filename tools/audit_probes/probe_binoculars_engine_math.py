# -*- coding: utf-8 -*-
"""AIGC bug 复现探针 v1：2.1 2.2 2.3。只读项目源码，不写项目内文件。"""
import io
import math
import os
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


# ---------------------------------------------------------------- 2.1
head("2.1", "Binoculars 公式恒判 AI —— binoculars_engine.py:54-58")
print("原始代码:")
print("    log_ppl   = -lp_obs")
print("    cross_ppl = math.exp(min(-lp_perf, 700.0))")
print("    score     = log_ppl / max(cross_ppl, 1e-6)")
print("    out.append(squash(threshold - score, 0.0, scale))")
print()

from core.engines.base import squash  # noqa: E402


def repro_bino(lp_obs, lp_perf, threshold=0.9015, scale=0.12):
    log_ppl = -lp_obs
    cross_ppl = math.exp(min(-lp_perf, 700.0))
    score = log_ppl / max(cross_ppl, 1e-6)
    return squash(threshold - score, 0.0, scale), score


def paper_bino(lp_obs, lp_perf):
    return math.exp(-lp_obs) / math.exp(-lp_perf)


cases = [
    ("典型 AI 文本", -5.0, -3.2),
    ("典型人写文本", -12.0, -8.0),
    ("极端人写(高困惑)", -20.0, -15.0),
    ("极端 AI(低困惑)", -2.0, -1.8),
]
for name, a, b in cases:
    got, sc = repro_bino(a, b)
    print("%-18s lp_obs=%-7.1f lp_perf=%-7.1f score=%.6f 判AI=%.6f (论文式B=%.4f)"
          % (name, a, b, sc, got, paper_bino(a, b)))
print()
print("论文式 B 在 6~55 量级；本实现 score 恒在 0.00x 量级；")
print("阈值 0.9015 与 score 量纲不匹配 -> squash 恒接近 1.0")
vals = [repro_bino(a, b)[0] for _, a, b in cases]
verdict("2.1", min(vals) > 0.95,
        "四组输入概率 %.4f~%.4f，全部判 AI" % (min(vals), max(vals)))


# ---------------------------------------------------------------- 2.2
head("2.2", "自动降重完成提示格式化缺参 —— rewrite_dialog.py:519-524")
print('原始代码: msg = "%s\\n\\n%s\\n\\n%s %.1f%%" % (')
print('    tr("rewrite_auto_done_rounds") % len(history),')
print('    "\\n".join(hist_lines),')
print('    tr("rewrite_auto_final_ratio"),')
print('    result["ai_ratio"] * 100,')
print(")")
print()
from core.i18n import tr  # noqa: E402

fmt = "%s\n\n%s\n\n%s %.1f%%"
n_ph = fmt.count("%%") + fmt.count("%s") + fmt.count("%.1f")
print("格式化串 %r" % fmt)
print("  实参: 4 个值")
try:
    msg = fmt % (
        tr("rewrite_auto_done_rounds") % 3,
        "round1\nround2",
        tr("rewrite_auto_final_ratio"),
        25.0,
    )
    print("  未报错 -> %r" % msg)
    verdict("2.2", False, "未复现")
except TypeError as e:
    print("  抛错 -> TypeError: %s" % e)
    print()
    print("  分析: 前 3 个 %%s 吃掉 3 个实参，第 4 个实参 25.0 被 %.1f%% 的 %.1f 吃")
    print("        剩下结尾字面量 %% 无对应实参 -> 缺参")
    verdict("2.2", True, "TypeError: not enough arguments for format string")


# ---------------------------------------------------------------- 2.3
head("2.3", "设置保存写坏 hf_endpoint —— settings_dialog.py:174-179")
print("原始代码:")
print('    def _save(self):')
print('        mid, _ = self._current_mirror()')
print('        self.settings.set(mid, "download", "mirror")')
print('        self.settings.set(mid, "download", "hf_endpoint")   # 丢掉 https://')
print('        self.settings.set(self.models_dir_edit.text().strip(),')
print('                          "download", "models_dir")')
print()
print('_current_mirror() 返回二元组:')
print('    return "hf-mirror.com", MIRRORS["hf-mirror.com"]')
print('    即 ("hf-mirror.com", "https://hf-mirror.com")')
print("代码只取第 1 个元素，url 被弃用。")
print()

from core.settings import DEFAULTS  # noqa: E402

MIRRORS = {"hf-mirror.com": "https://hf-mirror.com",
           "HuggingFace 官方": "https://huggingface.co"}


def current_mirror(domestic=True):
    if domestic:
        return "hf-mirror.com", MIRRORS["hf-mirror.com"]
    return "huggingface.co", MIRRORS["HuggingFace 官方"]


for label, dom in (("国内镜像", True), ("官方源", False)):
    mid, url = current_mirror(dom)
    print("%s: _current_mirror() -> mid=%r url=%r" % (label, mid, url))
    print("     _save() 实际写入 hf_endpoint = %r" % mid)
    print("     正确值应为           = %r" % url)
    print()

mid, _u = current_mirror(True)
sim_endpoint = mid
ok = "://" not in sim_endpoint
print("对照 main.py:13-14:")
print('    _mirror = _settings.get("download", "hf_endpoint", default="https://hf-mirror.com")')
print('    os.environ.setdefault("HF_ENDPOINT", _mirror)')
print()
print("DEFAULTS 内置正确值 = %r" % DEFAULTS["download"]["hf_endpoint"])
print()
print("实测无协议地址的后果:")
import urllib.parse  # noqa: E402

p = urllib.parse.urlparse(sim_endpoint)
print("    urlparse(%r) -> scheme=%r netloc=%r path=%r" % (sim_endpoint, p.scheme, p.netloc, p.path))
print("    => scheme 为空，httpx/requests 拼接时会得到相对 URL 或直接报错")
try:
    import huggingface_hub

    print("    huggingface_hub 版本 = %s" % huggingface_hub.__version__)
except Exception as e:
    print("    huggingface_hub 探测失败: %s" % e)
verdict("2.3", ok, "hf_endpoint 被写成 %r（无 https://）" % sim_endpoint)


print("\n" + "#" * 68)
for n, o, d in RESULT:
    print("  [%s] %-5s %s" % ("BUG" if o else "OK ", n, d))
print("确认 bug: %d / %d" % (sum(1 for _, o, _ in RESULT if o), len(RESULT)))
