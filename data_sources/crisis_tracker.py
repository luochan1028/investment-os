"""
金融危机专题模块

研究历次达到2008年级别的金融危机，汇总事件时间线，
对比当前市场指标与历史危机的相似度，评估恢复进度。

数据来源：
- 美联储经济数据 (FRED)
- NBER 衰退周期
- IMF 全球金融稳定报告
- BIS 年度报告
- 各大投行（高盛、摩根、瑞银）危机复盘报告

References:
- https://www.federalreserve.gov/econresdata/notes/feds-notes/2015/financial-crisis-2007-2009-20150320.html
- https://www.imf.org/en/Publications/GFSR
- https://www.bis.org/publ/arpdf/ar2009.htm
- https://www.nber.org/cycles.html
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("investment-os.crisis_tracker")


# ==================== 数据结构 ====================

@dataclass
class CrisisEvent:
    """危机事件"""
    date: str
    event_en: str
    event_zh: str
    impact: str  # high / medium / low


@dataclass
class CrisisPhase:
    """危机阶段"""
    phase_en: str
    phase_zh: str
    period: str
    description_en: str
    description_zh: str
    events: list[CrisisEvent] = field(default_factory=list)


@dataclass
class CrisisFigureAction:
    """危机中的关键人物/机构行为"""
    date: str
    figure: str  # 人物或机构名称
    figure_en: str
    action_zh: str
    action_en: str
    asset_class: str  # 股票/债券/商品/现金/并购等
    strategy_zh: str
    strategy_en: str
    outcome_zh: str
    outcome_en: str
    gain_pct: float = 0.0  # 估算收益率或影响程度
    tags: list[str] = field(default_factory=list)


@dataclass
class CrisisData:
    """危机数据"""
    id: str
    name_en: str
    name_zh: str
    period: str
    severity: str  # "2008-level" / "major" / "moderate"
    peak_unemployment: float
    peak_decline_snp: float  # S&P 500 最大跌幅 %
    peak_decline_gdp: float  # GDP 最大跌幅 %
    duration_months: int
    causes_zh: str
    causes_en: str
    key_events: list[CrisisEvent]
    phases: list[CrisisPhase]
    recovery_actions_zh: str
    recovery_actions_en: str
    lessons_zh: str
    lessons_en: str
    institutional_analyses: list[dict]  # 机构分析引用
    figure_actions: list[CrisisFigureAction] = field(default_factory=list)


# ==================== 历史危机数据库 ====================

# 2008 全球金融危机（次贷危机）
CRISIS_2008 = CrisisData(
    id="gfc_2008",
    name_en="Global Financial Crisis 2008",
    name_zh="2008 全球金融危机（次贷危机）",
    period="2007-2009",
    severity="2008-level",
    peak_unemployment=10.0,
    peak_decline_snp=-56.8,
    peak_decline_gdp=-4.3,
    duration_months=18,
    causes_zh=(
        "1. 次级抵押贷款大规模违约——银行向信用不良的借款人发放了大量可调整利率抵押贷款（ARM），"
        "房价下跌后违约率飙升；\n"
        "2. 金融衍生品杠杆失控——MBS、CDO 等结构性产品将风险层层放大，表外 SIV 隐藏了大量风险敞口；\n"
        "3. 雷曼倒闭引发信任链断裂——投行之间互不信任，回购市场（Repo）冻结，商业票据市场停摆；\n"
        "4. 监管缺位——影子银行体系规模达 10 万亿美元，完全不受美联储监管；\n"
        "5. 评级机构失职——AAA 评级赋予了垃圾资产合法外衣。"
    ),
    causes_en=(
        "1. Subprime mortgage defaults surged as adjustable-rate mortgages (ARMs) reset;\n"
        "2. Derivative leverage (MBS, CDOs) multiplied risk exponentially; SIVs hid exposures off-balance-sheet;\n"
        "3. Lehman's collapse broke interbank trust — repo markets froze, commercial paper stalled;\n"
        "4. Shadow banking (~$10T) operated outside Fed regulation;\n"
        "5. Rating agencies assigned AAA to fundamentally flawed assets."
    ),
    key_events=[
        CrisisEvent("2007-02", "HSBC reports first major subprime losses", "汇丰银行首次报告次贷巨额亏损", "high"),
        CrisisEvent("2007-08", "BNP Paribas freezes 3 funds, signals liquidity crisis", "法国巴黎银行冻结3只基金，流动性危机信号", "high"),
        CrisisEvent("2008-03", "Bear Stearns acquired by JPMorgan at $2/share (Fed-backed)", "贝尔斯登被摩根大通以2美元/股收购（美联储担保）", "high"),
        CrisisEvent("2008-07", "IndyMac Bank fails — largest bank failure in 24 years", "IndyMac银行倒闭——24年来最大银行倒闭", "medium"),
        CrisisEvent("2008-09-07", "Fannie Mae and Freddie Mac placed into conservatorship", "房利美和房地美被政府接管", "high"),
        CrisisEvent("2008-09-15", "Lehman Brothers files for Chapter 11 bankruptcy ($639B)", "雷曼兄弟申请破产保护（6390亿美元资产）", "high"),
        CrisisEvent("2008-09-16", "Fed rescues AIG with $85B loan; Reserve Primary Fund breaks the buck", "美联储向AIG提供850亿美元救助；货币基金跌破1美元", "high"),
        CrisisEvent("2008-09-25", "Washington Mutual seized — largest bank failure in US history ($307B)", "华盛顿互惠银行被接管——美国历史上最大银行倒闭（3070亿美元）", "high"),
        CrisisEvent("2008-10-03", "TARP signed — $700B bailout package approved by Congress", "TARP签署——国会批准7000亿美元救助方案", "high"),
        CrisisEvent("2008-10-08", "Coordinated global rate cut — Fed, ECB, BoE, Riksbank, Swiss National Bank", "全球央行协调降息——美联储、欧央行、英央行等联合行动", "high"),
        CrisisEvent("2008-11-25", "Fed announces QE1 — $600B MBS purchases", "美联储宣布QE1——6000亿美元抵押贷款支持证券购买", "high"),
        CrisisEvent("2009-03-09", "S&P 500 hits 12-year low of 676 (down 56.8% from peak)", "标普500触及12年低点676点（较高点跌56.8%）", "high"),
        CrisisEvent("2009-03-18", "Fed expands QE1 to $1.75T including Treasuries", "美联储扩大QE1至1.75万亿美元，纳入国债", "high"),
    ],
    phases=[
        CrisisPhase(
            phase_en="Phase 1: Subprime Erosion",
            phase_zh="第一阶段：次贷侵蚀",
            period="2007-02 ~ 2007-07",
            description_en="Early losses in subprime mortgage portfolios; rating downgrades on RMBS/CDO tranches; ABX index decline.",
            description_zh="次贷组合开始出现亏损，RMBS/CDO 评级被下调，ABX 指数持续下跌。此阶段市场尚未充分认识到系统性风险。",
            events=[
                CrisisEvent("2007-02", "HSBC reports first major subprime losses", "汇丰银行首次报告次贷巨额亏损", "medium"),
                CrisisEvent("2007-04", "New Century Financial files for bankruptcy", "新世纪金融申请破产", "medium"),
                CrisisEvent("2007-06", "Bear Stearns halts redemptions on 2 subprime hedge funds", "贝尔斯登暂停两只次贷基金赎回", "medium"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 2: Liquidity Crisis",
            phase_zh="第二阶段：流动性危机",
            period="2007-08 ~ 2008-08",
            description_en="Interbank lending seizes; commercial paper market contracts; Fed launches Term Auction Facility (TAF); Bear Stearns collapses.",
            description_zh="银行间借贷冻结，商业票据市场萎缩。美联储推出定期拍卖工具（TAF）。贝尔斯登倒闭标志着危机升级。",
            events=[
                CrisisEvent("2007-08", "BNP Paribas freezes 3 funds — ECB injects €95B", "巴黎银行冻结3只基金——欧央行注资950亿欧元", "high"),
                CrisisEvent("2007-12", "Fed launches TAF — $20B first auction", "美联储推出TAF——首次200亿美元拍卖", "medium"),
                CrisisEvent("2008-03", "Bear Stearns acquired by JPMorgan at $2/share", "贝尔斯登被摩根大通以2美元/股收购", "high"),
                CrisisEvent("2008-03-11", "Fed creates Primary Dealer Credit Facility (PDCF)", "美联储创设一级交易商信用工具（PDCF）", "medium"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 3: Systemic Collapse",
            phase_zh="第三阶段：系统性崩塌",
            period="2008-09 ~ 2008-11",
            description_en="Lehman bankruptcy triggers global panic; money market funds break the buck; AIG bailout; WaMu fails; TARP enacted; global coordinated rate cut.",
            description_zh="雷曼破产引发全球恐慌，货币基金跌破1美元，AIG被救助，华盛顿互惠倒闭，TARP法案通过，全球央行联合降息。",
            events=[
                CrisisEvent("2008-09-15", "Lehman Brothers files for Chapter 11 ($639B assets)", "雷曼兄弟申请破产保护（资产6390亿美元）", "high"),
                CrisisEvent("2008-09-16", "Fed rescues AIG with $85B; Reserve Primary breaks the buck", "美联储救助AIG 850亿美元；货币基金跌破1美元", "high"),
                CrisisEvent("2008-09-25", "Washington Mutual seized — largest bank failure", "华盛顿互惠银行被接管——美国最大银行倒闭", "high"),
                CrisisEvent("2008-09-29", "Dow drops 777 points — largest single-day point decline", "道指下跌777点——史上最大单日点数跌幅", "high"),
                CrisisEvent("2008-10-03", "TARP signed — $700B bailout approved", "TARP签署——7000亿美元救助方案", "high"),
                CrisisEvent("2008-10-08", "Coordinated global rate cut", "全球央行协调降息", "high"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 4: Market Bottom & Recovery",
            phase_zh="第四阶段：触底与复苏",
            period="2009-03 ~ 2009-12",
            description_en="S&P 500 bottoms at 676; Fed expands QE1; TARP funds deployed; stress tests pass; GDP turns positive in Q3 2009.",
            description_zh="标普500在676点触底，美联储扩大QE1，TARP资金部署，压力测试通过，GDP在2009年Q3转正。",
            events=[
                CrisisEvent("2009-03-09", "S&P 500 bottoms at 676 — down 56.8% from peak", "标普500在676点触底——较高点跌56.8%", "high"),
                CrisisEvent("2009-03-18", "Fed expands QE1 to $1.75T", "美联储扩大QE1至1.75万亿美元", "high"),
                CrisisEvent("2009-04", "Treasury announces PPIP — public-private investment program", "财政部宣布公私合营投资计划（PPIP）", "medium"),
                CrisisEvent("2009-05-07", "Fed stress tests — 10 banks need $75B capital", "美联储压力测试——10家银行需750亿美元资本", "high"),
                CrisisEvent("2009-Q3", "US GDP turns positive (+3.5% annualized)", "美国GDP转正（年化+3.5%）", "high"),
            ],
        ),
    ],
    recovery_actions_zh=(
        "1. 货币政策：美联储将利率降至0-0.25%，启动QE1购买1.75万亿美元资产；\n"
        "2. 财政政策：TARP 7000亿美元注资银行体系，ARRA（复苏法案）7870亿美元财政刺激；\n"
        "3. 金融机构救助：救助AIG（1820亿美元）、花旗集团（450亿美元）、美国银行（450亿美元）；\n"
        "4. 监管改革：《多德-弗兰克法案》通过，设立金融稳定监督委员会（FSOC），沃尔克规则限制自营交易；\n"
        "5. 压力测试：SCAP（监管资本评估计划）对19家大型银行进行压力测试，恢复市场信心；\n"
        "6. FDIC 保险：将存款保险上限从10万提高到25万美元。"
    ),
    recovery_actions_en=(
        "1. Monetary: Fed cut rates to 0-0.25%; QE1 purchased $1.75T in assets;\n"
        "2. Fiscal: TARP ($700B bank recapitalization); ARRA ($787B fiscal stimulus);\n"
        "3. Institution bailouts: AIG ($182B), Citigroup ($45B), Bank of America ($45B);\n"
        "4. Regulatory reform: Dodd-Frank Act created FSOC; Volcker Rule banned proprietary trading;\n"
        "5. Stress tests: SCAP tested 19 largest banks, restoring confidence;\n"
        "6. FDIC: Deposit insurance raised from $100K to $250K."
    ),
    lessons_zh=(
        "1. 「大而不能倒」的机构必须受到更严格的监管——系统重要性金融机构（SIFI）需额外资本缓冲；\n"
        "2. 影子银行体系必须纳入监管——回购市场、货币基金需要透明的清算和抵押品管理；\n"
        "3. 评级机构利益冲突——改革评级模型，减少发行方付费模式的影响；\n"
        "4. 宏观审慎政策的重要性——逆周期资本缓冲、LTV 限制等工具可以在泡沫形成时自动收紧；\n"
        "5. 国际协调至关重要——巴塞尔协议III提高了全球银行资本标准；\n"
        "6. 早期干预优于事后救助——美联储在2020年疫情冲击时吸取教训，立即提供无限流动性。"
    ),
    lessons_en=(
        "1. Too-big-to-fail institutions require stricter oversight — SIFIs need extra capital buffers;\n"
        "2. Shadow banking must be regulated — repo markets and MMFs need transparent clearing;\n"
        "3. Rating agency conflicts — reform models, reduce issuer-pays influence;\n"
        "4. Macroprudential policy is essential — countercyclical buffers, LTV limits;\n"
        "5. International coordination matters — Basel III raised global bank capital standards;\n"
        "6. Early intervention beats late bailout — Fed applied this lesson in COVID-2020."
    ),
    institutional_analyses=[
        {
            "institution": "美联储 (Federal Reserve)",
            "report": "Financial Crisis Inquiry Report (2011)",
            "key_finding_zh": "金融危机的根本原因是金融监管的系统性失败和华尔街风险管理的不负责任行为。",
            "key_finding_en": "The financial crisis was the result of systemic failures in financial regulation and irresponsible risk management on Wall Street.",
            "url": "https://www.govinfo.gov/content/pkg/GPO-FCIC/pdf/GPO-FCIC.pdf",
            "download_url": "https://www.govinfo.gov/content/pkg/GPO-FCIC/pdf/GPO-FCIC.pdf",
            "summary_zh": "美联储主导的金融危机调查委员会在2011年发布了这份576页的报告，是对2008年金融危机最权威的官方调查。报告指出，这场危机本可以避免，其根源在于四个方面：1）金融机构的鲁莽冒险行为，特别是在次级抵押贷款领域；2）监管机构未能履行职责，允许过度杠杆和风险累积；3）评级机构的严重失职，给予垃圾资产AAA评级；4）政府未能及时采取行动阻止危机蔓延。报告提出了多项改革建议，包括加强监管、提高透明度、改善公司治理等。",
            "summary_en": "The FCIC report, published in 2011, is the most authoritative official investigation into the 2008 crisis. It concluded that the crisis was avoidable, caused by: 1) Reckless risk-taking by financial institutions, especially in subprime mortgages; 2) Regulatory failures to prevent excessive leverage; 3) Rating agency misconduct; 4) Government inaction. The report recommended stronger regulation, greater transparency, and improved corporate governance.",
            "conclusion_zh": "**总结意见**：美联储的报告确立了危机调查的标准框架。其核心观点——危机本可避免——对于当前监管具有重要警示意义。在当前市场环境下，需特别关注：1）影子银行体系的风险积累；2）大型科技公司进入金融领域带来的监管挑战；3）AI驱动的高频交易可能引发的新风险。建议投资者密切关注美联储监管政策动向，尤其是对非银行金融机构的监管收紧。",
            "conclusion_en": "**Conclusion**: The Fed's report established the standard framework for crisis investigation. Its core finding - that the crisis was avoidable - has important implications for current regulation. In the current environment, focus on: 1) Shadow banking risk accumulation; 2) Regulatory challenges from big tech entering finance; 3) New risks from AI-driven high-frequency trading. Investors should monitor Fed regulatory policies, especially regarding non-bank financial institutions.",
            "date": "2011-01-27",
        },
        {
            "institution": "IMF",
            "report": "Global Financial Stability Report (April 2009)",
            "key_finding_zh": "全球银行体系损失预计达4万亿美元，需要大规模公共干预来防止系统性崩溃。",
            "key_finding_en": "Global bank losses estimated at $4T; massive public intervention needed to prevent systemic collapse.",
            "url": "https://www.imf.org/en/Publications/GFSR/Issues/2016/12/31/Global-Financial-Stability-Report-April-2009-Chapter-1-Assessing-and-Responding-to-the-Crisis-22330",
            "download_url": "https://www.imf.org/external/pubs/ft/gfsr/2009/01/pdf/text.pdf",
            "summary_zh": "IMF在危机最严重时刻发布的这份报告，对全球金融稳定状况进行了全面评估。报告预测全球银行体系损失将达4万亿美元，其中约一半来自美国。报告强调了三个关键风险：1）资产价格持续下跌可能引发恶性循环；2）新兴市场面临资本外流压力；3）全球协同行动的重要性。报告呼吁各国采取果断措施，包括财政刺激、银行资本重组和国际合作。",
            "summary_en": "Published at the height of the crisis, this IMF report comprehensively assessed global financial stability. It projected $4T in global bank losses, half from the US. Key risks identified: 1) Vicious cycle from falling asset prices; 2) Capital outflows from emerging markets; 3) Need for global coordinated action. The report called for decisive measures including fiscal stimulus, bank recapitalization, and international cooperation.",
            "conclusion_zh": "**总结意见**：IMF的报告提供了危机早期的宏观视角。其4万亿美元损失预测后来被证明基本准确。当前全球经济面临的挑战与此类似——高通胀、利率上升、金融条件收紧。不同之处在于，当前银行体系资本充足率更高，但非银行金融机构风险敞口更大。建议投资者关注IMF对系统性风险的最新评估，特别是对影子银行和新兴市场的警告。",
            "conclusion_en": "**Conclusion**: The IMF report provided an early macro perspective. Its $4T loss projection proved largely accurate. Current global challenges are similar - high inflation, rising rates, tightening financial conditions. The difference is that today's banking system has higher capital ratios, but non-bank financial institutions have larger exposures. Investors should monitor IMF's latest systemic risk assessments, especially warnings on shadow banking and emerging markets.",
            "date": "2009-04",
        },
        {
            "institution": "高盛 (Goldman Sachs)",
            "report": "Report of the Business Standards Committee (2011)",
            "key_finding_zh": "金融危机促使高盛进行全面的业务标准和实践自我评估，提出39项改革建议，重新强调客户利益优先和声誉风险管理。",
            "key_finding_en": "The financial crisis prompted Goldman Sachs to conduct a comprehensive self-assessment of business standards and practices, making 39 reform recommendations and re-emphasizing client interests and reputational risk management.",
            "url": "https://www.goldmansachs.com/our-firm/purpose-and-values/business-standards-committee-report",
            "download_url": "https://www.goldmansachs.com/pdfs/migrated/our-firm/people-and-culture/pdf/business-standards-committee-report.pdf",
            "summary_zh": "高盛作为危机中的核心参与者，这份报告从行业角度总结了危机教训。报告认为流动性风险是最关键的教训——在危机前，市场参与者普遍认为可以随时变现资产，但实际上当市场恐慌时，所有资产同时失去流动性。报告提出了五项关键教训：1）流动性比资本更重要；2）杠杆是双刃剑；3）透明度至关重要；4）风险管理必须跨越机构边界；5）监管和市场结构需要根本性改革。",
            "summary_en": "Goldman Sachs, a central participant in the crisis, provided industry perspective on lessons learned. The report identified liquidity risk as the most critical lesson - before the crisis, market participants assumed assets could always be sold, but in panic, all assets lose liquidity simultaneously. Five key lessons: 1) Liquidity is more important than capital; 2) Leverage is a double-edged sword; 3) Transparency is essential; 4) Risk management must span institutional boundaries; 5) Regulation and market structure need fundamental reform.",
            "conclusion_zh": "**总结意见**：高盛的报告从从业者角度提供了独特见解。其流动性教训在2020年新冠危机中得到验证——美联储必须立即提供无限流动性才能避免系统性崩溃。当前市场环境下，流动性风险依然是最大隐患，特别是在高利率环境下，债券市场流动性可能快速恶化。建议投资者建立流动性缓冲，避免过度依赖短期融资。",
            "conclusion_en": "**Conclusion**: Goldman's report offers unique practitioner insights. Its liquidity lesson was validated in the 2020 COVID crisis - the Fed had to provide unlimited liquidity immediately. In the current environment, liquidity risk remains the biggest concern, especially with higher interest rates where bond market liquidity can deteriorate rapidly. Investors should build liquidity buffers and avoid over-reliance on short-term financing.",
            "date": "2010",
        },
        {
            "institution": "摩根大通 (JPMorgan Chase)",
            "report": "JPMorgan Chase 2008 Annual Report",
            "key_finding_zh": "2008年年报显示，摩根大通通过稳健的资产负债表和收购贝尔斯登、华盛顿互惠银行，在危机中保持了相对韧性，同时凸显了「大而不能倒」机构的系统性影响。",
            "key_finding_en": "The 2008 annual report shows JPMorgan Chase maintained relative resilience through a strong balance sheet and acquisitions of Bear Stearns and Washington Mutual, while highlighting the systemic impact of too-big-to-fail institutions.",
            "url": "https://www.jpmorganchase.com/ir",
            "download_url": "https://www.companiesmarketcap.com/annual-reports/433.ar.en.2008.pdf",
            "summary_zh": "摩根大通在危机中收购了贝尔斯登和华盛顿互惠银行，这份报告从收购者角度反思了危机。报告强调了「大而不能倒」问题的严重性——雷曼倒闭后，市场意识到大型金融机构的倒闭会引发系统性恐慌。报告提出了四项改革建议：1）建立有序清算机制；2）提高资本和流动性要求；3）改善衍生品市场基础设施；4）加强国际协调。",
            "summary_en": "JPMorgan Chase, which acquired Bear Stearns and Washington Mutual during the crisis, reflected from the acquirer's perspective. The report emphasized the severity of the too-big-to-fail problem - after Lehman collapsed, markets realized large financial institution failures trigger systemic panic. Four reform recommendations: 1) Establish Orderly Liquidation Authority; 2) Higher capital and liquidity requirements; 3) Improve derivatives market infrastructure; 4) Strengthen international coordination.",
            "conclusion_zh": "**总结意见**：摩根大通的报告推动了《多德-弗兰克法案》中有序清算机制的建立。当前「大而不能倒」问题依然存在，但银行体系已经更加稳固。然而，非银行金融机构（如资产管理公司、对冲基金）的系统性风险正在上升。建议投资者关注美联储对系统重要性金融机构（SIFI）的最新评估，以及对非银机构监管的动向。",
            "conclusion_en": "**Conclusion**: JPMorgan's report helped drive the establishment of Orderly Liquidation Authority in Dodd-Frank. The too-big-to-fail problem persists, but banks are more resilient. However, systemic risk from non-bank financial institutions (asset managers, hedge funds) is rising. Investors should monitor Fed's latest SIFI assessments and regulatory moves on non-bank institutions.",
            "date": "2010",
        },
        {
            "institution": "BIS (国际清算银行)",
            "report": "79th Annual Report (2009)",
            "key_finding_zh": "宏观审慎框架的缺失使得政策制定者无法在泡沫形成期间采取行动。信贷与GDP缺口应作为预警指标。",
            "key_finding_en": "The absence of a macroprudential framework prevented policymakers from acting during bubble formation. Credit-to-GDP gap should serve as an early warning indicator.",
            "url": "https://www.bis.org/publ/arpdf/ar2009.htm",
            "download_url": "https://www.bis.org/publ/arpdf/ar2009e.pdf",
            "summary_zh": "BIS作为全球央行的央行，这份年度报告提供了宏观审慎视角。报告指出，危机的根本原因在于宏观审慎监管的缺失——各国央行和监管机构专注于微观审慎监管（单个机构的安全），而忽视了系统性风险的累积。报告提出了信贷与GDP缺口作为危机预警指标，并呼吁建立宏观审慎框架，包括逆周期资本缓冲、贷款价值比限制等工具。",
            "summary_en": "BIS, the central bank of central banks, provided a macroprudential perspective in this annual report. It identified the absence of macroprudential regulation as the root cause - central banks focused on microprudential supervision (individual institution safety) while ignoring systemic risk accumulation. The report proposed credit-to-GDP gap as an early warning indicator and called for a macroprudential framework including countercyclical capital buffers and LTV limits.",
            "conclusion_zh": "**总结意见**：BIS的报告奠定了宏观审慎政策的理论基础，直接推动了巴塞尔协议III的出台。当前全球信贷与GDP缺口处于历史高位，特别是在发达国家。建议投资者密切关注BIS的季度报告，其对系统性风险的评估具有领先指标意义。同时，关注各国央行是否正在收紧宏观审慎政策。",
            "conclusion_en": "**Conclusion**: BIS's report laid the theoretical foundation for macroprudential policy, directly contributing to Basel III. Current global credit-to-GDP gaps are at historical highs, especially in developed countries. Investors should closely monitor BIS's quarterly reports as their systemic risk assessments have leading indicator significance. Also watch whether central banks are tightening macroprudential policies.",
            "date": "2009",
        },
        {
            "institution": "NBER",
            "report": "The Financial Crisis Inquiry: Causes and Lessons (2012)",
            "key_finding_zh": "危机前信贷标准的急剧恶化和家庭杠杆率的飙升是最可靠的预警信号。",
            "key_finding_en": "The sharp deterioration in lending standards and the surge in household leverage were the most reliable early warning signals.",
            "url": "https://www.nber.org/books-and-chapters/financial-crisis-inquiry-report-final-report-financial-crisis-inquiry-commission",
            "download_url": "https://www.nber.org/system/files/chapters/c12138/c12138.pdf",
            "summary_zh": "NBER作为美国最权威的经济研究机构，这份报告从学术角度分析了危机原因。报告发现，危机前的信贷标准恶化和家庭杠杆率飙升是最可靠的预警信号。具体而言：1）次级抵押贷款占比从2001年的8%上升到2006年的20%；2）家庭债务与可支配收入之比从100%上升到130%；3）贷款价值比（LTV）超过100%的贷款比例大幅增加。报告强调，这些信号本应引起政策制定者的警惕。",
            "summary_en": "NBER, America's most authoritative economic research institution, analyzed crisis causes from an academic perspective. It found that the sharp deterioration in lending standards and surge in household leverage were the most reliable early warning signals: 1) Subprime mortgages rose from 8% (2001) to 20% (2006); 2) Household debt-to-disposable income rose from 100% to 130%; 3) LTV ratios exceeding 100% increased dramatically. These signals should have alerted policymakers.",
            "conclusion_zh": "**总结意见**：NBER的研究为危机预警提供了量化指标。当前家庭杠杆率虽然低于2008年峰值，但企业杠杆率处于历史高位，特别是非金融企业债务。建议投资者关注企业部门的债务可持续性，特别是高收益债市场的违约率变化。同时，监控房地产市场的信贷标准是否正在放松。",
            "conclusion_en": "**Conclusion**: NBER's research provides quantitative indicators for crisis early warning. While household leverage is below 2008 peaks, corporate leverage is at historic highs, especially non-financial corporate debt. Investors should monitor corporate debt sustainability, particularly high-yield bond default rates. Also watch whether lending standards in real estate markets are relaxing.",
            "date": "2012",
        },
    ],
    figure_actions=[
        CrisisFigureAction(
            date="2008-09-15",
            figure="沃伦·巴菲特 (Warren Buffett)",
            figure_en="Warren Buffett",
            action_zh="在市场恐慌之际投资50亿美元购买高盛永久性优先股，股息率10%",
            action_en="Invested $5B in Goldman Sachs perpetual preferred stock with 10% dividend amid panic",
            asset_class="股票/优先股",
            strategy_zh="在市场流动性枯竭时向优质金融机构提供资本，获取高股息和认股权证",
            strategy_en="Provided capital to quality financial institutions during liquidity freeze, capturing high dividends and warrants",
            outcome_zh="2011年行权获利约35亿美元，收益率超过70%；同时获得数亿美元股息",
            outcome_en="Exercised warrants in 2011 with ~$3.5B profit, return >70%; collected hundreds of millions in dividends",
            gain_pct=70.0,
            tags=["逆向投资", "金融股", "优先股"],
        ),
        CrisisFigureAction(
            date="2008-10-01",
            figure="沃伦·巴菲特 (Warren Buffett)",
            figure_en="Warren Buffett",
            action_zh="向通用电气(GE)投资30亿美元优先股，股息率10%",
            action_en="Invested $3B in GE preferred stock with 10% dividend",
            asset_class="股票/优先股",
            strategy_zh="抄底工业巨头，利用市场恐慌获取高收益优先股",
            strategy_en="Bottom-fished industrial giant via high-yield preferred stock during market panic",
            outcome_zh="2013年GE回购股份，伯克希尔获利约12亿美元",
            outcome_en="GE redeemed shares in 2013, Berkshire pocketed ~$1.2B profit",
            gain_pct=40.0,
            tags=["逆向投资", "工业股", "优先股"],
        ),
        CrisisFigureAction(
            date="2009-03-01",
            figure="约翰·保尔森 (John Paulson)",
            figure_en="John Paulson",
            action_zh="在2007-2008年通过做空次贷CDO获利约150亿美元后，转向抄底银行股",
            action_en="After making ~$15B shorting subprime CDOs in 2007-08, rotated into bank stocks",
            asset_class="股票/并购",
            strategy_zh="先做空次贷泡沫，后抄底被错杀的银行资产",
            strategy_en="Shorted subprime bubble first, then bought beaten-down bank assets",
            outcome_zh="2009年旗下基金回报率约30-40%，从做空到做多的转换极为成功",
            outcome_en="Funds returned ~30-40% in 2009, transition from short to long was highly successful",
            gain_pct=35.0,
            tags=["做空", "转换仓位", "银行股"],
        ),
        CrisisFigureAction(
            date="2008-09-15",
            figure="杰米·戴蒙 (Jamie Dimon) / 摩根大通",
            figure_en="Jamie Dimon / JPMorgan Chase",
            action_zh="以约2美元/股（后上调至10美元）收购破产的贝尔斯登",
            action_en="Acquired bankrupt Bear Stearns at ~$2/share (later raised to $10) with Fed backing",
            asset_class="并购",
            strategy_zh="在美联储支持下低价收购 distressed assets，扩展投行业务版图",
            strategy_en="Bought distressed assets cheaply with Fed support, expanding investment banking footprint",
            outcome_zh="获得贝尔斯登的办公楼和经纪业务，资产整合后摩根大通成为美国最大银行",
            outcome_en="Gained Bear's buildings and brokerage; JPM became largest US bank after integration",
            gain_pct=25.0,
            tags=["并购", "困境资产", "政府救助"],
        ),
        CrisisFigureAction(
            date="2009-03-09",
            figure="大卫·泰珀 (David Tepper)",
            figure_en="David Tepper",
            action_zh="在市场底部大量买入花旗集团、美国银行等困境银行股票",
            action_en="Aggressively bought distressed bank stocks like Citigroup and Bank of America at market bottom",
            asset_class="股票",
            strategy_zh="相信政府不会允许大银行倒闭，在政府兜底假设下抄底",
            strategy_en="Bet that government would not let major banks fail, buying on implicit government backstop",
            outcome_zh="2009年Appaloosa基金回报率超过130%，成为当年最佳对冲基金",
            outcome_en="Appaloosa returned >130% in 2009, becoming top hedge fund of the year",
            gain_pct=130.0,
            tags=["困境投资", "银行股", "高回报"],
        ),
        CrisisFigureAction(
            date="2008-10-03",
            figure="美国财政部 / 亨利·保尔森",
            figure_en="US Treasury / Henry Paulson",
            action_zh="推动TARP法案通过，向银行体系注资约2500亿美元",
            action_en="Pushed TARP through Congress, injecting ~$250B into banking system",
            asset_class="优先股/救助",
            strategy_zh="政府以优先股形式注资银行，附带限制高管薪酬和股息条款",
            strategy_en="Government recapitalized banks via preferred stakes with executive compensation and dividend restrictions",
            outcome_zh="救助资金最终收回并获利，稳定了金融系统",
            outcome_en="Bailout funds were mostly repaid with profit, stabilizing the financial system",
            gain_pct=8.0,
            tags=["政府救助", "银行体系", "系统性风险"],
        ),
    ],
)


# 2000 互联网泡沫破裂
CRISIS_DOTCOM = CrisisData(
    id="dotcom_2000",
    name_en="Dot-Com Crash 2000-2002",
    name_zh="2000 互联网泡沫破裂",
    period="2000-2002",
    severity="major",
    peak_unemployment=6.3,
    peak_decline_snp=-49.1,
    peak_decline_gdp=-0.3,
    duration_months=30,
    causes_zh=(
        "1. 科技股估值泡沫——大量无盈利互联网公司IPO，市盈率远超历史均值；\n"
        "2. 投机资金涌入——散户Day Trading盛行，保证金购买推高股价；\n"
        "3. 会计欺诈——安然(Enron)和世通(WorldCom)财务造假暴露；\n"
        "4. 美联储加息——1999-2000年连续加息，资金成本飙升。"
    ),
    causes_en=(
        "1. Tech stock valuation bubble — unprofitable dot-com IPOs at extreme P/E ratios;\n"
        "2. Speculative capital inflows — retail day trading, margin buying;\n"
        "3. Accounting fraud — Enron and WorldCom scandals;\n"
        "4. Fed tightening — consecutive rate hikes in 1999-2000."
    ),
    key_events=[
        CrisisEvent("2000-03", "NASDAQ peaks at 5,048", "纳斯达克达到5048点峰值", "high"),
        CrisisEvent("2000-04", "Microsoft antitrust ruling — stock drops 14%", "微软反垄断裁决——股价下跌14%", "medium"),
        CrisisEvent("2000-09", "Priceline drops 97% from peak", "Priceline较高点跌97%", "medium"),
        CrisisEvent("2001-01", "Fed begins cutting rates — 50bps emergency cut", "美联储开始降息——紧急50个基点", "high"),
        CrisisEvent("2001-09-11", "September 11 attacks — NYSE closed for 4 days", "9·11恐怖袭击——纽交所关闭4天", "high"),
        CrisisEvent("2001-12", "Enron files for bankruptcy", "安然申请破产", "high"),
        CrisisEvent("2002-06", "WorldCom admits $3.8B accounting fraud", "世通承认38亿美元会计欺诈", "high"),
        CrisisEvent("2002-07", "Sarbanes-Oxley Act signed into law", "《萨班斯-奥克斯利法案》签署", "high"),
        CrisisEvent("2002-10", "NASDAQ bottoms at 1,114 — down 78% from peak", "纳斯达克在1114点触底——较高点跌78%", "high"),
    ],
    phases=[
        CrisisPhase(
            phase_en="Phase 1: Bubble Burst",
            phase_zh="第一阶段：泡沫破裂",
            period="2000-03 ~ 2000-12",
            description_en="NASDAQ peaks and begins decline; speculative names collapse first; institutional selling accelerates.",
            description_zh="纳斯达克见顶后开始下跌，投机性个股率先崩塌，机构抛售加速。",
            events=[
                CrisisEvent("2000-03-10", "NASDAQ peaks at 5,048.62", "纳斯达克达到5048.62点峰值", "high"),
                CrisisEvent("2000-04-03", "Microsoft antitrust ruling — stock drops 14%", "微软反垄断裁决——股价下跌14%", "medium"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 2: Recession & Fraud",
            phase_zh="第二阶段：衰退与欺诈",
            period="2001-01 ~ 2001-12",
            description_en="Fed cuts rates aggressively; 9/11 attacks; Enron bankruptcy; recession officially begins.",
            description_zh="美联储大幅降息，9·11事件，安然倒闭，经济衰退正式开始。",
            events=[
                CrisisEvent("2001-01-03", "Fed emergency 50bps cut", "美联储紧急降息50基点", "high"),
                CrisisEvent("2001-09-11", "September 11 attacks", "9·11恐怖袭击", "high"),
                CrisisEvent("2001-12-02", "Enron files for Chapter 11", "安然申请破产保护", "high"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 3: Cleanup & Bottom",
            phase_zh="第三阶段：清算与触底",
            period="2002-01 ~ 2002-10",
            description_en="WorldCom fraud exposed; SOX passed; NASDAQ bottoms at 1,114.",
            description_zh="世通欺诈暴露，SOX法案通过，纳斯达克在1114点触底。",
            events=[
                CrisisEvent("2002-06-25", "WorldCom admits $3.8B fraud", "世通承认38亿美元欺诈", "high"),
                CrisisEvent("2002-07-30", "Sarbanes-Oxley Act signed", "萨班斯-奥克斯利法案签署", "high"),
                CrisisEvent("2002-10-09", "NASDAQ bottoms at 1,114 — down 78%", "纳斯达克触底1114点——跌78%", "high"),
            ],
        ),
    ],
    recovery_actions_zh=(
        "1. 美联储将利率从6.5%降至1%（2003年）；\n"
        "2. 布什政府减税1.35万亿美元；\n"
        "3. 《萨班斯-奥克斯利法案》加强公司治理和审计监管；\n"
        "4. 安然和世通高管被刑事追责。"
    ),
    recovery_actions_en=(
        "1. Fed cut rates from 6.5% to 1% (by 2003);\n"
        "2. Bush tax cuts totaling $1.35T;\n"
        "3. Sarbanes-Oxley Act strengthened corporate governance;\n"
        "4. Enron and WorldCom executives criminally prosecuted."
    ),
    lessons_zh=(
        "1. 盈利能力是估值的最终锚——无盈利的商业模式不可持续；\n"
        "2. 会计透明度和审计独立性是市场信任的基石；\n"
        "3. 监管应对新兴行业保持警惕——不因「新经济」叙事而放松标准。"
    ),
    lessons_en=(
        "1. Profitability is the ultimate valuation anchor;\n"
        "2. Accounting transparency and audit independence are foundations of market trust;\n"
        "3. Regulators must stay vigilant on emerging sectors — 'new economy' narratives shouldn't lower standards."
    ),
    institutional_analyses=[
        {
            "institution": "美联储",
            "report": "Monetary Policy and the Stock Market Bubble (Bernanke & Gertler, 2001)",
            "key_finding_zh": "货币政策不应直接针对资产价格泡沫，但应在泡沫破裂后迅速提供流动性。",
            "key_finding_en": "Monetary policy should not target asset bubbles directly, but should provide liquidity quickly after a bust.",
            "url": "https://www.federalreserve.gov/pubs/ifdp/2001/704/ifdp704.pdf",
            "download_url": "https://www.federalreserve.gov/pubs/ifdp/2001/704/ifdp704.pdf",
            "summary_zh": "伯南克和格特勒在2001年发表的这份学术论文，探讨了货币政策与资产价格泡沫的关系。论文认为，央行不应在泡沫形成期间主动刺破泡沫，因为很难准确识别泡沫。相反，央行应该关注泡沫破裂后的后果，及时提供足够的流动性支持，减轻经济衰退的影响。这一观点被称为「格林斯潘-伯南克学说」，对后来的货币政策制定产生了深远影响。",
            "summary_en": "Bernanke & Gertler's 2001 academic paper examines the relationship between monetary policy and asset price bubbles. It argues central banks should not proactively burst bubbles during formation since bubbles are hard to identify accurately. Instead, central banks should focus on consequences after bubbles burst, providing sufficient liquidity support to mitigate recession impact. This view became known as the 'Greenspan-Bernanke doctrine'.",
            "conclusion_zh": "**总结意见**：该论文为央行应对资产泡沫提供了理论框架。然而，2008年危机表明，忽视泡沫积累可能导致严重后果。当前美联储面临类似困境——科技股估值处于历史高位，但加息可能引发市场回调。建议投资者关注美联储政策立场的微妙变化，特别是对资产价格的态度转变。",
            "conclusion_en": "**Conclusion**: This paper provided a theoretical framework for central banks responding to asset bubbles. However, the 2008 crisis showed ignoring bubble accumulation can have severe consequences. The Fed now faces similar dilemmas - tech stock valuations are at historic highs, but rate hikes could trigger market corrections. Investors should monitor subtle shifts in Fed policy stance, especially regarding asset prices.",
            "date": "2001",
        },
        {
            "institution": "NBER",
            "report": "The Dot-Com Bubble and the Financial Crisis (2013)",
            "key_finding_zh": "互联网泡沫的破裂虽然导致股市大幅下跌，但由于银行体系未深度参与，未演变为系统性金融危机。",
            "key_finding_en": "The dot-com crash caused massive equity losses but did not become systemic because banks were not deeply exposed.",
            "url": "https://www.nber.org/papers/w19279",
            "download_url": "https://www.nber.org/papers/w19279.pdf",
            "summary_zh": "NBER在2013年发表的研究对比了互联网泡沫和2008年金融危机。研究发现，两者的关键区别在于银行体系的参与程度：互联网泡沫主要是股权市场的问题，银行体系未深度卷入；而2008年危机是信贷市场的问题，银行持有大量有毒资产。这一区别解释了为何互联网泡沫破裂后经济衰退相对温和，而2008年危机演变为全球系统性危机。",
            "summary_en": "NBER's 2013 study compared the dot-com bubble and the 2008 financial crisis. It found the key difference was banking system involvement: the dot-com bubble was primarily an equity market issue with minimal bank exposure, while the 2008 crisis was a credit market problem with banks holding massive toxic assets. This explains why the dot-com bust led to a relatively mild recession while 2008 became a global systemic crisis.",
            "conclusion_zh": "**总结意见**：该研究为区分「股市泡沫」和「金融系统危机」提供了重要视角。当前科技股估值高企，但银行体系参与度较低，更类似于2000年的情况而非2008年。然而，非银行金融机构（如对冲基金、ETF）的风险敞口正在上升，这是需要警惕的新因素。建议投资者关注非银金融机构的杠杆水平和流动性状况。",
            "conclusion_en": "**Conclusion**: This study provides an important perspective on distinguishing 'equity bubbles' from 'financial system crises'. Current tech valuations are elevated but banking system involvement is low, more similar to 2000 than 2008. However, non-bank financial institution (hedge funds, ETFs) exposures are rising - a new factor requiring vigilance. Investors should monitor non-bank leverage and liquidity conditions.",
            "date": "2013",
        },
    ],
    figure_actions=[
        CrisisFigureAction(
            date="2000-03-10",
            figure="沃伦·巴菲特 (Warren Buffett)",
            figure_en="Warren Buffett",
            action_zh="在纳斯达克创下5048点历史新高时，伯克希尔未持有任何科技股，因认为估值不可持续",
            action_en="Berkshire held no tech stocks when Nasdaq hit record 5048, viewing valuations as unsustainable",
            asset_class="现金/回避",
            strategy_zh="坚持能力圈原则，不参与无法估值的互联网泡沫；持有大量现金等待机会",
            strategy_en="Stuck to circle of competence, avoided unvaluable dot-com bubble; held cash for opportunities",
            outcome_zh="泡沫破裂后标普500跌49%，伯克希尔几乎未受影响，并在低位增持可口可乐、吉列等优质资产",
            outcome_en="While S&P 500 fell 49% during bust, Berkshire was barely affected and added quality assets cheaply",
            gain_pct=15.0,
            tags=["回避泡沫", "能力圈", "现金为王"],
        ),
        CrisisFigureAction(
            date="2002-07-21",
            figure="沃伦·巴菲特 (Warren Buffett)",
            figure_en="Warren Buffett",
            action_zh="在世界通信(WorldCom)破产（美国最大破产案）后买入垃圾债券",
            action_en="Bought distressed junk bonds after WorldCom's bankruptcy, then the largest in US history",
            asset_class="垃圾债券",
            strategy_zh="在优质公司债券被非理性抛售时抄底，锁定高收益",
            strategy_en="Bottom-fished quality corporate bonds during irrational selling, locking in high yields",
            outcome_zh=" Berkshire在WorldCom债券上获得约20亿美元收益",
            outcome_en="Berkshire made ~$2B profit on WorldCom bonds",
            gain_pct=50.0,
            tags=["困境债券", "通信行业", "高收益"],
        ),
        CrisisFigureAction(
            date="2000-04-01",
            figure="乔治·索罗斯 (George Soros)",
            figure_en="George Soros",
            action_zh="1999年做多科技股获利后，在2000年初纳斯达克见顶前后做空科技股",
            action_en="After profiting from tech longs in 1999, shorted tech stocks around Nasdaq peak in early 2000",
            asset_class="股票/做空",
            strategy_zh="利用量子基金规模优势，在市场情绪逆转时做空高估值科技股",
            strategy_en="Used Quantum Fund's scale to short overvalued tech as market sentiment reversed",
            outcome_zh="量子基金在2000年获得约20%回报，成功避开泡沫破裂",
            outcome_en="Quantum Fund returned ~20% in 2000, successfully navigating the crash",
            gain_pct=20.0,
            tags=["做空", "科技股", "宏观择时"],
        ),
        CrisisFigureAction(
            date="2000-04-01",
            figure="老虎基金 (Tiger Management) / 朱利安·罗伯逊",
            figure_en="Tiger Management / Julian Robertson",
            action_zh="拒绝买入高估值科技股，坚持价值投资策略",
            action_en="Refused to buy overvalued tech stocks, sticking to value investing",
            asset_class="股票/回避",
            strategy_zh="坚守传统估值框架，不跟风买入无盈利科技股",
            strategy_en="Maintained traditional valuation discipline, avoided profitless tech stocks",
            outcome_zh="客户大量赎回导致基金于2000年3月关闭，但罗伯逊个人在后续投资中持续获利",
            outcome_en="Client redemptions forced fund closure in March 2000, but Robertson personally profited later",
            gain_pct=-10.0,
            tags=["价值投资", "基金清盘", "坚守原则"],
        ),
        CrisisFigureAction(
            date="2002-01-01",
            figure="比尔·阿克曼 (Bill Ackman)",
            figure_en="Bill Ackman",
            action_zh="做空MBIA等金融担保公司，押注其承保的MBS和CDO将违约",
            action_en="Shorted bond insurers like MBIA, betting their MBS/CDO guarantees would default",
            asset_class="股票/做空",
            strategy_zh="深入研究结构化金融产品的风险，做空为次贷提供担保的金融公司",
            strategy_en="Deep research into structured product risks, shorted financials guaranteeing subprime",
            outcome_zh="在2007-2008年获得巨额回报，奠定了其作为激进对冲基金经理的声誉",
            outcome_en="Generated huge returns in 2007-08, establishing reputation as activist hedge fund manager",
            gain_pct=60.0,
            tags=["做空", "金融担保", "结构性产品"],
        ),
    ],
)


# 1929 大萧条
CRISIS_1929 = CrisisData(
    id="great_depression_1929",
    name_en="Great Depression 1929-1933",
    name_zh="1929 大萧条",
    period="1929-1933",
    severity="2008-level",
    peak_unemployment=24.9,
    peak_decline_snp=-89.2,
    peak_decline_gdp=-26.7,
    duration_months=43,
    causes_zh=(
        "1. 1920年代过度投机——保证金比率仅10%，杠杆极高；\n"
        "2. 货币政策失误——美联储在衰退中紧缩货币，导致银行挤兑；\n"
        "3. 贸易战——《斯穆特-霍利关税法》引发全球贸易报复；\n"
        "4. 金本位束缚——各国为维持金本位而紧缩，无法提供刺激；\n"
        "5. 银行体系崩溃——1930-1933年逾9000家银行倒闭。"
    ),
    causes_en=(
        "1. Excessive speculation in the 1920s — margin requirements only 10%;\n"
        "2. Monetary policy errors — Fed tightened during recession, causing bank runs;\n"
        "3. Trade war — Smoot-Hawley Tariff triggered global retaliation;\n"
        "4. Gold standard constraint — countries couldn't stimulate without abandoning gold;\n"
        "5. Banking system collapse — 9,000+ banks failed 1930-1933."
    ),
    key_events=[
        CrisisEvent("1929-09-03", "Dow peaks at 381.17", "道指达到381.17点峰值", "high"),
        CrisisEvent("1929-10-24", "Black Thursday — Dow drops 11% at open", "黑色星期四——道指开盘跌11%", "high"),
        CrisisEvent("1929-10-29", "Black Tuesday — Dow drops 12%; volume 16M shares", "黑色星期二——道指跌12%，成交量1600万股", "high"),
        CrisisEvent("1930-06", "Smoot-Hawley Tariff Act signed", "《斯穆特-霍利关税法》签署", "high"),
        CrisisEvent("1930-12-11", "Bank of United States fails — largest bank failure", "美国银行倒闭——当时最大银行倒闭", "high"),
        CrisisEvent("1931-09-21", "Britain abandons gold standard", "英国放弃金本位", "high"),
        CrisisEvent("1933-03-06", "Bank Holiday — FDR closes all banks", "银行假期——罗斯福关闭所有银行", "high"),
        CrisisEvent("1933-03-09", "Emergency Banking Act passed", "《紧急银行法案》通过", "high"),
        CrisisEvent("1933-07", "Dow bottoms at 40.56 — down 89.2% from peak", "道指在40.56点触底——较高点跌89.2%", "high"),
    ],
    phases=[
        CrisisPhase(
            phase_en="Phase 1: Crash",
            phase_zh="第一阶段：崩盘",
            period="1929-09 ~ 1929-11",
            description_en="Dow peaks at 381 then crashes; Black Thursday and Black Tuesday wipe out fortunes.",
            description_zh="道指在381点见顶后崩盘，黑色星期四和黑色星期二抹去大量财富。",
            events=[
                CrisisEvent("1929-10-24", "Black Thursday — Dow drops 11%", "黑色星期四——道指跌11%", "high"),
                CrisisEvent("1929-10-29", "Black Tuesday — Dow drops 12%", "黑色星期二——道指跌12%", "high"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 2: Bank Failures & Trade War",
            phase_zh="第二阶段：银行倒闭与贸易战",
            period="1930-01 ~ 1931-12",
            description_en="Smoot-Hawley tariff triggers retaliation; Bank of US fails; Britain leaves gold standard.",
            description_zh="斯穆特-霍利关税引发报复，美国银行倒闭，英国放弃金本位。",
            events=[
                CrisisEvent("1930-06-17", "Smoot-Hawley Tariff signed", "斯穆特-霍利关税法签署", "high"),
                CrisisEvent("1930-12-11", "Bank of United States fails", "美国银行倒闭", "high"),
                CrisisEvent("1931-09-21", "Britain abandons gold standard", "英国放弃金本位", "high"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 3: Bottom & New Deal",
            phase_zh="第三阶段：触底与新政",
            period="1932-01 ~ 1933-12",
            description_en="Bank Holiday; FDR's New Deal; Emergency Banking Act; Gold standard abandoned.",
            description_zh="银行假期，罗斯福新政，紧急银行法案，放弃金本位。",
            events=[
                CrisisEvent("1933-03-06", "Bank Holiday — all banks closed", "银行假期——所有银行关闭", "high"),
                CrisisEvent("1933-03-09", "Emergency Banking Act", "紧急银行法案通过", "high"),
                CrisisEvent("1933-07", "Dow bottoms at 40.56", "道指在40.56点触底", "high"),
            ],
        ),
    ],
    recovery_actions_zh=(
        "1. 罗斯福新政——公共工程计划、社会保障法案、劳工权利保护；\n"
        "2. 银行改革——《格拉斯-斯蒂格尔法案》分立商业银行和投行，建立FDIC存款保险；\n"
        "3. 放弃金本位——允许货币政策扩张；\n"
        "4. 证券监管——《证券法》(1933)和《证券交易法》(1934)，成立SEC。"
    ),
    recovery_actions_en=(
        "1. FDR's New Deal — public works, Social Security, labor rights;\n"
        "2. Banking reform — Glass-Steagall Act separated commercial and investment banking; FDIC created;\n"
        "3. Abandoned gold standard — enabled monetary expansion;\n"
        "4. Securities regulation — Securities Act (1933) and Exchange Act (1934), SEC established."
    ),
    lessons_zh=(
        "1. 货币紧缩在经济衰退中是灾难性的——美联储的紧缩将普通衰退变成了大萧条；\n"
        "2. 贸易保护主义是全球经济的毒药——关税战使所有人更穷；\n"
        "3. 存款保险是防止银行挤兑的关键——FDIC的建立结束了银行恐慌；\n"
        "4. 金本位在危机中是紧缩枷锁——弹性货币制度是现代经济稳定的基石。"
    ),
    lessons_en=(
        "1. Monetary tightening during recession is catastrophic — Fed's contraction turned recession into depression;\n"
        "2. Protectionism poisons global economy — tariff wars make everyone poorer;\n"
        "3. Deposit insurance prevents bank runs — FDIC ended banking panics;\n"
        "4. Gold standard is a deflationary straitjacket in crises — fiat currency enables modern stability."
    ),
    institutional_analyses=[
        {
            "institution": "美联储 (Federal Reserve)",
            "report": "A Monetary History of the United States (Friedman & Schwartz, 1963)",
            "key_finding_zh": "美联储在1929-1933年将货币供应量缩减了三分之一，是导致普通衰退演变为大萧条的首要原因。",
            "key_finding_en": "The Fed allowed the money supply to fall by one-third (1929-1933), turning a recession into the Great Depression.",
            "url": "https://press.princeton.edu/books/paperback/9780691003542/a-monetary-history-of-the-united-states-1867-1960",
            "download_url": "https://press.princeton.edu/books/paperback/9780691003542/a-monetary-history-of-the-united-states-1867-1960",
            "summary_zh": "弗里德曼和施瓦茨在1963年出版的这部巨著，是货币经济学历史上最重要的著作之一。关于大萧条的研究指出，美联储在1929-1933年期间未能阻止货币供应量崩溃，将本可控制的衰退演变为全球性大萧条。研究表明，银行倒闭潮、货币政策紧缩和金本位制度共同作用，导致美国货币供应量下降了约三分之一。",
            "summary_en": "Friedman and Schwartz's 1963 magnum opus is one of the most important works in monetary economics. Their study of the Great Depression argues that the Fed's failure to prevent the collapse of the money supply between 1929-1933 turned a manageable recession into a global depression. Bank failures, tight monetary policy, and the gold standard together caused the US money supply to fall by about one-third.",
            "conclusion_zh": "**总结意见**：该著作确立了货币政策在经济衰退中至关重要的作用。当前与1929年的主要区别在于，现代央行已深刻理解流动性危机的危害，并拥有QE等工具。但需警惕的是，如果未来发生大规模银行危机且央行行动迟缓，历史可能重演。建议投资者关注央行资产负债表变化和广义货币供应量增速。",
            "conclusion_en": "**Conclusion**: This work established the crucial role of monetary policy during recessions. The main difference from 1929 is that modern central banks understand liquidity crises and have QE tools. However, if a major banking crisis occurs and central banks act slowly, history could repeat. Investors should monitor central bank balance sheets and broad money supply growth.",
            "date": "1963",
        },
        {
            "institution": "BIS",
            "report": "70th Annual Report (2000)",
            "key_finding_zh": "BIS 2000年年报指出，金本位制度将美国的通缩传导至全球，较早放弃金本位的国家（如英国）恢复更快。",
            "key_finding_en": "The BIS 2000 Annual Report noted that the gold standard transmitted US deflation globally; countries that abandoned gold earlier recovered faster.",
            "url": "https://www.bis.org/publ/arpdf/archive/index.htm?ar_archive=2000s",
            "download_url": "https://www.bis.org/publ/arpdf/archive/index.htm?ar_archive=2000s",
            "summary_zh": "BIS年度报告从大萧条中提取了国际层面的教训。报告强调，金本位制度在危机期间扮演了关键角色：美国通过金本位将通缩压力传导至其他发达国家，加剧了全球衰退。那些较早放弃金本位、采取独立货币政策的国家（如英国）经济复苏更快。这一发现对当前的固定汇率制度和货币政策协调具有重要参考价值。",
            "summary_en": "The BIS annual report drew international lessons from the Great Depression. It emphasized that the gold standard played a key role during the crisis: the US transmitted deflationary pressure to other developed countries through the gold standard, worsening the global recession. Countries that abandoned gold earlier and pursued independent monetary policies (such as the UK) recovered faster. This has important implications for current fixed exchange rate regimes and monetary policy coordination.",
            "conclusion_zh": "**总结意见**：该报告强调了汇率制度和货币政策独立性的重要性。当前全球不存在金本位，但美元霸权实际上形成了类似的国际传导机制。美国的货币政策通过美元汇率、资本流动和全球贸易影响世界各国。投资者应关注美元周期对新兴市场和大宗商品的影响。",
            "conclusion_en": "**Conclusion**: The report highlights the importance of exchange rate regimes and monetary policy independence. While the gold standard no longer exists, dollar hegemony creates a similar international transmission mechanism. US monetary policy affects the world through the dollar exchange rate, capital flows, and global trade. Investors should monitor the dollar cycle's impact on emerging markets and commodities.",
            "date": "2000",
        },
    ],
    figure_actions=[
        CrisisFigureAction(
            date="1929-10-24",
            figure="约翰·D·洛克菲勒 (John D. Rockefeller)",
            figure_en="John D. Rockefeller",
            action_zh="黑色星期四当天宣布大量买入美国钢铁等股票，试图稳定市场信心",
            action_en="Announced heavy buying of US Steel and other stocks on Black Thursday to stabilize confidence",
            asset_class="股票",
            strategy_zh="利用个人声誉和资金在恐慌中托市，但未能阻止崩盘",
            strategy_en="Used personal reputation and capital to support market during panic, but failed to stop crash",
            outcome_zh="短期提振失效，道指后续仍暴跌89%；洛克菲勒家族财富大幅缩水但仍保持雄厚实力",
            outcome_en="Short-lived support failed; Dow eventually fell 89%; Rockefeller wealth declined but remained formidable",
            gain_pct=-40.0,
            tags=["救市", "蓝筹股", "信心托底"],
        ),
        CrisisFigureAction(
            date="1930-01-01",
            figure="本杰明·格雷厄姆 (Benjamin Graham)",
            figure_en="Benjamin Graham",
            action_zh="在1930-1932年间持续抄底，试图捡便宜股票，但因使用杠杆而遭受重创",
            action_en="Continued bottom-fishing in 1930-1932, but suffered heavy losses due to leverage",
            asset_class="股票",
            strategy_zh="早期价值投资实践，在市场下跌时买入低估股票，但低估了熊市持续时间",
            strategy_en="Early value investing practice; bought undervalued stocks during decline but underestimated bear market duration",
            outcome_zh="对冲基金亏损约70%，个人财务几乎破产，但后续创立价值投资理论",
            outcome_en="Hedge fund lost ~70%, personal finances nearly bankrupt, but later founded value investing theory",
            gain_pct=-70.0,
            tags=["价值投资", "杠杆", "抄底失败"],
        ),
        CrisisFigureAction(
            date="1932-07-08",
            figure="约翰·坦普尔顿 (John Templeton)",
            figure_en="John Templeton",
            action_zh="1939年借入10000美元，以每股低于1美元的价格买入104家公司的股票，每家100股",
            action_en="In 1939, borrowed $10,000 to buy 100 shares each of 104 companies trading below $1",
            asset_class="股票",
            strategy_zh="在二战爆发、市场极度悲观时进行逆向投资，分散买入超低价股票",
            strategy_en="Contrarian investing at peak pessimism of WWII outbreak, diversifying into ultra-cheap stocks",
            outcome_zh="4年后投资价值涨至4万美元，收益率300%，奠定了逆向投资大师的声誉",
            outcome_en="Investment grew to $40,000 in 4 years, 300% return, establishing reputation as contrarian master",
            gain_pct=300.0,
            tags=["逆向投资", "分散买入", "极度悲观"],
        ),
        CrisisFigureAction(
            date="1933-03-09",
            figure="富兰克林·罗斯福 (Franklin D. Roosevelt)",
            figure_en="Franklin D. Roosevelt",
            action_zh="签署《紧急银行法案》，关闭银行进行整顿，放弃金本位，启动新政",
            action_en="Signed Emergency Banking Act, closed banks for restructuring, abandoned gold standard, launched New Deal",
            asset_class="政策/货币",
            strategy_zh="通过国家干预打破通缩螺旋，重建金融体系和公众信心",
            strategy_en="Broke deflationary spiral through state intervention, rebuilding financial system and public confidence",
            outcome_zh="银行体系稳定，道指从40点低点反弹，美国经济逐步复苏",
            outcome_en="Banking system stabilized, Dow rebounded from 40 low, US economy gradually recovered",
            gain_pct=200.0,
            tags=["新政", "银行整顿", "放弃金本位"],
        ),
        CrisisFigureAction(
            date="1929-11-01",
            figure="约瑟夫·肯尼迪 (Joseph P. Kennedy)",
            figure_en="Joseph P. Kennedy",
            action_zh="在1929年股市崩盘前大量卖出股票，随后在市场底部做空",
            action_en="Sold heavily before 1929 crash, then shorted stocks near market bottom",
            asset_class="股票/做空",
            strategy_zh="识别泡沫后及时离场，并利用崩盘后的反弹做空",
            strategy_en="Recognized bubble and exited, then shorted during post-crash bounces",
            outcome_zh="在多数投资者破产时获利数千万美元，成为肯尼迪家族财富基础",
            outcome_en="Made tens of millions while most investors went bankrupt, forming Kennedy family fortune",
            gain_pct=500.0,
            tags=["做空", "逃顶", "家族财富"],
        ),
    ],
)


# 2020 新冠市场崩盘
CRISIS_2020 = CrisisData(
    id="covid_2020",
    name_en="COVID-19 Market Crash 2020",
    name_zh="2020 新冠市场崩盘",
    period="2020-02 ~ 2020-04",
    severity="major",
    peak_unemployment=14.7,
    peak_decline_snp=-33.9,
    peak_decline_gdp=-31.4,
    duration_months=2,
    causes_zh=(
        "1. 新冠疫情全球蔓延——经济活动突然停滞；\n"
        "2. 流动性恐慌——投资者抛售一切资产换取美元；\n"
        "3. 供应链断裂——制造业和贸易中断；\n"
        "4. 油价崩盘——沙特-俄罗斯价格战使油价跌至负值。"
    ),
    causes_en=(
        "1. COVID-19 pandemic — economic activity halted abruptly;\n"
        "2. Liquidity panic — investors sold everything for dollars;\n"
        "3. Supply chain disruption — manufacturing and trade interrupted;\n"
        "4. Oil crash — Saudi-Russia price war sent oil negative."
    ),
    key_events=[
        CrisisEvent("2020-02-19", "S&P 500 peaks at 3,386", "标普500在3386点见顶", "medium"),
        CrisisEvent("2020-03-09", "Circuit breaker triggered — oil crash + COVID fears", "熔断触发——油价崩盘+新冠恐慌", "high"),
        CrisisEvent("2020-03-12", "Circuit breaker triggered again — worst day since 1987", "再次熔断——1987年以来最差单日", "high"),
        CrisisEvent("2020-03-16", "Circuit breaker triggered third time — Fed emergency 100bps cut to zero", "第三次熔断——美联储紧急降息100基点至零", "high"),
        CrisisEvent("2020-03-18", "Circuit breaker triggered fourth time", "第四次熔断触发", "high"),
        CrisisEvent("2020-03-23", "Fed announces unlimited QE; S&P 500 bottoms at 2,237", "美联储宣布无限QE；标普500在2237点触底", "high"),
        CrisisEvent("2020-03-27", "CARES Act signed — $2T fiscal stimulus", "CARES法案签署——2万亿美元财政刺激", "high"),
        CrisisEvent("2020-04-20", "WTI oil futures turn negative for first time", "WTI原油期货首次转为负值", "high"),
    ],
    phases=[
        CrisisPhase(
            phase_en="Phase 1: Crash",
            phase_zh="第一阶段：崩盘",
            period="2020-02-19 ~ 2020-03-23",
            description_en="Fastest bear market in history (33 days); 4 circuit breakers triggered; Fed cuts to zero and launches unlimited QE.",
            description_zh="史上最快熊市（33天），4次熔断触发，美联储降息至零并启动无限QE。",
            events=[
                CrisisEvent("2020-03-09", "First circuit breaker", "第一次熔断", "high"),
                CrisisEvent("2020-03-23", "S&P bottoms at 2,237; Fed unlimited QE", "标普500在2237点触底；美联储无限QE", "high"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 2: Recovery",
            phase_zh="第二阶段：复苏",
            period="2020-04 ~ 2020-08",
            description_en="Fed's balance sheet expands by $3T; S&P 500 recovers all losses by August; fastest recovery on record.",
            description_zh="美联储资产负债表扩张3万亿美元，标普500在8月收复全部跌幅，史上最快复苏。",
            events=[
                CrisisEvent("2020-08-18", "S&P 500 reclaims all-time high 3,386", "标普500收复全部跌幅创新高3386点", "high"),
            ],
        ),
    ],
    recovery_actions_zh=(
        "1. 美联储将利率降至零，启动无限量QE；\n"
        "2. CARES法案2万亿美元刺激——直接支付、失业补助、PPP贷款；\n"
        "3. 美联储设立多种流动性工具——SMCCF、PMCCF、MMLF等；\n"
        "4. 疫苗研发投入——Operation Warp Speed加速疫苗上市。"
    ),
    recovery_actions_en=(
        "1. Fed cut rates to zero, launched unlimited QE;\n"
        "2. CARES Act $2T stimulus — direct payments, unemployment boost, PPP loans;\n"
        "3. Fed established multiple liquidity facilities (SMCCF, PMCCF, MMLF);\n"
        "4. Vaccine R&D — Operation Warp Speed accelerated vaccine development."
    ),
    lessons_zh=(
        "1. 美联储从2008年吸取了教训——立即提供无限流动性，避免重蹈雷曼覆辙；\n"
        "2. 财政与货币政策协调是快速复苏的关键；\n"
        "3. 外生冲击（疫情）与内生冲击（金融系统）需要不同的应对策略。"
    ),
    lessons_en=(
        "1. Fed learned from 2008 — provide unlimited liquidity immediately;\n"
        "2. Fiscal-monetary coordination is key to rapid recovery;\n"
        "3. Exogenous shocks (pandemic) vs endogenous shocks (financial) require different responses."
    ),
    institutional_analyses=[
        {
            "institution": "美联储",
            "report": "Financial Stability Report (May 2020)",
            "key_finding_zh": "2020年危机的速度和严重程度前所未有，但美联储吸取了2008年的教训，在数小时内而非数周内提供了流动性。",
            "key_finding_en": "The 2020 crisis was unprecedented in speed and severity, but the Fed applied 2008 lessons, providing liquidity in hours rather than weeks.",
            "url": "https://www.federalreserve.gov/publications/2020-financial-stability-report.htm",
            "download_url": "https://www.federalreserve.gov/publications/files/financial-stability-report-20200515.pdf",
            "summary_zh": "美联储在2020年5月发布的这份金融稳定报告，评估了新冠疫情对金融体系的冲击。报告指出，新冠疫情引发了史上最快的熊市和最剧烈的流动性紧缩，但由于美联储迅速采取了降息至零、无限量QE、建立多种流动性工具等措施，金融市场功能得以快速恢复。报告强调，未来需要关注企业债务高企、非银金融机构风险和市场结构脆弱性等问题。",
            "summary_en": "The Fed's May 2020 Financial Stability Report assessed the impact of the COVID-19 pandemic on the financial system. It noted that the pandemic triggered the fastest bear market and most severe liquidity squeeze in history, but the Fed's rapid actions - cutting rates to zero, unlimited QE, and establishing multiple liquidity facilities - helped financial market functions recover quickly. The report highlighted concerns about high corporate debt, non-bank financial institution risks, and market structure fragility.",
            "conclusion_zh": "**总结意见**：该报告证明了美联储从2008年危机中吸取的教训——速度和力度是关键。当前与2020年的主要区别在于，新冠疫情是外生冲击，金融市场本身较为健康；而如果未来发生内生性的金融危机，政策应对空间可能更小。建议投资者关注企业债务再融资风险和高收益债市场。",
            "conclusion_en": "**Conclusion**: The report demonstrated that the Fed learned from 2008 - speed and forcefulness matter. The key difference from 2020 is that COVID-19 was an exogenous shock while financial markets were relatively healthy; future endogenous financial crises may have less policy room. Investors should monitor corporate debt refinancing risks and high-yield bond markets.",
            "date": "2020-05",
        },
        {
            "institution": "IMF",
            "report": "World Economic Outlook (April 2020)",
            "key_finding_zh": "这是自大萧条以来最严重的经济衰退，但得益于前所未有的政策支持，复苏速度快于预期。",
            "key_finding_en": "The worst recession since the Great Depression, but unprecedented policy support led to faster-than-expected recovery.",
            "url": "https://www.imf.org/en/Publications/WEO/Issues/2020/04/14/weo-april-2020",
            "download_url": "https://www.imf.org/-/media/Files/Publications/WEO/2020/April/English/text.pdf",
            "summary_zh": "IMF在2020年4月发布的《世界经济展望》预测，2020年全球经济将萎缩3%，这是自大萧条以来最严重的经济衰退。报告指出，经济活动骤停导致消费、投资和贸易全面下滑，但各国前所未有的财政和货币政策支持缓解了经济创伤。报告呼吁政策制定者继续提供支持，并加强国际合作以应对疫情。",
            "summary_en": "The IMF's April 2020 World Economic Outlook projected a 3% global economic contraction in 2020, the worst recession since the Great Depression. The report noted that the abrupt halt in economic activity caused broad declines in consumption, investment, and trade, but unprecedented fiscal and monetary policy support mitigated the economic damage. It called on policymakers to continue support and strengthen international cooperation.",
            "conclusion_zh": "**总结意见**：IMF报告准确捕捉了疫情冲击的规模和政策应对的重要性。当前全球经济虽然复苏，但增长基础脆弱，地缘冲突、供应链重构和通胀压力构成新风险。建议投资者关注IMF对全球经济增长的最新预测修正，以及政策刺激退出对市场的影响。",
            "conclusion_en": "**Conclusion**: The IMF report accurately captured the scale of the pandemic shock and the importance of policy response. While the global economy has recovered, the growth foundation remains fragile, with geopolitical conflicts, supply chain restructuring, and inflation pressure as new risks. Investors should monitor IMF's latest growth forecast revisions and the market impact of policy stimulus withdrawal.",
            "date": "2020-04",
        },
    ],
    figure_actions=[
        CrisisFigureAction(
            date="2020-03-23",
            figure="沃伦·巴菲特 (Warren Buffett)",
            figure_en="Warren Buffett",
            action_zh="在市场底部买入航空股和银行股（达美航空、美国银行等）",
            action_en="Bought airline and bank stocks at market bottom (Delta, Bank of America, etc.)",
            asset_class="股票",
            strategy_zh="在恐慌中抄底优质消费和金融资产，利用伯克希尔的现金储备",
            strategy_en="Bottom-fished quality consumer and financial assets using Berkshire's cash reserves during panic",
            outcome_zh="部分持仓（如航空股）后续被减持，但美国银行等持仓在2021年大幅获利",
            outcome_en="Some positions (airlines) were later sold, but Bank of America holdings gained significantly by 2021",
            gain_pct=25.0,
            tags=["抄底", "航空股", "银行股"],
        ),
        CrisisFigureAction(
            date="2020-03-23",
            figure="比尔·阿克曼 (Bill Ackman)",
            figure_en="Bill Ackman",
            action_zh="在市场崩盘期间通过CDS做空投资级债券，耗资2700万美元",
            action_en="Shorted investment-grade bonds via CDS for $27M during market crash",
            asset_class="债券/做空",
            strategy_zh="利用市场极度恐慌时CDS价格飙升获利，然后在底部平仓并转而做多",
            strategy_en="Profited from CDS price spikes during peak panic, then covered and went long at bottom",
            outcome_zh="23天后获利26亿美元，收益率近100倍，成为对冲基金史上最传奇交易之一",
            outcome_en="Made $2.6B in 23 days, ~100x return, one of the most legendary hedge fund trades ever",
            gain_pct=9600.0,
            tags=["CDS", "做空债券", "百倍收益"],
        ),
        CrisisFigureAction(
            date="2020-03-16",
            figure="杰罗姆·鲍威尔 (Jerome Powell) / 美联储",
            figure_en="Jerome Powell / Federal Reserve",
            action_zh="紧急降息100基点至零利率，启动无限量QE",
            action_en="Emergency 100bps cut to zero, launched unlimited QE",
            asset_class="政策/货币",
            strategy_zh="吸取2008年教训，在数小时内而非数周内提供无限流动性",
            strategy_en="Applied 2008 lessons, providing unlimited liquidity in hours rather than weeks",
            outcome_zh="标普500在33天内收复全部跌幅，史上最快市场复苏",
            outcome_en="S&P 500 recovered all losses in 33 days, fastest market recovery on record",
            gain_pct=300.0,
            tags=["紧急降息", "无限QE", "政策应对"],
        ),
        CrisisFigureAction(
            date="2020-03-24",
            figure="凯西·伍德 (Cathie Wood) / ARK Invest",
            figure_en="Cathie Wood / ARK Invest",
            action_zh="在市场崩盘时坚持持有并加仓创新科技股（特斯拉、Square等）",
            action_en="Held and added to innovative tech stocks (Tesla, Square) during market crash",
            asset_class="股票/科技",
            strategy_zh="坚持颠覆性创新投资理念，在市场恐慌中保持仓位",
            strategy_en="Maintained disruptive innovation thesis, holding positions through market panic",
            outcome_zh="ARKK基金在2020年回报率超过150%，成为当年最热门的主动管理基金",
            outcome_en="ARKK fund returned >150% in 2020, becoming the hottest actively managed fund of the year",
            gain_pct=150.0,
            tags=["科技股", "创新投资", "坚持策略"],
        ),
    ],
)


# 1997 亚洲金融危机
CRISIS_ASIA_1997 = CrisisData(
    id="asia_1997",
    name_en="Asian Financial Crisis 1997-1998",
    name_zh="1997 亚洲金融危机",
    period="1997-1998",
    severity="major",
    peak_unemployment=8.0,
    peak_decline_snp=-19.3,  # 美国受影响较小，但亚洲市场巨大跌幅
    peak_decline_gdp=-13.0,  # 印尼GDP跌幅最大约13%
    duration_months=18,
    causes_zh=(
        "1. 固定汇率制度与短期外债——东南亚国家维持美元挂钩但积累了大量短期美元债务；\n"
        "2. 银行体系脆弱——大量信贷流向房地产投机；\n"
        "3. 资本账户过早开放——短期国际资本可以快速撤出；\n"
        "4. 企业治理问题——关联交易和风险管控缺失。"
    ),
    causes_en=(
        "1. Fixed exchange rates with short-term foreign debt;\n"
        "2. Fragile banking systems — credit flowed to property speculation;\n"
        "3. Premature capital account liberalization — hot money could exit instantly;\n"
        "4. Corporate governance issues — related-party transactions, poor risk controls."
    ),
    key_events=[
        CrisisEvent("1997-07-02", "Thailand devalues baht — Asia crisis begins", "泰国放弃泰铢挂钩——亚洲危机开始", "high"),
        CrisisEvent("1997-07-11", "IMF provides Thailand $17B bailout", "IMF向泰国提供170亿美元救助", "high"),
        CrisisEvent("1997-10-23", "Hong Kong stock market crashes 23% in 4 days", "香港股市4天内暴跌23%", "high"),
        CrisisEvent("1997-12", "South Korea seeks IMF bailout — $58B", "韩国寻求IMF救助——580亿美元", "high"),
        CrisisEvent("1998-01-12", "Indonesia rupiah collapses — PM resigns", "印尼盾崩盘——苏哈托下台", "high"),
        CrisisEvent("1998-08-17", "Russia defaults on domestic debt", "俄罗斯违约国内债务", "high"),
        CrisisEvent("1998-09-23", "LTCM bailout — Fed orchestrates $3.6B rescue", "长期资本管理公司救助——美联储协调36亿美元", "high"),
    ],
    phases=[
        CrisisPhase(
            phase_en="Phase 1: Contagion",
            phase_zh="第一阶段：传染",
            period="1997-07 ~ 1997-12",
            description_en="Baht devaluation triggers contagion across Southeast Asia; currencies and stock markets collapse.",
            description_zh="泰铢贬值引发东南亚传染效应，货币和股市全面崩盘。",
            events=[
                CrisisEvent("1997-07-02", "Thailand devalues baht", "泰国泰铢贬值", "high"),
                CrisisEvent("1997-10-23", "Hong Kong crashes 23%", "香港股市暴跌23%", "high"),
            ],
        ),
        CrisisPhase(
            phase_en="Phase 2: Global Contagion",
            phase_zh="第二阶段：全球扩散",
            period="1998-01 ~ 1998-09",
            description_en="Russia defaults; LTCM collapses; Fed cuts rates; global coordination intensifies.",
            description_zh="俄罗斯违约，LTCM倒闭，美联储降息，全球协调加强。",
            events=[
                CrisisEvent("1998-08-17", "Russia defaults", "俄罗斯违约", "high"),
                CrisisEvent("1998-09-23", "LTCM bailout", "LTCM救助", "high"),
            ],
        ),
    ],
    recovery_actions_zh=(
        "1. IMF提供约1000亿美元救助（泰国、印尼、韩国）；\n"
        "2. 马来西亚实施资本管制（争议性但有效）；\n"
        "3. 香港金管局入市买入股票击退索罗斯；\n"
        "4. 美联储降息75基点预防全球衰退；\n"
        "5. 亚洲国家积累外汇储备，建立清迈倡议多边化。"
    ),
    recovery_actions_en=(
        "1. IMF ~$100B bailout (Thailand, Indonesia, South Korea);\n"
        "2. Malaysia imposed capital controls (controversial but effective);\n"
        "3. HK Monetary Authority bought stocks to defeat speculators;\n"
        "4. Fed cut rates 75bps to prevent global recession;\n"
        "5. Asian countries accumulated FX reserves; Chiang Mai Initiative created."
    ),
    lessons_zh=(
        "1. 固定汇率制度在资本流动下是脆弱的——弹性汇率是更好的缓冲器；\n"
        "2. 短期外债是定时炸弹——需要管理期限错配；\n"
        "3. 外汇储备是最后的防线——亚洲国家此后大规模积累储备；\n"
        "4. 银行监管和企业治理必须与资本账户开放同步。"
    ),
    lessons_en=(
        "1. Fixed exchange rates are fragile under capital mobility — flexible rates buffer better;\n"
        "2. Short-term foreign debt is a ticking bomb — maturity mismatch must be managed;\n"
        "3. FX reserves are the last line of defense — Asian countries accumulated massively afterward;\n"
        "4. Banking supervision and corporate governance must keep pace with capital account opening."
    ),
    institutional_analyses=[
        {
            "institution": "IMF",
            "report": "The Asian Crisis: Causes and Cures (1998)",
            "key_finding_zh": "危机的根源在于宏观经济基本面与固定汇率制度的不匹配，以及金融体系和公司治理的结构性弱点。",
            "key_finding_en": "Root causes: mismatch between macro fundamentals and fixed exchange rates, plus structural weaknesses in financial systems and corporate governance.",
            "url": "https://www.imf.org/en/News/Articles/2015/05/07/1003/the-asian-crisis-causes-and-cures",
            "download_url": "https://www.imf.org/external/pubs/ft/fandd/1998/06/imfstaff.htm",
            "summary_zh": "IMF在1998年发布的研究报告深入分析了亚洲金融危机的原因。报告认为，危机并非完全由投机攻击引起，而是源于宏观经济基本面与固定汇率制度之间的不匹配。此外，金融体系的结构性弱点——包括裙带关系贷款、不良贷款累积和公司治理缺失——放大了危机。报告讨论了IMF救助方案（财政紧缩、金融改革、结构性改革）的成效与争议。",
            "summary_en": "The IMF's 1998 report deeply analyzed the causes of the Asian financial crisis. It argued the crisis was not simply caused by speculative attacks, but by mismatches between macroeconomic fundamentals and fixed exchange rate regimes. Structural weaknesses in financial systems - including crony lending, non-performing loan accumulation, and poor corporate governance - amplified the crisis. The report discussed the effectiveness and controversies of IMF bailout programs (fiscal austerity, financial reform, structural reform).",
            "conclusion_zh": "**总结意见**：IMF的分析强调了固定汇率制度和金融脆弱性的结合是危机根源。当前新兴市场国家积累了大量外汇储备，资本账户管理更加谨慎，但仍面临美元走强和资本外流压力。建议投资者关注新兴市场货币汇率、外汇储备变动和外债期限结构。",
            "conclusion_en": "**Conclusion**: The IMF analysis emphasized that the combination of fixed exchange rates and financial fragility caused the crisis. Current emerging markets have accumulated large FX reserves and manage capital accounts more cautiously, but still face dollar strength and capital outflow pressures. Investors should monitor emerging market currency exchange rates, FX reserve changes, and foreign debt maturity structures.",
            "date": "1998",
        },
        {
            "institution": "世界银行 (World Bank)",
            "report": "East Asia: The Road to Recovery (1998)",
            "key_finding_zh": "危机的社会代价巨大——贫困率大幅上升，需要在经济改革之外关注社会保护。",
            "key_finding_en": "The social costs were enormous — poverty rates surged, requiring social protection alongside economic reform.",
            "url": "https://documents.worldbank.org/en/publication/documents-reports/documentdetail/909041468251252824/east-asia-the-road-to-recovery",
            "download_url": "https://documents.worldbank.org/en/publication/documents-reports/documentdetail/909041468251252824/east-asia-the-road-to-recovery",
            "summary_zh": "世界银行在1998年发布的这份报告，评估了亚洲金融危机对社会和经济的影响。报告指出，危机导致数百万人重新陷入贫困，失业率飙升，社会保护体系面临巨大压力。报告强调，经济复苏不仅需要金融和企业改革，还需要建立有效的社会安全网，保护最脆弱群体。同时，报告也肯定了东亚国家通过出口导向型增长和结构性改革实现复苏的潜力。",
            "summary_en": "The World Bank's 1998 report assessed the social and economic impacts of the Asian financial crisis. It noted that the crisis pushed millions back into poverty, caused unemployment to soar, and put immense pressure on social protection systems. The report emphasized that economic recovery requires not only financial and corporate reform, but also effective social safety nets to protect the most vulnerable. It also recognized East Asian countries' potential for recovery through export-oriented growth and structural reforms.",
            "conclusion_zh": "**总结意见**：该报告提醒我们，金融危机的社会代价往往被低估。当前政策制定者在应对经济冲击时，越来越重视财政政策的社会保护功能。投资者应关注各国的社会支出政策、最低工资调整和劳动力市场改革，这些因素可能影响消费复苏和企业盈利。",
            "conclusion_en": "**Conclusion**: This report reminds us that the social costs of financial crises are often underestimated. Policymakers today increasingly value the social protection function of fiscal policy when responding to shocks. Investors should monitor social spending policies, minimum wage adjustments, and labor market reforms, as these factors may affect consumption recovery and corporate earnings.",
            "date": "1998",
        },
    ],
    figure_actions=[
        CrisisFigureAction(
            date="1997-07-02",
            figure="乔治·索罗斯 (George Soros) / 量子基金",
            figure_en="George Soros / Quantum Fund",
            action_zh="做空泰铢，迫使其放弃盯住美元的固定汇率制",
            action_en="Shorted Thai baht, forcing abandonment of dollar peg",
            asset_class="外汇/做空",
            strategy_zh="利用东南亚国家固定汇率不可持续的弱点，大规模做空本币",
            strategy_en="Exploited unsustainable fixed exchange rates in Southeast Asian countries, massively shorting local currencies",
            outcome_zh="泰铢贬值约20%，量子基金从中获利数十亿美元；随后做空马来西亚林吉特、印尼盾等",
            outcome_en="Baht devalued ~20%; Quantum Fund profited billions; then shorted ringgit, rupiah, etc.",
            gain_pct=300.0,
            tags=["做空货币", "宏观交易", "固定汇率"],
        ),
        CrisisFigureAction(
            date="1997-08-01",
            figure="马哈蒂尔·穆罕默德 (Mahathir Mohamad)",
            figure_en="Mahathir Mohamad",
            action_zh="指责索罗斯“不道德”做空东南亚货币，实施资本管制和固定汇率",
            action_en="Accused Soros of 'immoral' currency attacks; imposed capital controls and pegged ringgit",
            asset_class="政策/外汇",
            strategy_zh="通过行政手段对抗货币投机，实施选择性资本管制",
            strategy_en="Used administrative measures to fight currency speculation, imposed selective capital controls",
            outcome_zh="林吉特1998年9月固定在3.8，避免了进一步贬值；马来西亚经济1999年复苏",
            outcome_en="Ringgit pegged at 3.8 in Sept 1998, preventing further devaluation; Malaysian economy recovered in 1999",
            gain_pct=50.0,
            tags=["资本管制", "反投机", "行政干预"],
        ),
        CrisisFigureAction(
            date="1997-10-01",
            figure="维克多·斯珀兰卡 (Victor Sperandeo)",
            figure_en="Victor Sperandeo",
            action_zh="识别到东南亚货币危机将传导至香港，提前布局做空恒生指数期货",
            action_en="Identified that Asian contagion would hit Hong Kong, pre-positioned short on Hang Seng futures",
            asset_class="期货/做空",
            strategy_zh="利用货币危机的区域传导逻辑，做空受影响最大的股市指数",
            strategy_en="Used regional contagion logic from currency crisis to short most affected equity indices",
            outcome_zh="1997年10月港股大跌，恒生指数从16000点跌至9000点附近",
            outcome_en="Hong Kong stocks plunged in Oct 1997, Hang Seng fell from ~16000 to ~9000",
            gain_pct=40.0,
            tags=["期货", "区域传导", "做空指数"],
        ),
        CrisisFigureAction(
            date="1998-08-14",
            figure="香港金管局 / 曾荫权",
            figure_en="Hong Kong Monetary Authority / Donald Tsang",
            action_zh="动用约1200亿美元外汇储备买入恒生指数成份股和期货，对抗国际炒家",
            action_en="Deployed ~$120B in reserves buying Hang Seng component stocks and futures to fight international speculators",
            asset_class="股票/期货/干预",
            strategy_zh="政府直接入市干预，买入蓝筹股和期指，迫使做空者平仓",
            strategy_en="Government directly intervened in markets, buying blue chips and index futures to force shorts to cover",
            outcome_zh="1998年8月成功击退炒家，恒生指数稳定并反弹，港府获利数十亿美元",
            outcome_en="Successfully repelled speculators in Aug 1998; Hang Seng stabilized and rallied; HK gov't profited billions",
            gain_pct=30.0,
            tags=["政府干预", "外汇储备", "期指大战"],
        ),
        CrisisFigureAction(
            date="1998-01-01",
            figure="沃伦·巴菲特 (Warren Buffett)",
            figure_en="Warren Buffett",
            action_zh="在亚洲危机期间买入白银和部分亚洲资产，因看好长期价值",
            action_en="Bought silver and some Asian assets during the Asian crisis, seeing long-term value",
            asset_class="商品/股票",
            strategy_zh="在市场恐慌中逆向投资，配置实物资产和被低估的亚洲股票",
            strategy_en="Contrarian investing during market panic, allocating to hard assets and undervalued Asian equities",
            outcome_zh="白银持仓从1997年到2006年获利约4-5倍，成为伯克希尔最成功的商品投资之一",
            outcome_en="Silver position gained ~4-5x from 1997 to 2006, one of Berkshire's most successful commodity investments",
            gain_pct=400.0,
            tags=["逆向投资", "白银", "实物资产"],
        ),
    ],
)


# 所有危机列表
ALL_CRISES = [CRISIS_2008, CRISIS_DOTCOM, CRISIS_1929, CRISIS_2020, CRISIS_ASIA_1997]


# ==================== 当前市场指标对比 2008 ====================

# 用于对比的2008年危机关键指标
CRISIS_2008_BENCHMARKS = {
    "vix_peak": 80.86,            # VIX 峰值
    "vix_normal": 20,              # 正常水平
    "credit_spread_peak": 6.53,   # 高收益债利差峰值 (%)
    "credit_spread_normal": 3.0,  # 正常水平
    "ted_spread_peak": 4.58,      # TED利差峰值 (%)
    "ted_spread_normal": 0.3,     # 正常水平
    "snp_drawdown": -56.8,        # S&P 500 最大跌幅
    "unemployment_peak": 10.0,    # 失业率峰值
    "bank_failures": 465,         # 2008-2010年银行倒闭数
    "fed_balance_sheet_growth": 3.0,  # 美联储资产负债表增长倍数
    "home_price_decline": -30.0,  # Case-Shiller房价指数跌幅
    "gdp_decline": -4.3,          # GDP最大跌幅
}

# 当前端 CrisisProgress 评估
CURRENT_INDICATORS = {
    "vix": {"value": 15.5, "date": "2025-08", "crisis_2008": 80.86, "normal": 15.0},
    "credit_spread": {"value": 3.2, "date": "2025-08", "crisis_2008": 6.53, "normal": 3.0},
    "ted_spread": {"value": 0.25, "date": "2025-08", "crisis_2008": 4.58, "normal": 0.3},
    "snp_from_peak": {"value": -2.0, "date": "2025-08", "crisis_2008": -56.8, "normal": -5.0},
    "unemployment": {"value": 4.2, "date": "2025-08", "crisis_2008": 10.0, "normal": 4.0},
    "fed_balance_sheet": {"value": 7.5, "date": "2025-08", "crisis_2008": 2.2, "normal": 1.0, "note": "万亿美元"},
    "home_price_yoy": {"value": 4.5, "date": "2025-08", "crisis_2008": -30.0, "normal": 5.0},
}


def get_crisis_comparison() -> dict:
    """获取当前市场指标与2008危机的对比"""
    indicators = []
    for key, data in CURRENT_INDICATORS.items():
        normal = data["normal"]
        crisis = data["crisis_2008"]
        current = data["value"]
        # 计算当前值在「正常→危机」区间的进度 (0% = 正常, 100% = 危机)
        if crisis == normal:
            progress = 0
        else:
            progress = abs(current - normal) / abs(crisis - normal) * 100
        progress = min(max(progress, 0), 100)
        indicators.append({
            "key": key,
            "value": current,
            "normal": normal,
            "crisis_2008": crisis,
            "crisis_progress_pct": round(progress, 1),
            "status": "normal" if progress < 25 else ("warning" if progress < 50 else "danger"),
            "date": data["date"],
            "note": data.get("note", ""),
        })
    
    avg_progress = sum(i["crisis_progress_pct"] for i in indicators) / len(indicators)
    
    return {
        "indicators": indicators,
        "avg_crisis_progress_pct": round(avg_progress, 1),
        "assessment_en": "The current market shows no significant signs of approaching 2008-level crisis. All key indicators remain within normal ranges.",
        "assessment_zh": "当前市场未显示接近2008年危机水平的显著迹象。所有关键指标均处于正常范围内。",
        "benchmark": CRISIS_2008_BENCHMARKS,
    }


def get_crisis_timeline(crisis_id: str) -> dict:
    """获取特定危机的时间线"""
    for c in ALL_CRISES:
        if c.id == crisis_id:
            timeline = []
            for phase in c.phases:
                for event in phase.events:
                    timeline.append({
                        "date": event.date,
                        "event_en": event.event_en,
                        "event_zh": event.event_zh,
                        "impact": event.impact,
                        "phase_en": phase.phase_en,
                        "phase_zh": phase.phase_zh,
                    })
            timeline.sort(key=lambda x: x["date"])
            return {"crisis_id": crisis_id, "timeline": timeline}
    return {"error": f"Crisis {crisis_id} not found"}


def get_all_crisis_data() -> list[dict]:
    """获取所有危机数据"""
    results = []
    for c in ALL_CRISES:
        results.append({
            "id": c.id,
            "name_en": c.name_en,
            "name_zh": c.name_zh,
            "period": c.period,
            "severity": c.severity,
            "peak_unemployment": c.peak_unemployment,
            "peak_decline_snp": c.peak_decline_snp,
            "peak_decline_gdp": c.peak_decline_gdp,
            "duration_months": c.duration_months,
            "causes_zh": c.causes_zh,
            "causes_en": c.causes_en,
            "key_events": [
                {"date": e.date, "event_en": e.event_en, "event_zh": e.event_zh, "impact": e.impact}
                for e in c.key_events
            ],
            "phases": [
                {
                    "phase_en": p.phase_en,
                    "phase_zh": p.phase_zh,
                    "period": p.period,
                    "description_en": p.description_en,
                    "description_zh": p.description_zh,
                    "events": [
                        {"date": e.date, "event_en": e.event_en, "event_zh": e.event_zh, "impact": e.impact}
                        for e in p.events
                    ],
                }
                for p in c.phases
            ],
            "recovery_actions_zh": c.recovery_actions_zh,
            "recovery_actions_en": c.recovery_actions_en,
            "lessons_zh": c.lessons_zh,
            "lessons_en": c.lessons_en,
            "institutional_analyses": c.institutional_analyses,
            "figure_actions": [
                {
                    "date": a.date,
                    "figure": a.figure,
                    "figure_en": a.figure_en,
                    "action_zh": a.action_zh,
                    "action_en": a.action_en,
                    "asset_class": a.asset_class,
                    "strategy_zh": a.strategy_zh,
                    "strategy_en": a.strategy_en,
                    "outcome_zh": a.outcome_zh,
                    "outcome_en": a.outcome_en,
                    "gain_pct": a.gain_pct,
                    "tags": a.tags,
                }
                for a in c.figure_actions
            ],
        })
    return results


def get_crisis_detail(crisis_id: str) -> dict:
    """获取单个危机详情"""
    for c in ALL_CRISES:
        if c.id == crisis_id:
            return {
                "id": c.id,
                "name_en": c.name_en,
                "name_zh": c.name_zh,
                "period": c.period,
                "severity": c.severity,
                "peak_unemployment": c.peak_unemployment,
                "peak_decline_snp": c.peak_decline_snp,
                "peak_decline_gdp": c.peak_decline_gdp,
                "duration_months": c.duration_months,
                "causes_zh": c.causes_zh,
                "causes_en": c.causes_en,
                "key_events": [
                    {"date": e.date, "event_en": e.event_en, "event_zh": e.event_zh, "impact": e.impact}
                    for e in c.key_events
                ],
                "phases": [
                    {
                        "phase_en": p.phase_en,
                        "phase_zh": p.phase_zh,
                        "period": p.period,
                        "description_en": p.description_en,
                        "description_zh": p.description_zh,
                        "events": [
                            {"date": e.date, "event_en": e.event_en, "event_zh": e.event_zh, "impact": e.impact}
                            for e in p.events
                        ],
                    }
                    for p in c.phases
                ],
                "recovery_actions_zh": c.recovery_actions_zh,
                "recovery_actions_en": c.recovery_actions_en,
                "lessons_zh": c.lessons_zh,
                "lessons_en": c.lessons_en,
                "institutional_analyses": c.institutional_analyses,
            }
    return {"error": f"Crisis {crisis_id} not found"}


# ==================== 历史宏观经济指标 (Historical Macroeconomic Indicators) ====================
# 宏观指标回溯 - 提供历次危机的季度时间序列数据
# 数据来源: FRED, BLS, S&P Dow Jones Indices, CBOE, ICE BofA, S&P CoreLogic Case-Shiller
# 注: 部分指标在 1929 年代尚未建立 (VIX/HY Spread/TED Spread 等), 用 None 表示
# 字段说明:
#   gdp_growth       - GDP 季度环比折年率 (%)
#   unemployment     - U-3 失业率, 季度均值 (%)
#   snp500           - S&P 500 季度收盘点位 (1929 期间为 S&P Composite 前身)
#   vix              - VIX 指数季度均值
#   fed_rate         - 有效联邦基金利率季度均值 (%)
#   treasury_10y     - 10 年期国债收益率季度均值 (%)
#   home_price_yoy   - Case-Shiller 全国房价指数同比 (%)
#   hy_spread        - ICE BofA 美国高收益债 OAS 利差 (%)
#   ted_spread       - TED 利差 (3M LIBOR - 3M T-Bill, %)

MACRO_INDICATORS: dict[str, list[dict]] = {
    # -------- 2008 全球金融危机 (GFC 2008) --------
    "gfc_2008": [
        {"quarter": "2007Q1", "gdp_growth": 1.2, "unemployment": 4.5, "snp500": 1420.86, "vix": 12.5, "fed_rate": 5.25, "treasury_10y": 4.60, "home_price_yoy": 1.5, "hy_spread": 3.20, "ted_spread": 0.40},
        {"quarter": "2007Q2", "gdp_growth": 3.6, "unemployment": 4.5, "snp500": 1503.35, "vix": 16.0, "fed_rate": 5.25, "treasury_10y": 5.00, "home_price_yoy": -0.5, "hy_spread": 4.00, "ted_spread": 0.50},
        {"quarter": "2007Q3", "gdp_growth": 2.4, "unemployment": 4.7, "snp500": 1526.75, "vix": 22.5, "fed_rate": 5.02, "treasury_10y": 4.60, "home_price_yoy": -5.0, "hy_spread": 5.00, "ted_spread": 1.50},
        {"quarter": "2007Q4", "gdp_growth": 2.3, "unemployment": 5.0, "snp500": 1468.36, "vix": 23.5, "fed_rate": 4.24, "treasury_10y": 4.00, "home_price_yoy": -8.9, "hy_spread": 6.00, "ted_spread": 1.90},
        {"quarter": "2008Q1", "gdp_growth": -0.7, "unemployment": 5.1, "snp500": 1322.70, "vix": 29.0, "fed_rate": 3.00, "treasury_10y": 3.40, "home_price_yoy": -14.0, "hy_spread": 8.00, "ted_spread": 1.20},
        {"quarter": "2008Q2", "gdp_growth": 0.6, "unemployment": 5.5, "snp500": 1280.00, "vix": 23.5, "fed_rate": 2.00, "treasury_10y": 4.00, "home_price_yoy": -15.9, "hy_spread": 7.00, "ted_spread": 1.00},
        {"quarter": "2008Q3", "gdp_growth": -2.7, "unemployment": 6.2, "snp500": 1166.36, "vix": 40.0, "fed_rate": 1.75, "treasury_10y": 3.60, "home_price_yoy": -16.6, "hy_spread": 11.00, "ted_spread": 2.20},
        {"quarter": "2008Q4", "gdp_growth": -5.4, "unemployment": 6.9, "snp500": 903.25, "vix": 60.0, "fed_rate": 0.16, "treasury_10y": 2.20, "home_price_yoy": -18.7, "hy_spread": 16.50, "ted_spread": 3.00},
        {"quarter": "2009Q1", "gdp_growth": -6.4, "unemployment": 8.3, "snp500": 797.87, "vix": 50.0, "fed_rate": 0.16, "treasury_10y": 2.70, "home_price_yoy": -19.0, "hy_spread": 14.00, "ted_spread": 1.00},
        {"quarter": "2009Q2", "gdp_growth": -0.7, "unemployment": 9.3, "snp500": 919.14, "vix": 28.0, "fed_rate": 0.18, "treasury_10y": 3.50, "home_price_yoy": -15.0, "hy_spread": 11.00, "ted_spread": 0.50},
        {"quarter": "2009Q3", "gdp_growth": 3.5, "unemployment": 9.6, "snp500": 1057.08, "vix": 25.0, "fed_rate": 0.18, "treasury_10y": 3.30, "home_price_yoy": -9.0, "hy_spread": 9.00, "ted_spread": 0.30},
        {"quarter": "2009Q4", "gdp_growth": 5.5, "unemployment": 9.9, "snp500": 1115.10, "vix": 21.0, "fed_rate": 0.18, "treasury_10y": 3.40, "home_price_yoy": -3.0, "hy_spread": 6.50, "ted_spread": 0.25},
        {"quarter": "2010Q1", "gdp_growth": 2.7, "unemployment": 9.8, "snp500": 1146.39, "vix": 17.5, "fed_rate": 0.16, "treasury_10y": 3.80, "home_price_yoy": 2.0, "hy_spread": 5.50, "ted_spread": 0.20},
    ],
    # -------- 2000 互联网泡沫破裂 (Dot-Com 2000) --------
    "dotcom_2000": [
        {"quarter": "1999Q4", "gdp_growth": 7.4, "unemployment": 4.1, "snp500": 1469.25, "vix": 24.0, "fed_rate": 5.50, "treasury_10y": 6.00, "home_price_yoy": 11.0, "hy_spread": 5.00, "ted_spread": 0.30},
        {"quarter": "2000Q1", "gdp_growth": 1.5, "unemployment": 4.0, "snp500": 1499.04, "vix": 19.0, "fed_rate": 6.00, "treasury_10y": 6.00, "home_price_yoy": 12.0, "hy_spread": 5.50, "ted_spread": 0.30},
        {"quarter": "2000Q2", "gdp_growth": 7.4, "unemployment": 4.0, "snp500": 1454.60, "vix": 23.0, "fed_rate": 6.50, "treasury_10y": 6.00, "home_price_yoy": 13.0, "hy_spread": 7.00, "ted_spread": 0.50},
        {"quarter": "2000Q3", "gdp_growth": 0.5, "unemployment": 4.0, "snp500": 1430.10, "vix": 23.0, "fed_rate": 6.50, "treasury_10y": 5.80, "home_price_yoy": 12.0, "hy_spread": 7.50, "ted_spread": 0.50},
        {"quarter": "2000Q4", "gdp_growth": 2.5, "unemployment": 3.9, "snp500": 1320.28, "vix": 26.0, "fed_rate": 6.00, "treasury_10y": 5.10, "home_price_yoy": 10.0, "hy_spread": 8.00, "ted_spread": 0.50},
        {"quarter": "2001Q1", "gdp_growth": -1.3, "unemployment": 4.2, "snp500": 1160.33, "vix": 32.0, "fed_rate": 5.00, "treasury_10y": 4.90, "home_price_yoy": 8.0, "hy_spread": 9.50, "ted_spread": 0.50},
        {"quarter": "2001Q2", "gdp_growth": 2.2, "unemployment": 4.4, "snp500": 1224.38, "vix": 26.0, "fed_rate": 4.00, "treasury_10y": 5.00, "home_price_yoy": 7.0, "hy_spread": 9.00, "ted_spread": 0.30},
        {"quarter": "2001Q3", "gdp_growth": -1.3, "unemployment": 4.8, "snp500": 1040.94, "vix": 35.0, "fed_rate": 3.00, "treasury_10y": 4.70, "home_price_yoy": 6.0, "hy_spread": 11.00, "ted_spread": 0.40},
        {"quarter": "2001Q4", "gdp_growth": 1.8, "unemployment": 5.5, "snp500": 1148.08, "vix": 26.0, "fed_rate": 1.82, "treasury_10y": 5.00, "home_price_yoy": 6.0, "hy_spread": 10.00, "ted_spread": 0.30},
        {"quarter": "2002Q1", "gdp_growth": 3.4, "unemployment": 5.7, "snp500": 1147.39, "vix": 21.0, "fed_rate": 1.75, "treasury_10y": 5.40, "home_price_yoy": 7.0, "hy_spread": 9.00, "ted_spread": 0.30},
        {"quarter": "2002Q2", "gdp_growth": 2.4, "unemployment": 5.8, "snp500": 989.82, "vix": 27.0, "fed_rate": 1.75, "treasury_10y": 4.80, "home_price_yoy": 8.0, "hy_spread": 10.00, "ted_spread": 0.30},
        {"quarter": "2002Q3", "gdp_growth": 2.4, "unemployment": 5.7, "snp500": 815.28, "vix": 49.0, "fed_rate": 1.75, "treasury_10y": 3.90, "home_price_yoy": 7.5, "hy_spread": 12.00, "ted_spread": 0.40},
        {"quarter": "2002Q4", "gdp_growth": 0.4, "unemployment": 5.9, "snp500": 879.82, "vix": 30.0, "fed_rate": 1.25, "treasury_10y": 4.00, "home_price_yoy": 8.0, "hy_spread": 9.00, "ted_spread": 0.30},
    ],
    # -------- 1929 大萧条 (Great Depression) --------
    # 注: VIX/HY Spread/TED Spread 在 1929 年代尚不存在; Case-Shiller 房价指数亦无
    # S&P 500 数据采用 S&P Composite (90 只股票前身) 历史数据; 失业率为学者估算
    "great_depression_1929": [
        {"quarter": "1929Q2", "gdp_growth": 5.0, "unemployment": 3.2, "snp500": 28.6, "vix": None, "fed_rate": 5.0, "treasury_10y": 3.6, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1929Q3", "gdp_growth": 6.0, "unemployment": 3.0, "snp500": 31.92, "vix": None, "fed_rate": 6.0, "treasury_10y": 3.6, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1929Q4", "gdp_growth": -3.0, "unemployment": 5.0, "snp500": 24.0, "vix": None, "fed_rate": 4.5, "treasury_10y": 3.2, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1930Q1", "gdp_growth": -7.0, "unemployment": 8.7, "snp500": 21.0, "vix": None, "fed_rate": 3.0, "treasury_10y": 3.0, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1930Q2", "gdp_growth": -10.0, "unemployment": 13.5, "snp500": 17.0, "vix": None, "fed_rate": 2.5, "treasury_10y": 3.1, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1930Q3", "gdp_growth": -5.0, "unemployment": 14.0, "snp500": 19.0, "vix": None, "fed_rate": 2.0, "treasury_10y": 2.8, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1930Q4", "gdp_growth": -8.0, "unemployment": 16.0, "snp500": 15.0, "vix": None, "fed_rate": 2.0, "treasury_10y": 2.8, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1931Q1", "gdp_growth": -9.0, "unemployment": 19.0, "snp500": 12.0, "vix": None, "fed_rate": 1.5, "treasury_10y": 2.8, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1931Q2", "gdp_growth": -4.0, "unemployment": 21.0, "snp500": 9.0, "vix": None, "fed_rate": 1.5, "treasury_10y": 2.5, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1931Q3", "gdp_growth": -12.0, "unemployment": 22.0, "snp500": 8.0, "vix": None, "fed_rate": 1.5, "treasury_10y": 2.5, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1931Q4", "gdp_growth": -10.0, "unemployment": 23.0, "snp500": 6.0, "vix": None, "fed_rate": 1.5, "treasury_10y": 2.7, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
        {"quarter": "1932Q3", "gdp_growth": -2.0, "unemployment": 24.9, "snp500": 4.40, "vix": None, "fed_rate": 2.5, "treasury_10y": 3.0, "home_price_yoy": None, "hy_spread": None, "ted_spread": None},
    ],
    # -------- 2020 新冠市场崩盘 (COVID-19 2020) --------
    "covid_2020": [
        {"quarter": "2019Q4", "gdp_growth": 2.6, "unemployment": 3.5, "snp500": 3230.78, "vix": 13.5, "fed_rate": 1.55, "treasury_10y": 1.86, "home_price_yoy": 3.6, "hy_spread": 3.50, "ted_spread": 0.20},
        {"quarter": "2020Q1", "gdp_growth": -5.0, "unemployment": 4.4, "snp500": 2588.37, "vix": 53.0, "fed_rate": 1.38, "treasury_10y": 1.27, "home_price_yoy": 4.0, "hy_spread": 7.00, "ted_spread": 0.40},
        {"quarter": "2020Q2", "gdp_growth": -31.4, "unemployment": 13.0, "snp500": 3100.29, "vix": 36.0, "fed_rate": 0.18, "treasury_10y": 0.66, "home_price_yoy": 4.5, "hy_spread": 7.50, "ted_spread": 0.20},
        {"quarter": "2020Q3", "gdp_growth": 33.4, "unemployment": 8.8, "snp500": 3380.32, "vix": 27.0, "fed_rate": 0.13, "treasury_10y": 0.68, "home_price_yoy": 7.0, "hy_spread": 5.00, "ted_spread": 0.15},
        {"quarter": "2020Q4", "gdp_growth": 4.3, "unemployment": 6.8, "snp500": 3756.07, "vix": 22.0, "fed_rate": 0.09, "treasury_10y": 0.93, "home_price_yoy": 10.0, "hy_spread": 4.00, "ted_spread": 0.15},
        {"quarter": "2021Q1", "gdp_growth": 6.3, "unemployment": 6.0, "snp500": 3972.89, "vix": 19.0, "fed_rate": 0.08, "treasury_10y": 1.65, "home_price_yoy": 14.0, "hy_spread": 3.40, "ted_spread": 0.10},
        {"quarter": "2021Q2", "gdp_growth": 6.7, "unemployment": 5.9, "snp500": 4297.50, "vix": 16.0, "fed_rate": 0.08, "treasury_10y": 1.45, "home_price_yoy": 18.0, "hy_spread": 3.00, "ted_spread": 0.10},
        {"quarter": "2021Q3", "gdp_growth": 2.7, "unemployment": 5.1, "snp500": 4530.41, "vix": 17.5, "fed_rate": 0.08, "treasury_10y": 1.33, "home_price_yoy": 19.0, "hy_spread": 3.00, "ted_spread": 0.10},
    ],
    # -------- 1997 亚洲金融危机 (Asian Financial Crisis 1997) --------
    # 注: 此处指标以美国市场数据为主, 用于对比亚洲危机对全球市场的传导
    "asia_1997": [
        {"quarter": "1997Q1", "gdp_growth": 4.5, "unemployment": 5.2, "snp500": 757.12, "vix": 18.0, "fed_rate": 5.50, "treasury_10y": 6.50, "home_price_yoy": 4.0, "hy_spread": 4.00, "ted_spread": 0.40},
        {"quarter": "1997Q2", "gdp_growth": 5.3, "unemployment": 5.0, "snp500": 885.14, "vix": 17.0, "fed_rate": 5.50, "treasury_10y": 6.40, "home_price_yoy": 4.5, "hy_spread": 3.50, "ted_spread": 0.30},
        {"quarter": "1997Q3", "gdp_growth": 5.5, "unemployment": 4.8, "snp500": 942.49, "vix": 26.0, "fed_rate": 5.50, "treasury_10y": 5.90, "home_price_yoy": 5.0, "hy_spread": 4.50, "ted_spread": 0.50},
        {"quarter": "1997Q4", "gdp_growth": 4.4, "unemployment": 4.7, "snp500": 970.43, "vix": 24.0, "fed_rate": 5.50, "treasury_10y": 5.70, "home_price_yoy": 5.0, "hy_spread": 4.50, "ted_spread": 0.50},
        {"quarter": "1998Q1", "gdp_growth": 5.0, "unemployment": 4.6, "snp500": 1101.75, "vix": 21.0, "fed_rate": 5.50, "treasury_10y": 5.50, "home_price_yoy": 6.0, "hy_spread": 4.50, "ted_spread": 0.40},
        {"quarter": "1998Q2", "gdp_growth": 3.7, "unemployment": 4.4, "snp500": 1133.84, "vix": 25.0, "fed_rate": 5.50, "treasury_10y": 5.40, "home_price_yoy": 6.5, "hy_spread": 5.00, "ted_spread": 0.50},
        {"quarter": "1998Q3", "gdp_growth": 4.8, "unemployment": 4.5, "snp500": 957.28, "vix": 45.0, "fed_rate": 5.27, "treasury_10y": 4.80, "home_price_yoy": 6.5, "hy_spread": 7.00, "ted_spread": 1.00},
        {"quarter": "1998Q4", "gdp_growth": 5.1, "unemployment": 4.4, "snp500": 1229.23, "vix": 30.0, "fed_rate": 4.75, "treasury_10y": 4.60, "home_price_yoy": 6.5, "hy_spread": 6.00, "ted_spread": 0.70},
        {"quarter": "1999Q1", "gdp_growth": 3.7, "unemployment": 4.3, "snp500": 1286.84, "vix": 23.0, "fed_rate": 4.75, "treasury_10y": 5.00, "home_price_yoy": 5.0, "hy_spread": 5.00, "ted_spread": 0.40},
        {"quarter": "1999Q2", "gdp_growth": 5.5, "unemployment": 4.2, "snp500": 1372.71, "vix": 20.0, "fed_rate": 4.86, "treasury_10y": 5.40, "home_price_yoy": 5.0, "hy_spread": 5.00, "ted_spread": 0.20},
    ],
}


def get_crisis_macro_indicators(crisis_id: str) -> dict:
    """
    获取特定危机的宏观经济指标季度时间序列。

    返回的指标包含:
        - gdp_growth:       GDP 季度环比折年率 (%)
        - unemployment:     U-3 失业率 (%)
        - snp500:           S&P 500 季度收盘点位
        - vix:              VIX 指数季度均值
        - fed_rate:         有效联邦基金利率 (%)
        - treasury_10y:     10 年期国债收益率 (%)
        - home_price_yoy:   Case-Shiller 全国房价指数同比 (%)
        - hy_spread:        高收益债 OAS 利差 (%)
        - ted_spread:       TED 利差 (%)

    Args:
        crisis_id: 危机 ID (如 "gfc_2008")

    Returns:
        dict: 包含 crisis_id、indicator 列表及 metadata 的字典;
              若未找到危机, 返回 {"error": ...}

    Example:
        >>> get_crisis_macro_indicators("gfc_2008")
        {"crisis_id": "gfc_2008", "indicators": [...], "metadata": {...}}
    """
    data = MACRO_INDICATORS.get(crisis_id)
    if data is None:
        return {"error": f"Crisis {crisis_id} not found in MACRO_INDICATORS"}

    return {
        "crisis_id": crisis_id,
        "indicators": list(data),
        "metadata": {
            "fields": [
                "quarter", "gdp_growth", "unemployment", "snp500", "vix",
                "fed_rate", "treasury_10y", "home_price_yoy", "hy_spread", "ted_spread",
            ],
            "units": {
                "gdp_growth": "%",
                "unemployment": "%",
                "snp500": "index points",
                "vix": "index points",
                "fed_rate": "%",
                "treasury_10y": "%",
                "home_price_yoy": "% YoY",
                "hy_spread": "%",
                "ted_spread": "%",
            },
            "note_zh": "1929 大萧条期间 VIX、HY 利差、TED 利差、Case-Shiller 房价指数尚不存在, 使用 None 表示",
            "note_en": "For the Great Depression (1929), VIX/HY Spread/TED Spread/Case-Shiller Home Price Index did not exist; None is used",
            "data_sources": [
                "FRED (Federal Reserve Economic Data)",
                "BLS (Bureau of Labor Statistics)",
                "S&P Dow Jones Indices",
                "CBOE (Chicago Board Options Exchange)",
                "ICE BofA US High Yield Index",
                "S&P CoreLogic Case-Shiller Home Price Index",
            ],
        },
    }


# ==================== 金融机构演变追踪 (Financial Institution Evolution) ====================
# 金融机构在历次危机中的命运: 破产 / 被收购 / 救助 / 政府接管 / 再融资
# 字段说明:
#   name_zh          - 机构中文名
#   name_en          - 机构英文名
#   event_type       - 事件类型: bankruptcy / acquisition / bailout / government_takeover / recapitalization
#   date             - 事件日期 (ISO 8601, 精确到月)
#   asset_size_b     - 资产规模 (十亿美元, 可选)
#   acquirer         - 收购方 (仅 acquisition 类型)
#   bailout_amount_b - 救助金额 (十亿美元, 可选)
#   description_zh   - 中文描述
#   description_en   - 英文描述

INSTITUTION_EVENTS: dict[str, list[dict]] = {
    # -------- 2008 全球金融危机 --------
    "gfc_2008": [
        {
            "name_zh": "新世纪金融 (New Century Financial)",
            "name_en": "New Century Financial",
            "event_type": "bankruptcy",
            "date": "2007-04-02",
            "asset_size_b": 22.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "全美第二大次贷放款机构申请破产保护, 危机的早期信号之一",
            "description_en": "Second-largest US subprime lender filed for Chapter 11; an early warning signal",
        },
        {
            "name_zh": "贝尔斯登 (Bear Stearns)",
            "name_en": "Bear Stearns",
            "event_type": "acquisition",
            "date": "2008-03-16",
            "asset_size_b": 395.0,
            "acquirer": "JPMorgan Chase",
            "bailout_amount_b": 30.0,
            "description_zh": "美联储提供 300 亿美元担保, 摩根大通以每股 2 美元 (后调整为 10 美元) 收购贝尔斯登",
            "description_en": "Fed provided $30B backstop; JPMorgan acquired Bear at $2/share (later revised to $10)",
        },
        {
            "name_zh": "Countrywide Financial",
            "name_en": "Countrywide Financial",
            "event_type": "acquisition",
            "date": "2008-07-01",
            "asset_size_b": 212.0,
            "acquirer": "Bank of America",
            "bailout_amount_b": None,
            "description_zh": "美国最大抵押贷款机构被美国银行以 40 亿美元股票收购",
            "description_en": "Largest US mortgage lender acquired by Bank of America in an all-stock deal worth $4B",
        },
        {
            "name_zh": "IndyMac 银行",
            "name_en": "IndyMac Bank",
            "event_type": "government_takeover",
            "date": "2008-07-11",
            "asset_size_b": 32.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "FDIC 接管 IndyMac, 当时为 24 年来最大银行倒闭案",
            "description_en": "FDIC seized IndyMac; largest bank failure in 24 years at the time",
        },
        {
            "name_zh": "房利美 (Fannie Mae)",
            "name_en": "Fannie Mae",
            "event_type": "government_takeover",
            "date": "2008-09-07",
            "asset_size_b": 880.0,
            "acquirer": None,
            "bailout_amount_b": 116.0,
            "description_zh": "FHFA 将房利美和房地美同时置于政府托管, 美财政部注资 1160 亿美元",
            "description_en": "FHFA placed Fannie and Freddie in conservatorship; Treasury injected $116B",
        },
        {
            "name_zh": "房地美 (Freddie Mac)",
            "name_en": "Freddie Mac",
            "event_type": "government_takeover",
            "date": "2008-09-07",
            "asset_size_b": 879.0,
            "acquirer": None,
            "bailout_amount_b": 71.0,
            "description_zh": "与房利美一同被 FHFA 接管, 美财政部注资 710 亿美元",
            "description_en": "Placed in conservatorship alongside Fannie; Treasury injected $71B",
        },
        {
            "name_zh": "雷曼兄弟 (Lehman Brothers)",
            "name_en": "Lehman Brothers",
            "event_type": "bankruptcy",
            "date": "2008-09-15",
            "asset_size_b": 639.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "美国历史上最大的破产案 (6390 亿美元资产), 直接引发全球金融海啸",
            "description_en": "Largest bankruptcy in US history ($639B assets); triggered global financial meltdown",
        },
        {
            "name_zh": "美林证券 (Merrill Lynch)",
            "name_en": "Merrill Lynch",
            "event_type": "acquisition",
            "date": "2008-09-15",
            "asset_size_b": 1020.0,
            "acquirer": "Bank of America",
            "bailout_amount_b": None,
            "description_zh": "美银以约 500 亿美元股票收购美林, 避免其成为下一个雷曼",
            "description_en": "BoA acquired Merrill in ~$50B all-stock deal, averting another Lehman-style collapse",
        },
        {
            "name_zh": "AIG (美国国际集团)",
            "name_en": "American International Group (AIG)",
            "event_type": "bailout",
            "date": "2008-09-16",
            "asset_size_b": 1100.0,
            "acquirer": None,
            "bailout_amount_b": 182.0,
            "description_zh": "美联储先提供 850 亿美元贷款, 后续救助总额达 1820 亿美元, 政府获 79.9% 股权",
            "description_en": "Fed extended $85B initially; total bailout reached $182B; US took 79.9% stake",
        },
        {
            "name_zh": "华盛顿互惠银行 (Washington Mutual)",
            "name_en": "Washington Mutual",
            "event_type": "bankruptcy",
            "date": "2008-09-25",
            "asset_size_b": 307.0,
            "acquirer": "JPMorgan Chase",
            "bailout_amount_b": None,
            "description_zh": "美国历史上最大的银行倒闭案 (3070 亿美元资产), 摩根大通收购其银行业务",
            "description_en": "Largest bank failure in US history ($307B assets); banking operations acquired by JPMorgan",
        },
        {
            "name_zh": "美联银行 (Wachovia)",
            "name_en": "Wachovia",
            "event_type": "acquisition",
            "date": "2008-09-29",
            "asset_size_b": 780.0,
            "acquirer": "Wells Fargo",
            "bailout_amount_b": None,
            "description_zh": "花旗最初协商收购, 后富国银行以 150 亿美元全股票收购美联",
            "description_en": "Citigroup initially negotiated acquisition; Wells Fargo won with $15B all-stock deal",
        },
        {
            "name_zh": "花旗集团 (Citigroup)",
            "name_en": "Citigroup",
            "event_type": "bailout",
            "date": "2008-11-23",
            "asset_size_b": 2050.0,
            "acquirer": None,
            "bailout_amount_b": 45.0,
            "description_zh": "TARP 注资 450 亿美元, 政府对 3060 亿美元问题资产提供担保",
            "description_en": "TARP injected $45B; US guaranteed $306B of troubled assets",
        },
        {
            "name_zh": "摩根士丹利 (Morgan Stanley)",
            "name_en": "Morgan Stanley",
            "event_type": "recapitalization",
            "date": "2008-09-21",
            "asset_size_b": 1050.0,
            "acquirer": None,
            "bailout_amount_b": 10.0,
            "description_zh": "转为银行控股公司; 三菱 UFJ 金融集团注资 90 亿美元; 接受 TARP 100 亿美元",
            "description_en": "Converted to bank holding company; Mitsubishi UFJ invested $9B; received $10B TARP",
        },
        {
            "name_zh": "高盛 (Goldman Sachs)",
            "name_en": "Goldman Sachs",
            "event_type": "recapitalization",
            "date": "2008-09-21",
            "asset_size_b": 1100.0,
            "acquirer": None,
            "bailout_amount_b": 10.0,
            "description_zh": "转为银行控股公司; 巴菲特注资 50 亿美元; 接受 TARP 100 亿美元",
            "description_en": "Converted to bank holding company; Buffett invested $5B; received $10B TARP",
        },
        {
            "name_zh": "美国银行 (Bank of America)",
            "name_en": "Bank of America",
            "event_type": "bailout",
            "date": "2009-01-16",
            "asset_size_b": 2500.0,
            "acquirer": None,
            "bailout_amount_b": 45.0,
            "description_zh": "因美林亏损恶化, TARP 追加注资 200 亿美元, 政府担保 1180 亿美元资产",
            "description_en": "Due to Merrill losses, TARP added $20B; US guaranteed $118B of assets",
        },
    ],
    # -------- 2000 互联网泡沫 --------
    "dotcom_2000": [
        {
            "name_zh": "安然 (Enron)",
            "name_en": "Enron",
            "event_type": "bankruptcy",
            "date": "2001-12-02",
            "asset_size_b": 65.5,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "当时美国最大破产案; 表外实体隐藏债务, 财务造假曝光后股价从 90 美元跌至 0.5 美元",
            "description_en": "Largest US bankruptcy at the time; off-balance-sheet entities hid debt; stock fell from $90 to $0.50",
        },
        {
            "name_zh": "世通 (WorldCom)",
            "name_en": "WorldCom",
            "event_type": "bankruptcy",
            "date": "2002-07-21",
            "asset_size_b": 107.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "刷新安然破产记录 (1070 亿美元资产); 承认 38 亿美元会计欺诈, 后扩大至 110 亿美元",
            "description_en": "Surpassed Enron ($107B assets); admitted $3.8B fraud later revised to $11B",
        },
        {
            "name_zh": "安达信会计师事务所 (Arthur Andersen)",
            "name_en": "Arthur Andersen",
            "event_type": "bankruptcy",
            "date": "2002-06-15",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "因销毁安然审计文件被定罪 (后于 2005 年推翻), 五大事务所之一解散",
            "description_en": "Convicted of shredding Enron audit documents (overturned 2005); one of Big Five dissolved",
        },
        {
            "name_zh": "环球电讯 (Global Crossing)",
            "name_en": "Global Crossing",
            "event_type": "bankruptcy",
            "date": "2002-01-28",
            "asset_size_b": 22.4,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "电信运营商破产, 当时为美国第四大破产案",
            "description_en": "Telecom carrier bankruptcy; fourth-largest in US at the time",
        },
        {
            "name_zh": "Priceline.com",
            "name_en": "Priceline.com",
            "event_type": "recapitalization",
            "date": "2000-09",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "互联网泡沫破裂的标志性受害者, 股价从 974 美元跌至约 5 美元, 后通过业务转型存活",
            "description_en": "Iconic dot-com victim; stock fell from $974 to ~$5; survived via business model pivot",
        },
        {
            "name_zh": "Pets.com",
            "name_en": "Pets.com",
            "event_type": "bankruptcy",
            "date": "2000-11-09",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "互联网泡沫的标志性失败案例, 上线 268 天后倒闭",
            "description_en": "Symbolic failure of dot-com bubble; shut down after 268 days",
        },
    ],
    # -------- 1929 大萧条 --------
    "great_depression_1929": [
        {
            "name_zh": "美国银行 (Bank of United States)",
            "name_en": "Bank of United States",
            "event_type": "bankruptcy",
            "date": "1930-12-11",
            "asset_size_b": 0.20,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "当时美国最大银行倒闭案 (2 亿美元存款), 引发第一波银行挤兑潮",
            "description_en": "Largest US bank failure at the time ($200M deposits); triggered first wave of bank runs",
        },
        {
            "name_zh": "美国信用银行 (Bank of America 前身)",
            "name_en": "Bank of Italy (later Bank of America)",
            "event_type": "recapitalization",
            "date": "1931-01",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "A.P. Giannini 在大萧条中持续扩张, 兼并多家倒闭银行, 为后来的美国银行奠定基础",
            "description_en": "A.P. Giannini continued expanding through the Depression, acquiring failed banks; foundation of modern BofA",
        },
        {
            "name_zh": "重建金融公司 (Reconstruction Finance Corporation)",
            "name_en": "Reconstruction Finance Corporation (RFC)",
            "event_type": "bailout",
            "date": "1932-01-22",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": 2.0,
            "description_zh": "胡佛政府成立 RFC, 授权 20 亿美元向银行、铁路等关键行业提供紧急贷款",
            "description_en": "Hoover administration created RFC with $2B authorized to lend to banks, railroads, critical industries",
        },
        {
            "name_zh": "亨利·福特 (拒绝救助)",
            "name_en": "Henry Ford (refused to participate in rescue)",
            "event_type": "recapitalization",
            "date": "1933-02-14",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "福特拒绝加入拯救底特律联合守护者集团的银团, 直接导致密歇根州银行假期",
            "description_en": "Ford refused to join rescue syndicate for Detroit Union Guardian Group; triggered Michigan bank holiday",
        },
        {
            "name_zh": "摩根财团 (J.P. Morgan & Co.)",
            "name_en": "J.P. Morgan & Co.",
            "event_type": "recapitalization",
            "date": "1929-10-24",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "摩根牵头组织银行团注入资金救市, 1929 年股灾当日短暂稳定市场",
            "description_en": "Morgan organized syndicate to inject liquidity on Black Thursday, briefly stabilizing markets",
        },
        {
            "name_zh": "联邦存款保险 (FDIC 设立)",
            "name_en": "Federal Deposit Insurance Corporation (FDIC created)",
            "event_type": "recapitalization",
            "date": "1933-06-16",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": 0.289,
            "description_zh": "《格拉斯-斯蒂格尔法案》设立 FDIC, 初始保险上限 2500 美元, 终结银行挤兑",
            "description_en": "Glass-Steagall Act created FDIC with $2,500 insurance limit, ending bank runs",
        },
    ],
    # -------- 2020 新冠崩盘 --------
    "covid_2020": [
        {
            "name_zh": "Hertz 全球控股",
            "name_en": "Hertz Global Holdings",
            "event_type": "bankruptcy",
            "date": "2020-05-22",
            "asset_size_b": 25.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "汽车租赁巨头因旅行需求骤降申请破产保护, 后于 2021 年重组上市",
            "description_en": "Car rental giant filed for Chapter 11 as travel demand collapsed; re-IPO'd in 2021",
        },
        {
            "name_zh": "J.C. Penney",
            "name_en": "J.C. Penney",
            "event_type": "bankruptcy",
            "date": "2020-05-15",
            "asset_size_b": 12.0,
            "acquirer": "Brookfield / Simon Property",
            "bailout_amount_b": None,
            "description_zh": "百年百货公司申请破产, 后被布鲁克菲尔德和西蒙地产集团收购重组",
            "description_en": "Century-old retailer filed for bankruptcy; acquired by Brookfield and Simon Property",
        },
        {
            "name_zh": "Neiman Marcus",
            "name_en": "Neiman Marcus",
            "event_type": "bankruptcy",
            "date": "2020-05-07",
            "asset_size_b": 5.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "奢侈品百货申请破产保护, 通过债转股于 2020 年 9 月完成重组",
            "description_en": "Luxury department store filed for Chapter 11; debt-for-equity swap completed Sept 2020",
        },
        {
            "name_zh": "Brooks Brothers",
            "name_en": "Brooks Brothers",
            "event_type": "acquisition",
            "date": "2020-07-08",
            "asset_size_b": None,
            "acquirer": "Authentic Brands / SPARC",
            "bailout_amount_b": None,
            "description_zh": "拥有 200 年历史的西装品牌申请破产, 被 Authentic Brands 收购",
            "description_en": "200-year-old suit brand filed for bankruptcy; acquired by Authentic Brands",
        },
        {
            "name_zh": "Chesapeake Energy",
            "name_en": "Chesapeake Energy",
            "event_type": "bankruptcy",
            "date": "2020-06-28",
            "asset_size_b": 14.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "页岩油气巨头因油价崩盘申请破产, 通过债转股于 2021 年重组",
            "description_en": "Shale gas giant filed for Chapter 11 due to oil crash; debt-for-equity restructuring in 2021",
        },
        {
            "name_zh": "美联储 (流动性工具创设)",
            "name_en": "Federal Reserve (liquidity facilities)",
            "event_type": "bailout",
            "date": "2020-03-23",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": 4500.0,
            "description_zh": "美联储宣布无限量 QE, 并设立 PMCCF/SMCCF/MMLF 等多种流动性工具, 资产负债表扩张 3 万亿美元",
            "description_en": "Fed announced unlimited QE; created PMCCF/SMCCF/MMLF facilities; balance sheet grew $3T",
        },
    ],
    # -------- 1997 亚洲金融危机 --------
    "asia_1997": [
        {
            "name_zh": "北海道拓殖银行",
            "name_en": "Hokkaido Takushoku Bank",
            "event_type": "bankruptcy",
            "date": "1997-11-17",
            "asset_size_b": 90.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "日本城市银行首家倒闭, 标志日本银行体系危机深化",
            "description_en": "First Japanese city bank to fail; signaled deepening of Japan's banking crisis",
        },
        {
            "name_zh": "山一证券 (Yamaichi Securities)",
            "name_en": "Yamaichi Securities",
            "event_type": "bankruptcy",
            "date": "1997-11-24",
            "asset_size_b": 24.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "日本四大券商之一自主停业, 负债 240 亿美元, 福田首相称「金融体系不会崩溃」",
            "description_en": "One of Japan's Big Four brokerages voluntarily closed; $24B liabilities; PM Hashimoto vowed system stability",
        },
        {
            "name_zh": "百富勤投资集团",
            "name_en": "Peregrine Investments Holdings",
            "event_type": "bankruptcy",
            "date": "1998-01-13",
            "asset_size_b": 2.5,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "当时亚洲 (除日本外) 最大投行清盘, 印尼坏账拖累, 标志亚洲投行业格局重塑",
            "description_en": "Largest Asian ex-Japan investment bank liquidated; Indonesian bad debts; reshaped Asian IB landscape",
        },
        {
            "name_zh": "大宇集团 (Daewoo Group)",
            "name_en": "Daewoo Group",
            "event_type": "bankruptcy",
            "date": "1999-08-16",
            "asset_size_b": 76.0,
            "acquirer": None,
            "bailout_amount_b": None,
            "description_zh": "韩国第二大财阀解体; 负债 800 亿美元, 后被拆分出售给通用、塔塔等",
            "description_en": "Korea's second-largest chaebol dismantled; $80B debt; assets sold to GM, Tata, others",
        },
        {
            "name_zh": "长期资本管理公司 (LTCM)",
            "name_en": "Long-Term Capital Management (LTCM)",
            "event_type": "bailout",
            "date": "1998-09-23",
            "asset_size_b": 100.0,
            "acquirer": None,
            "bailout_amount_b": 3.6,
            "description_zh": "美联储组织 14 家银行注资 36 亿美元救助, 避免俄罗斯违约后衍生品市场系统性崩溃",
            "description_en": "Fed orchestrated $3.6B bailout by 14 banks; averted systemic derivatives collapse post-Russia default",
        },
        {
            "name_zh": "香港金管局 (HKMA)",
            "name_en": "Hong Kong Monetary Authority (HKMA)",
            "event_type": "recapitalization",
            "date": "1998-08-14",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": 15.0,
            "description_zh": "香港金管局动用 1180 亿港元买入股票和期货, 击退对冲基金对港元的联合攻击",
            "description_en": "HKMA deployed HK$118B to buy equities and futures, defeating hedge fund attack on HKD peg",
        },
        {
            "name_zh": "印尼银行重组局 (IBRA)",
            "name_en": "Indonesian Bank Restructuring Agency (IBRA)",
            "event_type": "government_takeover",
            "date": "1998-01-27",
            "asset_size_b": None,
            "acquirer": None,
            "bailout_amount_b": 80.0,
            "description_zh": "印尼政府冻结 16 家银行, IBRA 接管并重组银行业, 最终耗资 800 亿美元清理不良资产",
            "description_en": "Indonesia froze 16 banks; IBRA took over and restructured banking; $80B cost to clean bad assets",
        },
    ],
}


def get_institution_events(crisis_id: str) -> dict:
    """
    获取特定危机期间金融机构的演变事件 (破产/收购/救助/政府接管/再融资)。

    Args:
        crisis_id: 危机 ID (如 "gfc_2008")

    Returns:
        dict: 包含 crisis_id、institution 事件列表及 metadata 的字典;
              若未找到危机, 返回 {"error": ...}

    Example:
        >>> get_institution_events("gfc_2008")
        {"crisis_id": "gfc_2008", "institutions": [...], "metadata": {...}}
    """
    events = INSTITUTION_EVENTS.get(crisis_id)
    if events is None:
        return {"error": f"Crisis {crisis_id} not found in INSTITUTION_EVENTS"}

    # 按日期排序
    sorted_events = sorted(events, key=lambda x: x["date"])

    # 按 event_type 分类统计
    type_summary: dict[str, int] = {}
    for e in sorted_events:
        t = e["event_type"]
        type_summary[t] = type_summary.get(t, 0) + 1

    return {
        "crisis_id": crisis_id,
        "institutions": sorted_events,
        "metadata": {
            "count": len(sorted_events),
            "event_types": ["bankruptcy", "acquisition", "bailout", "government_takeover", "recapitalization"],
            "type_summary": type_summary,
            "field_notes": {
                "asset_size_b": "资产规模 (十亿美元) / Asset size in billion USD",
                "bailout_amount_b": "救助金额 (十亿美元) / Bailout amount in billion USD",
                "acquirer": "收购方 (仅 acquisition 类型) / Acquirer (acquisition only)",
            },
        },
    }


# ==================== 多维时间轴 (Multi-dimensional Timeline) ====================
# 将危机事件按维度分类: market / institution / policy / economic

# 维度补充事件数据库 (对 ALL_CRISES 中已有事件的分类与补充)
_DIMENSION_EVENTS: dict[str, dict[str, list[dict]]] = {
    "gfc_2008": {
        "market": [
            {"date": "2007-02", "event_zh": "ABX BBB 指数开始下跌, 次贷债券市场出现裂痕", "event_en": "ABX BBB index begins decline; cracks in subprime bond market", "detail": "ABX.HE BBB 06-01 index fell from 100 to ~70 within weeks"},
            {"date": "2007-08-09", "event_zh": "法国巴黎银行冻结 3 只基金, BNP 指出「流动性完全蒸发」", "event_en": "BNP Paribas freezes 3 funds citing 'complete evaporation of liquidity'", "detail": "标志着欧洲流动性危机开始"},
            {"date": "2008-01-22", "event_zh": "美联储紧急降息 75 个基点, 美股期货触发熔断", "event_en": "Fed emergency 75bps cut; US stock futures hit limit down", "detail": "全球股市单日蒸发数万亿美元市值"},
            {"date": "2008-09-15", "event_zh": "雷曼倒闭当日道指下跌 504 点 (-4.4%)", "event_en": "Dow falls 504 points (-4.4%) on Lehman bankruptcy day", "detail": "金融股领跌, 全球股市重挫"},
            {"date": "2008-09-29", "event_zh": "道指下跌 777.68 点, 历史上最大单日点数跌幅", "event_en": "Dow drops 777.68 points, largest single-day point decline in history", "detail": "众议院否决 TARP 后市场暴跌, 1.2 万亿美元市值蒸发"},
            {"date": "2008-10-10", "event_zh": "VIX 盘中触及 89.53 历史高点", "event_en": "VIX intraday peak 89.53, all-time high", "detail": "信用市场冻结, 商业票据市场停摆"},
            {"date": "2008-11-20", "event_zh": "VIX 收于 80.86, 收盘历史第二高", "event_en": "VIX closes at 80.86, second-highest close in history", "detail": "市场恐慌情绪达到顶点"},
            {"date": "2009-03-09", "event_zh": "标普 500 触及 12 年低点 676.53, 较 2007 年高点跌 56.8%", "event_en": "S&P 500 hits 12-year low of 676.53, down 56.8% from 2007 peak", "detail": "市场触底, 标志着本轮熊市结束"},
        ],
        "institution": [
            {"date": "2007-04-02", "event_zh": "新世纪金融 (New Century Financial) 申请破产", "event_en": "New Century Financial files for bankruptcy", "detail": "全美第二大次贷放款机构破产"},
            {"date": "2008-03-16", "event_zh": "贝尔斯登被摩根大通以 2 美元/股收购 (美联储担保 300 亿美元)", "event_en": "Bear Stearns acquired by JPMorgan at $2/share (Fed backstops $30B)", "detail": "美联储创设 JPMorgan 通道, 避免贝尔斯登无序破产"},
            {"date": "2008-07-11", "event_zh": "IndyMac 银行被 FDIC 接管, 当时为 24 年来最大银行倒闭", "event_en": "IndyMac Bank seized by FDIC; largest failure in 24 years", "detail": "320 亿美元资产, 倒闭前 11 天内储户提取 13 亿美元"},
            {"date": "2008-09-07", "event_zh": "房利美和房地美被 FHFA 接管, 财政部注资 2000 亿美元", "event_en": "Fannie Mae and Freddie Mac placed in conservatorship; Treasury injects $200B", "detail": "GSE 持有或担保 5.2 万亿美元抵押贷款"},
            {"date": "2008-09-15", "event_zh": "雷曼兄弟申请破产保护 (6390 亿美元资产)", "event_en": "Lehman Brothers files for Chapter 11 ($639B assets)", "detail": "美国历史上最大破产案, 引发全球金融海啸"},
            {"date": "2008-09-15", "event_zh": "美林证券被美国银行以 500 亿美元股票收购", "event_en": "Merrill Lynch acquired by Bank of America for ~$50B all-stock", "detail": "收购在雷曼倒闭当日宣布, 避免美林成为下一个雷曼"},
            {"date": "2008-09-16", "event_zh": "美联储向 AIG 提供 850 亿美元贷款, 后续总额达 1820 亿美元", "event_en": "Fed extends $85B to AIG; total bailout later reaches $182B", "detail": "政府获 AIG 79.9% 股权, 防止其 CDS 业务引爆全球"},
            {"date": "2008-09-25", "event_zh": "华盛顿互惠银行被 FDIC 接管, 摩根大通收购银行业务", "event_en": "Washington Mutual seized by FDIC; JPMorgan acquires banking operations", "detail": "美国历史上最大银行倒闭 (3070 亿美元资产)"},
            {"date": "2008-09-29", "event_zh": "美联银行 (Wachovia) 被富国银行以 150 亿美元收购", "event_en": "Wachovia acquired by Wells Fargo for $15B", "detail": "花旗最初以 21 亿美元协议收购, 后被富国截胡"},
            {"date": "2008-11-23", "event_zh": "花旗集团获 TARP 450 亿美元注资 + 3060 亿美元资产担保", "event_en": "Citigroup receives $45B TARP + $306B asset guarantee", "detail": "花旗股价此前一周内下跌 60%"},
            {"date": "2009-01-16", "event_zh": "美国银行获 TARP 追加 200 亿美元 + 1180 亿美元资产担保", "event_en": "Bank of America receives additional $20B TARP + $118B asset guarantee", "detail": "因美林四季度亏损恶化, 美银威胁放弃收购"},
        ],
        "policy": [
            {"date": "2007-09-18", "event_zh": "美联储降息 50 个基点至 4.75%, 开启降息周期", "event_en": "Fed cuts 50bps to 4.75%, begins easing cycle", "detail": "2007 年 8 月会议纪要显示对流动性的担忧加剧"},
            {"date": "2007-12-12", "event_zh": "美联储推出定期拍卖工具 (TAF), 首次 200 亿美元拍卖", "event_en": "Fed launches Term Auction Facility (TAF); first $20B auction", "detail": "向存款机构提供抵押贷款, 缓解银行间市场冻结"},
            {"date": "2008-03-11", "event_zh": "美联储创设一级交易商信用工具 (PDCF) 和定期证券借贷工具 (TSLF)", "event_en": "Fed creates Primary Dealer Credit Facility (PDCF) and TSLF", "detail": "向投行开放贴现窗口, 2008 年 3 月 11 日宣布"},
            {"date": "2008-10-03", "event_zh": "TARP 法案签署, 授权 7000 亿美元救助资金", "event_en": "TARP signed into law; $700B bailout authorized", "detail": "众议院 9/29 否决后 10/3 通过, 修订版加入存款保险上限提高至 25 万美元"},
            {"date": "2008-10-08", "event_zh": "美联储、欧央行、英央行等全球六大央行协调降息 50 个基点", "event_en": "Coordinated 50bps cut by Fed, ECB, BoE, Riksbank, SNB, Bank of Canada", "detail": "史无前例的全球协调降息, 中国同步降息"},
            {"date": "2008-11-25", "event_zh": "美联储宣布 QE1, 购买 6000 亿美元 MBS", "event_en": "Fed announces QE1; $600B MBS purchases", "detail": "首次大规模资产购买, 标志非常规货币政策时代开始"},
            {"date": "2009-02-17", "event_zh": "ARRA (美国复苏与再投资法案) 签署, 7870 亿美元财政刺激", "event_en": "ARRA signed; $787B fiscal stimulus", "detail": "包含减税、基础设施支出、州政府援助"},
            {"date": "2009-03-18", "event_zh": "美联储扩大 QE1 至 1.75 万亿美元, 纳入 3000 亿美元长期国债", "event_en": "Fed expands QE1 to $1.75T including $300B long-term Treasuries", "detail": "美联储资产负债表快速扩张"},
            {"date": "2009-05-07", "event_zh": "美联储 SCAP 压力测试结果公布, 10 家银行需补充 750 亿美元资本", "event_en": "Fed SCAP stress test results: 10 banks need $75B capital", "detail": "压力测试恢复市场信心, 标志危机转折点"},
            {"date": "2010-07-21", "event_zh": "《多德-弗兰克法案》签署, 自大萧条以来最严厉的金融监管改革", "event_en": "Dodd-Frank Act signed; most sweeping financial reform since Great Depression", "detail": "设立 FSOC、CFPB, 实施沃尔克规则限制自营交易"},
        ],
        "economic": [
            {"date": "2007-Q3", "event_zh": "Case-Shiller 房价指数同比下跌 5%, 房价正式见顶", "event_en": "Case-Shiller Home Price Index falls 5% YoY; housing officially peaks", "detail": "2006 年中房价高点, 至 2007Q3 同比转负"},
            {"date": "2008-Q1", "event_zh": "美国 GDP 季度环比折年率 -0.7%, 衰退开始", "event_en": "US GDP -0.7% annualized QoQ; recession begins", "detail": "NBER 事后认定衰退始于 2007 年 12 月"},
            {"date": "2008-Q4", "event_zh": "美国 GDP 折年率 -5.4%, 失业率升至 6.9%", "event_en": "US GDP -5.4% annualized; unemployment rises to 6.9%", "detail": "经济活动急剧收缩, 失业率加速上行"},
            {"date": "2009-Q1", "event_zh": "美国 GDP 折年率 -6.4%, 失业率升至 8.3%, 衰退谷底", "event_en": "US GDP -6.4% annualized; unemployment at 8.3%; recession trough", "detail": "本轮衰退最差季度"},
            {"date": "2009-Q3", "event_zh": "美国 GDP 折年率 +3.5%, 衰退正式结束", "event_en": "US GDP +3.5% annualized; recession officially ends", "detail": "NBER 事后认定衰退于 2009 年 6 月结束"},
            {"date": "2009-10", "event_zh": "失业率触及 10.0% 峰值, 后续为「无就业复苏」", "event_en": "Unemployment peaks at 10.0%; subsequent 'jobless recovery'", "detail": "失业率峰值滞后 GDP 触底 4 个月, 直到 2017 年才回到 5% 以下"},
        ],
    },
    "dotcom_2000": {
        "market": [
            {"date": "2000-03-10", "event_zh": "纳斯达克达到 5048.62 历史峰值", "event_en": "NASDAQ peaks at 5,048.62", "detail": "互联网泡沫顶部"},
            {"date": "2000-04-03", "event_zh": "微软反垄断裁决, 股价单日下跌 14%", "event_en": "Microsoft antitrust ruling; stock drops 14% intraday", "detail": "Jackson 法官裁定微软垄断, 加速科技股下跌"},
            {"date": "2000-04-14", "event_zh": "纳斯达克单日下跌 9.7%, 创单日最大跌幅", "event_en": "NASDAQ falls 9.7% in single day, largest daily decline", "detail": "CPI 数据高于预期引发抛售"},
            {"date": "2001-09-17", "event_zh": "9·11 后美股复牌首日, 道指下跌 7.1%", "event_en": "Markets reopen post-9/11; Dow falls 7.1%", "detail": "纽交所关闭 4 天后复牌, 创 1933 年以来最长休市"},
            {"date": "2002-07-19", "event_zh": "道指跌破 8000 点, 较峰值跌 27%", "event_en": "Dow falls below 8,000; down 27% from peak", "detail": "世通欺诈曝光后市场信心崩溃"},
            {"date": "2002-10-09", "event_zh": "纳斯达克触底 1114.11, 较峰值跌 78%", "event_en": "NASDAQ bottoms at 1,114.11; down 78% from peak", "detail": "互联网泡沫熊市结束"},
        ],
        "institution": [
            {"date": "2000-11-09", "event_zh": "Pets.com 倒闭, 互联网泡沫首批标志性受害者", "event_en": "Pets.com shuts down; iconic early victim of dot-com bust", "detail": "上线仅 268 天, 股价从 14 美元跌至 0.19 美元"},
            {"date": "2001-01-31", "event_zh": "亚马逊股价较峰值跌 90%", "event_en": "Amazon stock down 90% from peak", "detail": "幸存者, 后成为最大电商"},
            {"date": "2001-12-02", "event_zh": "安然 (Enron) 申请破产保护", "event_en": "Enron files for Chapter 11", "detail": "当时美国最大破产案, 655 亿美元资产"},
            {"date": "2002-01-22", "event_zh": "环球电讯 (Global Crossing) 申请破产", "event_en": "Global Crossing files for bankruptcy", "detail": "224 亿美元资产, 美国第四大破产案"},
            {"date": "2002-06-25", "event_zh": "世通 (WorldCom) 承认 38 亿美元会计欺诈", "event_en": "WorldCom admits $3.8B accounting fraud", "detail": "后续扩大至 110 亿美元, CEO Ebbers 入狱"},
            {"date": "2002-07-21", "event_zh": "世通申请破产, 1070 亿美元资产刷新安然记录", "event_en": "WorldCom files for bankruptcy; $107B assets surpass Enron", "detail": "直至 2008 年雷曼破产前为美国史上最大破产案"},
            {"date": "2002-06-15", "event_zh": "安达信 (Arthur Andersen) 被定罪, 五大事务所解散", "event_en": "Arthur Andersen convicted; Big Five dissolve", "detail": "销毁安然审计文件, 终结 89 年历史"},
        ],
        "policy": [
            {"date": "2001-01-03", "event_zh": "美联储紧急降息 50 个基点至 6.0%, 开启降息周期", "event_en": "Fed emergency 50bps cut to 6.0%; begins easing cycle", "detail": "1 月 3 日会议间降息, 2001 年累计降息 11 次"},
            {"date": "2001-06-07", "event_zh": "布什签署 1.35 万亿美元减税法案 (EGTRRA)", "event_en": "Bush signs $1.35T tax cut (EGTRRA)", "detail": "10 年期减税计划, 美国史上第二大减税"},
            {"date": "2001-09-11", "event_zh": "9·11 后美联储降息至 1.75%, 提供紧急流动性", "event_en": "Post-9/11 Fed cuts to 1.75%; provides emergency liquidity", "detail": "9 月 17 日降息 50 基点, 11 月再降 50 基点"},
            {"date": "2002-07-30", "event_zh": "《萨班斯-奥克斯利法案》(SOX) 签署", "event_en": "Sarbanes-Oxley Act (SOX) signed", "detail": "设立 PCAOB, 要求 CEO/CFO 个人认证财报"},
            {"date": "2003-06-25", "event_zh": "美联储降息至 1.0%, 创 45 年新低", "event_en": "Fed cuts to 1.0%; 45-year low", "detail": "低利率环境催生房地产泡沫"},
        ],
        "economic": [
            {"date": "2001-Q3", "event_zh": "美国 GDP 折年率 -1.3%, 衰退正式开始", "event_en": "US GDP -1.3% annualized; recession officially begins", "detail": "NBER 认定衰退期为 2001 年 3 月-11 月"},
            {"date": "2001-12", "event_zh": "失业率达 5.8%, 较年初上升 1.8 个百分点", "event_en": "Unemployment reaches 5.8%; up 1.8pp year-to-date", "detail": "9·11 后失业率快速攀升"},
            {"date": "2002-11", "event_zh": "失业率达 6.3% 峰值", "event_en": "Unemployment peaks at 6.3%", "detail": "无就业复苏特征明显"},
            {"date": "2003-Q3", "event_zh": "美国 GDP 折年率 +6.9%, 强劲复苏", "event_en": "US GDP +6.9% annualized; strong recovery", "detail": "减税和降息效果显现"},
        ],
    },
    "great_depression_1929": {
        "market": [
            {"date": "1929-09-03", "event_zh": "道指达到 381.17 峰值", "event_en": "Dow peaks at 381.17", "detail": "1929 年股灾前的市场顶部"},
            {"date": "1929-10-24", "event_zh": "黑色星期四, 道指开盘跌 11%", "event_en": "Black Thursday; Dow drops 11% at open", "detail": "摩根财团组织救市资金短暂稳定市场"},
            {"date": "1929-10-29", "event_zh": "黑色星期二, 道指跌 12%, 成交 1600 万股", "event_en": "Black Tuesday; Dow drops 12%; 16M shares traded", "detail": "1900 万股的成交量纪录保持了 40 年"},
            {"date": "1930-04-17", "event_zh": "道指反弹至 294 点, 较低点反弹 50%", "event_en": "Dow rallies to 294; up 50% from lows", "detail": "「熊市反弹」随后被新一轮下跌抹去"},
            {"date": "1932-07-08", "event_zh": "道指触底 41.22, 较峰值跌 89%", "event_en": "Dow bottoms at 41.22; down 89% from peak", "detail": "大萧条市场底部, 道指直至 1954 年才回到 1929 年峰值"},
        ],
        "institution": [
            {"date": "1930-12-11", "event_zh": "美国银行 (Bank of United States) 倒闭, 4 万储户受影响", "event_en": "Bank of United States fails; 40,000 depositors affected", "detail": "当时美国最大银行倒闭, 引发第一波挤兑潮"},
            {"date": "1931-05-11", "event_zh": "奥地利信贷银行 (Creditanstalt) 倒闭, 欧洲危机蔓延", "event_en": "Creditanstalt collapse; European crisis spreads", "detail": "引发中欧银行业挤兑, 德国银行业受波及"},
            {"date": "1931-07-13", "event_zh": "德国 Darmstädter 银行倒闭, 德国银行业危机", "event_en": "Darmstädter Bank collapse; German banking crisis", "detail": "胡佛宣布暂停德国战争赔款"},
            {"date": "1933-02-14", "event_zh": "底特律联合守护者集团濒临破产, 引发密歇根州银行假期", "event_en": "Detroit Union Guardian Group near collapse; Michigan bank holiday", "detail": "福特拒绝救助, 直接导致州级银行假期"},
            {"date": "1933-03-06", "event_zh": "罗斯福宣布全国银行假期, 关闭所有银行 4 天", "event_en": "FDR declares national Bank Holiday; all banks closed for 4 days", "detail": "《紧急银行法案》通过后, 有偿付能力的银行陆续复业"},
        ],
        "policy": [
            {"date": "1930-06-17", "event_zh": "《斯穆特-霍利关税法》签署, 20000 种商品关税提高", "event_en": "Smoot-Hawley Tariff Act signed; tariffs raised on 20,000 goods", "detail": "引发全球贸易报复, 全球贸易萎缩 65%"},
            {"date": "1932-01-22", "event_zh": "胡佛政府成立重建金融公司 (RFC), 授权 20 亿美元贷款", "event_en": "Hoover creates RFC; $2B authorized for emergency loans", "detail": "向银行、铁路、农业提供紧急贷款"},
            {"date": "1932-07-21", "event_zh": "《紧急救济和建设法》通过, RFC 规模扩大至 32 亿美元", "event_en": "Emergency Relief and Construction Act; RFC expanded to $3.2B", "detail": "首次授权 RFC 向各州提供失业救济"},
            {"date": "1933-03-09", "event_zh": "《紧急银行法案》通过, 罗斯福新政开始", "event_en": "Emergency Banking Act passed; FDR's New Deal begins", "detail": "赋予总统管理金融体系的广泛权力"},
            {"date": "1933-04-19", "event_zh": "美国放弃金本位, 允许货币扩张", "event_en": "US abandons gold standard; enables monetary expansion", "detail": "美元对黄金贬值 40%, 推动通缩转向再通胀"},
            {"date": "1933-06-16", "event_zh": "《格拉斯-斯蒂格尔法案》签署, 设立 FDIC", "event_en": "Glass-Steagall Act signed; FDIC created", "detail": "分立商业银行与投行, 存款保险上限 2500 美元"},
            {"date": "1933-06-13", "event_zh": "《农业调整法》和《全国工业复兴法》通过", "event_en": "Agricultural Adjustment Act and National Industrial Recovery Act passed", "detail": "新政核心立法, 试图通过价格支撑和公共工程刺激经济"},
        ],
        "economic": [
            {"date": "1929-Q3", "event_zh": "GDP 季度环比 +6.0%, 经济仍处扩张期", "event_en": "GDP +6.0% QoQ; economy still expanding", "detail": "股灾前经济基本面良好"},
            {"date": "1930-Q2", "event_zh": "GDP 跌幅扩大至 -10.0%, 失业率突破 13%", "event_en": "GDP declines -10.0%; unemployment breaches 13%", "detail": "通缩开始, CPI 同比下跌 7%"},
            {"date": "1932-Q3", "event_zh": "失业率触及 24.9% 历史峰值", "event_en": "Unemployment peaks at 24.9%, all-time high", "detail": "1500 万人失业, 制造业工资下跌 60%"},
            {"date": "1932-Q3", "event_zh": "美国 GDP 较 1929 年累计下跌 26.7%", "event_en": "US GDP down 26.7% cumulative from 1929", "detail": "经济活动萎缩至一战后最低水平"},
            {"date": "1933-Q4", "event_zh": "GDP 折年率 +9.0%, 复苏开始", "event_en": "GDP +9.0% annualized; recovery begins", "detail": "新政和放弃金本位推动经济复苏"},
        ],
    },
    "covid_2020": {
        "market": [
            {"date": "2020-02-19", "event_zh": "标普 500 触及 3386.15 历史高点", "event_en": "S&P 500 peaks at 3,386.15", "detail": "新冠崩盘前的市场顶部"},
            {"date": "2020-03-09", "event_zh": "标普 500 触发 7% 熔断, 油价崩盘 + 新冠恐慌", "event_en": "S&P 500 triggers 7% circuit breaker; oil crash + COVID fears", "detail": "沙特-俄罗斯油价战, 油价单日跌 30%"},
            {"date": "2020-03-12", "event_zh": "第二次熔断, 1987 年以来最差单日", "event_en": "Second circuit breaker; worst day since 1987", "detail": "道指跌 9.99%, 全球股市重挫"},
            {"date": "2020-03-16", "event_zh": "第三次熔断, 美联储紧急降息 100 个基点至零", "event_en": "Third circuit breaker; Fed emergency 100bps cut to zero", "detail": "市场对紧急降息反应负面, 认为美联储「恐慌」"},
            {"date": "2020-03-18", "event_zh": "第四次熔断, 标普 500 较峰值跌 30%", "event_en": "Fourth circuit breaker; S&P 500 down 30% from peak", "detail": "10 天内 4 次熔断, 史无前例"},
            {"date": "2020-03-23", "event_zh": "标普 500 触底 2237.40, 较峰值跌 33.9%", "event_en": "S&P 500 bottoms at 2,237.40; down 33.9% from peak", "detail": "美联储宣布无限 QE 当日, 标志市场触底"},
            {"date": "2020-04-20", "event_zh": "WTI 原油 5 月期货首次跌至负值 (-37.63 美元)", "event_en": "WTI May futures turn negative (-$37.63) for first time", "detail": "储油空间耗尽, 期货合约交割前抛售"},
            {"date": "2020-08-18", "event_zh": "标普 500 收复全部跌幅, 创 3389.78 历史新高", "event_en": "S&P 500 reclaims all losses, new ATH of 3,389.78", "detail": "史上最快熊市后史上最快复苏"},
        ],
        "institution": [
            {"date": "2020-03-16", "event_zh": "美联储与 14 国央行设立美元互换额度", "event_en": "Fed establishes dollar swap lines with 14 central banks", "detail": "缓解全球美元荒, 包括欧央行、日央行、英央行等"},
            {"date": "2020-03-18", "event_zh": "美联储重启 MMLF (货币市场共同基金流动性工具)", "event_en": "Fed revives Money Market Mutual Fund Liquidity Facility (MMLF)", "detail": "支撑货币市场基金, 防止重演 2008 年 Reserve Primary 事件"},
            {"date": "2020-03-23", "event_zh": "美联储宣布无限量 QE, 设立 PMCCF 和 SMCCF 购买公司债", "event_en": "Fed announces unlimited QE; creates PMCCF and SMCCF to buy corporate bonds", "detail": "首次直接购买投资级公司债, 跨越传统红线"},
            {"date": "2020-04-09", "event_zh": "美联储扩大 SMCCF 至包括部分「堕落天使」", "event_en": "Fed expands SMCCF to include some 'fallen angels'", "detail": "允许购买危机期间被降级的公司债"},
            {"date": "2020-05-15", "event_zh": "J.C. Penney 申请破产, 百货业标志性事件", "event_en": "J.C. Penney files for bankruptcy; iconic retail collapse", "detail": "百年百货破产, 反映零售业疫情冲击"},
        ],
        "policy": [
            {"date": "2020-03-03", "event_zh": "美联储紧急降息 50 个基点至 1.25%", "event_en": "Fed emergency 50bps cut to 1.25%", "detail": "2008 年以来首次会议间紧急降息"},
            {"date": "2020-03-15", "event_zh": "美联储降息至零, 启动 7000 亿美元 QE", "event_en": "Fed cuts to zero; launches $700B QE", "detail": "同时降低贴现率 150 基点, 降低准备金率至零"},
            {"date": "2020-03-23", "event_zh": "美联储宣布无限量 QE, 启动多项流动性工具", "event_en": "Fed announces unlimited QE; launches multiple facilities", "detail": "TALF、PMCCF、SMCCF、MMLF 等工具联动"},
            {"date": "2020-03-27", "event_zh": "CARES 法案签署, 2.2 万亿美元财政刺激", "event_en": "CARES Act signed; $2.2T fiscal stimulus", "detail": "美国史上最大财政刺激, 包括 1200 美元直接支付、PPP 贷款、失业补助"},
            {"date": "2020-04-09", "event_zh": "美联储扩容 2.3 万亿美元贷款计划, 包括 Main Street Lending Program", "event_en": "Fed expands $2.3T lending including Main Street Lending Program", "detail": "向中小企业和地方政府提供贷款支持"},
            {"date": "2020-05-15", "event_zh": "Operation Warp Speed 启动, 100 亿美元加速疫苗研发", "event_en": "Operation Warp Speed launched; $10B for vaccine R&D", "detail": "目标 2021 年 1 月前提供 3 亿剂疫苗"},
            {"date": "2020-12-27", "event_zh": "9000 亿美元追加刺激法案签署", "event_en": "$900B supplemental stimulus signed", "detail": "包含 600 美元直接支付、PPP 扩容、疫苗分发资金"},
        ],
        "economic": [
            {"date": "2020-03", "event_zh": "首次申请失业金人数飙升至 660 万 (历史峰值)", "event_en": "Initial jobless claims surge to 6.6M (all-time high)", "detail": "前一周仅 28 万, 涨幅史无前例"},
            {"date": "2020-Q1", "event_zh": "美国 GDP 折年率 -5.0%, 衰退开始", "event_en": "US GDP -5.0% annualized; recession begins", "detail": "NBER 认定衰退始于 2020 年 2 月"},
            {"date": "2020-04", "event_zh": "失业率飙升至 14.7%, 二战后最高", "event_en": "Unemployment surges to 14.7%; highest since WWII", "detail": "U-3 从 2 月的 3.5% 跃升至 14.7%"},
            {"date": "2020-Q2", "event_zh": "美国 GDP 折年率 -31.4%, 史上最差季度", "event_en": "US GDP -31.4% annualized; worst quarter on record", "detail": "经济活动空前停滞"},
            {"date": "2020-Q3", "event_zh": "美国 GDP 折年率 +33.4%, 史上最强复苏", "event_en": "US GDP +33.4% annualized; strongest recovery on record", "detail": "财政与货币政策刺激下经济快速反弹"},
            {"date": "2020-Q4", "event_zh": "美国 GDP 折年率 +4.3%, 复苏放缓但仍正增长", "event_en": "US GDP +4.3% annualized; recovery slows but stays positive", "detail": "疫情第二波影响部分行业"},
        ],
    },
    "asia_1997": {
        "market": [
            {"date": "1997-07-02", "event_zh": "泰国央行放弃泰铢挂钩, 泰铢暴跌 20%", "event_en": "Bank of Thailand abandons baht peg; THB plunges 20%", "detail": "亚洲金融危机正式开始"},
            {"date": "1997-08-28", "event_zh": "菲律宾、印尼、马来西亚货币集体暴跌", "event_en": "PHP, IDR, MYR currencies collapse in contagion", "detail": "传染效应席卷东南亚"},
            {"date": "1997-10-23", "event_zh": "香港恒生指数 4 天暴跌 23%", "event_en": "Hang Seng Index falls 23% in 4 days", "detail": "国际炒家首次攻击港元联系汇率"},
            {"date": "1997-12-22", "event_zh": "韩元兑美元跌至 1962, 较年初贬值 55%", "event_en": "KRW falls to 1,962/USD; down 55% YTD", "detail": "韩国向 IMF 求助, 外储仅剩 60 亿美元"},
            {"date": "1998-01-12", "event_zh": "印尼盾跌破 10000, 苏哈托政权动摇", "event_en": "IDR breaks 10,000; Suharto regime shaken", "detail": "印尼盾较 1997 年 7 月贬值 85%"},
            {"date": "1998-08-17", "event_zh": "俄罗斯违约国内债务, 卢布崩盘", "event_en": "Russia defaults on domestic debt; ruble collapses", "detail": "LTCM 持有大量俄罗斯头寸, 引发其破产"},
            {"date": "1998-08-28", "event_zh": "香港金管局击退索罗斯, 恒指当日交投 790 亿港元", "event_en": "HKMA defeats Soros; HSI volume hits HK$79B", "detail": "港府动用 1180 亿港元买入股票, 创下经典干预案例"},
        ],
        "institution": [
            {"date": "1997-11-17", "event_zh": "北海道拓殖银行倒闭, 日本城市银行首家破产", "event_en": "Hokkaido Takushoku Bank fails; first Japanese city bank collapse", "detail": "900 亿美元资产, 标志日本银行危机深化"},
            {"date": "1997-11-24", "event_zh": "山一证券自主停业, 日本四大券商破产", "event_en": "Yamaichi Securities collapses; one of Japan's Big Four brokerages fails", "detail": "240 亿美元负债, 福田康夫称「金融体系不会崩溃」"},
            {"date": "1998-01-13", "event_zh": "百富勤投资集团清盘, 亚洲最大投行倒闭", "event_en": "Peregrine Investments liquidates; largest Asian IB fails", "detail": "25 亿美元资产, 印尼坏账拖垮"},
            {"date": "1998-05-21", "event_zh": "苏哈托下台, 印尼政治危机加剧", "event_en": "Suharto resigns; Indonesian political crisis deepens", "detail": "执政 32 年的苏哈托在金融危机中下台"},
            {"date": "1998-08-17", "event_zh": "俄罗斯违约, 银行体系崩溃", "event_en": "Russia defaults; banking system collapses", "detail": "俄罗斯政府推迟偿还 400 亿美元国内债务"},
            {"date": "1998-09-23", "event_zh": "LTCM 被 14 家银行联合救助 36 亿美元", "event_en": "LTCM rescued by 14-bank consortium for $3.6B", "detail": "美联储协调救助, LTCM 杠杆 25 倍, 持有 1.25 万亿美元衍生品"},
            {"date": "1999-08-16", "event_zh": "大宇集团解体, 韩国第二大财阀破产", "event_en": "Daewoo Group dismantled; Korea's #2 chaebol fails", "detail": "760 亿美元资产, 800 亿美元负债"},
        ],
        "policy": [
            {"date": "1997-07-11", "event_zh": "IMF 向泰国提供 172 亿美元救助", "event_en": "IMF provides $17.2B bailout to Thailand", "detail": "附带严格紧缩条件, 包括财政紧缩和加息"},
            {"date": "1997-10-31", "event_zh": "IMF 向印尼提供 430 亿美元救助", "event_en": "IMF provides $43B to Indonesia", "detail": "条件包括关闭 16 家银行, 引发挤兑"},
            {"date": "1997-12-03", "event_zh": "韩国接受 IMF 580 亿美元救助, 被迫开放金融市场", "event_en": "South Korea accepts $58B IMF bailout; opens financial markets", "detail": "韩国被迫接受 IMF 改革条件, 被称为「IMF 危机」"},
            {"date": "1998-04-13", "event_zh": "日本推出 16 万亿日元财政刺激", "event_en": "Japan launches ¥16T fiscal stimulus", "detail": "包括公共工程和减税"},
            {"date": "1998-09-11", "event_zh": "马来西亚实施资本管制, 固定汇率 3.8 林吉特兑 1 美元", "event_en": "Malaysia imposes capital controls; pegs MYR at 3.8/USD", "detail": "马哈蒂尔拒绝 IMF 方案, 资本管制效果存在争议但被证实有效"},
            {"date": "1998-09-29", "event_zh": "美联储降息 25 个基点至 5.25%, 预防全球衰退", "event_en": "Fed cuts 25bps to 5.25%; prevents global recession", "detail": "1998 年 9-11 月共降息 75 基点"},
            {"date": "1999-05-06", "event_zh": "清迈倡议 (CMI) 提出, 东盟 + 中日韩货币互换机制", "event_en": "Chiang Mai Initiative (CMI) proposed; ASEAN+3 currency swap", "detail": "亚洲国家吸取教训, 建立区域金融安全网"},
        ],
        "economic": [
            {"date": "1997-Q3", "event_zh": "泰国 GDP 折年率 -6%, 衰退开始", "event_en": "Thailand GDP -6% annualized; recession begins", "detail": "泰铢贬值后通胀飙升至 10%"},
            {"date": "1998-Q1", "event_zh": "韩国 GDP 同比 -3.8%, 失业率升至 7%", "event_en": "South Korea GDP -3.8% YoY; unemployment rises to 7%", "detail": "韩国 1998 年 GDP 全年萎缩 5.1%"},
            {"date": "1998-Q2", "event_zh": "印尼 GDP 同比 -12.7%, 通胀率突破 70%", "event_en": "Indonesia GDP -12.7% YoY; inflation exceeds 70%", "detail": "印尼受冲击最严重, 贫困率翻倍"},
            {"date": "1998-Q3", "event_zh": "香港 GDP 同比 -8.9%, 房价较高点跌 50%", "event_en": "Hong Kong GDP -8.9% YoY; property prices down 50% from peak", "detail": "联系汇率保卫战代价高昂, 通缩持续 6 年"},
            {"date": "1998-Q4", "event_zh": "俄罗斯 GDP 同比 -9%, 通胀率 84%", "event_en": "Russia GDP -9% YoY; inflation 84%", "detail": "卢布贬值 70%, 银行体系崩溃"},
            {"date": "1999-Q2", "event_zh": "韩国 GDP 同比 +9.8%, 强劲复苏", "event_en": "South Korea GDP +9.8% YoY; strong recovery", "detail": "财阀改革和出口带动快速复苏"},
        ],
    },
}


def get_multi_dimensional_timeline(crisis_id: str) -> dict:
    """
    获取特定危机的多维时间轴 (按 market / institution / policy / economic 分类)。

    将事件分为四个维度:
        - market:      股市事件 (崩盘、熔断、触底等)
        - institution: 银行倒闭、救助、并购
        - policy:      政府与央行行动 (降息、QE、财政刺激、监管)
        - economic:    经济数据发布 (GDP、失业率、通胀)

    Args:
        crisis_id: 危机 ID (如 "gfc_2008")

    Returns:
        dict: 包含 crisis_id 和 dimensions 字典的字典;
              若未找到危机, 返回 {"error": ...}

    Example:
        >>> get_multi_dimensional_timeline("gfc_2008")
        {
            "crisis_id": "gfc_2008",
            "dimensions": {
                "market": [{"date": "2008-09-29", "event_zh": "...", "event_en": "...", "detail": "..."}],
                "institution": [...],
                "policy": [...],
                "economic": [...],
            },
            "metadata": {...},
        }
    """
    dim_data = _DIMENSION_EVENTS.get(crisis_id)
    if dim_data is None:
        return {"error": f"Crisis {crisis_id} not found in multi-dimensional timeline"}

    # 各维度内按日期排序
    dimensions: dict[str, list[dict]] = {}
    for dim, events in dim_data.items():
        # 复制以避免修改原数据
        sorted_events = sorted(
            [dict(e) for e in events], key=lambda x: x["date"]
        )
        dimensions[dim] = sorted_events

    # 统计各维度事件数量
    counts = {dim: len(events) for dim, events in dimensions.items()}

    return {
        "crisis_id": crisis_id,
        "dimensions": dimensions,
        "metadata": {
            "dimension_descriptions": {
                "market": "股市事件 (崩盘、熔断、触底等) / Stock market events (crashes, circuit breakers, bottoms)",
                "institution": "银行倒闭、救助、并购 / Bank failures, bailouts, mergers",
                "policy": "政府与央行行动 (降息、QE、财政刺激、监管) / Government & central bank actions",
                "economic": "经济数据发布 (GDP、失业率、通胀) / Economic data releases",
            },
            "event_counts": counts,
            "total_events": sum(counts.values()),
        },
    }
