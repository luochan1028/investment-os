"""SEC EDGAR 财报抓取层

负责 HTTP 抓取、缓存、XBRL 指标提取。不含投资信号分析逻辑。

生产级特性:
- 合规 User-Agent (SEC 政策要求真实邮箱)
- HTTP 重试: requests HTTPAdapter + urllib3 Retry (3 次, 指数退避)
- companyfacts JSON 本地缓存 (TTL 6h, key=CIK, 存为 {cik}.json)
- logging 替代 print
- 完整 type hints
- 可独立 import, 不依赖 server.py
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("investment-os.sec_filings")

# ==================== 配置常量 ====================

# SEC 政策要求 User-Agent 含真实联系邮箱
USER_AGENT: str = "investment-os <luochan1028@126.com>"
SEC_BASE: str = "https://data.sec.gov"
DEFAULT_TIMEOUT: int = 30
CACHE_TTL_SECONDS: int = 6 * 3600  # 6 小时
HTTP_MAX_RETRIES: int = 3
HTTP_BACKOFF_BASE: float = 0.5  # 0.5, 1, 2 秒

# 项目根目录: d:\\software\\investment-os
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
CACHE_DIR: Path = _PROJECT_ROOT / "data" / "sec_cache"

# 12 家科技巨头 (公司名, ticker, CIK)
COMPANIES: list[tuple[str, str, str]] = [
    ("Tesla 特斯拉", "TSLA", "0001318605"),
    ("NVIDIA 英伟达", "NVDA", "0001045810"),
    ("Microsoft 微软", "MSFT", "0000789019"),
    ("Apple 苹果", "AAPL", "0000320193"),
    ("Micron 美光", "MU", "0000723125"),
    ("Broadcom 博通", "AVGO", "0001730168"),
    ("AMD 超威半导体", "AMD", "0000002488"),
    ("Intel 英特尔", "INTC", "0000050863"),
    ("Meta Platforms", "META", "0001326801"),
    ("Alphabet 谷歌", "GOOGL", "0001652044"),
    ("Amazon 亚马逊", "AMZN", "0001018724"),
    ("TSMC 台积电", "TSM", "0001158449"),
]

# SEC EDGAR XBRL concept 候选列表
REVENUE_CONCEPTS: list[str] = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet", "Revenue", "TotalRevenuesAndOtherIncome",
]
NET_INCOME_CONCEPTS: list[str] = [
    "NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholders",
    "ProfitLoss", "NetIncome",
]
GROSS_PROFIT_CONCEPTS: list[str] = ["GrossProfit", "GrossMargin"]
RD_CONCEPTS: list[str] = [
    "ResearchAndDevelopmentExpense", "ResearchDevelopmentAndRelatedExpense",
]
CASH_CONCEPTS: list[str] = [
    "CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents", "Cash",
]
ASSETS_CONCEPTS: list[str] = ["Assets"]
EQUITY_CONCEPTS: list[str] = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
EPS_CONCEPTS: list[str] = [
    "EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted",
]

# 8 项原始指标 → 加上派生毛利率共 9 项
METRICS: dict[str, list[str]] = {
    "revenue": REVENUE_CONCEPTS,
    "net_income": NET_INCOME_CONCEPTS,
    "gross_profit": GROSS_PROFIT_CONCEPTS,
    "rd_expense": RD_CONCEPTS,
    "cash": CASH_CONCEPTS,
    "total_assets": ASSETS_CONCEPTS,
    "equity": EQUITY_CONCEPTS,
    "eps": EPS_CONCEPTS,
}

ALL_FORMS: list[str] = ["10-K", "10-Q", "20-F"]
NAMESPACES: list[str] = ["us-gaap", "ifrs-full", "srt"]


# ==================== HTTP Session (重试) ====================


def _build_session() -> requests.Session:
    """构造带 urllib3 Retry 策略的 requests session。

    3 次重试，指数退避 (0.5/1/2 秒)，针对 429/500/502/503/504。
    """
    session = requests.Session()
    retry = Retry(
        total=HTTP_MAX_RETRIES,
        backoff_factor=HTTP_BACKOFF_BASE,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """单例 session (带连接池复用)。"""
    global _session
    if _session is None:
        _session = _build_session()
    return _session


def _reset_session() -> None:
    """测试用: 重置单例 session。"""
    global _session
    _session = None


# ==================== 缓存 ====================


def _cache_path(cik: str) -> Path:
    return CACHE_DIR / f"{cik}.json"


def _read_cache(cik: str, ttl: int = CACHE_TTL_SECONDS) -> Optional[dict]:
    """读取缓存，TTL 内返回 dict，否则返回 None。"""
    p = _cache_path(cik)
    if not p.exists():
        return None
    try:
        age = time.time() - p.stat().st_mtime
        if age > ttl:
            logger.debug(f"cache miss (expired): {cik} age={age:.0f}s")
            return None
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"cache read failed for {cik}: {e}")
        return None


def _write_cache(cik: str, data: dict) -> None:
    p = _cache_path(cik)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError as e:
        logger.warning(f"cache write failed for {cik}: {e}")


# ==================== 核心抓取 ====================


def fetch_xbrl_data(cik: str) -> Optional[dict]:
    """获取 companyfacts JSON (带缓存 + HTTPAdapter 重试 + 应用层重试)。

    Args:
        cik: CIK 编号 (含前导 0, 10 位)
    Returns:
        companyfacts dict 或 None
    """
    cached = _read_cache(cik)
    if cached is not None:
        logger.debug(f"cache hit: {cik}")
        return cached

    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    session = _get_session()

    # 应用层重试: urllib3 Retry 已处理连接级错误,
    # 这里处理 HTTP 5xx 状态码与 RequestException, 保证 mock 可测
    for attempt in range(HTTP_MAX_RETRIES):
        try:
            r = session.get(url, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                _write_cache(cik, data)
                return data
            if r.status_code in (429, 500, 502, 503, 504) and attempt < HTTP_MAX_RETRIES - 1:
                backoff = HTTP_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    f"fetch_xbrl_data {cik} HTTP {r.status_code}, "
                    f"retry {attempt + 1}/{HTTP_MAX_RETRIES} after {backoff}s"
                )
                time.sleep(backoff)
                continue
            logger.warning(f"fetch_xbrl_data {cik} HTTP {r.status_code} (non-retryable)")
            return None
        except requests.RequestException as e:
            if attempt < HTTP_MAX_RETRIES - 1:
                backoff = HTTP_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    f"fetch_xbrl_data {cik} error: {e}, "
                    f"retry {attempt + 1}/{HTTP_MAX_RETRIES} after {backoff}s"
                )
                time.sleep(backoff)
            else:
                logger.warning(f"fetch_xbrl_data {cik} exhausted retries: {e}")
                return None
    return None


def get_latest_filing_date(cik: str) -> tuple[Optional[str], dict[str, Optional[str]]]:
    """获取最近一次财报提交日期。

    Returns:
        (latest_date, {"10-K": ..., "10-Q": ...})
        latest_date 为 10-K/10-Q/20-F 中最近日期
    """
    url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    try:
        r = _get_session().get(url, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:
            logger.warning(f"get_latest_filing_date {cik} HTTP {r.status_code}")
            return None, {"10-K": None, "10-Q": None}
        data = r.json()
    except requests.RequestException as e:
        logger.warning(f"get_latest_filing_date {cik} error: {e}")
        return None, {"10-K": None, "10-Q": None}

    recent = data.get("filings", {}).get("recent", {})
    latest_10k: Optional[str] = None
    latest_10q: Optional[str] = None

    for idx, form in enumerate(recent.get("form", [])):
        if latest_10k is None and form in ("10-K", "20-F"):
            latest_10k = recent["filingDate"][idx]
        elif latest_10q is None and form == "10-Q":
            latest_10q = recent["filingDate"][idx]
        if latest_10k and latest_10q:
            break

    candidates = [x for x in (latest_10k, latest_10q) if x]
    latest = max(candidates) if candidates else None
    return latest, {"10-K": latest_10k, "10-Q": latest_10q}


# ==================== 指标提取 ====================


def _get_metric_for_date(
    xbrl_data: dict,
    concept_list: list[str],
    target_end_date: str,
    target_forms: list[str],
) -> Optional[float]:
    """从 xbrl_data 提取指定日期 + form 的指标值。"""
    facts = xbrl_data.get("facts", {})
    for ns in NAMESPACES:
        namespace = facts.get(ns, {})
        for concept in concept_list:
            if concept not in namespace:
                continue
            units = namespace[concept].get("units", {})
            for entries in units.values():
                for entry in entries:
                    if (entry.get("end") == target_end_date
                            and entry.get("form") in target_forms):
                        val = entry.get("val")
                        if val is not None and val != 0:
                            return float(val)
    return None


def find_report_dates_with_metrics(
    xbrl_data: dict,
) -> tuple[list[str], dict[str, dict]]:
    """找到所有有 revenue/net_income/gross_profit 的报告日期，按日期降序。"""
    facts = xbrl_data.get("facts", {})
    date_info: dict[str, dict] = {}
    core = {
        "revenue": REVENUE_CONCEPTS,
        "net_income": NET_INCOME_CONCEPTS,
        "gross_profit": GROSS_PROFIT_CONCEPTS,
    }

    for metric_name, concept_list in core.items():
        for ns in ("us-gaap", "ifrs-full"):
            namespace = facts.get(ns, {})
            if not namespace:
                continue
            for concept in concept_list:
                if concept not in namespace:
                    continue
                units = namespace[concept].get("units", {})
                for entries in units.values():
                    for entry in entries:
                        form = entry.get("form")
                        end = entry.get("end")
                        val = entry.get("val")
                        if form in ALL_FORMS and end and val and val != 0:
                            if end not in date_info:
                                date_info[end] = {"form": form, "metrics": {}}
                            date_info[end]["metrics"][metric_name] = float(val)

    valid = {d: info for d, info in date_info.items() if "revenue" in info["metrics"]}
    sorted_dates = sorted(valid.keys(), reverse=True)
    return sorted_dates, valid


def get_all_metrics(
    xbrl_data: dict,
    target_end_date: Optional[str],
    forms: list[str],
) -> dict[str, Optional[float]]:
    """提取 9 项核心指标 (含派生毛利率)。

    当 target_end_date 为 None 时返回全 None 的指标字典。
    """
    m: dict[str, Optional[float]] = {k: None for k in METRICS}
    m["gross_margin"] = None
    if target_end_date is None:
        return m

    for key, concepts in METRICS.items():
        m[key] = _get_metric_for_date(xbrl_data, concepts, target_end_date, forms)

    if m.get("gross_profit") and m.get("revenue") and m["revenue"] > 0:
        m["gross_margin"] = (m["gross_profit"] / m["revenue"]) * 100
    return m


def find_matching_comparison_date(
    current_date: str,
    valid_dates: list[str],
    date_info: dict[str, dict],
) -> Optional[str]:
    """找到同比对比日 (10-K/20-F → 同期去年; 10-Q → 去年同期季)。"""
    if current_date not in date_info:
        return None
    current_form = date_info[current_date]["form"]
    try:
        curr = date.fromisoformat(current_date)
    except ValueError:
        return None

    same_form = [d for d in valid_dates if date_info[d]["form"] == current_form]

    # 年报/季报都优先找 350-390 天前的同期
    for d in same_form:
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        delta = (curr - dd).days
        if 350 <= delta <= 390:
            return d

    # 10-Q 再尝试 80-120 天 (上一季度)
    if current_form == "10-Q":
        for d in same_form:
            try:
                dd = date.fromisoformat(d)
            except ValueError:
                continue
            delta = (curr - dd).days
            if 80 <= delta <= 120:
                return d

    # 兜底: 用同 form 的下一个最近日期
    if len(same_form) > 1:
        for d in same_form:
            if d != current_date:
                return d
    return None
