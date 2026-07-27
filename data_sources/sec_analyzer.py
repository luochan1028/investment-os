"""SEC 财报投资信号分析层

工具函数 + 规则引擎 + 公司级分析入口。
依赖 sec_fetcher 提供的指标抓取能力，不含 HTTP/缓存细节。
"""
from __future__ import annotations

import logging
from typing import Optional

from data_sources.sec_fetcher import (
    fetch_xbrl_data,
    find_matching_comparison_date,
    find_report_dates_with_metrics,
    get_all_metrics,
    ALL_FORMS,
)

logger = logging.getLogger("investment-os.sec_filings")


# ==================== 工具函数 ====================


def pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    """百分比变化，None 或除零时返回 None。

    使用 abs(prev) 作为分母，保证负基期也能给出合理正负号。
    """
    if curr is None or prev is None or prev == 0:
        return None
    return ((curr - prev) / abs(prev)) * 100


def fmt_num(n: Optional[float], is_currency: bool = True) -> str:
    """格式化大数字为 T/B/M 单位字符串。"""
    if n is None:
        return "N/A"
    if abs(n) >= 1_000_000_000_000:
        v = n / 1_000_000_000_000
        return f"${v:.2f}T" if is_currency else f"{v:.2f}T"
    if abs(n) >= 1_000_000_000:
        v = n / 1_000_000_000
        return f"${v:.2f}B" if is_currency else f"{v:.2f}B"
    if abs(n) >= 1_000_000:
        v = n / 1_000_000
        return f"${v:.2f}M" if is_currency else f"{v:.2f}M"
    return f"${n:.2f}" if is_currency else f"{n:.2f}"


# ==================== 投资信号分析 ====================


def analyze_investment_signal(
    curr: dict[str, Optional[float]],
    prev: dict[str, Optional[float]],
) -> tuple[list[str], list[str]]:
    """生成利好/利空信号列表。

    Args:
        curr: 当期指标 dict (revenue/net_income/gross_margin/cash/eps/rd_expense 等)
        prev: 上期指标 dict
    Returns:
        (bullish, bearish) 两条字符串列表
    """
    bullish: list[str] = []
    bearish: list[str] = []

    # 营收
    if curr.get("revenue") and prev.get("revenue"):
        rc = pct_change(curr["revenue"], prev["revenue"])
        if rc is not None:
            if rc > 10:
                bullish.append(f"营收大幅增长 {rc:.1f}%")
            elif rc > 0:
                bullish.append(f"营收稳健增长 {rc:.1f}%")
            elif rc < -10:
                bearish.append(f"营收大幅下滑 {abs(rc):.1f}%")
            elif rc < 0:
                bearish.append(f"营收小幅下降 {abs(rc):.1f}%")

    # 净利润变化
    if curr.get("net_income") and prev.get("net_income"):
        ni = pct_change(curr["net_income"], prev["net_income"])
        if ni is not None:
            if ni > 20:
                bullish.append(f"净利润大幅增长 {ni:.1f}%")
            elif ni > 0:
                bullish.append(f"净利润增长 {ni:.1f}%")
            elif ni < -20:
                bearish.append(f"净利润大幅下降 {abs(ni):.1f}%")
            elif ni < 0:
                bearish.append(f"净利润下降 {abs(ni):.1f}%")

    # 扭亏/转亏
    if prev.get("net_income") is not None and curr.get("net_income") is not None:
        if prev["net_income"] < 0 and curr["net_income"] >= 0:
            bullish.append("净利润扭亏为盈")
        elif prev["net_income"] >= 0 and curr["net_income"] < 0:
            bearish.append("净利润由盈转亏")

    # 毛利率变化 (pp)
    if curr.get("gross_margin") and prev.get("gross_margin"):
        gm = curr["gross_margin"] - prev["gross_margin"]
        if gm > 2:
            bullish.append(f"毛利率显著提升 {gm:.1f}pp")
        elif gm > 0:
            bullish.append(f"毛利率改善 {gm:.1f}pp")
        elif gm < -2:
            bearish.append(f"毛利率大幅下降 {abs(gm):.1f}pp")
        elif gm < 0:
            bearish.append(f"毛利率下降 {abs(gm):.1f}pp")

    # 毛利率绝对值
    if curr.get("gross_margin"):
        if curr["gross_margin"] > 60:
            bullish.append(f"高毛利率 {curr['gross_margin']:.0f}%")
        elif curr["gross_margin"] < 20:
            bearish.append(f"低毛利率 {curr['gross_margin']:.0f}%")

    # 现金
    if curr.get("cash"):
        if curr["cash"] > 10_000_000_000:
            bullish.append("现金充裕")
        elif curr["cash"] < 1_000_000_000:
            bearish.append("现金紧张")

    # EPS
    if curr.get("eps") and prev.get("eps"):
        eps = pct_change(curr["eps"], prev["eps"])
        if eps is not None and eps > 10:
            bullish.append(f"EPS增长 {eps:.1f}%")
        elif eps is not None and eps < -10:
            bearish.append(f"EPS下降 {abs(eps):.1f}%")

    # 研发投入
    if curr.get("rd_expense") and prev.get("rd_expense"):
        rd = pct_change(curr["rd_expense"], prev["rd_expense"])
        if rd is not None:
            if rd > 15:
                bullish.append(f"研发投入大幅增加 {rd:.1f}%")
            elif rd < -15:
                bearish.append(f"研发投入大幅削减 {abs(rd):.1f}%")

    return bullish, bearish


def get_investment_summary(
    bullish: list[str],
    bearish: list[str],
) -> tuple[str, str]:
    """根据利好/利空数量做 7 档分级。

    Returns:
        (signal_label, description)
    """
    b, r = len(bullish), len(bearish)
    if b >= 3 and r <= 1:
        return "🟢 强烈利好", "多项关键指标向好，营收、利润、毛利率同步改善"
    if b >= 2 and r == 0:
        return "🟢 利好", "核心指标表现优异，建议关注"
    if b > r:
        return "🟡 偏利好", "整体向好，但存在部分风险因素"
    if r >= 3 and b <= 1:
        return "🔴 强烈利空", "多项关键指标恶化，营收、利润、毛利率同步下降"
    if r >= 2 and b == 0:
        return "🔴 利空", "核心指标表现疲软，需谨慎"
    if r > b:
        return "🟡 偏利空", "整体承压，但部分指标仍有亮点"
    return "⚪ 中性", "指标分化，无明确趋势信号"


# ==================== 公司级分析 ====================


def analyze_company(name: str, cik: str) -> Optional[dict]:
    """抓取并分析一家公司的最新财报。

    Returns:
        {
            "name", "cik", "form" (年报/季报), "report_form",
            "current_date", "previous_date",
            "current" (metrics dict), "previous" (metrics dict),
            "bullish" (list), "bearish" (list),
            "signal" (label), "signal_desc" (str)
        } 或 None
    """
    logger.info(f"analyze_company: {name} (CIK {cik})")

    xbrl = fetch_xbrl_data(cik)
    if xbrl is None:
        logger.warning(f"  无法获取 {name} XBRL 数据")
        return None

    valid_dates, date_info = find_report_dates_with_metrics(xbrl)
    if not valid_dates:
        logger.warning(f"  {name} 无可用报告日期")
        return None

    current_date = valid_dates[0]
    current_form = date_info[current_date]["form"]
    forms_for_current = [current_form] + [f for f in ALL_FORMS if f != current_form]

    previous_date = find_matching_comparison_date(current_date, valid_dates, date_info)

    current = get_all_metrics(xbrl, current_date, forms_for_current)
    previous = get_all_metrics(xbrl, previous_date, forms_for_current) if previous_date else {}

    bullish, bearish = analyze_investment_signal(current, previous)
    signal, signal_desc = get_investment_summary(bullish, bearish)

    useful = sum(1 for v in current.values() if v is not None)
    logger.info(
        f"  {name}: 当期 {current_date} ({current_form}), "
        f"指标 {useful}/9, 信号 {signal}"
    )

    return {
        "name": name,
        "cik": cik,
        "form": "年报" if current_form in ("10-K", "20-F") else "季报",
        "report_form": current_form,
        "current_date": current_date,
        "previous_date": previous_date,
        "current": current,
        "previous": previous,
        "bullish": bullish,
        "bearish": bearish,
        "signal": signal,
        "signal_desc": signal_desc,
    }
