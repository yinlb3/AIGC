from html import escape

from core.i18n import get_lang, tr


def _pct100(frac):
    """把占比转成**和为 100 的整数百分比**。

    为什么不能各自 round：四档之和恒为 1，但各自四舍五入后**和可能是
    99 或 101**（实测 3000 个随机样本里 1014 个如此）。用户会把四个数字
    加起来核对，看到 99% 会以为程序算错了。

    做法：先各自向下取整，再把差额补给原值最大的那档（最大余数法的简化版
    —— 只补一档即可，因为差额绝对值最大为 3）。

    :param frac: ``(绿, 黄, 红, 紫)`` 占比（和为 1）
    :return: 四个整数百分比，**和恰为 100**
    """
    vals = [v * 100.0 for v in frac]
    # 全 0 是异常输入（引擎按 rank 分档，必有一档命中，和恒为 1）——
    # 若原样补差额会变成「绿 100%」，反而显示成"全是绿档"这种错误结论。
    # 故全 0 直接返回全 0，让调用方自行决定是否显示。
    if sum(vals) <= 0:
        return [0, 0, 0, 0]
    ints = [int(v) for v in vals]
    diff = 100 - sum(ints)
    if diff:
        # 补给小数部分最大、或（diff<0 时）整数部分最大的一档
        idx = max(range(4), key=lambda i: (vals[i] - ints[i]) if diff > 0
                  else ints[i])
        ints[idx] += diff
    return ints


def _bucket_cell(frac):
    """把一段的四档占比渲染成「绿 78% │ 黄 8% │ 红 14% │ 紫 0%」。

    GLTR 论文 §3 的 Test-2 特征（逐 token rank 分四档）；论文原产物是
    涂色图 + 直方图，这里先只给数字，**柱状图见 TODO**（docs/FIXES.md §9）。

    :param frac: ``(绿, 黄, 红, 紫)`` 占比，或 None（文本过短/非统计派引擎）
    """
    if not frac:
        return ""
    g, y, r, p = _pct100(frac)
    if g + y + r + p == 0:
        return ""               # 全 0 无信息，不显示空行
    return tr("bucket_cell") % (g, y, r, p)


def build_report(paragraphs, probs, ratio, file_name, engine_name, threshold=0.5,
                 diagnosis=None, buckets=None):
    rows = []
    for i, (para, prob) in enumerate(zip(paragraphs, probs), 1):
        suspicious = prob >= threshold
        bg = "#fff3cd" if suspicious else "#ffffff"
        color = "#b02a37" if suspicious else "#000000"
        snippet = escape(para if len(para) <= 180 else para[:180] + "…")
        rows.append(
            "<tr><td style='background:%s'>%s</td>"
            "<td style='background:%s;color:%s'>%s</td>"
            "<td style='background:%s'>%s</td></tr>"
            % (bg, tr("para_n") % i, bg, color, tr("ai_prob") % (prob * 100), bg, snippet)
        )
        # 四档另起一行（只对统计派引擎有数据）—— 不塞进上面那行，
        # 避免把「AI 概率」列撑宽影响阅读。见 FIXES.md §9。
        #
        # 判据用**渲染结果是否为空**，而不是 buckets[i-1] 是否为 None ——
        # 全 0 元组是非空的（真值），但渲染为空串，若按后者判断会生成一行
        # 空的 <tr>（踩过）。
        if buckets and i - 1 < len(buckets):
            cell = _bucket_cell(buckets[i - 1])
            if cell:
                rows.append(
                    "<tr><td colspan='3' style='background:%s;color:#475569;"
                    "font-size:12px'>%s</td></tr>" % (bg, cell)
                )
    html = [
        "<h2>%s</h2>" % escape(str(file_name)),
        "<p style='font-size:17px'>%s</p>"
        % tr("report_summary") % (engine_name, ratio * 100, threshold * 100),
        "<p>%s</p>" % tr("report_legend"),
        "<table border='1' cellspacing='0' cellpadding='6' style='border-collapse:collapse'>",
        "".join(rows),
        "</table>",
    ]
    if diagnosis:
        s = diagnosis.get("summary", {})
        high = s.get("high_risk_paras", 0)
        medium = s.get("medium_risk_paras", 0)
        top = s.get("top_patterns", [])[:4]
        footer = [
            "<p style='margin-top:14px;font-size:14px;color:#1d4ed8;font-weight:700;'>%s</p>"
            % tr("report_diag_footer") % (high, medium),
        ]
        if top:
            names = []
            for t in top:
                names.append("%s×%d" % (t["zh"] if get_lang() == "zh" else t["en"], t["count"]))
            footer.append(
                "<p style='font-size:13px;color:#475569;'>%s</p>"
                % tr("report_diag_top") % "、".join(names)
            )
        footer.append(
            "<p style='font-size:13px;color:#475569;'>%s</p>"
            % tr("report_diag_hint")
        )
        html += footer
    return "".join(html)
