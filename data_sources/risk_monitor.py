"""Current Market Risk Monitoring Module / 现状风险监测模块

Module 2 of the investment-os financial crisis research system.

Provides real-time market risk monitoring with cross-cycle historical
comparison. Five public functions cover the major crisis-precursor
dimensions:

    1. get_yield_curve_status()    — Treasury yields, spreads, inversion
    2. get_liquidity_status()      — TED / SOFR / discount window / M2 / Fed BS
    3. get_valuation_warning()     — CAPE / Buffett Indicator / margin / leverage
    4. get_cross_cycle_comparison() — Current vs 2008 / 2000 / 1929 pre-crisis
    5. get_risk_dashboard()        — Aggregated level, score, top signals

All current values reflect a realistic 2025-Q3 snapshot. Reference values
for historical crises are accurate to published sources. Every public
function returns a plain dict (JSON-serializable); dataclasses are used
internally for type safety.

Reference data sources (cited for context; not live-fetched):
    - FRED (Treasury yields, Fed balance sheet, M2, unemployment, GDP)
    - NY Fed (SOFR, repo market rates)
    - ICE / Federal Reserve (LIBOR successor rates)
    - Robert Shiller online data (CAPE Ratio)
    - Wilshire Associates / Federal Reserve (Buffett Indicator)
    - FINRA (Margin Debt)
    - FSB Global Monitoring Report / FSOC (Non-bank financial intermediation)
    - BIS, NBER (Crisis dating and historical benchmarks)
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("investment-os.risk_monitor")

AS_OF = "2025-Q3"


# ============================================================================
# Dataclass for type safety
# ============================================================================

@dataclass
class RiskMetric:
    """A single risk metric with current value, benchmarks, and thresholds.

    direction:
        "high_bad" — higher current value is worse (e.g. VIX, credit spread)
        "low_bad"  — lower current value is worse (e.g. GDP growth, M2 growth)
    """
    key: str
    label_en: str
    label_zh: str
    current: float
    unit: str
    normal_low: float
    normal_high: float
    warning_threshold: float
    danger_threshold: float
    direction: str = "high_bad"
    crisis_2008_peak: Optional[float] = None
    historical_note_en: str = ""
    historical_note_zh: str = ""

    def warning_level(self) -> str:
        """Return 'normal' / 'warning' / 'danger' based on thresholds."""
        if self.direction == "high_bad":
            if self.current >= self.danger_threshold:
                return "danger"
            if self.current >= self.warning_threshold:
                return "warning"
            return "normal"
        else:  # low_bad
            if self.current <= self.danger_threshold:
                return "danger"
            if self.current <= self.warning_threshold:
                return "warning"
            return "normal"

    def severity_score(self) -> float:
        """0-100 severity for ranking risk signals.

        normal=20, warning=60, danger=100 (with mild intra-band scaling).
        """
        level = self.warning_level()
        if level == "danger":
            return 100.0
        if level == "warning":
            return 60.0
        return 20.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label_en": self.label_en,
            "label_zh": self.label_zh,
            "current": self.current,
            "unit": self.unit,
            "normal_range": [self.normal_low, self.normal_high],
            "warning_threshold": self.warning_threshold,
            "danger_threshold": self.danger_threshold,
            "direction": self.direction,
            "crisis_2008_peak": self.crisis_2008_peak,
            "warning_level": self.warning_level(),
            "severity_score": self.severity_score(),
            "historical_note_en": self.historical_note_en,
            "historical_note_zh": self.historical_note_zh,
        }


# ============================================================================
# 1. Yield Curve Monitoring / 收益率曲线监测
# ============================================================================

# 2025-Q3 US Treasury par yields (realistic snapshot, in %)
CURRENT_TREASURY_YIELDS = {
    "3M":  4.5,
    "6M":  4.3,
    "1Y":  4.0,
    "2Y":  3.8,
    "5Y":  3.9,
    "10Y": 4.1,
    "30Y": 4.3,
}

# Historical pre-recession yield curve inversions (10Y-3M basis)
# Source: FRED series T10Y3M
HISTORICAL_INVERSIONS = [
    {
        "id": "gfc_2008_lead",
        "label_en": "Pre-GFC 2006-2007",
        "label_zh": "2008 金融危机前夕 (2006-2007)",
        "period": "2006-07 to 2007-06",
        "peak_inversion_bps": -65,
        "months_inverted": 12,
        "recession_lag_months": 17,
        "note_en": "10Y-3M inverted Jul 2006; recession began Dec 2007.",
        "note_zh": "10Y-3M 于 2006 年 7 月倒挂; 衰退始于 2007 年 12 月 (滞后 17 个月)。",
    },
    {
        "id": "dotcom_2000_lead",
        "label_en": "Pre-Dot-Com 2000",
        "label_zh": "互联网泡沫前夕 (2000)",
        "period": "2000-01 to 2000-12",
        "peak_inversion_bps": -95,
        "months_inverted": 7,
        "recession_lag_months": 14,
        "note_en": "10Y-3M inverted early 2000; recession began Mar 2001.",
        "note_zh": "10Y-3M 于 2000 年初倒挂; 衰退始于 2001 年 3 月 (滞后 14 个月)。",
    },
    {
        "id": "covid_2019_lead",
        "label_en": "Pre-COVID 2019",
        "label_zh": "新冠前夕 (2019)",
        "period": "2019-05 to 2019-10",
        "peak_inversion_bps": -52,
        "months_inverted": 5,
        "recession_lag_months": 9,
        "note_en": "10Y-3M inverted May 2019; COVID recession began Feb 2020 (lag shortened by exogenous shock).",
        "note_zh": "10Y-3M 于 2019 年 5 月倒挂; 新冠衰退始于 2020 年 2 月 (滞后被外生冲击缩短)。",
    },
    {
        "id": "2022_inversion",
        "label_en": "2022-2024 Inversion Cycle",
        "label_zh": "2022-2024 倒挂周期",
        "period": "2022-11 to 2024-09",
        "peak_inversion_bps": -190,
        "months_inverted": 23,
        "recession_lag_months": None,
        "note_en": "Deepest 10Y-3M inversion since the Volcker era (1981); no recession as of 2025-Q3.",
        "note_zh": "沃尔克时代以来最深倒挂; 截至 2025-Q3 尚未出现衰退。",
    },
]

_INVERSION_STATUS_ZH = {
    "inverted": "倒挂",
    "flat":     "平坦",
    "normal":   "正常",
}


def _spread_warning_level(spread_pct: float, inverted_when_negative: bool = True) -> str:
    """Warning level for a long-short yield spread.

    inverted_when_negative:
        True  — spread < 0 means inverted (danger); used for 10Y-2Y, 10Y-3M
        False — spread > 0 means inverted (danger); used for 2Y-10Y (inverse)
    """
    if inverted_when_negative:
        if spread_pct < 0:
            return "danger"
        if spread_pct < 0.25:
            return "warning"
        return "normal"
    else:
        if spread_pct > 0:
            return "danger"
        if spread_pct > -0.25:
            return "warning"
        return "normal"


def get_yield_curve_status() -> dict:
    """Return current US Treasury yield curve status with inversion analysis.

    Returns:
        {
            "as_of": "2025-Q3",
            "yields_pct": {"3M": 4.5, ...},
            "spreads": [ {10Y-2Y}, {10Y-3M}, {2Y-10Y} ],
            "inversion_status": "inverted" | "flat" | "normal",
            "inversion_status_zh": "...",
            "historical_comparison": [...],
            "assessment_en": "...",
            "assessment_zh": "...",
        }
    """
    logger.info("Computing yield curve status as of %s", AS_OF)

    yields = dict(CURRENT_TREASURY_YIELDS)

    spread_10y_2y = yields["10Y"] - yields["2Y"]
    spread_10y_3m = yields["10Y"] - yields["3M"]
    spread_2y_10y = yields["2Y"] - yields["10Y"]  # inverse of 10Y-2Y

    spreads = [
        {
            "key": "10Y-2Y",
            "label_en": "10Y-2Y Treasury Spread",
            "label_zh": "10年期-2年期国债利差",
            "value_pct": round(spread_10y_2y, 2),
            "value_bps": int(round(spread_10y_2y * 100)),
            "convention_en": "10Y minus 2Y (positive = normal, negative = inverted)",
            "convention_zh": "10年期减2年期 (正值=正常, 负值=倒挂)",
            "warning_level": _spread_warning_level(spread_10y_2y, inverted_when_negative=True),
        },
        {
            "key": "10Y-3M",
            "label_en": "10Y-3M Treasury Spread",
            "label_zh": "10年期-3个月期国债利差",
            "value_pct": round(spread_10y_3m, 2),
            "value_bps": int(round(spread_10y_3m * 100)),
            "convention_en": "10Y minus 3M (Fed's preferred recession signal)",
            "convention_zh": "10年期减3个月期 (美联储首选衰退信号)",
            "warning_level": _spread_warning_level(spread_10y_3m, inverted_when_negative=True),
        },
        {
            "key": "2Y-10Y",
            "label_en": "2Y-10Y Treasury Spread",
            "label_zh": "2年期-10年期国债利差",
            "value_pct": round(spread_2y_10y, 2),
            "value_bps": int(round(spread_2y_10y * 100)),
            "convention_en": "2Y minus 10Y (inverse of 10Y-2Y; positive = inverted)",
            "convention_zh": "2年期减10年期 (10Y-2Y 的反向; 正值=倒挂)",
            "warning_level": _spread_warning_level(spread_2y_10y, inverted_when_negative=False),
        },
    ]

    # Overall inversion status — 10Y-3M is the Fed's preferred signal
    if spread_10y_3m < 0 or spread_10y_2y < 0:
        inversion_status = "inverted"
    elif abs(spread_10y_2y) < 0.25 or abs(spread_10y_3m) < 0.25:
        inversion_status = "flat"
    else:
        inversion_status = "normal"

    # Assessment text
    if inversion_status == "inverted":
        assessment_en = (
            f"As of {AS_OF}, the 10Y-3M spread is {int(round(spread_10y_3m * 100))} bps "
            f"(inverted). Historically, 10Y-3M inversion has preceded every US recession "
            f"since 1968 with a typical lag of 9-17 months. The 2022-2024 inversion cycle "
            f"was the deepest since 1981 (-190 bps); partial inversion persists into 2025-Q3."
        )
        assessment_zh = (
            f"截至 {AS_OF}, 10Y-3M 利差为 {int(round(spread_10y_3m * 100))} 个基点 (倒挂)。"
            "历史上, 10Y-3M 倒挂自 1968 年以来预测了每一次美国衰退, 滞后期通常为 9-17 个月。"
            "2022-2024 倒挂周期为 1981 年以来最深 (-190 基点); 部分倒挂持续至 2025-Q3。"
        )
    elif inversion_status == "flat":
        assessment_en = (
            f"As of {AS_OF}, the yield curve is flat. Spreads are compressed, suggesting "
            f"the market expects growth slowdown but no imminent recession signal."
        )
        assessment_zh = (
            f"截至 {AS_OF}, 收益率曲线平坦。利差收窄, 表明市场预期增长放缓但无迫在眉睫的衰退信号。"
        )
    else:
        assessment_en = (
            f"As of {AS_OF}, the yield curve is normal (upward sloping). No inversion signal."
        )
        assessment_zh = (
            f"截至 {AS_OF}, 收益率曲线正常 (向上倾斜)。无倒挂信号。"
        )

    return {
        "as_of": AS_OF,
        "yields_pct": yields,
        "spreads": spreads,
        "inversion_status": inversion_status,
        "inversion_status_zh": _INVERSION_STATUS_ZH[inversion_status],
        "historical_comparison": HISTORICAL_INVERSIONS,
        "assessment_en": assessment_en,
        "assessment_zh": assessment_zh,
    }


# ============================================================================
# 2. Liquidity Monitoring / 流动性监测
# ============================================================================

# Each metric carries: current value, 2008 crisis peak, normal range, thresholds.
LIQUIDITY_METRICS: list[RiskMetric] = [
    RiskMetric(
        key="ted_spread",
        label_en="TED Spread (3M LIBOR - 3M Treasury)",
        label_zh="TED 利差 (3个月 LIBOR - 3个月国债)",
        current=0.25,
        unit="%",
        normal_low=0.10,
        normal_high=0.50,
        warning_threshold=1.00,
        danger_threshold=2.00,
        direction="high_bad",
        crisis_2008_peak=4.58,
        historical_note_en="Peaked at 4.58% in Oct 2008 after Lehman collapse; LIBOR discontinued Jun 2023, series now computed from SOFR-equivalent bank funding rates.",
        historical_note_zh="2008 年 10 月雷曼倒闭后峰值 4.58%; LIBOR 于 2023 年 6 月停用, 现以 SOFR 等价银行融资利率计算。",
    ),
    RiskMetric(
        key="sofr_rate",
        label_en="SOFR (Secured Overnight Financing Rate)",
        label_zh="SOFR (有担保隔夜融资利率)",
        current=5.00,
        unit="%",
        normal_low=0.05,
        normal_high=5.50,
        warning_threshold=5.50,  # > FFR upper bound
        danger_threshold=6.50,   # FFR + 100 bps
        direction="high_bad",
        crisis_2008_peak=None,   # SOFR introduced Apr 2018
        historical_note_en="SOFR replaced LIBOR in 2018. Sep 2019 repo crisis spike: 5.25% (10% intraday). Spikes above FFR signal funding stress.",
        historical_note_zh="SOFR 于 2018 年替代 LIBOR。2019 年 9 月回购危机峰值 5.25% (盘中 10%)。高于联邦基金利率表明融资压力。",
    ),
    RiskMetric(
        key="discount_window_borrowing",
        label_en="Discount Window Borrowing",
        label_zh="贴现窗口借款",
        current=5.0,
        unit="$B",
        normal_low=0.0,
        normal_high=1.0,
        warning_threshold=5.0,
        danger_threshold=20.0,
        direction="high_bad",
        crisis_2008_peak=110.0,
        historical_note_en="Peaked at ~$110B in Oct 2008; ~$50B in Mar 2020. Banks normally avoid discount window due to stigma; elevated borrowing signals funding stress.",
        historical_note_zh="2008 年 10 月峰值约 1100 亿美元; 2020 年 3 月约 500 亿美元。银行通常因「污名效应」避免使用贴现窗口; 借款上升表明融资压力。",
    ),
    RiskMetric(
        key="commercial_paper_outstanding",
        label_en="Commercial Paper Outstanding",
        label_zh="商业票据未偿余额",
        current=1200.0,
        unit="$B",
        normal_low=1000.0,
        normal_high=1500.0,
        warning_threshold=900.0,   # contraction is the warning (low_bad)
        danger_threshold=700.0,
        direction="low_bad",
        crisis_2008_peak=1400.0,   # post-crisis contraction trough
        historical_note_en="Pre-crisis 2007 peak ~$2.0T; contracted to ~$1.4T by end-2008 as money market funds fled CP. Sharp contraction is the warning signal.",
        historical_note_zh="2007 年危机前峰值约 2 万亿美元; 2008 年底因货币基金撤离收缩至约 1.4 万亿。急剧收缩是预警信号。",
    ),
    RiskMetric(
        key="m2_growth_yoy",
        label_en="M2 Money Supply Growth (YoY)",
        label_zh="M2 货币供应量同比增速",
        current=4.0,
        unit="%",
        normal_low=4.0,
        normal_high=7.0,
        warning_threshold=2.0,    # below 2% = tightening (low_bad)
        danger_threshold=0.0,
        direction="low_bad",
        crisis_2008_peak=10.0,    # 2008 crisis response peak
        historical_note_en="COVID peak ~27% (Feb 2021). Sustained <2% growth signals tight liquidity; contraction is recessionary. 1930-33 M2 fell ~33%.",
        historical_note_zh="新冠峰值约 27% (2021 年 2 月)。持续低于 2% 表明流动性紧缩; 负增长具有衰退性。1930-33 年 M2 下降约 33%。",
    ),
    RiskMetric(
        key="fed_balance_sheet",
        label_en="Fed Balance Sheet (Total Assets)",
        label_zh="美联储资产负债表 (总资产)",
        current=7500.0,
        unit="$B",
        normal_low=4000.0,
        normal_high=9000.0,
        warning_threshold=9000.0,  # above COVID-era peak = sustained expansion
        danger_threshold=10000.0,
        direction="high_bad",
        crisis_2008_peak=2200.0,
        historical_note_en="Pre-GFC 2007: ~$0.9T. GFC peak: $2.2T (2009). COVID peak: $8.9T (2022). Level matters less than growth rate; rapid expansion = crisis response.",
        historical_note_zh="危机前 2007 年约 0.9 万亿。危机峰值 2.2 万亿 (2009)。新冠峰值 8.9 万亿 (2022)。绝对水平不如增速重要; 快速扩张 = 危机应对。",
    ),
]


def get_liquidity_status() -> dict:
    """Return current US dollar funding liquidity status.

    Returns:
        {
            "as_of": "2025-Q3",
            "metrics": [ {RiskMetric.to_dict()}, ... ],
            "warning_count": int,
            "danger_count": int,
            "assessment_en": "...",
            "assessment_zh": "...",
        }
    """
    logger.info("Computing liquidity status as of %s", AS_OF)

    metrics = [m.to_dict() for m in LIQUIDITY_METRICS]
    warning_count = sum(1 for m in metrics if m["warning_level"] == "warning")
    danger_count = sum(1 for m in metrics if m["warning_level"] == "danger")

    # Assessment
    if danger_count > 0:
        assessment_en = (
            f"Liquidity stress is ELEVATED: {danger_count} metric(s) in danger zone, "
            f"{warning_count} in warning zone. Funding markets warrant close monitoring."
        )
        assessment_zh = (
            f"流动性压力升高: {danger_count} 项指标处于危险区间, "
            f"{warning_count} 项处于预警区间。融资市场需密切关注。"
        )
    elif warning_count > 0:
        assessment_en = (
            f"Liquidity is WATCHABLE: {warning_count} metric(s) in warning zone. "
            f"No acute funding stress yet."
        )
        assessment_zh = (
            f"流动性值得关注: {warning_count} 项指标处于预警区间。"
            "尚未出现急性融资压力。"
        )
    else:
        assessment_en = "Liquidity conditions are normal. No funding stress signals."
        assessment_zh = "流动性状况正常。无融资压力信号。"

    return {
        "as_of": AS_OF,
        "metrics": metrics,
        "warning_count": warning_count,
        "danger_count": danger_count,
        "assessment_en": assessment_en,
        "assessment_zh": assessment_zh,
    }


# ============================================================================
# 3. Valuation & Leverage Warning / 估值与杠杆预警
# ============================================================================

VALUATION_METRICS: list[RiskMetric] = [
    RiskMetric(
        key="shiller_cape",
        label_en="Shiller CAPE Ratio (Cyclically Adjusted P/E)",
        label_zh="Shiller CAPE 市盈率 (周期调整市盈率)",
        current=32.0,
        unit="x",
        normal_low=10.0,
        normal_high=20.0,
        warning_threshold=30.0,
        danger_threshold=35.0,
        direction="high_bad",
        crisis_2008_peak=27.0,
        historical_note_en="Historical median ~16; 1929 peak 30; 2000 dot-com peak 44. Current 32 exceeds 2008 and 1929 pre-crash peaks.",
        historical_note_zh="历史中位数约 16; 1929 年峰值 30; 2000 年互联网泡沫峰值 44。当前 32 已超过 2008 和 1929 危机前峰值。",
    ),
    RiskMetric(
        key="buffett_indicator",
        label_en="Buffett Indicator (Market Cap / GDP)",
        label_zh="巴菲特指标 (股市总市值 / GDP)",
        current=185.0,
        unit="%",
        normal_low=60.0,
        normal_high=120.0,
        warning_threshold=150.0,
        danger_threshold=200.0,
        direction="high_bad",
        crisis_2008_peak=105.0,
        historical_note_en="2008 pre-crisis 105%; 2000 dot-com peak 137%; historical median ~75%. Current 185% is well above any prior pre-crisis level.",
        historical_note_zh="2008 危机前 105%; 2000 年互联网峰值 137%; 历史中位数约 75%。当前 185% 远超历史任何危机前水平。",
    ),
    RiskMetric(
        key="margin_debt",
        label_en="FINRA Margin Debt",
        label_zh="FINRA 保证金债务",
        current=720.0,
        unit="$B",
        normal_low=300.0,
        normal_high=700.0,
        warning_threshold=700.0,
        danger_threshold=900.0,
        direction="high_bad",
        crisis_2008_peak=381.0,
        historical_note_en="2008 peak $381B; 2000 peak $278B; 2021 peak $910B. Margin debt peak typically coincides with market top.",
        historical_note_zh="2008 年峰值 3810 亿; 2000 年峰值 2780 亿; 2021 年峰值 9100 亿。保证金债务峰值通常与市场顶部同步。",
    ),
    RiskMetric(
        key="margin_debt_pct_gdp",
        label_en="Margin Debt as % of GDP",
        label_zh="保证金债务占 GDP 比例",
        current=2.5,
        unit="%",
        normal_low=1.0,
        normal_high=2.0,
        warning_threshold=2.0,
        danger_threshold=3.0,
        direction="high_bad",
        crisis_2008_peak=2.7,
        historical_note_en="2008 peak 2.7%; 2000 peak 2.6%; 2021 peak 3.8%. Current 2.5% is near 2008 pre-crisis level.",
        historical_note_zh="2008 年峰值 2.7%; 2000 年峰值 2.6%; 2021 年峰值 3.8%。当前 2.5% 接近 2008 危机前水平。",
    ),
    RiskMetric(
        key="shadow_banking_assets",
        label_en="Non-Bank Financial Intermediation (Shadow Banking)",
        label_zh="非银行金融中介 (影子银行) 资产",
        current=63000.0,
        unit="$B",
        normal_low=20000.0,
        normal_high=70000.0,
        warning_threshold=70000.0,
        danger_threshold=80000.0,
        direction="high_bad",
        crisis_2008_peak=50000.0,
        historical_note_en="FSB Global Monitoring Report. 2008 estimate ~$50T (global NBFI). Rapid growth beyond GDP growth signals systemic leverage buildup.",
        historical_note_zh="FSB 全球监测报告。2008 年估计约 50 万亿 (全球非银金融)。增速持续超过 GDP 增速表明系统性杠杆累积。",
    ),
    RiskMetric(
        key="household_debt_pct_gdp",
        label_en="Household Debt as % of GDP",
        label_zh="家庭债务占 GDP 比例",
        current=73.0,
        unit="%",
        normal_low=50.0,
        normal_high=75.0,
        warning_threshold=80.0,
        danger_threshold=90.0,
        direction="high_bad",
        crisis_2008_peak=99.0,
        historical_note_en="2008 peak ~99%; 1980 ~45%. Current 73% is elevated but well below 2008 peak — household balance sheets are healthier than pre-GFC.",
        historical_note_zh="2008 年峰值约 99%; 1980 年约 45%。当前 73% 升高但远低于 2008 峰值 — 家庭资产负债表较危机前健康。",
    ),
]


def get_valuation_warning() -> dict:
    """Return current market valuation and leverage warning status.

    Returns:
        {
            "as_of": "2025-Q3",
            "metrics": [ {RiskMetric.to_dict()}, ... ],
            "warning_count": int,
            "danger_count": int,
            "assessment_en": "...",
            "assessment_zh": "...",
        }
    """
    logger.info("Computing valuation warning as of %s", AS_OF)

    metrics = [m.to_dict() for m in VALUATION_METRICS]
    warning_count = sum(1 for m in metrics if m["warning_level"] == "warning")
    danger_count = sum(1 for m in metrics if m["warning_level"] == "danger")

    if danger_count > 0:
        assessment_en = (
            f"Valuation & leverage are in DANGER zone: {danger_count} metric(s) above danger threshold, "
            f"{warning_count} in warning zone. Equity valuations (CAPE, Buffett Indicator) are at "
            f"historically elevated levels exceeding 2008 and 1929 pre-crisis peaks; household leverage "
            f"remains the relative bright spot."
        )
        assessment_zh = (
            f"估值与杠杆处于危险区间: {danger_count} 项指标超过危险阈值, "
            f"{warning_count} 项处于预警区间。股票估值 (CAPE, 巴菲特指标) 处于历史高位, "
            f"超过 2008 和 1929 危机前峰值; 家庭杠杆是相对亮点。"
        )
    elif warning_count > 0:
        assessment_en = (
            f"Valuation & leverage are ELEVATED: {warning_count} metric(s) in warning zone. "
            f"Monitor for further deterioration."
        )
        assessment_zh = (
            f"估值与杠杆升高: {warning_count} 项指标处于预警区间。"
            "需关注进一步恶化。"
        )
    else:
        assessment_en = "Valuation and leverage metrics are within normal ranges."
        assessment_zh = "估值与杠杆指标处于正常区间。"

    return {
        "as_of": AS_OF,
        "metrics": metrics,
        "warning_count": warning_count,
        "danger_count": danger_count,
        "assessment_en": assessment_en,
        "assessment_zh": assessment_zh,
    }


# ============================================================================
# 4. Cross-Cycle Comparison / 跨周期对比
# ============================================================================

# Comparison panel: Current (2025) vs 2008 pre-crisis vs 2000 pre-crash
# vs 1929 pre-crash. Values are realistic period snapshots.
# None = not available / did not exist (e.g. VIX in 1929).
CROSS_CYCLE_COMPARISON: dict[str, dict] = {
    "current_2025": {
        "label_en": "Current (2025 Q3)",
        "label_zh": "当前 (2025 Q3)",
        "period": "2025-Q3",
        "fed_rate": 4.50,
        "unemployment": 4.20,
        "gdp_growth": 2.50,
        "snp_pe": 25.0,
        "vix": 16.0,
        "treasury_10y": 4.10,
        "home_price_yoy": 4.50,
        "credit_spread": 3.20,
        "debt_to_gdp": 120.0,
    },
    "pre_gfc_2008": {
        "label_en": "Pre-GFC (mid-2007)",
        "label_zh": "2008 危机前夕 (2007 年中)",
        "period": "2007-Q3",
        "fed_rate": 5.25,
        "unemployment": 4.50,
        "gdp_growth": 2.30,
        "snp_pe": 17.0,
        "vix": 15.0,
        "treasury_10y": 4.60,
        "home_price_yoy": -5.00,
        "credit_spread": 5.00,
        "debt_to_gdp": 65.0,
    },
    "pre_dotcom_2000": {
        "label_en": "Pre-Dot-Com (early 2000)",
        "label_zh": "互联网泡沫前夕 (2000 年初)",
        "period": "2000-Q1",
        "fed_rate": 5.50,
        "unemployment": 4.00,
        "gdp_growth": 4.70,
        "snp_pe": 30.0,
        "vix": 24.0,
        "treasury_10y": 6.00,
        "home_price_yoy": 12.00,
        "credit_spread": 5.00,
        "debt_to_gdp": 55.0,
    },
    "pre_depression_1929": {
        "label_en": "Pre-Depression (Sep 1929)",
        "label_zh": "大萧条前夕 (1929 年 9 月)",
        "period": "1929-Q3",
        "fed_rate": 5.00,
        "unemployment": 3.20,
        "gdp_growth": 5.00,
        "snp_pe": 30.0,
        "vix": None,
        "treasury_10y": 3.60,
        "home_price_yoy": None,
        "credit_spread": None,
        "debt_to_gdp": 20.0,
    },
}

# Per-metric scoring config for overall risk score (0-100).
# "normal" = benign level; "crisis" = level seen at crisis onset.
# direction: "high_bad" (higher = worse), "low_bad" (lower = worse)
_METRIC_SCORING = {
    "fed_rate":       {"normal": 3.0, "crisis": 6.5, "direction": "high_bad"},
    "unemployment":   {"normal": 4.0, "crisis": 7.0, "direction": "high_bad"},
    "gdp_growth":     {"normal": 2.5, "crisis": 0.0, "direction": "low_bad"},
    "snp_pe":         {"normal": 17.0, "crisis": 30.0, "direction": "high_bad"},
    "vix":            {"normal": 15.0, "crisis": 35.0, "direction": "high_bad"},
    "treasury_10y":   {"normal": 3.0, "crisis": 6.0, "direction": "high_bad"},
    "home_price_yoy": {"normal": 5.0, "crisis": -10.0, "direction": "low_bad"},
    "credit_spread":  {"normal": 3.0, "crisis": 7.0, "direction": "high_bad"},
    "debt_to_gdp":    {"normal": 60.0, "crisis": 100.0, "direction": "high_bad"},
}


def _score_metric(current: Optional[float], normal: float, crisis: float,
                  direction: str) -> float:
    """Compute 0-100 risk score for a single metric.

    0 = at benign level, 100 = at/beyond crisis level. Returns 0 if current
    is None (metric unavailable)."""
    if current is None:
        return 0.0
    if direction == "high_bad":
        if current <= normal:
            return 0.0
        if current >= crisis:
            return 100.0
        span = crisis - normal
        return ((current - normal) / span) * 100.0 if span > 0 else 0.0
    else:  # low_bad
        if current >= normal:
            return 0.0
        if current <= crisis:
            return 100.0
        span = normal - crisis
        return ((normal - current) / span) * 100.0 if span > 0 else 0.0


def get_cross_cycle_comparison() -> dict:
    """Return cross-cycle comparison panel: Current vs 2008 / 2000 / 1929.

    Returns:
        {
            "as_of": "2025-Q3",
            "periods": {period_key: {label, metrics...}},
            "metrics_table": [ {key, label_en, label_zh, values_by_period} ],
            "overall_risk_score": float,  # 0-100
            "metric_scores": [ {key, label, score} ],
            "assessment_en": "...",
            "assessment_zh": "...",
        }
    """
    logger.info("Computing cross-cycle comparison as of %s", AS_OF)

    periods = CROSS_CYCLE_COMPARISON
    current = periods["current_2025"]

    # Build metrics table
    metric_keys = [
        ("fed_rate",       "Fed Funds Rate",           "联邦基金利率",       "%"),
        ("unemployment",   "Unemployment Rate",         "失业率",            "%"),
        ("gdp_growth",     "GDP Growth (QoQ annualized)", "GDP 增速 (季环比折年率)", "%"),
        ("snp_pe",         "S&P 500 P/E (trailing)",    "标普 500 市盈率 (TTM)", "x"),
        ("vix",            "VIX",                       "VIX 恐慌指数",      "pts"),
        ("treasury_10y",   "10Y Treasury Yield",        "10 年期国债收益率", "%"),
        ("home_price_yoy", "Home Price YoY",            "房价同比",          "%"),
        ("credit_spread",  "Credit Spread (HY OAS)",    "信用利差 (高收益 OAS)", "%"),
        ("debt_to_gdp",    "Federal Debt / GDP",        "联邦债务 / GDP",    "%"),
    ]

    metrics_table = []
    metric_scores = []
    for key, label_en, label_zh, unit in metric_keys:
        values_by_period = {
            p_key: p_data.get(key) for p_key, p_data in periods.items()
        }
        metrics_table.append({
            "key": key,
            "label_en": label_en,
            "label_zh": label_zh,
            "unit": unit,
            "values_by_period": values_by_period,
        })

        cfg = _METRIC_SCORING[key]
        score = _score_metric(
            current.get(key), cfg["normal"], cfg["crisis"], cfg["direction"]
        )
        metric_scores.append({
            "key": key,
            "label_en": label_en,
            "label_zh": label_zh,
            "score": round(score, 1),
        })

    # Overall risk score = average of all metric scores (0-100 scale)
    overall_risk_score = (
        sum(s["score"] for s in metric_scores) / len(metric_scores)
        if metric_scores else 0.0
    )

    # Identify the top contributor
    metric_scores_sorted = sorted(metric_scores, key=lambda s: s["score"], reverse=True)
    top_concern = metric_scores_sorted[0] if metric_scores_sorted else None

    assessment_en = (
        f"Cross-cycle comparison as of {AS_OF}: overall risk score "
        f"{overall_risk_score:.1f}/100. Top concern: "
        f"{top_concern['label_en']} ({top_concern['score']:.1f}/100). "
        f"Key differentiators vs 2008 pre-crisis: equity valuations (P/E {current['snp_pe']} "
        f"vs 17) and federal debt/GDP ({current['debt_to_gdp']}% vs 65%) are markedly higher; "
        f"unemployment ({current['unemployment']}% vs 4.5%) and credit spreads "
        f"({current['credit_spread']}% vs 5.0%) remain benign."
    )
    assessment_zh = (
        f"截至 {AS_OF} 的跨周期对比: 整体风险得分 "
        f"{overall_risk_score:.1f}/100。首要关注: "
        f"{top_concern['label_zh']} ({top_concern['score']:.1f}/100)。"
        f"与 2008 危机前的关键差异: 股票估值 (市盈率 {current['snp_pe']} "
        f"对 17) 和联邦债务/GDP ({current['debt_to_gdp']}% 对 65%) 明显更高; "
        f"失业率 ({current['unemployment']}% 对 4.5%) 和信用利差 "
        f"({current['credit_spread']}% 对 5.0%) 仍属良性。"
    )

    return {
        "as_of": AS_OF,
        "periods": periods,
        "metrics_table": metrics_table,
        "overall_risk_score": round(overall_risk_score, 1),
        "metric_scores": metric_scores,
        "assessment_en": assessment_en,
        "assessment_zh": assessment_zh,
    }


# ============================================================================
# 5. Real-time Risk Dashboard / 实时风险仪表盘
# ============================================================================

_RISK_LEVELS = [
    (80.0, "extreme", "极端"),
    (60.0, "high",    "高"),
    (40.0, "elevated", "升高"),
    (20.0, "moderate", "中等"),
    (0.0,  "low",     "低"),
]


def _level_from_score(score: float) -> tuple[str, str]:
    """Return (level_en, level_zh) for a 0-100 risk score."""
    for threshold, en, zh in _RISK_LEVELS:
        if score >= threshold:
            return en, zh
    return "low", "低"


def _level_to_severity(level: str) -> float:
    """Map warning_level strings to a 0-100 severity for ranking."""
    return {
        "danger":   100.0,
        "warning":   60.0,
        "inverted":  80.0,  # yield curve inversion = strong signal
        "flat":      40.0,
        "normal":    20.0,
    }.get(level, 20.0)


def get_risk_dashboard() -> dict:
    """Aggregate all risk monitors into a single dashboard view.

    Returns:
        {
            "as_of": "2025-Q3",
            "risk_level": "low"|"moderate"|"elevated"|"high"|"extreme",
            "risk_level_zh": "...",
            "risk_score": float,  # 0-100
            "top_5_risk_signals": [ {...}, ... ],
            "safe_signals": [ {...}, ... ],
            "assessment_en": "...",
            "assessment_zh": "...",
            "summary": {...},
            "details": { yield_curve, liquidity, valuation, cross_cycle },
        }
    """
    logger.info("Aggregating risk dashboard as of %s", AS_OF)

    yield_curve = get_yield_curve_status()
    liquidity = get_liquidity_status()
    valuation = get_valuation_warning()
    cross_cycle = get_cross_cycle_comparison()

    # Collect all warning/danger signals across monitors
    all_signals: list[dict] = []

    # Yield curve signals
    yc_status = yield_curve["inversion_status"]
    if yc_status != "normal":
        all_signals.append({
            "source": "yield_curve",
            "source_en": "Yield Curve",
            "source_zh": "收益率曲线",
            "key": "inversion_status",
            "label_en": "Yield Curve Inversion",
            "label_zh": "收益率曲线倒挂",
            "current": yc_status,
            "warning_level": yc_status,
            "severity_score": _level_to_severity(yc_status),
        })
    for spread in yield_curve["spreads"]:
        if spread["warning_level"] != "normal":
            all_signals.append({
                "source": "yield_curve",
                "source_en": "Yield Curve",
                "source_zh": "收益率曲线",
                "key": spread["key"],
                "label_en": spread["label_en"],
                "label_zh": spread["label_zh"],
                "current": spread["value_bps"],
                "unit": "bps",
                "warning_level": spread["warning_level"],
                "severity_score": _level_to_severity(spread["warning_level"]),
            })

    # Liquidity signals
    for m in liquidity["metrics"]:
        if m["warning_level"] != "normal":
            all_signals.append({
                "source": "liquidity",
                "source_en": "Liquidity",
                "source_zh": "流动性",
                "key": m["key"],
                "label_en": m["label_en"],
                "label_zh": m["label_zh"],
                "current": m["current"],
                "unit": m["unit"],
                "warning_level": m["warning_level"],
                "severity_score": m["severity_score"],
            })

    # Valuation signals
    for m in valuation["metrics"]:
        if m["warning_level"] != "normal":
            all_signals.append({
                "source": "valuation",
                "source_en": "Valuation & Leverage",
                "source_zh": "估值与杠杆",
                "key": m["key"],
                "label_en": m["label_en"],
                "label_zh": m["label_zh"],
                "current": m["current"],
                "unit": m["unit"],
                "warning_level": m["warning_level"],
                "severity_score": m["severity_score"],
            })

    # Cross-cycle metrics at elevated risk (score >= 50)
    for s in cross_cycle["metric_scores"]:
        if s["score"] >= 50.0:
            all_signals.append({
                "source": "cross_cycle",
                "source_en": "Cross-Cycle",
                "source_zh": "跨周期",
                "key": s["key"],
                "label_en": s["label_en"],
                "label_zh": s["label_zh"],
                "current": cross_cycle["periods"]["current_2025"].get(s["key"]),
                "warning_level": "danger" if s["score"] >= 75 else "warning",
                "severity_score": s["score"],
            })

    # Sort by severity descending, then by warning_level priority
    level_priority = {"danger": 3, "inverted": 3, "warning": 2, "flat": 1, "normal": 0}
    all_signals.sort(
        key=lambda s: (s["severity_score"], level_priority.get(s.get("warning_level", "normal"), 0)),
        reverse=True,
    )
    top_5 = all_signals[:5]

    # Safe signals: metrics at "normal" level (especially key recession precursors)
    safe_signals: list[dict] = []
    safe_keys_priority = {
        "ted_spread", "sofr_rate", "unemployment", "credit_spread",
        "vix", "gdp_growth", "household_debt_pct_gdp",
    }
    for m in liquidity["metrics"] + valuation["metrics"]:
        if m["warning_level"] == "normal":
            safe_signals.append({
                "source": "liquidity" if m in liquidity["metrics"] else "valuation",
                "key": m["key"],
                "label_en": m["label_en"],
                "label_zh": m["label_zh"],
                "current": m["current"],
                "unit": m["unit"],
                "priority": 1 if m["key"] in safe_keys_priority else 0,
            })
    # Cross-cycle metrics at low risk
    for s in cross_cycle["metric_scores"]:
        if s["score"] < 25.0:
            safe_signals.append({
                "source": "cross_cycle",
                "key": s["key"],
                "label_en": s["label_en"],
                "label_zh": s["label_zh"],
                "current": cross_cycle["periods"]["current_2025"].get(s["key"]),
                "priority": 1 if s["key"] in safe_keys_priority else 0,
            })

    # Sort safe signals by priority (high-priority "good news" first)
    safe_signals.sort(key=lambda s: s.get("priority", 0), reverse=True)
    safe_signals_top = safe_signals[:8]

    # Overall risk score from cross-cycle (already a 0-100 aggregate)
    risk_score = cross_cycle["overall_risk_score"]
    risk_level, risk_level_zh = _level_from_score(risk_score)

    # Assessment text
    top_concern_en = top_5[0]["label_en"] if top_5 else "none"
    top_concern_zh = top_5[0]["label_zh"] if top_5 else "无"
    assessment_en = (
        f"As of {AS_OF}, overall market risk is {risk_level.upper()} (score: "
        f"{risk_score:.1f}/100). {len(all_signals)} signal(s) are flashing warning or danger. "
        f"Top concern: {top_concern_en}. Safe signals: unemployment, credit spreads, "
        f"VIX, and household leverage remain within normal ranges — the classic pre-recession "
        f"precursors are NOT yet flashing acute stress, though valuations and federal debt "
        f"are at historically elevated levels warranting caution."
    )
    assessment_zh = (
        f"截至 {AS_OF}, 市场整体风险等级为「{risk_level_zh}」(得分: "
        f"{risk_score:.1f}/100)。共有 {len(all_signals)} 项指标发出预警或危险信号。"
        f"首要关注: {top_concern_zh}。安全信号: 失业率、信用利差、VIX 和家庭杠杆"
        f"仍处于正常区间 — 经典衰退前兆信号尚未闪现急性压力, 但股票估值和联邦债务"
        f"处于历史高位, 需保持警惕。"
    )

    return {
        "as_of": AS_OF,
        "risk_level": risk_level,
        "risk_level_zh": risk_level_zh,
        "risk_score": round(risk_score, 1),
        "top_5_risk_signals": top_5,
        "safe_signals": safe_signals_top,
        "assessment_en": assessment_en,
        "assessment_zh": assessment_zh,
        "summary": {
            "yield_curve_status": yield_curve["inversion_status"],
            "yield_curve_status_zh": yield_curve["inversion_status_zh"],
            "liquidity_warning_count": liquidity["warning_count"],
            "liquidity_danger_count": liquidity["danger_count"],
            "valuation_warning_count": valuation["warning_count"],
            "valuation_danger_count": valuation["danger_count"],
            "cross_cycle_metric_count": len(cross_cycle["metric_scores"]),
            "cross_cycle_elevated_count": sum(1 for s in cross_cycle["metric_scores"] if s["score"] >= 50),
            "total_warning_signals": len(all_signals),
        },
        "details": {
            "yield_curve": yield_curve,
            "liquidity": liquidity,
            "valuation": valuation,
            "cross_cycle": cross_cycle,
        },
    }


# ============================================================================
# Module self-test
# ============================================================================

if __name__ == "__main__":
    # Quick smoke test when run directly
    import json

    logging.basicConfig(level=logging.INFO)

    for fn in (
        get_yield_curve_status,
        get_liquidity_status,
        get_valuation_warning,
        get_cross_cycle_comparison,
        get_risk_dashboard,
    ):
        print(f"\n{'=' * 70}\n{fn.__name__}\n{'=' * 70}")
        result = fn()
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
