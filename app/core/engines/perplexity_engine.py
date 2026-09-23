# -*- coding: utf-8 -*-
"""GLTR 困惑度检测引擎：语言模型困惑度越低越像机器写的。

阈值为什么分语言（实测标定，2026-09-23）
----------------------------------------
``ppl_low`` / ``ppl_high`` 把 PPL 线性映射到 [0.85, 0.15]。实测（各 300 条
1:1 平衡样本，gpt2）：

===========  =============  ============  ============
语言          AI PPL 中位     human 中位     现阈值准确率
===========  =============  ============  ============
英文          12.96          29.50         93.67%
中文          12.06          17.18         68.33%
===========  =============  ============  ============

现有 (12, 25) 是**英文的最优值**；中文下 human 的 PPL 中位仅 17.18，落进了
插值区间，判别力被稀释。所以中文单独用标定出的 (11.35, 18.72)，准确率
68.33% → 74.67%（FPR 58.45% → 29.58%）。两组阈值存在 catalog 的 params 里，
按文本语言自动切换。

数据来源：Ghostbuster Student Essay（英）/ HC3-Chinese（中），
详见 docs/calibration.md

注：论文 GLTR（arXiv:1906.04043）的主特征是逐 token rank 四档分布
（§4 实测 AUC 0.87），本实现用的是整段平均 PPL（Test-1 路线的退化版，
AUC 0.71）。按 rank 四档重做见 docs/AUDIT_2026-09-22.md 的 TODO-3。
"""
from .base import BaseEngine
from .registry import register


def _is_chinese(text):
    """粗判语言：CJK 字符占比是否过半（只看前 200 字，够用且快）。"""
    s = text[:200]
    if not s:
        return False
    cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    return cjk * 2 >= len(s)


@register("perplexity")
class PerplexityEngine(BaseEngine):
    """统计派方法：PPL ≤ ppl_low 判 0.85，≥ ppl_high 判 0.15，中间线性插值。"""

    type = "perplexity"
    MODEL_KINDS = ("causal",)
    MODELS = (("gpt2", "causal", "困惑度打分模型"),)

    def predict_paragraphs(
        self,
        paragraphs,
        device,
        ppl_high=25.0,
        ppl_low=12.0,
        ppl_high_zh=None,
        ppl_low_zh=None,
        progress_cb=None,
        **kwargs
    ):
        tok = self.tok(0)
        model = self.mdl(0, device)
        out = []
        total = len(paragraphs)
        for i, p in enumerate(paragraphs):
            # 中文用中文标定的一组阈值（未配置时退回通用值）
            if _is_chinese(p) and ppl_low_zh and ppl_high_zh:
                lo, hi = float(ppl_low_zh), float(ppl_high_zh)
            else:
                lo, hi = float(ppl_low), float(ppl_high)
            ppl = self.perplexity(p, model, tok, device)
            if ppl <= lo:
                prob = 0.85
            elif ppl >= hi:
                prob = 0.15
            else:
                t = (ppl - lo) / max(hi - lo, 1e-6)
                prob = 0.85 - 0.7 * t
            out.append(prob)
            if progress_cb:
                progress_cb(i + 1, total)
        return out

