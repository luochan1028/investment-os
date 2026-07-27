"""SEC EDGAR 财报抓取与投资信号分析 - 统一入口 (facade)

实际实现拆分为两个子模块:
- sec_fetcher.py: HTTP 抓取 / 缓存 / XBRL 指标提取
- sec_analyzer.py: 工具函数 / 规则引擎 / 公司级分析

本文件 re-export 全部公共 API，保证:
    from data_sources.sec_filings import analyze_company
    from data_sources.sec_filings import fetch_xbrl_data, USER_AGENT, COMPANIES, METRICS
    from data_sources.sec_filings import analyze_investment_signal, get_investment_summary
    from data_sources.sec_filings import pct_change, fmt_num, get_all_metrics, get_latest_filing_date
均可正常工作 (向后兼容)。
"""
from data_sources.sec_fetcher import (
    ALL_FORMS,
    ASSETS_CONCEPTS,
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    CASH_CONCEPTS,
    COMPANIES,
    DEFAULT_TIMEOUT,
    EQUITY_CONCEPTS,
    EPS_CONCEPTS,
    GROSS_PROFIT_CONCEPTS,
    HTTP_BACKOFF_BASE,
    HTTP_MAX_RETRIES,
    METRICS,
    NAMESPACES,
    NET_INCOME_CONCEPTS,
    RD_CONCEPTS,
    REVENUE_CONCEPTS,
    SEC_BASE,
    USER_AGENT,
    _build_session,
    _cache_path,
    _get_session,
    _read_cache,
    _reset_session,
    _write_cache,
    fetch_xbrl_data,
    find_matching_comparison_date,
    find_report_dates_with_metrics,
    get_all_metrics,
    get_latest_filing_date,
)
from data_sources.sec_analyzer import (
    analyze_company,
    analyze_investment_signal,
    fmt_num,
    get_investment_summary,
    pct_change,
)

__all__ = [
    # 配置常量
    "USER_AGENT", "SEC_BASE", "DEFAULT_TIMEOUT", "CACHE_TTL_SECONDS",
    "HTTP_MAX_RETRIES", "HTTP_BACKOFF_BASE", "CACHE_DIR",
    "COMPANIES", "METRICS", "ALL_FORMS", "NAMESPACES",
    "REVENUE_CONCEPTS", "NET_INCOME_CONCEPTS", "GROSS_PROFIT_CONCEPTS",
    "RD_CONCEPTS", "CASH_CONCEPTS", "ASSETS_CONCEPTS", "EQUITY_CONCEPTS", "EPS_CONCEPTS",
    # 抓取层 API
    "fetch_xbrl_data", "get_latest_filing_date", "get_all_metrics",
    "find_report_dates_with_metrics", "find_matching_comparison_date",
    "_build_session", "_get_session", "_reset_session",
    "_cache_path", "_read_cache", "_write_cache",
    # 分析层 API
    "analyze_investment_signal", "get_investment_summary",
    "analyze_company", "pct_change", "fmt_num",
]
