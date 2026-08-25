"""Crisis Recovery & Policy Simulation Module / 危机恢复与政策推演模块

Module 3 of the investment-os financial crisis research system.

Provides a crisis-recovery policy toolbox, a combined-effect policy simulator,
a risk transmission path knowledge graph, a recovery capacity dashboard, and
a historical policy comparison. Five public functions cover the major
crisis-response dimensions:

    1. get_policy_toolbox()           — Central bank / fiscal / regulatory tools
    2. simulate_policies(...)          — Combined-effect simulation of selected tools
    3. get_risk_transmission_paths()   — Knowledge-graph of 2008-style contagion
    4. get_transmission_graph()        — Nodes + edges formatted for visualization
    5. get_recovery_dashboard()        — Current monetary/fiscal/banking space
    6. get_historical_policies()       — Crisis-by-crisis policy comparison

All current values reflect a realistic 2025-Q3 snapshot. Historical figures
are accurate to published sources (TARP, ARRA, CARES, IMF, FOMC, FDIC, BIS,
FCIC report). Every public function returns a plain dict (JSON-serializable);
dataclasses are used internally for type safety.

Reference data sources (cited for context; not live-fetched):
    - Federal Reserve (FOMC statements, balance sheet, H.4.1, H.8)
    - U.S. Treasury (debt outstanding, monthly statement, TARP reports)
    - FDIC (call reports, stress test results, QBP)
    - Congressional Budget Office (budget outlook, debt ceiling)
    - IMF (World Economic Outlook, GFSR)
    - FCIC Final Report (2011); NBER crisis dating
    - BIS Annual Reports
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("investment-os.policy_simulator")

AS_OF = "2025-Q3"


# ============================================================================
# Dataclasses for type safety
# ============================================================================

@dataclass
class PolicyTool:
    """A single crisis-response policy tool.

    category:
        "central_bank" / "fiscal" / "regulatory"
    time_to_effect:
        "immediate" (days) / "short" (weeks) / "medium" (1-2 quarters) / "long" (multi-quarter)
    """
    id: str
    name_zh: str
    name_en: str
    category: str
    description_zh: str
    description_en: str
    typical_scale: str
    time_to_effect: str
    historical_usage: list[str] = field(default_factory=list)


@dataclass
class TransmissionEdge:
    """A single risk transmission path between two nodes."""
    from_node: str
    to_node: str
    description_zh: str
    description_en: str
    transmission_speed: str  # "fast" (days/weeks) / "slow" (months/quarters)
    severity: str            # "high" / "medium" / "low"


# ============================================================================
# 1. Policy Toolbox Data (政策工具箱)
# ============================================================================

CENTRAL_BANK_TOOLS: list[PolicyTool] = [
    PolicyTool(
        id="rate_cut",
        name_zh="政策利率下调",
        name_en="Policy Rate Cut",
        category="central_bank",
        description_zh="降低联邦基金利率目标区间,降低全社会的融资成本,刺激信贷需求。",
        description_en="Lower the federal funds rate target range to reduce economy-wide funding costs and stimulate credit demand.",
        typical_scale="单次 25-100 个基点;周期累计可达 500+ 基点",
        time_to_effect="short",
        historical_usage=["gfc_2008", "dotcom_2000", "covid_2020", "asia_1997"],
    ),
    PolicyTool(
        id="qe",
        name_zh="量化宽松 (QE)",
        name_en="Quantitative Easing",
        category="central_bank",
        description_zh="美联储大规模购买国债和抵押贷款支持证券 (MBS),扩张资产负债表,压低长端利率。",
        description_en="Fed purchases large-scale Treasuries and MBS to expand the balance sheet and compress long-term yields.",
        typical_scale="万亿美元级别 (QE1 $1.75T, COVID 无上限)",
        time_to_effect="medium",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="forward_guidance",
        name_zh="前瞻性指引",
        name_en="Forward Guidance",
        category="central_bank",
        description_zh="通过沟通未来政策路径预期,影响市场对利率的定价,降低不确定性。",
        description_en="Communicate the expected future policy path to shape market rate pricing and reduce uncertainty.",
        typical_scale="政策声明、纪要、主席讲话",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="discount_window",
        name_zh="贴现窗口",
        name_en="Discount Window Lending",
        category="central_bank",
        description_zh="向存款机构提供贴现贷款,缓解短期流动性压力;正常时期存在使用污名。",
        description_en="Provide discount loans to depository institutions to relieve short-term liquidity stress; carries stigma in normal times.",
        typical_scale="数十至数百亿美元",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="swap_lines",
        name_zh="央行美元互换额度",
        name_en="Central Bank Swap Lines",
        category="central_bank",
        description_zh="美联储与主要央行建立美元互换额度,向全球市场提供美元流动性,缓解海外美元荒。",
        description_en="Fed establishes swap lines with major central banks to supply dollar liquidity globally and relieve offshore dollar shortages.",
        typical_scale="与 14 家央行;单周可达数千亿美元",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="repo_operations",
        name_zh="回购市场操作",
        name_en="Repo Market Operations",
        category="central_bank",
        description_zh="通过隔夜/定期回购向一级交易商提供资金,稳定回购市场,压低回购利率。",
        description_en="Provide overnight/term repo to primary dealers to stabilize the repo market and suppress repo rates.",
        typical_scale="单日数千亿美元",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="pDCF",
        name_zh="一级交易商信用工具 (PDCF)",
        name_en="Primary Dealer Credit Facility",
        category="central_bank",
        description_zh="向一级交易商 (含投行) 提供隔夜抵押贷款,使其能像存款机构一样获得美联储流动性。",
        description_en="Provide overnight collateralized loans to primary dealers (including investment banks), giving them discount-window-like access to Fed liquidity.",
        typical_scale="数百亿美元",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="mMLF",
        name_zh="货币市场共同基金流动性工具 (MMLF)",
        name_en="Money Market Mutual Fund Liquidity Facility",
        category="central_bank",
        description_zh="向银行提供贷款,用于购买货币市场基金资产,阻止 MMF 大规模赎回 (挤兑)。",
        description_en="Lend to banks to purchase money market fund assets, halting MMF runs (e.g. post-Reserve Primary break-the-buck).",
        typical_scale="数百亿美元",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
]

FISCAL_TOOLS: list[PolicyTool] = [
    PolicyTool(
        id="fiscal_stimulus",
        name_zh="财政刺激一揽子",
        name_en="Fiscal Stimulus Package",
        category="fiscal",
        description_zh="政府综合财政刺激方案,通常包含减税、转移支付、基建与州政府援助。",
        description_en="A comprehensive fiscal package typically combining tax cuts, transfers, infrastructure, and state-aid.",
        typical_scale="占 GDP 5-10% (ARRA $787B, CARES $2.2T)",
        time_to_effect="medium",
        historical_usage=["gfc_2008", "covid_2020", "great_depression_1929"],
    ),
    PolicyTool(
        id="tax_cut",
        name_zh="减税",
        name_en="Tax Cuts",
        category="fiscal",
        description_zh="降低个人或企业所得税,提升家庭可支配收入和企业现金流,刺激消费与投资。",
        description_en="Cut personal or corporate income taxes to raise disposable income and corporate cash flow, stimulating consumption and investment.",
        typical_scale="十年期 1-2 万亿美元 (EGTRRA $1.35T)",
        time_to_effect="medium",
        historical_usage=["dotcom_2000", "gfc_2008"],
    ),
    PolicyTool(
        id="infrastructure",
        name_zh="基础设施投资",
        name_en="Infrastructure Investment",
        category="fiscal",
        description_zh="政府直接投资公路、桥梁、电网、宽带等基础设施,创造就业并提升长期产能。",
        description_en="Direct government investment in roads, bridges, grid, and broadband to create jobs and raise long-run capacity.",
        typical_scale="数千亿美元",
        time_to_effect="long",
        historical_usage=["great_depression_1929", "gfc_2008"],
    ),
    PolicyTool(
        id="direct_payments",
        name_zh="直接支付 (支票)",
        name_en="Direct Payments (Stimulus Checks)",
        category="fiscal",
        description_zh="向家庭直接发放现金支票,迅速支撑消费支出,缓解短期需求冲击。",
        description_en="Send cash checks directly to households to quickly support consumption and offset demand shocks.",
        typical_scale="每成人 $1200-2000;总规模数千亿美元",
        time_to_effect="short",
        historical_usage=["covid_2020", "gfc_2008"],
    ),
    PolicyTool(
        id="unemployment_benefit",
        name_zh="失业补助扩展",
        name_en="Expanded Unemployment Benefits",
        category="fiscal",
        description_zh="延长失业保险期限、提高每周补助金额、覆盖零工等非传统就业者。",
        description_en="Extend unemployment insurance duration, raise weekly benefit amounts, and cover non-traditional (gig) workers.",
        typical_scale="每周额外 $300-600;数百至数千亿美元",
        time_to_effect="short",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
    PolicyTool(
        id="ppp_loans",
        name_zh="薪酬保护计划 (PPP)",
        name_en="Paycheck Protection Program",
        category="fiscal",
        description_zh="向中小企业提供可豁免贷款,条件是维持员工薪酬,防止大规模裁员。",
        description_en="Provide forgivable loans to small businesses conditional on maintaining payrolls, preventing mass layoffs.",
        typical_scale="$800B+ (COVID 期间)",
        time_to_effect="short",
        historical_usage=["covid_2020"],
    ),
]

REGULATORY_TOOLS: list[PolicyTool] = [
    PolicyTool(
        id="bank_holiday",
        name_zh="银行假期",
        name_en="Bank Holiday",
        category="regulatory",
        description_zh="全国性关闭银行数日,审计偿付能力后允许稳健银行复业,终止挤兑恐慌。",
        description_en="Nationally close banks for several days; only solvent banks reopen after audit, ending panic runs.",
        typical_scale="全国性,持续 4-8 天",
        time_to_effect="immediate",
        historical_usage=["great_depression_1929"],
    ),
    PolicyTool(
        id="short_sale_ban",
        name_zh="卖空禁令",
        name_en="Short Sale Ban",
        category="regulatory",
        description_zh="临时禁止对金融股 (或全市场) 卖空,试图遏制恐慌性做空,但效果存在争议。",
        description_en="Temporarily ban short selling of financial stocks (or the entire market) to curb panic; effectiveness is debated.",
        typical_scale="799 只金融股 (2008) 或全市场",
        time_to_effect="immediate",
        historical_usage=["gfc_2008"],
    ),
    PolicyTool(
        id="circuit_breaker",
        name_zh="市场熔断机制",
        name_en="Circuit Breaker",
        category="regulatory",
        description_zh="指数下跌 7%/13%/20% 时暂停交易,提供冷静期以防止恐慌性抛售螺旋。",
        description_en="Halt trading at index declines of 7%/13%/20% to provide cooling-off periods and prevent panic spirals.",
        typical_scale="单日 5-15 分钟 (Lv1/Lv2) 或收市 (Lv3)",
        time_to_effect="immediate",
        historical_usage=["covid_2020", "asia_1997"],
    ),
    PolicyTool(
        id="capital_injection",
        name_zh="银行资本注入",
        name_en="Bank Capital Injection",
        category="regulatory",
        description_zh="通过 TARP 等机制向系统重要性银行注资,提升资本充足率,恢复信贷投放能力。",
        description_en="Inject capital into systemically important banks via TARP-like mechanisms to raise capital ratios and restore lending capacity.",
        typical_scale="$700B (TARP 授权);实际注资约 $250B",
        time_to_effect="medium",
        historical_usage=["gfc_2008"],
    ),
    PolicyTool(
        id="deposit_insurance",
        name_zh="存款保险上限提升",
        name_en="Deposit Insurance Limit Raise",
        category="regulatory",
        description_zh="提高 FDIC 存款保险上限 (如 $100K → $250K),并临时担保无息账户,消除储户挤兑动机。",
        description_en="Raise the FDIC insurance limit (e.g. $100K → $250K) and temporarily guarantee non-interest-bearing accounts to remove run incentives.",
        typical_scale="上限提高 + 临时全额担保",
        time_to_effect="immediate",
        historical_usage=["gfc_2008", "great_depression_1929"],
    ),
    PolicyTool(
        id="foreclosure_moratorium",
        name_zh="止赎暂停",
        name_en="Foreclosure Moratorium",
        category="regulatory",
        description_zh="临时禁止银行对违约房贷启动止赎程序,缓解家庭流离失所压力,稳定住房市场。",
        description_en="Temporarily prohibit banks from initiating foreclosure proceedings, reducing household displacement and stabilizing housing.",
        typical_scale="数月至一年",
        time_to_effect="medium",
        historical_usage=["gfc_2008", "covid_2020"],
    ),
]

ALL_POLICY_TOOLS: list[PolicyTool] = (
    CENTRAL_BANK_TOOLS + FISCAL_TOOLS + REGULATORY_TOOLS
)


# ============================================================================
# 2. Policy Effect Coefficients (用于 simulate_policies)
# ============================================================================
# 每个工具对各项指标的边际贡献 (单位与下文 SEVERITY_BASELINES 一致)
#   recovery_months_delta   : 负值 = 缩短恢复时间 (改善)
#   gdp_impact_delta        : 正值 = 提升 GDP (改善, 单位 pp)
#   unemployment_delta      : 负值 = 降低失业率上升幅度 (改善, 单位 pp)
#   inflation_delta         : 正值 = 推升通胀 (副作用, 单位 pp)
#   fiscal_cost_gdp_delta   : 正值 = 增加财政成本 (单位 % GDP)
#   confidence_boost        : 正值 = 提升信心 (0-100 量表)
#   side_effect_risk        : 正值 = 增加副作用风险 (0-100 量表)

POLICY_EFFECTS: dict[str, dict] = {
    "rate_cut":               {"recovery_months_delta": -3, "gdp_impact_delta": 0.6,  "unemployment_delta": -0.5, "inflation_delta": 0.4,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 8,  "side_effect_risk": 5},
    "qe":                     {"recovery_months_delta": -4, "gdp_impact_delta": 1.1,  "unemployment_delta": -1.0, "inflation_delta": 1.0,  "fiscal_cost_gdp_delta": 0.5,  "confidence_boost": 12, "side_effect_risk": 12},
    "forward_guidance":       {"recovery_months_delta": -1, "gdp_impact_delta": 0.2,  "unemployment_delta": -0.2, "inflation_delta": 0.1,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 6,  "side_effect_risk": 2},
    "discount_window":        {"recovery_months_delta": -1, "gdp_impact_delta": 0.3,  "unemployment_delta": -0.2, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 5,  "side_effect_risk": 3},
    "swap_lines":             {"recovery_months_delta": -1, "gdp_impact_delta": 0.4,  "unemployment_delta": -0.3, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 7,  "side_effect_risk": 2},
    "repo_operations":        {"recovery_months_delta": -1, "gdp_impact_delta": 0.3,  "unemployment_delta": -0.2, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 5,  "side_effect_risk": 2},
    "pDCF":                   {"recovery_months_delta": -2, "gdp_impact_delta": 0.5,  "unemployment_delta": -0.4, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 6,  "side_effect_risk": 4},
    "mMLF":                   {"recovery_months_delta": -1, "gdp_impact_delta": 0.3,  "unemployment_delta": -0.2, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 5,  "side_effect_risk": 2},
    "fiscal_stimulus":        {"recovery_months_delta": -3, "gdp_impact_delta": 1.4,  "unemployment_delta": -1.2, "inflation_delta": 0.6,  "fiscal_cost_gdp_delta": 5.0,  "confidence_boost": 12, "side_effect_risk": 8},
    "tax_cut":                {"recovery_months_delta": -2, "gdp_impact_delta": 0.8,  "unemployment_delta": -0.5, "inflation_delta": 0.3,  "fiscal_cost_gdp_delta": 3.0,  "confidence_boost": 7,  "side_effect_risk": 6},
    "infrastructure":         {"recovery_months_delta": -2, "gdp_impact_delta": 1.0,  "unemployment_delta": -1.0, "inflation_delta": 0.4,  "fiscal_cost_gdp_delta": 3.5,  "confidence_boost": 8,  "side_effect_risk": 4},
    "direct_payments":        {"recovery_months_delta": -2, "gdp_impact_delta": 0.9,  "unemployment_delta": -0.6, "inflation_delta": 0.5,  "fiscal_cost_gdp_delta": 3.0,  "confidence_boost": 9,  "side_effect_risk": 5},
    "unemployment_benefit":   {"recovery_months_delta": -1, "gdp_impact_delta": 0.6,  "unemployment_delta": -0.5, "inflation_delta": 0.2,  "fiscal_cost_gdp_delta": 1.5,  "confidence_boost": 6,  "side_effect_risk": 4},
    "ppp_loans":              {"recovery_months_delta": -2, "gdp_impact_delta": 0.7,  "unemployment_delta": -1.0, "inflation_delta": 0.2,  "fiscal_cost_gdp_delta": 3.0,  "confidence_boost": 8,  "side_effect_risk": 5},
    "bank_holiday":           {"recovery_months_delta": -3, "gdp_impact_delta": 0.5,  "unemployment_delta": -0.5, "inflation_delta": -0.2, "fiscal_cost_gdp_delta": 0.5,  "confidence_boost": 10, "side_effect_risk": 6},
    "short_sale_ban":         {"recovery_months_delta": 0,  "gdp_impact_delta": 0.0,  "unemployment_delta": 0.0,  "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 3,  "side_effect_risk": 7},
    "circuit_breaker":        {"recovery_months_delta": 0,  "gdp_impact_delta": 0.0,  "unemployment_delta": 0.0,  "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.0,  "confidence_boost": 2,  "side_effect_risk": 1},
    "capital_injection":      {"recovery_months_delta": -3, "gdp_impact_delta": 1.0,  "unemployment_delta": -0.8, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 2.5,  "confidence_boost": 12, "side_effect_risk": 9},
    "deposit_insurance":      {"recovery_months_delta": -2, "gdp_impact_delta": 0.4,  "unemployment_delta": -0.3, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.5,  "confidence_boost": 10, "side_effect_risk": 3},
    "foreclosure_moratorium": {"recovery_months_delta": -1, "gdp_impact_delta": 0.3,  "unemployment_delta": -0.2, "inflation_delta": 0.0,  "fiscal_cost_gdp_delta": 0.5,  "confidence_boost": 5,  "side_effect_risk": 4},
}

# 不同严重程度下的「不采取任何政策」基线指标
SEVERITY_BASELINES: dict[str, dict] = {
    "mild": {
        "recovery_months": 6,   "gdp_impact": -1.5,  "unemployment_delta": 1.0,
        "inflation_delta": 0.5,  "fiscal_cost_gdp": 1.0,
        "confidence_baseline": 50, "side_effect_baseline": 5,
    },
    "moderate": {
        "recovery_months": 12,  "gdp_impact": -3.0,  "unemployment_delta": 2.5,
        "inflation_delta": 1.0,  "fiscal_cost_gdp": 2.5,
        "confidence_baseline": 40, "side_effect_baseline": 8,
    },
    "severe": {
        "recovery_months": 24,  "gdp_impact": -5.0,  "unemployment_delta": 5.0,
        "inflation_delta": 1.5,  "fiscal_cost_gdp": 5.0,
        "confidence_baseline": 25, "side_effect_baseline": 12,
    },
    "2008-level": {
        "recovery_months": 36,  "gdp_impact": -8.0,  "unemployment_delta": 8.0,
        "inflation_delta": 2.0,  "fiscal_cost_gdp": 8.0,
        "confidence_baseline": 15, "side_effect_baseline": 18,
    },
}


# ============================================================================
# 3. Risk Transmission Paths (风险传导路径)
# ============================================================================
# 节点分类:
#   asset_class    - 资产类 (subprime_mortgages, commercial_paper ...)
#   institution    - 机构 (banks, investment_banks, money_market_funds ...)
#   market         - 市场 (housing_market, repo_market, credit_market, stock_market ...)
#   real_economy   - 实体经济 (real_economy, employment, consumer_spending)

TRANSMISSION_NODES: list[dict] = [
    {"id": "subprime_mortgages",  "label_zh": "次级抵押贷款",       "label_en": "Subprime Mortgages",      "category": "asset_class"},
    {"id": "housing_market",      "label_zh": "房地产市场",         "label_en": "Housing Market",          "category": "market"},
    {"id": "banks",               "label_zh": "商业银行",           "label_en": "Commercial Banks",        "category": "institution"},
    {"id": "investment_banks",    "label_zh": "投资银行",           "label_en": "Investment Banks",        "category": "institution"},
    {"id": "money_market_funds",  "label_zh": "货币市场基金",       "label_en": "Money Market Funds",      "category": "institution"},
    {"id": "commercial_paper",    "label_zh": "商业票据市场",       "label_en": "Commercial Paper Market", "category": "market"},
    {"id": "repo_market",         "label_zh": "回购市场",           "label_en": "Repo Market",             "category": "market"},
    {"id": "credit_market",       "label_zh": "信贷市场",           "label_en": "Credit Market",           "category": "market"},
    {"id": "stock_market",        "label_zh": "股票市场",           "label_en": "Stock Market",            "category": "market"},
    {"id": "real_economy",        "label_zh": "实体经济",           "label_en": "Real Economy",            "category": "real_economy"},
    {"id": "employment",          "label_zh": "就业市场",           "label_en": "Employment",              "category": "real_economy"},
    {"id": "consumer_spending",   "label_zh": "消费支出",           "label_en": "Consumer Spending",       "category": "real_economy"},
    {"id": "corporations",        "label_zh": "非金融企业",         "label_en": "Non-Financial Corporations", "category": "real_economy"},
]

TRANSMISSION_EDGES: list[TransmissionEdge] = [
    # ---- 资产 → 市场/机构 ----
    TransmissionEdge(
        "subprime_mortgages", "housing_market",
        "次贷大规模违约导致房屋被法拍,供给激增压低房价",
        "Mass subprime defaults push foreclosures onto the market, oversupplying and depressing home prices",
        "fast", "high",
    ),
    TransmissionEdge(
        "housing_market", "subprime_mortgages",
        "房价下跌使再融资困难,可调整利率房贷 (ARM) 重置后违约率飙升,形成正反馈",
        "Falling prices block refinancing; ARM resets cause default rates to spike — a positive feedback loop",
        "slow", "high",
    ),
    TransmissionEdge(
        "subprime_mortgages", "banks",
        "银行持有大量 MBS 与 CDO 风险敞口,次贷损失直接侵蚀资本",
        "Banks hold large MBS/CDO exposures; subprime losses directly erode capital",
        "fast", "high",
    ),
    TransmissionEdge(
        "subprime_mortgages", "investment_banks",
        "投行承销并持有 CDO/SIV,表外实体损失回流资产负债表",
        "Investment banks underwrote and held CDOs/SIVs; off-balance-sheet losses return on-balance-sheet",
        "fast", "high",
    ),
    # ---- 机构 → 市场 ----
    TransmissionEdge(
        "banks", "credit_market",
        "银行为自保收紧信贷标准,冻结贷款投放,信贷市场开始停摆",
        "Banks hoard capital, tighten standards, and freeze new lending — credit market seizes up",
        "fast", "high",
    ),
    TransmissionEdge(
        "investment_banks", "repo_market",
        "投行高度依赖回购市场滚动融资,抵押品 (MBS) 估值下降触发追加保证金",
        "IBs rely on repo for funding; falling MBS collateral values trigger margin calls",
        "fast", "high",
    ),
    TransmissionEdge(
        "investment_banks", "credit_market",
        "投行去杠杆抛售资产,信用利差急剧走阔,新发债几乎停滞",
        "IBs deleverage and dump assets; credit spreads blow out, new issuance freezes",
        "fast", "medium",
    ),
    TransmissionEdge(
        "banks", "money_market_funds",
        "银行从 MMF 拆走短期资金,且 MMF 持有银行发行的商业票据和存单",
        "Banks pull short-term funding from MMFs; MMFs also hold bank-issued CP and CDs",
        "fast", "high",
    ),
    # ---- MMF → 商业票据 → 企业 ----
    TransmissionEdge(
        "money_market_funds", "commercial_paper",
        "Reserve Primary 跌破 1 美元后,MMF 大规模赎回导致其停止购买商业票据",
        "After Reserve Primary breaks the buck, MMF redemptions cause them to stop buying commercial paper",
        "fast", "high",
    ),
    TransmissionEdge(
        "commercial_paper", "corporations",
        "非金融企业无法滚动短期商业票据融资,营运资金断裂",
        "Non-financial corporations cannot roll over commercial paper, severing working-capital funding",
        "fast", "high",
    ),
    # ---- 回购 → 信贷 ----
    TransmissionEdge(
        "repo_market", "credit_market",
        "回购市场冻结切断抵押融资渠道,几乎所有依赖短期抵押融资的信贷活动受阻",
        "Repo freeze cuts off collateralized funding; nearly all short-term secured credit activity stalls",
        "fast", "high",
    ),
    # ---- 信贷 → 实体经济 ----
    TransmissionEdge(
        "credit_market", "real_economy",
        "企业无法获得运营和扩张所需的信贷,投资和产出急剧收缩",
        "Businesses lose access to operating and expansion credit; investment and output contract sharply",
        "slow", "high",
    ),
    TransmissionEdge(
        "credit_market", "corporations",
        "银行抽贷导致企业现金流断裂,部分企业被迫裁员或破产",
        "Bank credit line pulls cause corporate cash-flow breaks; firms are forced into layoffs or bankruptcy",
        "slow", "high",
    ),
    # ---- 实体经济 → 就业 → 消费 ----
    TransmissionEdge(
        "real_economy", "employment",
        "经济衰退使企业大规模裁员,失业率快速攀升",
        "Recession triggers mass layoffs; unemployment rises rapidly",
        "slow", "high",
    ),
    TransmissionEdge(
        "employment", "consumer_spending",
        "失业和收入不确定性使家庭削减可选消费,转向储蓄",
        "Unemployment and income uncertainty cause households to cut discretionary spending and save",
        "slow", "high",
    ),
    TransmissionEdge(
        "consumer_spending", "real_economy",
        "消费占美国 GDP 约 70%,支出下降直接拖累经济增长,形成负反馈",
        "Consumption is ~70% of US GDP; spending declines drag down growth — a negative feedback loop",
        "slow", "high",
    ),
    TransmissionEdge(
        "real_economy", "housing_market",
        "衰退导致更多房贷违约,房价进一步下跌",
        "Recession causes more mortgage defaults, further depressing home prices",
        "slow", "medium",
    ),
    TransmissionEdge(
        "real_economy", "banks",
        "衰退使企业和家庭贷款违约率上升,银行资产质量恶化,资本进一步承压",
        "Recession raises corporate and household loan defaults; bank asset quality deteriorates, capital pressured",
        "slow", "high",
    ),
    # ---- 财富效应 ----
    TransmissionEdge(
        "stock_market", "consumer_spending",
        "股市下跌产生负财富效应,家庭资产缩水削减消费",
        "Equity declines produce a negative wealth effect; household assets shrink and consumption falls",
        "slow", "medium",
    ),
    TransmissionEdge(
        "housing_market", "consumer_spending",
        "房价下跌使家庭净资产缩水,抵押品价值下降限制再融资和消费信贷",
        "Falling home prices reduce household net worth; lower collateral limits refinancing and consumer credit",
        "slow", "medium",
    ),
    TransmissionEdge(
        "banks", "stock_market",
        "银行股暴跌拖累大盘,金融板块占标普 500 权重较高时期约 22%",
        "Bank stocks crater and drag the index lower; financials were ~22% of the S&P 500 at the time",
        "fast", "medium",
    ),
]


# ============================================================================
# 4. Recovery Dashboard Data (恢复进程看板)
# ============================================================================
# 当前 (2025-Q3) 与 2007 年 (危机前) 和 2009 年 (危机后) 的政策空间对比
# 数据来源: FRED, U.S. Treasury, FDIC QBP, CBO, FOMC statements

RECOVERY_DASHBOARD_DATA: dict = {
    "monetary_policy_space": {
        "fed_funds_rate": {
            "current_pct": 5.50,                # 当前联邦基金利率上限 (%)
            "lower_bound_pct": 0.125,           # 实际有效下限 (%)
            "room_to_cut_bps": 538,             # 可降息空间 (基点)
            "pre_crisis_2007_pct": 5.25,        # 2007 年危机前利率
            "post_crisis_2009_pct": 0.16,       # 2009 年危机后利率
            "assessment_zh": "当前美联储拥有约 538 个基点的降息空间,与 2007 年危机前相当,远高于 2009 年的接近零利率。",
            "assessment_en": "The Fed currently has ~538 bps of rate-cut headroom, comparable to pre-crisis 2007 and far above the near-zero 2009 level.",
        },
        "fed_balance_sheet": {
            "current_size_t": 7.5,              # 当前美联储资产负债表规模 (万亿美元)
            "pre_crisis_2007_t": 0.87,          # 2007 年危机前规模
            "peak_2022_t": 8.97,                # 2022 年峰值
            "room_to_expand_pct_of_gdp": 30.0,  # 估计可扩张空间 (% GDP)
            "assessment_zh": "美联储资产负债表约 7.5 万亿美元,虽然已较 2022 年峰值缩减,但仍远高于 2007 年的 0.87 万亿,QE 工具储备充足。",
            "assessment_en": "Fed balance sheet is ~$7.5T; though reduced from the 2022 peak, it remains well above the $0.87T pre-crisis level — ample QE capacity.",
        },
        "forward_guidance_credibility": {
            "score_0_100": 72,                  # 前瞻性指引可信度评分
            "status": "high",
            "assessment_zh": "美联储沟通机制成熟,但 2021-2023 年「暂时性通胀」叙事受损可信度,目前评分 72/100。",
            "assessment_en": "Fed communication is mature, but the 2021-2023 'transitory inflation' narrative damaged credibility; current score 72/100.",
        },
    },
    "fiscal_space": {
        "us_debt_to_gdp": {
            "current_pct": 124.0,               # 当前联邦债务占 GDP 比例 (%)
            "pre_crisis_2007_pct": 62.0,        # 2007 年危机前
            "post_crisis_2009_pct": 82.0,       # 2009 年危机后
            "post_crisis_2020_pct": 129.0,      # 2020 年新冠危机后峰值
            "historical_average_pct": 60.0,     # 战后历史均值
            "assessment_zh": "联邦债务/GDP 约 124%,远高于 2007 年的 62% 和历史均值 60%,财政扩张空间较 2008 年显著收窄。",
            "assessment_en": "Federal debt/GDP is ~124%, well above 2007's 62% and the 60% historical average — fiscal space is materially tighter than in 2008.",
        },
        "budget_deficit": {
            "current_pct_gdp": 6.4,             # 当前财政赤字占 GDP 比例 (%)
            "pre_crisis_2007_pct": 1.7,         # 2007 年危机前
            "post_crisis_2009_pct": 9.8,        # 2009 年危机后
            "structural_pct_gdp": 4.0,          # 估算结构性赤字
            "assessment_zh": "财政赤字占 GDP 约 6.4%,远高于 2007 年的 1.7%,结构性赤字约 4%,限制了大规模刺激的可持续性。",
            "assessment_en": "Budget deficit is ~6.4% of GDP vs 1.7% pre-crisis; structural deficit near 4% limits stimulus sustainability.",
        },
        "debt_ceiling_status": {
            "current_status": "suspended",      # 当前状态
            "next_deadline": "2026-01-01",      # 下一个关键日期
            "risk_level": "medium",
            "assessment_zh": "债务上限目前处于暂停状态至 2025 年底,2026 年初重启后可能引发政治博弈,构成尾部风险。",
            "assessment_en": "The debt ceiling is suspended through end-2025; reinstatement in early 2026 may trigger political brinkmanship — a tail risk.",
        },
    },
    "banking_system_resilience": {
        "tier1_capital_ratio": {
            "current_pct": 14.7,                # 当前 Tier 1 资本充足率 (%)
            "pre_crisis_2007_pct": 8.8,         # 2007 年危机前
            "regulatory_minimum_pct": 8.0,      # 监管最低要求
            "assessment_zh": "银行 Tier 1 资本充足率约 14.7%,显著高于 2007 年的 8.8% 和监管下限 8.0%,资本缓冲充足。",
            "assessment_en": "Tier 1 capital ratio is ~14.7%, well above 2007's 8.8% and the 8.0% regulatory floor — ample capital buffer.",
        },
        "cet1_capital_ratio": {
            "current_pct": 13.2,                # 当前 CET1 资本充足率 (%)
            "pre_crisis_2007_pct": 7.5,         # 2007 年危机前估算
            "regulatory_minimum_pct": 4.5,      # 监管最低要求
            "assessment_zh": "CET1 资本充足率约 13.2%,远高于 2007 年水平,巴塞尔协议 III 改革显著提升了核心一级资本质量。",
            "assessment_en": "CET1 ratio is ~13.2%, far above 2007 levels; Basel III reforms have markedly improved core capital quality.",
        },
        "stress_test_results": {
            "latest_result": "all_pass",        # 最近一次压力测试结果
            "latest_year": 2024,
            "severely_adverse_capital_min_pct": 9.4,
            "assessment_zh": "2024 年美联储压力测试中,所有 31 家大型银行在严重不利情景下仍能维持最低资本要求。",
            "assessment_en": "In the 2024 Fed stress tests, all 31 large banks maintained minimum capital under the severely adverse scenario.",
        },
        "lcr_liquidity_coverage_ratio": {
            "current_pct": 121.0,               # 当前 LCR (%)
            "regulatory_minimum_pct": 100.0,    # 监管最低要求
            "pre_crisis_2007_pct": None,        # 2007 年尚无 LCR 要求
            "assessment_zh": "银行体系 LCR 约 121%,高于 100% 监管下限,流动性覆盖率优于危机前 (当时尚无该要求)。",
            "assessment_en": "Banking system LCR is ~121%, above the 100% floor; liquidity coverage is stronger than pre-crisis (when LCR didn't exist).",
        },
    },
}

# 整体恢复能力评分 (0-100, 越高越好)
# 综合考虑: 货币政策空间 (40%) + 财政空间 (30%) + 银行韧性 (30%)
RECOVERY_CAPACITY_SCORES: dict = {
    "current_2025": {
        "monetary_space_score": 78,             # 利率空间大但 BS 已高位
        "fiscal_space_score": 35,               # 债务高企,赤字大
        "banking_resilience_score": 82,         # 资本充足,压力测试通过
        "overall_score": 65,                    # 加权综合分
    },
    "pre_crisis_2007": {
        "monetary_space_score": 95,             # 利率 5.25%, BS 仅 0.87T
        "fiscal_space_score": 88,               # 债务/GDP 62%, 赤字 1.7%
        "banking_resilience_score": 35,         # 资本充足率低,杠杆高
        "overall_score": 74,
    },
    "post_crisis_2009": {
        "monetary_space_score": 8,              # 利率已降至零
        "fiscal_space_score": 55,               # 债务/GDP 82%, 赤字 9.8%
        "banking_resilience_score": 28,         # 资本严重消耗
        "overall_score": 30,
    },
}


# ============================================================================
# 5. Historical Policy Comparison Data (历史政策对比)
# ============================================================================
# 每个危机的政策清单、财政成本、有效性评级 (1-5)、恢复时间、关键教训
# 数据来源: FCIC Final Report (2011), IMF GFSR, CBO, TARP 标准报告, NBER

HISTORICAL_POLICIES: dict[str, dict] = {
    "gfc_2008": {
        "crisis_id": "gfc_2008",
        "crisis_name_zh": "2008 全球金融危机",
        "crisis_name_en": "Global Financial Crisis 2008",
        "period": "2007-2009",
        "policies_used": [
            {"tool_id": "rate_cut",          "detail_zh": "美联储将利率从 5.25% 降至 0-0.25%,累计降息 525 基点",                        "detail_en": "Fed cut rates from 5.25% to 0-0.25%, cumulative 525 bps"},
            {"tool_id": "qe",                "detail_zh": "QE1: 购买 1.75 万亿美元 MBS 和长期国债",                                  "detail_en": "QE1: $1.75T in MBS and long-term Treasuries"},
            {"tool_id": "forward_guidance",  "detail_zh": "2008 年 12 月起承诺「长时间维持低利率」",                                  "detail_en": "From Dec 2008, committed to keep rates low for an 'extended period'"},
            {"tool_id": "discount_window",   "detail_zh": "延长贴现窗口期限并降低贴现率 25 基点",                                    "detail_en": "Extended discount window term and cut discount rate 25 bps"},
            {"tool_id": "swap_lines",        "detail_zh": "与 14 国央行设立美元互换额度,规模无上限",                                "detail_en": "Unlimited swap lines with 14 central banks"},
            {"tool_id": "pDCF",              "detail_zh": "2008-03 创设 PDCF,向一级交易商提供隔夜抵押贷款",                          "detail_en": "Created PDCF in Mar 2008; overnight collateralized loans to primary dealers"},
            {"tool_id": "mMLF",              "detail_zh": "2008-09 创设 MMLF,支撑货币市场基金",                                     "detail_en": "Created MMLF in Sep 2008 to backstop money market funds"},
            {"tool_id": "fiscal_stimulus",   "detail_zh": "ARRA (美国复苏与再投资法案) 7870 亿美元",                                "detail_en": "ARRA (American Recovery and Reinvestment Act) $787B"},
            {"tool_id": "capital_injection", "detail_zh": "TARP 向银行注资约 2500 亿美元,授权 7000 亿美元",                         "detail_en": "TARP injected ~$250B into banks; $700B authorized"},
            {"tool_id": "deposit_insurance", "detail_zh": "FDIC 保险上限从 10 万提高到 25 万美元,并临时担保无息账户",                "detail_en": "FDIC limit raised from $100K to $250K; temporary guarantee on non-interest accounts"},
            {"tool_id": "short_sale_ban",    "detail_zh": "2008-09 临时禁止 799 只金融股卖空,持续 3 周",                            "detail_en": "Sep 2008: temporary ban on short selling 799 financial stocks for 3 weeks"},
            {"tool_id": "foreclosure_moratorium", "detail_zh": "部分州与机构实施止赎暂停,但联邦层面覆盖有限",                       "detail_en": "Some states and institutions imposed foreclosure moratoria; limited federal coverage"},
        ],
        "total_fiscal_cost": {
            "amount_usd_b": 1500,              # 总财政成本 (十亿美元, 含 TARP/ARRA/AIG/Fannie/Freddie)
            "pct_of_gdp": 10.2,                # 占 GDP 比例 (%)
            "net_cost_after_repayment_usd_b": 475,  # 扣除还款后的净成本
            "note_zh": "包括 TARP (实际净损失约 320 亿美元)、ARRA (7870 亿)、AIG 救助 (净损失约 50 亿)、GSE 救助 (~1900 亿)",
            "note_en": "Includes TARP (net loss ~$32B), ARRA ($787B), AIG bailout (net loss ~$5B), GSE rescue (~$190B)",
        },
        "effectiveness_rating": 4,             # 1-5, 4 表示「基本有效但代价高昂」
        "time_to_recovery_months": 18,         # 从危机爆发到 GDP 转正的月数
        "key_lessons_zh": (
            "1. 雷曼倒闭证明「不救助」会引发系统性灾难,后续救助 AIG、花旗、美银印证了「大而不能倒」;\n"
            "2. 压力测试 (SCAP) 是恢复市场信心的关键转折点;\n"
            "3. 协调的财政与货币政策比单一工具更有效;\n"
            "4. 救助成本远低于放任危机扩散的经济损失。"
        ),
        "key_lessons_en": (
            "1. Lehman's collapse proved non-bailout triggers systemic catastrophe; subsequent AIG/Citi/BoA rescues confirmed too-big-to-fail;\n"
            "2. Stress tests (SCAP) were the pivotal confidence-restoring moment;\n"
            "3. Coordinated fiscal-monetary policy beats single-instrument responses;\n"
            "4. Bailout costs were far lower than the economic cost of letting the crisis spread."
        ),
    },
    "dotcom_2000": {
        "crisis_id": "dotcom_2000",
        "crisis_name_zh": "2000 互联网泡沫破裂",
        "crisis_name_en": "Dot-Com Crash 2000-2002",
        "period": "2000-2002",
        "policies_used": [
            {"tool_id": "rate_cut",          "detail_zh": "美联储将利率从 6.5% 降至 1% (2003 年),累计降息 550 基点",                "detail_en": "Fed cut rates from 6.5% to 1% by 2003, cumulative 550 bps"},
            {"tool_id": "tax_cut",           "detail_zh": "布什签署 EGTRRA 减税法案,十年期 1.35 万亿美元",                          "detail_en": "Bush signed EGTRRA tax cut, $1.35T over 10 years"},
            {"tool_id": "forward_guidance",  "detail_zh": "格林斯潘暗示将维持宽松,但当时尚未系统使用前瞻性指引",                     "detail_en": "Greenspan hinted at sustained easing; systematic forward guidance not yet in use"},
            {"tool_id": "circuit_breaker",   "detail_zh": "9·11 后纽交所关闭 4 天,复牌后触发熔断机制",                              "detail_en": "NYSE closed 4 days post-9/11; circuit breakers triggered on reopen"},
        ],
        "total_fiscal_cost": {
            "amount_usd_b": 1350,             # EGTRRA + 其他减税 (十年期)
            "pct_of_gdp": 13.0,               # 占 GDP 比例 (十年期累计)
            "net_cost_after_repayment_usd_b": 1350,
            "note_zh": "主要为 EGTRRA 减税,十年期 1.35 万亿美元,无大规模银行救助",
            "note_en": "Primarily EGTRRA tax cuts, $1.35T over 10 years; no large-scale bank bailouts",
        },
        "effectiveness_rating": 3,            # 中等,低利率催生了下一轮房地产泡沫
        "time_to_recovery_months": 30,        # 2000-03 见顶至 2002-10 触底,经济复苏较慢
        "key_lessons_zh": (
            "1. 货币政策不应直接针对资产泡沫,但破裂后应迅速提供流动性;\n"
            "2. 长期低利率 (1%) 为 2008 年房地产泡沫埋下种子;\n"
            "3. 会计欺诈 (安然/世通) 暴露监管漏洞,催生《萨班斯-奥克斯利法案》;\n"
            "4. 银行体系未深度参与互联网股票,危机未演变为系统性金融危机。"
        ),
        "key_lessons_en": (
            "1. Monetary policy shouldn't target asset bubbles directly, but must provide liquidity quickly after a bust;\n"
            "2. Prolonged low rates (1%) planted the seeds for the 2008 housing bubble;\n"
            "3. Accounting fraud (Enron/WorldCom) exposed oversight gaps, leading to Sarbanes-Oxley;\n"
            "4. Banks weren't deeply exposed to dot-com equities, so the crisis never became systemic."
        ),
    },
    "great_depression_1929": {
        "crisis_id": "great_depression_1929",
        "crisis_name_zh": "1929 大萧条",
        "crisis_name_en": "Great Depression 1929-1933",
        "period": "1929-1933",
        "policies_used": [
            {"tool_id": "bank_holiday",         "detail_zh": "1933-03 罗斯福宣布全国银行假期,关闭所有银行 4 天审计",                "detail_en": "Mar 1933: FDR declared national bank holiday; all banks closed 4 days for audit"},
            {"tool_id": "deposit_insurance",    "detail_zh": "《格拉斯-斯蒂格尔法案》设立 FDIC,初始保险上限 2500 美元",            "detail_en": "Glass-Steagall Act created FDIC; initial insurance limit $2,500"},
            {"tool_id": "fiscal_stimulus",      "detail_zh": "罗斯福新政,公共工程、社会保障、农业调整等多项目",                     "detail_en": "FDR's New Deal: public works, Social Security, agricultural adjustment"},
            {"tool_id": "infrastructure",       "detail_zh": "WPA、CCC、TVA 等基础设施和就业项目",                                  "detail_en": "WPA, CCC, TVA — infrastructure and employment programs"},
            {"tool_id": "capital_injection",    "detail_zh": "RFC (重建金融公司) 向银行和铁路提供 32 亿美元贷款",                    "detail_en": "RFC (Reconstruction Finance Corporation) lent $3.2B to banks and railroads"},
        ],
        "total_fiscal_cost": {
            "amount_usd_b": 42,                # 1930s 名义美元 (新政总支出)
            "pct_of_gdp": 40.0,                # 占 GDP 比例 (峰值年度赤字约 5-6%)
            "net_cost_after_repayment_usd_b": 42,
            "note_zh": "新政总支出约 420 亿美元 (1930s 名义),约相当于今日 8000-9000 亿美元",
            "note_en": "Total New Deal spending ~$42B (1930s nominal), equivalent to ~$800-900B today",
        },
        "effectiveness_rating": 3,            # 新政有效但缓慢,1937-38 年二次衰退源于过早紧缩
        "time_to_recovery_months": 43,        # 1929 顶至 1933 底;实际完全恢复至 1929 年 GDP 需到二战
        "key_lessons_zh": (
            "1. 货币紧缩 (美联储放任货币供应缩减 1/3) 将普通衰退变成大萧条;\n"
            "2. 贸易保护主义 (斯穆特-霍利关税) 引发全球报复,加剧衰退;\n"
            "3. 存款保险 (FDIC) 是终结银行挤兑的关键制度创新;\n"
            "4. 金本位是危机中的紧缩枷锁,放弃金本位的国家恢复更快;\n"
            "5. 1937-38 年过早财政紧缩导致二次衰退,警示勿过早退出刺激。"
        ),
        "key_lessons_en": (
            "1. Monetary contraction (Fed allowed money supply to fall 1/3) turned recession into depression;\n"
            "2. Protectionism (Smoot-Hawley) triggered global retaliation, deepening the slump;\n"
            "3. Deposit insurance (FDIC) was the key institutional innovation ending bank runs;\n"
            "4. The gold standard was a deflationary straitjacket; countries that abandoned it recovered faster;\n"
            "5. The 1937-38 premature fiscal tightening caused a double-dip — don't exit stimulus too early."
        ),
    },
    "covid_2020": {
        "crisis_id": "covid_2020",
        "crisis_name_zh": "2020 新冠市场崩盘",
        "crisis_name_en": "COVID-19 Market Crash 2020",
        "period": "2020-02 ~ 2020-04",
        "policies_used": [
            {"tool_id": "rate_cut",          "detail_zh": "美联储两次紧急降息共 150 基点,降至 0-0.25%",                            "detail_en": "Two emergency cuts totaling 150 bps; rates to 0-0.25%"},
            {"tool_id": "qe",                "detail_zh": "无限量 QE,购买国债和 MBS,资产负债表扩张 3 万亿美元",                    "detail_en": "Unlimited QE; purchases of Treasuries and MBS; balance sheet grew $3T"},
            {"tool_id": "forward_guidance",  "detail_zh": "承诺维持低利率直到达到通胀和就业目标",                                    "detail_en": "Pledged to keep rates low until inflation and employment goals met"},
            {"tool_id": "discount_window",   "detail_zh": "降低贴现率 150 基点,延长期限至 90 天",                                    "detail_en": "Cut discount rate 150 bps; extended term to 90 days"},
            {"tool_id": "swap_lines",        "detail_zh": "与 14 国央行设立美元互换额度,缓解全球美元荒",                            "detail_en": "Swap lines with 14 central banks to relieve global dollar shortage"},
            {"tool_id": "repo_operations",   "detail_zh": "大规模回购操作,单日规模达数千亿美元",                                    "detail_en": "Large-scale repo operations; intraday size reached hundreds of billions"},
            {"tool_id": "pDCF",              "detail_zh": "重启 PDCF,延长至 90 天",                                                "detail_en": "Revived PDCF; extended term to 90 days"},
            {"tool_id": "mMLF",              "detail_zh": "重启 MMLF,支撑货币市场基金",                                            "detail_en": "Revived MMLF to backstop money market funds"},
            {"tool_id": "fiscal_stimulus",   "detail_zh": "CARES 法案 2.2 万亿美元 + 后续 9000 亿美元追加",                          "detail_en": "CARES Act $2.2T + $900B supplemental"},
            {"tool_id": "direct_payments",   "detail_zh": "向成人直接发放 1200/600 美元支票",                                       "detail_en": "Direct $1,200/$600 stimulus checks to adults"},
            {"tool_id": "unemployment_benefit", "detail_zh": "每周额外 600 美元失业补助,延长领取期限",                               "detail_en": "Extra $600/week unemployment benefits; extended duration"},
            {"tool_id": "ppp_loans",         "detail_zh": "薪酬保护计划 (PPP) 8000 亿美元可豁免贷款",                               "detail_en": "Paycheck Protection Program (PPP) $800B in forgivable loans"},
            {"tool_id": "circuit_breaker",   "detail_zh": "10 天内 4 次触发熔断机制",                                               "detail_en": "4 circuit breaker triggers in 10 days"},
        ],
        "total_fiscal_cost": {
            "amount_usd_b": 5200,             # CARES + 追加 + PPP (约 5.2 万亿美元财政)
            "pct_of_gdp": 24.5,               # 占 GDP 比例 (两年累计)
            "net_cost_after_repayment_usd_b": 4900,
            "note_zh": "包括 CARES 法案 2.2 万亿、追加 9000 亿、PPP 8000 亿、其他措施约 1.3 万亿",
            "note_en": "Includes CARES $2.2T, supplemental $900B, PPP $800B, other measures ~$1.3T",
        },
        "effectiveness_rating": 5,            # 史上最快复苏,标普 500 在 5 个月内收复全部跌幅
        "time_to_recovery_months": 5,         # 2020-02 见顶至 2020-08 创新高
        "key_lessons_zh": (
            "1. 美联储吸取 2008 年教训,数小时内而非数周内提供无限流动性;\n"
            "2. 财政与货币政策协调前所未有,直接支付和 PPP 迅速支撑家庭和企业;\n"
            "3. 外生冲击 (疫情) 与内生冲击 (金融系统) 需要不同策略,但快速响应是共同关键;\n"
            "4. 巨额刺激也带来副作用: 2021-2023 年通胀飙升至 40 年高点。"
        ),
        "key_lessons_en": (
            "1. The Fed applied 2008 lessons, providing unlimited liquidity in hours rather than weeks;\n"
            "2. Unprecedented fiscal-monetary coordination; direct payments and PPP rapidly supported households and firms;\n"
            "3. Exogenous shocks (pandemic) vs endogenous shocks (financial) require different tools but share the need for speed;\n"
            "4. Massive stimulus had side effects: 2021-2023 inflation surged to 40-year highs."
        ),
    },
    "asia_1997": {
        "crisis_id": "asia_1997",
        "crisis_name_zh": "1997 亚洲金融危机",
        "crisis_name_en": "Asian Financial Crisis 1997-1998",
        "period": "1997-1998",
        "policies_used": [
            {"tool_id": "rate_cut",          "detail_zh": "美联储 1998 年秋降息 75 基点预防全球衰退",                                "detail_en": "Fed cut 75 bps in fall 1998 to prevent global recession"},
            {"tool_id": "fiscal_stimulus",   "detail_zh": "日本推出 16 万亿日元财政刺激",                                            "detail_en": "Japan launched ¥16T fiscal stimulus"},
            {"tool_id": "capital_injection", "detail_zh": "IMF 向泰国、印尼、韩国提供约 1000 亿美元救助",                             "detail_en": "IMF provided ~$100B in bailouts to Thailand, Indonesia, South Korea"},
            {"tool_id": "forward_guidance",  "detail_zh": "美联储暗示进一步宽松,稳定市场预期",                                       "detail_en": "Fed hinted at further easing, stabilizing expectations"},
        ],
        "total_fiscal_cost": {
            "amount_usd_b": 175,             # IMF 救助 + 各国财政刺激
            "pct_of_gdp": 1.5,               # 占全球 GDP 比例较小
            "net_cost_after_repayment_usd_b": 30,
            "note_zh": "IMF 救助约 1000 亿美元 (大部分已偿还),亚洲各国财政刺激约 750 亿美元",
            "note_en": "IMF bailouts ~$100B (mostly repaid); Asian fiscal stimulus ~$75B",
        },
        "effectiveness_rating": 3,            # IMF 紧缩条件存在争议,马来西亚资本管制反而有效
        "time_to_recovery_months": 18,        # 1997-07 至 1998-12 大部分亚洲市场触底
        "key_lessons_zh": (
            "1. 固定汇率制度在资本自由流动下是脆弱的,弹性汇率是更好的缓冲;\n"
            "2. 短期外债是定时炸弹,期限错配管理至关重要;\n"
            "3. 外汇储备是最后的防线,亚洲国家此后大规模积累储备;\n"
            "4. IMF 的紧缩条件 (加息+财政紧缩) 加剧了衰退,引发争议;\n"
            "5. 马来西亚资本管制虽争议但有效,提示一揽子方案需考虑国情。"
        ),
        "key_lessons_en": (
            "1. Fixed exchange rates are fragile under capital mobility — flexible rates buffer better;\n"
            "2. Short-term foreign debt is a ticking bomb; maturity mismatch management is critical;\n"
            "3. FX reserves are the last line of defense; Asian countries accumulated massive reserves afterward;\n"
            "4. IMF austerity conditions (rate hikes + fiscal tightening) deepened recessions, sparking debate;\n"
            "5. Malaysia's capital controls were controversial but effective — packages must fit country context."
        ),
    },
}


# ============================================================================
# Public Functions
# ============================================================================

def get_policy_toolbox() -> dict:
    """获取所有可用的危机应对政策工具。

    返回按类别分组的政策工具箱,包含央行工具、财政工具、监管工具三大类。
    每个工具包含: id、中英文名称、中英文描述、典型规模、生效时间、历史使用记录。

    Returns:
        dict: 包含 categories 字典和 metadata 的字典

    Example:
        >>> get_policy_toolbox()
        {
            "categories": {
                "central_bank": [...],
                "fiscal": [...],
                "regulatory": [...],
            },
            "metadata": {
                "total_tools": 20,
                "category_counts": {"central_bank": 8, "fiscal": 6, "regulatory": 6},
                ...
            },
        }
    """
    def _tool_to_dict(t: PolicyTool) -> dict:
        return {
            "id": t.id,
            "name_zh": t.name_zh,
            "name_en": t.name_en,
            "category": t.category,
            "description_zh": t.description_zh,
            "description_en": t.description_en,
            "typical_scale": t.typical_scale,
            "time_to_effect": t.time_to_effect,
            "historical_usage": list(t.historical_usage),
        }

    central_bank = [_tool_to_dict(t) for t in CENTRAL_BANK_TOOLS]
    fiscal = [_tool_to_dict(t) for t in FISCAL_TOOLS]
    regulatory = [_tool_to_dict(t) for t in REGULATORY_TOOLS]

    return {
        "categories": {
            "central_bank": {
                "label_zh": "央行工具",
                "label_en": "Central Bank Tools",
                "tools": central_bank,
            },
            "fiscal": {
                "label_zh": "财政工具",
                "label_en": "Fiscal Tools",
                "tools": fiscal,
            },
            "regulatory": {
                "label_zh": "监管工具",
                "label_en": "Regulatory Tools",
                "tools": regulatory,
            },
        },
        "metadata": {
            "total_tools": len(ALL_POLICY_TOOLS),
            "category_counts": {
                "central_bank": len(CENTRAL_BANK_TOOLS),
                "fiscal": len(FISCAL_TOOLS),
                "regulatory": len(REGULATORY_TOOLS),
            },
            "time_to_effect_legend": {
                "immediate": "数日内生效 / takes effect within days",
                "short": "数周内生效 / takes effect within weeks",
                "medium": "1-2 个季度内生效 / takes effect within 1-2 quarters",
                "long": "多季度后生效 / takes effect over multiple quarters",
            },
            "as_of": AS_OF,
        },
    }


def simulate_policies(selected_tools: list[str], severity: str = "moderate") -> dict:
    """模拟选定政策工具组合在给定危机严重程度下的综合效果。

    模型逻辑:
        1. 根据 severity 选取「不采取任何政策」的基线指标;
        2. 对 selected_tools 中每个工具,叠加其对各指标的边际贡献;
        3. 应用边际效用递减 (相同类别工具越多,后续效果打折);
        4. 计算综合副作用风险 (高通胀、高债务、道德风险);
        5. 生成中英文叙事评估。

    Args:
        selected_tools: 选定的政策工具 ID 列表 (如 ["rate_cut", "qe", "fiscal_stimulus"])
        severity: 危机严重程度,可选 "mild" / "moderate" / "severe" / "2008-level"

    Returns:
        dict: 包含所有模拟指标和叙事评估的字典

    Example:
        >>> simulate_policies(["rate_cut", "qe", "fiscal_stimulus"], "severe")
        {
            "severity": "severe",
            "selected_tools": [...],
            "metrics": {
                "market_recovery_months": 14,
                "gdp_impact_pp": -2.5,
                ...
            },
            "narrative_zh": "...",
            "narrative_en": "...",
        }
    """
    # 参数校验
    if severity not in SEVERITY_BASELINES:
        return {"error": f"Invalid severity '{severity}'. Must be one of {list(SEVERITY_BASELINES.keys())}"}

    valid_tool_ids = {t.id for t in ALL_POLICY_TOOLS}
    invalid_tools = [t for t in selected_tools if t not in valid_tool_ids]
    if invalid_tools:
        return {"error": f"Unknown tool IDs: {invalid_tools}. Valid IDs: {sorted(valid_tool_ids)}"}

    baseline = SEVERITY_BASELINES[severity]

    # 按类别统计工具数量,用于边际效用递减
    tool_category_count: dict[str, int] = {"central_bank": 0, "fiscal": 0, "regulatory": 0}
    tool_lookup = {t.id: t for t in ALL_POLICY_TOOLS}

    # 初始化指标为基线
    recovery_months = baseline["recovery_months"]
    gdp_impact = baseline["gdp_impact"]
    unemployment_delta = baseline["unemployment_delta"]
    inflation_delta = baseline["inflation_delta"]
    fiscal_cost = baseline["fiscal_cost_gdp"]
    confidence = baseline["confidence_baseline"]
    side_effect = baseline["side_effect_baseline"]

    applied_tools: list[dict] = []

    for tool_id in selected_tools:
        tool = tool_lookup.get(tool_id)
        if tool is None:
            continue
        effects = POLICY_EFFECTS.get(tool_id)
        if effects is None:
            continue

        # 边际效用递减: 同类别每多一个工具,效果打折 10% (最低 50%)
        tool_category_count[tool.category] += 1
        n = tool_category_count[tool.category]
        discount = max(0.5, 1.0 - 0.1 * (n - 1))

        recovery_months += effects["recovery_months_delta"] * discount
        gdp_impact += effects["gdp_impact_delta"] * discount
        unemployment_delta += effects["unemployment_delta"] * discount
        inflation_delta += effects["inflation_delta"] * discount
        fiscal_cost += effects["fiscal_cost_gdp_delta"] * discount
        confidence += effects["confidence_boost"] * discount
        side_effect += effects["side_effect_risk"] * discount

        applied_tools.append({
            "tool_id": tool_id,
            "name_zh": tool.name_zh,
            "name_en": tool.name_en,
            "category": tool.category,
            "discount_applied": round(discount, 2),
        })

    # 钳制 (clamp) 各项指标到合理区间
    recovery_months = max(1, round(recovery_months))
    gdp_impact = round(gdp_impact, 2)
    unemployment_delta = round(unemployment_delta, 2)
    inflation_delta = round(inflation_delta, 2)
    fiscal_cost = round(max(0.0, fiscal_cost), 2)
    confidence = int(min(100, max(0, confidence)))
    side_effect = int(min(100, max(0, side_effect)))

    # 生成叙事评估
    severity_zh = {
        "mild": "温和衰退", "moderate": "中等衰退",
        "severe": "严重衰退", "2008-level": "2008 级别系统性危机",
    }[severity]
    severity_en = {
        "mild": "mild recession", "moderate": "moderate recession",
        "severe": "severe recession", "2008-level": "2008-level systemic crisis",
    }[severity]

    # 评估政策组合
    if confidence >= 70:
        verdict_zh = "政策组合有效,市场信心显著恢复"
        verdict_en = "Policy mix is effective; market confidence recovers markedly"
    elif confidence >= 50:
        verdict_zh = "政策组合基本有效,但仍有提升空间"
        verdict_en = "Policy mix is broadly effective, with room for improvement"
    elif confidence >= 30:
        verdict_zh = "政策组合效果有限,需更强力措施"
        verdict_en = "Policy mix has limited effect; stronger measures needed"
    else:
        verdict_zh = "政策组合不足以应对当前危机严重程度"
        verdict_en = "Policy mix is insufficient for the crisis severity"

    if side_effect >= 60:
        risk_zh = "副作用风险较高 (道德风险、通胀、债务负担)"
        risk_en = "Side-effect risk is high (moral hazard, inflation, debt burden)"
    elif side_effect >= 35:
        risk_zh = "副作用风险中等,需关注长期影响"
        risk_en = "Side-effect risk is moderate; long-term impacts warrant attention"
    else:
        risk_zh = "副作用风险可控"
        risk_en = "Side-effect risk is manageable"

    narrative_zh = (
        f"在「{severity_zh}」情景下,应用 {len(applied_tools)} 项政策工具后,"
        f"预计市场恢复时间约 {recovery_months} 个月,GDP 影响为 {gdp_impact:+.2f} 个百分点,"
        f"失业率变化 {unemployment_delta:+.2f} 个百分点,通胀影响 {inflation_delta:+.2f} 个百分点,"
        f"财政成本约占 GDP 的 {fiscal_cost:.2f}%。信心提升评分 {confidence}/100,副作用风险 {side_effect}/100。"
        f"{verdict_zh}。{risk_zh}。"
    )

    narrative_en = (
        f"Under a '{severity_en}' scenario, applying {len(applied_tools)} policy tools yields "
        f"an estimated market recovery time of {recovery_months} months, GDP impact of {gdp_impact:+.2f} pp, "
        f"unemployment change of {unemployment_delta:+.2f} pp, inflation impact of {inflation_delta:+.2f} pp, "
        f"and a fiscal cost of ~{fiscal_cost:.2f}% of GDP. Confidence boost scores {confidence}/100; "
        f"side-effect risk is {side_effect}/100. {verdict_en}. {risk_en}."
    )

    return {
        "severity": severity,
        "selected_tools": applied_tools,
        "metrics": {
            "market_recovery_months": recovery_months,
            "gdp_impact_pp": gdp_impact,
            "unemployment_change_pp": unemployment_delta,
            "inflation_impact_pp": inflation_delta,
            "fiscal_cost_pct_of_gdp": fiscal_cost,
            "confidence_boost_score": confidence,
            "side_effect_risk_score": side_effect,
            # 副作用细分 (基于指标的派生评估)
            "side_effect_breakdown": {
                "inflation_risk": int(min(100, inflation_delta * 25)),
                "debt_burden_risk": int(min(100, fiscal_cost * 5)),
                "moral_hazard_risk": int(min(100, 30 if "capital_injection" in selected_tools else 10
                                              + 20 if "deposit_insurance" in selected_tools else 0
                                              + 15 if "bank_holiday" in selected_tools else 0)),
            },
        },
        "baseline_no_policy": {
            "market_recovery_months": baseline["recovery_months"],
            "gdp_impact_pp": baseline["gdp_impact"],
            "unemployment_change_pp": baseline["unemployment_delta"],
            "inflation_impact_pp": baseline["inflation_delta"],
            "fiscal_cost_pct_of_gdp": baseline["fiscal_cost_gdp"],
            "confidence_boost_score": baseline["confidence_baseline"],
            "side_effect_risk_score": baseline["side_effect_baseline"],
        },
        "narrative_zh": narrative_zh,
        "narrative_en": narrative_en,
        "metadata": {
            "model_notes_zh": "本模型基于历史政策效果的简化估计,采用边际效用递减 (同类工具每增加一个,效果打折 10%,最低 50%)。结果仅供推演,非精确预测。",
            "model_notes_en": "This model is a simplified estimate based on historical policy effects, with diminishing marginal returns (each additional same-category tool discounted 10%, floored at 50%). Results are illustrative, not precise forecasts.",
            "as_of": AS_OF,
        },
    }


def get_risk_transmission_paths() -> dict:
    """获取风险传导路径知识图谱 (2008 危机传导链为蓝本)。

    返回节点 (资产类、机构、市场、实体经济) 和边 (传导路径) 的列表。
    每条边包含: from_node, to_node, 中英文描述, 传导速度 (fast/slow), 严重程度 (high/medium/low)。

    Returns:
        dict: 包含 nodes、edges 和 metadata 的字典

    Example:
        >>> get_risk_transmission_paths()
        {
            "nodes": [{"id": "subprime_mortgages", "label_zh": "...", ...}, ...],
            "edges": [{"from_node": "subprime_mortgages", "to_node": "housing_market", ...}, ...],
            "metadata": {...},
        }
    """
    edges = [
        {
            "from_node": e.from_node,
            "to_node": e.to_node,
            "description_zh": e.description_zh,
            "description_en": e.description_en,
            "transmission_speed": e.transmission_speed,
            "severity": e.severity,
        }
        for e in TRANSMISSION_EDGES
    ]

    return {
        "nodes": [dict(n) for n in TRANSMISSION_NODES],
        "edges": edges,
        "metadata": {
            "node_count": len(TRANSMISSION_NODES),
            "edge_count": len(TRANSMISSION_EDGES),
            "node_categories": {
                "asset_class":   "资产类 / Asset classes",
                "institution":   "金融机构 / Institutions",
                "market":        "金融市场 / Markets",
                "real_economy":  "实体经济 / Real economy",
            },
            "speed_legend": {
                "fast": "数日至数周内传导 / transmits within days to weeks",
                "slow": "数月至数季度内传导 / transmits over months to quarters",
            },
            "severity_legend": {
                "high":   "传导强度高,通常会引发下一节点显著恶化",
                "medium": "传导强度中等,在特定条件下放大",
                "low":    "传导强度较弱,通常为辅助性影响",
            },
            "primary_scenario": "2008 全球金融危机传导链 / GFC 2008 transmission chain",
        },
    }


def get_transmission_graph() -> dict:
    """获取适合前端可视化的图结构 (nodes + edges, 含节点分类和连接关系)。

    与 get_risk_transmission_paths() 相比,本函数为可视化场景做了优化:
        - nodes 增加 category 分组和索引;
        - edges 增加 id 字段 (适合作为 D3/Cytoscape 的 link id);
        - 提供 category_groups 字段方便图例渲染。

    Returns:
        dict: 适合前端渲染的图数据

    Example:
        >>> get_transmission_graph()
        {
            "nodes": [{"id": "...", "label": "...", "category": "...", "group": 0}, ...],
            "links": [{"source": "...", "target": "...", "id": "e0", ...}, ...],
            "category_groups": [...],
        }
    """
    # 节点: 加 group 索引,便于 force-directed 图按类别着色
    category_index = {"asset_class": 0, "institution": 1, "market": 2, "real_economy": 3}
    nodes = []
    for n in TRANSMISSION_NODES:
        nodes.append({
            "id": n["id"],
            "label": n["label_en"],          # 默认英文标签,前端可按需切换
            "label_zh": n["label_zh"],
            "label_en": n["label_en"],
            "category": n["category"],
            "group": category_index.get(n["category"], 99),
        })

    # 边: 转换 source/target 命名,加 id
    links = []
    for i, e in enumerate(TRANSMISSION_EDGES):
        links.append({
            "id": f"e{i}",
            "source": e.from_node,
            "target": e.to_node,
            "description_zh": e.description_zh,
            "description_en": e.description_en,
            "speed": e.transmission_speed,
            "severity": e.severity,
            "value": {"high": 3, "medium": 2, "low": 1}.get(e.severity, 1),  # 边粗细
        })

    # 类别分组信息 (用于图例)
    category_groups = [
        {"key": "asset_class",  "label_zh": "资产类",     "label_en": "Asset class",   "group": 0, "color": "#e41a1c"},
        {"key": "institution",  "label_zh": "金融机构",   "label_en": "Institution",   "group": 1, "color": "#377eb8"},
        {"key": "market",       "label_zh": "金融市场",   "label_en": "Market",        "group": 2, "color": "#4daf4e"},
        {"key": "real_economy", "label_zh": "实体经济",   "label_en": "Real economy",  "group": 3, "color": "#984ea3"},
    ]

    # 识别双向反馈环路 (A→B 且 B→A 同时存在),便于前端高亮
    # node_incoming[X] = 所有指向 X 的源节点列表
    node_incoming: dict[str, list[str]] = {n["id"]: [] for n in TRANSMISSION_NODES}
    for e in TRANSMISSION_EDGES:
        node_incoming.setdefault(e.to_node, []).append(e.from_node)

    feedback_pairs = []
    for i, e in enumerate(TRANSMISSION_EDGES):
        # 检查是否存在反向边 to_node → from_node (即 to_node 是否为指向 from_node 的源)
        if e.to_node in node_incoming.get(e.from_node, []):
            feedback_pairs.append({
                "node_a": e.from_node,
                "node_b": e.to_node,
                "edge_id_a_to_b": f"e{i}",
            })

    return {
        "nodes": nodes,
        "links": links,
        "category_groups": category_groups,
        "feedback_loops": feedback_pairs,
        "metadata": {
            "node_count": len(nodes),
            "link_count": len(links),
            "feedback_loop_count": len(feedback_pairs),
            "format": "D3 force-directed / Cytoscape compatible",
            "as_of": AS_OF,
        },
    }


def get_recovery_dashboard() -> dict:
    """获取当前恢复进程看板 (2025-Q3 快照)。

    返回三大维度的政策空间与韧性指标,并与 2008 危机前 (2007) 和危机后 (2009) 对比。
    最后给出综合恢复能力评分 (0-100)。

    Returns:
        dict: 包含 monetary_policy_space、fiscal_space、banking_system_resilience、
              overall_recovery_capacity 和 historical_comparison 的字典

    Example:
        >>> get_recovery_dashboard()
        {
            "monetary_policy_space": {...},
            "fiscal_space": {...},
            "banking_system_resilience": {...},
            "overall_recovery_capacity": {"score": 65, ...},
            "historical_comparison": {...},
        }
    """
    current = RECOVERY_CAPACITY_SCORES["current_2025"]
    pre_crisis = RECOVERY_CAPACITY_SCORES["pre_crisis_2007"]
    post_crisis = RECOVERY_CAPACITY_SCORES["post_crisis_2009"]

    # 综合评述
    overall_narrative_zh = (
        f"当前 (2025-Q3) 综合恢复能力评分 {current['overall_score']}/100,"
        f"高于 2009 年危机后 ({post_crisis['overall_score']}/100),"
        f"但低于 2007 年危机前 ({pre_crisis['overall_score']}/100)。"
        f"货币政策空间依然充足 (利率 5.50%,资产负债表 7.5 万亿),"
        f"银行体系韧性显著增强 (Tier 1 资本充足率 14.7% vs 2007 年 8.8%),"
        f"但财政空间大幅收窄 (债务/GDP 124% vs 2007 年 62%),成为最大约束。"
    )
    overall_narrative_en = (
        f"Current (2025-Q3) overall recovery capacity scores {current['overall_score']}/100, "
        f"above post-crisis 2009 ({post_crisis['overall_score']}/100) "
        f"but below pre-crisis 2007 ({pre_crisis['overall_score']}/100). "
        f"Monetary space remains ample (rates 5.50%, balance sheet $7.5T) and "
        f"banking resilience is markedly stronger (Tier 1 14.7% vs 2007's 8.8%), "
        f"but fiscal space has tightened sharply (debt/GDP 124% vs 2007's 62%) — the key constraint."
    )

    return {
        "monetary_policy_space": RECOVERY_DASHBOARD_DATA["monetary_policy_space"],
        "fiscal_space": RECOVERY_DASHBOARD_DATA["fiscal_space"],
        "banking_system_resilience": RECOVERY_DASHBOARD_DATA["banking_system_resilience"],
        "overall_recovery_capacity": {
            "score": current["overall_score"],
            "sub_scores": {
                "monetary_space": current["monetary_space_score"],
                "fiscal_space": current["fiscal_space_score"],
                "banking_resilience": current["banking_resilience_score"],
            },
            "weights": {
                "monetary_space": 0.40,
                "fiscal_space": 0.30,
                "banking_resilience": 0.30,
            },
            "narrative_zh": overall_narrative_zh,
            "narrative_en": overall_narrative_en,
        },
        "historical_comparison": {
            "current_2025": RECOVERY_CAPACITY_SCORES["current_2025"],
            "pre_crisis_2007": RECOVERY_CAPACITY_SCORES["pre_crisis_2007"],
            "post_crisis_2009": RECOVERY_CAPACITY_SCORES["post_crisis_2009"],
            "comparison_table": [
                {
                    "dimension": "monetary_space",
                    "label_zh": "货币政策空间",
                    "label_en": "Monetary space",
                    "current_2025": current["monetary_space_score"],
                    "pre_crisis_2007": pre_crisis["monetary_space_score"],
                    "post_crisis_2009": post_crisis["monetary_space_score"],
                },
                {
                    "dimension": "fiscal_space",
                    "label_zh": "财政空间",
                    "label_en": "Fiscal space",
                    "current_2025": current["fiscal_space_score"],
                    "pre_crisis_2007": pre_crisis["fiscal_space_score"],
                    "post_crisis_2009": post_crisis["fiscal_space_score"],
                },
                {
                    "dimension": "banking_resilience",
                    "label_zh": "银行体系韧性",
                    "label_en": "Banking resilience",
                    "current_2025": current["banking_resilience_score"],
                    "pre_crisis_2007": pre_crisis["banking_resilience_score"],
                    "post_crisis_2009": post_crisis["banking_resilience_score"],
                },
                {
                    "dimension": "overall",
                    "label_zh": "综合恢复能力",
                    "label_en": "Overall recovery capacity",
                    "current_2025": current["overall_score"],
                    "pre_crisis_2007": pre_crisis["overall_score"],
                    "post_crisis_2009": post_crisis["overall_score"],
                },
            ],
        },
        "metadata": {
            "as_of": AS_OF,
            "data_sources": [
                "Federal Reserve (FOMC statements, H.4.1, H.8)",
                "U.S. Treasury (debt outstanding, monthly statement)",
                "FDIC Quarterly Banking Profile (QBP)",
                "Congressional Budget Office (budget outlook)",
                "Federal Reserve Dodd-Frank Act Stress Test (DFAST)",
            ],
        },
    }


def get_historical_policies() -> dict:
    """获取历次危机的政策应对对比。

    覆盖 5 次主要危机 (GFC 2008、互联网泡沫 2000、大萧条 1929、新冠 2020、亚洲 1997),
    每次危机包含: 政策清单、总财政成本、有效性评级 (1-5)、恢复时间、关键教训。

    Returns:
        dict: 包含 crises 列表和 metadata 的字典

    Example:
        >>> get_historical_policies()
        {
            "crises": [{"crisis_id": "gfc_2008", ...}, ...],
            "metadata": {"crisis_count": 5, ...},
        }
    """
    crises = []
    for crisis_id, data in HISTORICAL_POLICIES.items():
        # 复制以避免修改原数据
        crises.append({
            "crisis_id": data["crisis_id"],
            "crisis_name_zh": data["crisis_name_zh"],
            "crisis_name_en": data["crisis_name_en"],
            "period": data["period"],
            "policies_used": [dict(p) for p in data["policies_used"]],
            "total_fiscal_cost": dict(data["total_fiscal_cost"]),
            "effectiveness_rating": data["effectiveness_rating"],
            "time_to_recovery_months": data["time_to_recovery_months"],
            "key_lessons_zh": data["key_lessons_zh"],
            "key_lessons_en": data["key_lessons_en"],
        })

    # 横向对比汇总表
    comparison_summary = []
    for c in crises:
        comparison_summary.append({
            "crisis_id": c["crisis_id"],
            "crisis_name_zh": c["crisis_name_zh"],
            "crisis_name_en": c["crisis_name_en"],
            "policy_count": len(c["policies_used"]),
            "fiscal_cost_usd_b": c["total_fiscal_cost"]["amount_usd_b"],
            "fiscal_cost_pct_gdp": c["total_fiscal_cost"]["pct_of_gdp"],
            "effectiveness_rating": c["effectiveness_rating"],
            "time_to_recovery_months": c["time_to_recovery_months"],
        })

    return {
        "crises": crises,
        "comparison_summary": comparison_summary,
        "metadata": {
            "crisis_count": len(crises),
            "effectiveness_scale": {
                "1": "无效或加剧危机 / ineffective or worsening",
                "2": "效果有限 / limited effect",
                "3": "部分有效,但代价或副作用显著 / partially effective with significant costs",
                "4": "基本有效,成功遏制危机扩散 / broadly effective, contained the crisis",
                "5": "高度有效,实现快速复苏 / highly effective, rapid recovery",
            },
            "covered_crises": [
                "gfc_2008", "dotcom_2000", "great_depression_1929",
                "covid_2020", "asia_1997",
            ],
            "data_sources": [
                "FCIC Final Report (2011)",
                "IMF World Economic Outlook & GFSR",
                "CBO Budget and Economic Outlook",
                "U.S. Treasury TARP Standard Reports",
                "NBER business cycle dating",
            ],
            "as_of": AS_OF,
        },
    }
