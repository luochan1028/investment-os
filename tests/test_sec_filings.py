"""SEC 财报抓取模块测试

覆盖:
- analyze_investment_signal 规则引擎 (利好/利空/扭亏/中性各种组合)
- get_investment_summary 7 档分级
- pct_change / fmt_num 工具函数
- 缓存命中/未命中逻辑 (mock 文件 IO)
- HTTP 重试逻辑 (mock requests, 第一次 500 第二次 200)
- User-Agent 正确设置
- 全部 mock, 不真实调用 SEC API

运行:
    cd d:\\software\\investment-os && python -m pytest tests/test_sec_filings.py -v
"""
import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

# 确保能 import data_sources.* (项目根在 tests/ 上一级)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_sources import sec_filings
from data_sources import sec_fetcher
from data_sources import sec_analyzer
from data_sources.sec_filings import (
    analyze_company,
    analyze_investment_signal,
    fetch_xbrl_data,
    fmt_num,
    get_all_metrics,
    get_investment_summary,
    get_latest_filing_date,
    pct_change,
    COMPANIES,
    METRICS,
    USER_AGENT,
    CACHE_DIR,
    _build_session,
    _read_cache,
    _write_cache,
    _reset_session,
)


# ==================== 公共 fixture ====================

@pytest.fixture(autouse=True)
def _reset_sec_session():
    """每个测试前后重置 sec_filings 单例 session, 避免测试间泄漏。"""
    _reset_session()
    yield
    _reset_session()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """禁止真实 sleep, 加速测试 (重试退避用)。"""
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    """每个测试用独立临时缓存目录, 避免污染真实 data/sec_cache。"""
    monkeypatch.setattr(sec_fetcher, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(sec_filings, "CACHE_DIR", tmp_path)


def _make_response(status_code, payload=None):
    """构造 mock requests.Response。"""
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload if payload is not None else {}
    return r


def _mock_session_with(responses):
    """构造一个 mock session, get 顺序返回 responses 列表。"""
    s = MagicMock()
    s.headers = {"User-Agent": USER_AGENT}
    s.get.side_effect = responses
    return s


# ==================== 工具函数: pct_change ====================

class TestPctChange:
    def test_basic_increase(self):
        assert pct_change(110, 100) == 10.0

    def test_basic_decrease(self):
        assert pct_change(90, 100) == -10.0

    def test_zero_curr(self):
        assert pct_change(0, 100) == -100.0

    def test_none_curr(self):
        assert pct_change(None, 100) is None

    def test_none_prev(self):
        assert pct_change(100, None) is None

    def test_zero_prev(self):
        """除零保护"""
        assert pct_change(100, 0) is None

    def test_negative_prev_uses_abs(self):
        """负基期用 abs(prev) 作分母: -10 -> 20 = 300% 增长"""
        assert pct_change(20, -10) == 300.0

    def test_negative_to_less_negative(self):
        """亏损收窄: -20 -> -10 = 50% 改善"""
        assert pct_change(-10, -20) == 50.0

    def test_negative_to_more_negative(self):
        """亏损扩大: -10 -> -20 = -50% 恶化"""
        assert pct_change(-20, -10) == -100.0


# ==================== 工具函数: fmt_num ====================

class TestFmtNum:
    def test_trillion(self):
        assert fmt_num(1.5e12) == "$1.50T"

    def test_billion(self):
        assert fmt_num(2.5e9) == "$2.50B"

    def test_million(self):
        assert fmt_num(3.5e6) == "$3.50M"

    def test_small_currency(self):
        assert fmt_num(42.5) == "$42.50"

    def test_none(self):
        assert fmt_num(None) == "N/A"

    def test_negative_billion(self):
        assert fmt_num(-2.5e9) == "$-2.50B"

    def test_non_currency(self):
        assert fmt_num(2.5e9, is_currency=False) == "2.50B"

    def test_non_currency_trillion(self):
        assert fmt_num(1.5e12, is_currency=False) == "1.50T"

    def test_zero(self):
        assert fmt_num(0) == "$0.00"


# ==================== analyze_investment_signal 规则引擎 ====================

class TestAnalyzeInvestmentSignal:
    def test_revenue_strong_growth_bullish(self):
        """营收 +25% → 营收大幅增长"""
        b, r = analyze_investment_signal({"revenue": 125}, {"revenue": 100})
        assert any("营收大幅增长" in x for x in b)
        assert r == []

    def test_revenue_modest_growth_bullish(self):
        """营收 +5% → 营收稳健增长"""
        b, _ = analyze_investment_signal({"revenue": 105}, {"revenue": 100})
        assert any("营收稳健增长" in x for x in b)

    def test_revenue_slight_decline_bearish(self):
        """营收 -5% → 营收小幅下降"""
        _, r = analyze_investment_signal({"revenue": 95}, {"revenue": 100})
        assert any("营收小幅下降" in x for x in r)

    def test_revenue_steep_decline_bearish(self):
        """营收 -20% → 营收大幅下滑"""
        _, r = analyze_investment_signal({"revenue": 80}, {"revenue": 100})
        assert any("营收大幅下滑" in x for x in r)

    def test_net_income_strong_growth_bullish(self):
        """净利润 +25% → 大幅增长"""
        b, _ = analyze_investment_signal({"net_income": 125}, {"net_income": 100})
        assert any("净利润大幅增长" in x for x in b)

    def test_net_income_modest_growth_bullish(self):
        """净利润 +10% → 净利润增长"""
        b, _ = analyze_investment_signal({"net_income": 110}, {"net_income": 100})
        assert any("净利润增长" in x for x in b)
        assert not any("大幅增长" in x for x in b)

    def test_net_income_decline_bearish(self):
        """净利润 -10% → 净利润下降"""
        _, r = analyze_investment_signal({"net_income": 90}, {"net_income": 100})
        assert any("净利润下降" in x for x in r)

    def test_net_income_steep_decline_bearish(self):
        """净利润 -25% → 大幅下降"""
        _, r = analyze_investment_signal({"net_income": 75}, {"net_income": 100})
        assert any("净利润大幅下降" in x for x in r)

    def test_net_income_turnaround_to_profit_bullish(self):
        """净利润扭亏为盈: prev<0, curr>=0"""
        b, _ = analyze_investment_signal({"net_income": 10}, {"net_income": -5})
        assert any("扭亏为盈" in x for x in b)

    def test_net_income_turnaround_to_loss_bearish(self):
        """净利润由盈转亏: prev>=0, curr<0"""
        _, r = analyze_investment_signal({"net_income": -10}, {"net_income": 5})
        assert any("由盈转亏" in x for x in r)

    def test_gross_margin_significant_improvement_bullish(self):
        """毛利率 +5pp → 显著提升"""
        b, _ = analyze_investment_signal(
            {"gross_margin": 45}, {"gross_margin": 40}
        )
        assert any("毛利率显著提升" in x for x in b)

    def test_gross_margin_slight_improvement_bullish(self):
        """毛利率 +1pp → 改善"""
        b, _ = analyze_investment_signal(
            {"gross_margin": 41}, {"gross_margin": 40}
        )
        assert any("毛利率改善" in x for x in b)
        assert not any("显著提升" in x for x in b)

    def test_gross_margin_significant_decline_bearish(self):
        """毛利率 -5pp → 大幅下降"""
        _, r = analyze_investment_signal(
            {"gross_margin": 35}, {"gross_margin": 40}
        )
        assert any("毛利率大幅下降" in x for x in r)

    def test_gross_margin_high_absolute_bullish(self):
        """毛利率 >60% → 高毛利率"""
        b, _ = analyze_investment_signal({"gross_margin": 75}, {})
        assert any("高毛利率" in x for x in b)

    def test_gross_margin_low_absolute_bearish(self):
        """毛利率 <20% → 低毛利率"""
        _, r = analyze_investment_signal({"gross_margin": 15}, {})
        assert any("低毛利率" in x for x in r)

    def test_gross_margin_midrange_no_absolute_signal(self):
        """毛利率 20-60% → 不触发绝对值信号"""
        b, r = analyze_investment_signal({"gross_margin": 40}, {})
        assert not any("高毛利率" in x for x in b)
        assert not any("低毛利率" in x for x in r)

    def test_cash_rich_bullish(self):
        """现金 >10B → 现金充裕"""
        b, _ = analyze_investment_signal({"cash": 20e9}, {})
        assert any("现金充裕" in x for x in b)

    def test_cash_low_bearish(self):
        """现金 <1B → 现金紧张"""
        _, r = analyze_investment_signal({"cash": 0.5e9}, {})
        assert any("现金紧张" in x for x in r)

    def test_cash_midrange_no_signal(self):
        """现金 1B-10B → 不触发"""
        b, r = analyze_investment_signal({"cash": 5e9}, {})
        assert not any("现金" in x for x in b)
        assert not any("现金" in x for x in r)

    def test_eps_growth_bullish(self):
        """EPS +25% → EPS增长"""
        b, _ = analyze_investment_signal({"eps": 1.5}, {"eps": 1.2})
        assert any("EPS增长" in x for x in b)

    def test_eps_decline_bearish(self):
        """EPS -25% → EPS下降"""
        _, r = analyze_investment_signal({"eps": 0.9}, {"eps": 1.2})
        assert any("EPS下降" in x for x in r)

    def test_eps_small_change_no_signal(self):
        """EPS +5% → 不触发 (阈值 10%)"""
        b, r = analyze_investment_signal({"eps": 1.05}, {"eps": 1.0})
        assert not any("EPS" in x for x in b)
        assert not any("EPS" in x for x in r)

    def test_rd_increase_bullish(self):
        """研发 +25% → 大幅增加"""
        b, _ = analyze_investment_signal({"rd_expense": 125}, {"rd_expense": 100})
        assert any("研发投入大幅增加" in x for x in b)

    def test_rd_cut_bearish(self):
        """研发 -25% → 大幅削减"""
        _, r = analyze_investment_signal({"rd_expense": 75}, {"rd_expense": 100})
        assert any("研发投入大幅削减" in x for x in r)

    def test_rd_small_change_no_signal(self):
        """研发 +10% → 不触发 (阈值 15%)"""
        b, r = analyze_investment_signal({"rd_expense": 110}, {"rd_expense": 100})
        assert not any("研发" in x for x in b)
        assert not any("研发" in x for x in r)

    def test_empty_dicts_returns_empty_lists(self):
        """空数据 → 空列表"""
        b, r = analyze_investment_signal({}, {})
        assert b == [] and r == []

    def test_none_values_skipped(self):
        """None 值的字段被跳过, 不抛异常"""
        b, r = analyze_investment_signal(
            {"revenue": None, "net_income": None}, {"revenue": 100, "net_income": 50}
        )
        assert b == [] and r == []

    def test_mixed_signals_revenue_up_margin_down(self):
        """营收增长但毛利率下降 → 同时有利好和利空"""
        b, r = analyze_investment_signal(
            {"revenue": 115, "gross_margin": 30},
            {"revenue": 100, "gross_margin": 40},
        )
        assert any("营收大幅增长" in x for x in b)
        assert any("毛利率大幅下降" in x for x in r)

    def test_task_example_returns_tuple_of_two_lists(self):
        """任务示例: 7 项指标对比, 返回 (list, list)"""
        curr = {"revenue": 100, "net_income": 20, "gross_profit": 40,
                "gross_margin": 40, "cash": 15, "eps": 1.5, "rd_expense": 5}
        prev = {"revenue": 80, "net_income": 15, "gross_profit": 35,
                "gross_margin": 35, "cash": 12, "eps": 1.2, "rd_expense": 4}
        result = analyze_investment_signal(curr, prev)
        assert isinstance(result, tuple)
        assert len(result) == 2
        bullish, bearish = result
        assert isinstance(bullish, list) and isinstance(bearish, list)
        # 营收 +25%, 净利润 +33%, 毛利率 +5pp, EPS +25%, 研发 +25% → 5 条利好
        assert len(bullish) == 5
        # cash=15 < 1B → 现金紧张
        assert len(bearish) == 1
        assert "现金紧张" in bearish[0]


# ==================== get_investment_summary 7 档分级 ====================

class TestGetInvestmentSummary:
    def test_strong_bullish(self):
        """b>=3 且 r<=1 → 🟢 强烈利好"""
        sig, _ = get_investment_summary(["a", "b", "c"], ["x"])
        assert "强烈利好" in sig

    def test_strong_bullish_zero_bearish(self):
        sig, _ = get_investment_summary(["a", "b", "c", "d"], [])
        assert "强烈利好" in sig

    def test_bullish(self):
        """b>=2 且 r==0 → 🟢 利好"""
        sig, _ = get_investment_summary(["a", "b"], [])
        assert sig.startswith("🟢 利好")

    def test_lean_bullish(self):
        """b>r (且不满足强烈利好/利好) → 🟡 偏利好"""
        sig, _ = get_investment_summary(["a", "b"], ["x"])
        assert "偏利好" in sig

    def test_strong_bearish(self):
        """r>=3 且 b<=1 → 🔴 强烈利空"""
        sig, _ = get_investment_summary(["a"], ["x", "y", "z"])
        assert "强烈利空" in sig

    def test_bearish(self):
        """r>=2 且 b==0 → 🔴 利空"""
        sig, _ = get_investment_summary([], ["x", "y"])
        assert sig.startswith("🔴 利空")

    def test_lean_bearish(self):
        """r>b (且不满足强烈利空/利空) → 🟡 偏利空"""
        sig, _ = get_investment_summary(["a"], ["x", "y"])
        assert "偏利空" in sig

    def test_neutral_equal(self):
        """b==r → ⚪ 中性"""
        sig, _ = get_investment_summary(["a"], ["x"])
        assert "中性" in sig

    def test_neutral_both_empty(self):
        """b==r==0 → ⚪ 中性"""
        sig, _ = get_investment_summary([], [])
        assert "中性" in sig

    def test_seven_tiers_distinct(self):
        """7 档分级标签互不相同"""
        tiers = set()
        tiers.add(get_investment_summary(["a", "b", "c"], ["x"])[0])
        tiers.add(get_investment_summary(["a", "b"], [])[0])
        tiers.add(get_investment_summary(["a", "b"], ["x"])[0])
        tiers.add(get_investment_summary(["a"], ["x", "y", "z"])[0])
        tiers.add(get_investment_summary([], ["x", "y"])[0])
        tiers.add(get_investment_summary(["a"], ["x", "y"])[0])
        tiers.add(get_investment_summary(["a"], ["x"])[0])
        assert len(tiers) == 7

    def test_returns_description_string(self):
        """第二返回值为非空描述"""
        _, desc = get_investment_summary(["a", "b", "c"], [])
        assert isinstance(desc, str) and desc


# ==================== 缓存命中/未命中 ====================

class TestCache:
    def test_cache_miss_no_file(self):
        """无缓存文件 → None"""
        assert _read_cache("9999999") is None

    def test_cache_write_then_read(self):
        """写缓存后能读到"""
        cik = "0001234"
        data = {"entityName": "Test", "facts": {}}
        _write_cache(cik, data)
        assert _read_cache(cik) == data

    def test_cache_expired_returns_none(self):
        """TTL 过期 → None"""
        cik = "0001234"
        p = sec_fetcher.CACHE_DIR / f"{cik}.json"
        p.write_text(json.dumps({"x": 1}))
        # 把 mtime 设到 10 小时前
        old = time.time() - 10 * 3600
        os.utime(p, (old, old))
        assert _read_cache(cik, ttl=6 * 3600) is None

    def test_cache_within_ttl_returns_data(self):
        """TTL 内 → 命中"""
        cik = "0001234"
        p = sec_fetcher.CACHE_DIR / f"{cik}.json"
        p.write_text(json.dumps({"x": 1}))
        # 1 小时前
        old = time.time() - 3600
        os.utime(p, (old, old))
        assert _read_cache(cik, ttl=6 * 3600) == {"x": 1}

    def test_cache_corrupt_json_returns_none(self):
        """损坏的 JSON → None, 不抛异常"""
        cik = "0001234"
        p = sec_fetcher.CACHE_DIR / f"{cik}.json"
        p.write_text("not valid json {")
        assert _read_cache(cik) is None

    def test_cache_key_is_cik_filename(self):
        """缓存文件名为 {cik}.json"""
        from data_sources.sec_fetcher import _cache_path
        cik = "0001318605"
        p = _cache_path(cik)
        assert p.name == "0001318605.json"
        assert p.parent == sec_fetcher.CACHE_DIR

    def test_fetch_uses_cache_no_http(self, monkeypatch):
        """缓存命中时不调用 HTTP"""
        cik = "0001234"
        _write_cache(cik, {"entityName": "Cached"})
        mock_session = _mock_session_with([])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        result = fetch_xbrl_data(cik)
        assert result == {"entityName": "Cached"}
        mock_session.get.assert_not_called()

    def test_fetch_writes_cache_on_success(self, monkeypatch):
        """HTTP 200 后写入缓存"""
        cik = "0001234"
        mock_session = _mock_session_with(
            [_make_response(200, {"entityName": "Live"})]
        )
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        result = fetch_xbrl_data(cik)
        assert result == {"entityName": "Live"}
        # 缓存已写入
        assert _read_cache(cik) == {"entityName": "Live"}


# ==================== HTTP 重试 + User-Agent ====================

class TestHttpRetry:
    def test_user_agent_format_compliant(self):
        """User-Agent 含项目名 + 真实邮箱 (SEC 政策要求)"""
        assert "investment-os" in USER_AGENT
        assert "@" in USER_AGENT
        assert USER_AGENT == "investment-os <luochan1028@126.com>"

    def test_session_sets_user_agent_header(self):
        """session.headers 含合规 User-Agent"""
        session = _build_session()
        assert session.headers["User-Agent"] == USER_AGENT

    def test_retry_configured_on_adapter(self):
        """https adapter 配置了 urllib3 Retry: 3 次 + 429/500/502/503/504"""
        session = _build_session()
        adapter = session.get_adapter("https://data.sec.gov")
        retry = adapter.max_retries
        assert retry.total == 3
        assert retry.backoff_factor >= 0.5
        for code in (429, 500, 502, 503, 504):
            assert code in retry.status_forcelist

    def test_http_500_returns_none(self, monkeypatch):
        """HTTP 500 → 重试耗尽后返回 None (优雅失败)

        500 为可重试状态码, fetch_xbrl_data 会重试 HTTP_MAX_RETRIES 次,
        故需提供 3 个 500 响应避免 StopIteration。
        """
        mock_session = _mock_session_with([
            _make_response(500),
            _make_response(500),
            _make_response(500),
        ])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        assert fetch_xbrl_data("0001234") is None
        assert mock_session.get.call_count == 3

    def test_http_404_returns_none(self, monkeypatch):
        """HTTP 404 (non-retryable) → 返回 None, 不重试"""
        mock_session = _mock_session_with([_make_response(404)])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        assert fetch_xbrl_data("0001234") is None
        assert mock_session.get.call_count == 1

    def test_http_200_returns_data(self, monkeypatch):
        """HTTP 200 → 返回 dict"""
        mock_session = _mock_session_with(
            [_make_response(200, {"entityName": "OK"})]
        )
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        assert fetch_xbrl_data("0001234") == {"entityName": "OK"}

    def test_retry_first_500_then_200(self, monkeypatch):
        """第一次 500 第二次 200: 应用层重试后返回 200 数据。

        urllib3 Retry 处理连接级重试; 应用层 for-loop 处理 HTTP 状态码重试,
        保证 mock 层面可测试。
        """
        mock_session = _mock_session_with([
            _make_response(500),
            _make_response(200, {"entityName": "Retried"}),
        ])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)

        result = fetch_xbrl_data("0001234")
        assert result == {"entityName": "Retried"}
        # 第一次 500 触发重试, 第二次 200 成功
        assert mock_session.get.call_count == 2

    def test_retry_exhausted_returns_none(self, monkeypatch):
        """连续 3 次 500 → 重试耗尽返回 None"""
        mock_session = _mock_session_with([
            _make_response(500),
            _make_response(500),
            _make_response(500),
        ])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        assert fetch_xbrl_data("0001234") is None
        assert mock_session.get.call_count == 3

    def test_request_exception_retried_then_returns_none(self, monkeypatch):
        """RequestException 触发重试, 全失败返回 None"""
        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": USER_AGENT}
        mock_session.get.side_effect = requests.RequestException("network down")
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        assert fetch_xbrl_data("0001234") is None
        assert mock_session.get.call_count == 3

    def test_request_exception_then_success(self, monkeypatch):
        """第一次 RequestException 第二次 200 → 重试成功"""
        mock_session = MagicMock()
        mock_session.headers = {"User-Agent": USER_AGENT}
        mock_session.get.side_effect = [
            requests.RequestException("transient"),
            _make_response(200, {"ok": True}),
        ]
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        assert fetch_xbrl_data("0001234") == {"ok": True}
        assert mock_session.get.call_count == 2

    def test_user_agent_sent_via_session_headers(self, monkeypatch):
        """session.get 调用时 User-Agent 通过 session.headers 携带"""
        mock_session = _mock_session_with([_make_response(200, {"ok": True})])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        fetch_xbrl_data("0001234")
        mock_session.get.assert_called_once()
        # User-Agent 在 session.headers 上 (requests 会自动随请求发送)
        assert mock_session.headers["User-Agent"] == USER_AGENT

    def test_get_latest_filing_date_handles_404(self, monkeypatch):
        """get_latest_filing_date HTTP 404 → (None, {10-K:None, 10-Q:None})"""
        mock_session = _mock_session_with([_make_response(404)])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        latest, details = get_latest_filing_date("0001234")
        assert latest is None
        assert details == {"10-K": None, "10-Q": None}

    def test_get_latest_filing_date_parses_submissions(self, monkeypatch):
        """get_latest_filing_date 正确解析 submissions JSON"""
        payload = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K", "10-Q"],
                    "filingDate": ["2025-12-31", "2025-09-30", "2025-11-15", "2025-06-30"],
                }
            }
        }
        mock_session = _mock_session_with([_make_response(200, payload)])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        latest, details = get_latest_filing_date("0001318605")
        assert latest == "2025-12-31"  # 10-K > 10-Q
        assert details["10-K"] == "2025-12-31"
        assert details["10-Q"] == "2025-09-30"

    def test_get_latest_filing_date_handles_20f_as_10k(self, monkeypatch):
        """20-F (外资公司年报) 视作 10-K 通道"""
        payload = {
            "filings": {
                "recent": {
                    "form": ["20-F", "10-Q"],
                    "filingDate": ["2025-04-30", "2025-09-30"],
                }
            }
        }
        mock_session = _mock_session_with([_make_response(200, payload)])
        monkeypatch.setattr(sec_fetcher, "_get_session", lambda: mock_session)
        latest, details = get_latest_filing_date("0001158449")
        assert details["10-K"] == "2025-04-30"
        assert latest == "2025-09-30"  # 10-Q 更晚


# ==================== get_all_metrics 指标提取 ====================

class TestGetAllMetrics:
    def test_none_date_returns_all_none(self):
        """target_end_date=None → 全 None 指标 (含 gross_margin)"""
        m = get_all_metrics({}, None, ["10-K"])
        assert m["revenue"] is None
        assert m["net_income"] is None
        assert m["gross_margin"] is None
        assert m["eps"] is None
        # 9 项
        assert len(m) == 9

    def test_derives_gross_margin(self):
        """有 gross_profit + revenue → 派生 gross_margin"""
        xbrl = {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [
                        {"end": "2024-12-31", "form": "10-K", "val": 100000},
                    ]}},
                    "GrossProfit": {"units": {"USD": [
                        {"end": "2024-12-31", "form": "10-K", "val": 40000},
                    ]}},
                }
            }
        }
        m = get_all_metrics(xbrl, "2024-12-31", ["10-K"])
        assert m["revenue"] == 100000.0
        assert m["gross_profit"] == 40000.0
        assert m["gross_margin"] == 40.0

    def test_skips_zero_values(self):
        """val=0 的条目被跳过 (原始逻辑保留)"""
        xbrl = {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [
                        {"end": "2024-12-31", "form": "10-K", "val": 0},
                        {"end": "2023-12-31", "form": "10-K", "val": 50000},
                    ]}},
                }
            }
        }
        m = get_all_metrics(xbrl, "2024-12-31", ["10-K"])
        assert m["revenue"] is None  # val=0 被跳过


# ==================== analyze_company 集成 (mock fetch_xbrl_data) ====================

class TestAnalyzeCompany:
    def test_returns_none_when_fetch_fails(self, monkeypatch):
        """fetch_xbrl_data 返回 None → analyze_company 返回 None"""
        monkeypatch.setattr(sec_analyzer, "fetch_xbrl_data", lambda cik: None)
        assert analyze_company("Test", "0001234") is None

    def test_returns_none_when_no_report_dates(self, monkeypatch):
        """XBRL 无可用报告日期 → None"""
        monkeypatch.setattr(
            sec_analyzer, "fetch_xbrl_data",
            lambda cik: {"facts": {}}
        )
        assert analyze_company("Test", "0001234") is None

    def test_full_pipeline_returns_expected_shape(self, monkeypatch):
        """完整流水线: 返回 dict 含 name/cik/form/signal 等字段"""
        xbrl = {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [
                        {"end": "2024-12-31", "form": "10-K", "val": 110000},
                        {"end": "2023-12-31", "form": "10-K", "val": 100000},
                    ]}},
                    "NetIncomeLoss": {"units": {"USD": [
                        {"end": "2024-12-31", "form": "10-K", "val": 20000},
                        {"end": "2023-12-31", "form": "10-K", "val": 15000},
                    ]}},
                    "GrossProfit": {"units": {"USD": [
                        {"end": "2024-12-31", "form": "10-K", "val": 50000},
                        {"end": "2023-12-31", "form": "10-K", "val": 45000},
                    ]}},
                }
            }
        }
        monkeypatch.setattr(sec_analyzer, "fetch_xbrl_data", lambda cik: xbrl)
        result = analyze_company("TestCo", "0001234")
        assert result is not None
        assert result["name"] == "TestCo"
        assert result["cik"] == "0001234"
        assert result["report_form"] == "10-K"
        assert result["form"] == "年报"
        assert result["current_date"] == "2024-12-31"
        assert result["previous_date"] == "2023-12-31"
        assert isinstance(result["bullish"], list)
        assert isinstance(result["bearish"], list)
        assert "signal" in result and "signal_desc" in result
        assert result["current"]["revenue"] == 110000.0
        # 营收 +10% 边界 (大于 10 触发大幅增长), 净利润 +33%, 毛利率 ~45.45% - 45% = 0.45pp
        assert len(result["bullish"]) >= 1


# ==================== 模块常量 ====================

class TestModuleConstants:
    def test_companies_count_is_12(self):
        """12 家科技巨头"""
        assert len(COMPANIES) == 12

    def test_companies_entries_are_3_tuples(self):
        """每条 (name, ticker, cik) 三元组"""
        for entry in COMPANIES:
            assert len(entry) == 3
            name, ticker, cik = entry
            assert isinstance(name, str) and name
            assert isinstance(ticker, str) and ticker
            # CIK 应为 10 位数字字符串 (允许前导 0)
            assert isinstance(cik, str) and cik.isdigit() and len(cik) == 10

    def test_metrics_contains_8_original_keys(self):
        """8 项原始指标 (毛利率为派生项, 不在 METRICS 中)"""
        expected = {"revenue", "net_income", "gross_profit", "rd_expense",
                    "cash", "total_assets", "equity", "eps"}
        assert set(METRICS.keys()) == expected

    def test_cache_dir_is_absolute_under_project(self):
        """CACHE_DIR 是项目 data/sec_cache 子目录"""
        assert CACHE_DIR.is_absolute()
        assert "sec_cache" in str(CACHE_DIR)
        assert CACHE_DIR.name == "sec_cache"

    def test_facade_reexports_all_public_api(self):
        """sec_filings facade 应 re-export 全部公共 API"""
        for name in [
            "analyze_company", "analyze_investment_signal", "get_investment_summary",
            "pct_change", "fmt_num", "fetch_xbrl_data", "get_latest_filing_date",
            "get_all_metrics", "USER_AGENT", "COMPANIES", "METRICS", "CACHE_DIR",
        ]:
            assert hasattr(sec_filings, name), f"sec_filings 缺失 {name}"
