"""舆情推送 + 财报详情推送 测试

验证：
- store.get_filing_by_symbol 按 symbol 返回详情
- /api/filings/{symbol} 返回完整字段
- /api/filings/{symbol}/push 端点：信号级别判定、Markdown 构造、调用 push_alert
- /api/sentiment/push-high 端点：未配置 Token 时返回 errors
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from store import get_filing_by_symbol, save_filing, init_db, get_connection
from shared.pusher import PushLevel


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    # 准备测试财报数据（含完整字段）
    save_filing(
        symbol="TESTF",
        company="Test Company",
        filing_type="10-Q",
        filing_date="2026-07-25",
        period="2026 Q2",
        signal="🟢 利好",
        summary="营收超预期 30%",
        revenue=1.23e9,
        net_income=4.56e7,
        gross_margin=0.456,
        bullish=["营收超预期", "AI 业务增长"],
        bearish=["成本上升"],
        fetched_at="2026-07-25 10:00:00",
    )
    yield


# ==================== store 层 ====================

class TestGetFilingBySymbol:
    """store.get_filing_by_symbol 单元测试"""

    def test_returns_filing_when_exists(self):
        f = get_filing_by_symbol("TESTF")
        assert f is not None
        assert f["symbol"] == "TESTF"
        assert f["company"] == "Test Company"

    def test_returns_none_when_not_exists(self):
        f = get_filing_by_symbol("NOTEXIST")
        assert f is None

    def test_decodes_bullish_bearish_lists(self):
        """JSON 字符串应被反序列化为 list"""
        f = get_filing_by_symbol("TESTF")
        assert isinstance(f["bullish"], list)
        assert isinstance(f["bearish"], list)
        assert "营收超预期" in f["bullish"]
        assert "成本上升" in f["bearish"]

    def test_includes_financial_metrics(self):
        f = get_filing_by_symbol("TESTF")
        assert f["revenue"] == 1.23e9
        assert f["net_income"] == 4.56e7
        assert f["gross_margin"] == pytest.approx(0.456)


# ==================== API 层 ====================

@pytest.fixture(scope="module")
def client():
    from server import app
    return TestClient(app)


class TestFilingDetailAPI:
    """/api/filings/{symbol}"""

    def test_returns_full_filing(self, client):
        r = client.get("/api/filings/TESTF")
        assert r.status_code == 200
        f = r.json()["filing"]
        assert f["symbol"] == "TESTF"
        assert f["revenue"] == 1.23e9
        assert "营收超预期" in f["bullish"]

    def test_returns_404_when_not_found(self, client):
        r = client.get("/api/filings/NOTEXIST")
        assert r.status_code == 404

    def test_symbol_case_insensitive(self, client):
        """symbol 应转大写后查询"""
        r = client.get("/api/filings/testf")
        assert r.status_code == 200


class TestFilingPushAPI:
    """/api/filings/{symbol}/push"""

    def test_bullish_signal_maps_to_high_level(self, client):
        """信号含'利好' → HIGH 级别"""
        with patch("server.push_alert") as mock_push:
            mock_push.return_value = True
            r = client.post("/api/filings/TESTF/push")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed"] is True
            assert d["level"] == "high"
            assert "🟢" in d["title"]
            # 验证 push_alert 调用参数
            mock_push.assert_called_once()
            call = mock_push.call_args
            assert call.kwargs["level"] == PushLevel.HIGH
            assert call.kwargs["symbol"] == "TESTF"
            assert call.kwargs["alert_type"] == "filing"

    def test_bearish_signal_maps_to_high_level(self, client):
        """信号含'利空' → HIGH 级别"""
        save_filing(
            symbol="BEARF",
            company="Bear Co",
            filing_type="10-Q",
            filing_date="2026-07-25",
            period="2026 Q2",
            signal="🔴 利空",
            summary="营收不及预期",
        )
        with patch("server.push_alert") as mock_push:
            mock_push.return_value = True
            r = client.post("/api/filings/BEARF/push")
            assert r.status_code == 200
            d = r.json()
            assert d["level"] == "high"
            assert "🔴" in d["title"]

    def test_neutral_signal_maps_to_medium_level(self, client):
        """中性信号 → MEDIUM 级别"""
        save_filing(
            symbol="NEUTF",
            company="Neutral Co",
            filing_type="10-Q",
            filing_date="2026-07-25",
            period="2026 Q2",
            signal="⚪ 中性",
            summary="符合预期",
        )
        with patch("server.push_alert") as mock_push:
            mock_push.return_value = True
            r = client.post("/api/filings/NEUTF/push")
            assert r.status_code == 200
            assert r.json()["level"] == "medium"

    def test_push_content_includes_revenue_and_signals(self, client):
        """推送内容应包含营收、净利、毛利率、利好/利空因素"""
        with patch("server.push_alert") as mock_push:
            mock_push.return_value = True
            client.post("/api/filings/TESTF/push")
            content = mock_push.call_args.kwargs["content"]
            assert "1.23 B" in content  # revenue
            assert "45.60%" in content or "45.6%" in content  # gross_margin
            assert "营收超预期" in content  # bullish
            assert "成本上升" in content  # bearish

    def test_returns_404_when_filing_not_found(self, client):
        r = client.post("/api/filings/NOTEXIST/push")
        assert r.status_code == 404

    def test_push_failure_returns_pushed_false(self, client):
        """push_alert 返回 False 时，pushed 应为 False"""
        with patch("server.push_alert") as mock_push:
            mock_push.return_value = False
            r = client.post("/api/filings/TESTF/push")
            assert r.status_code == 200
            assert r.json()["pushed"] is False


class TestSentimentPushHighAPI:
    """/api/sentiment/push-high"""

    def test_returns_errors_when_no_token_configured(self, client):
        """未配置 PUSHPLUS_TOKEN 时应返回 errors"""
        with patch("shared.pusher.get_default_config") as mock_cfg:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(push_type="pushplus", pushplus_token="")
            r = client.post("/api/sentiment/push-high")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed_count"] == 0
            assert any("PUSHPLUS_TOKEN" in e for e in d["errors"])

    def test_returns_zero_when_no_real_tweets(self, client):
        """x-monitor-push 未部署时返回 0"""
        with patch("shared.pusher.get_default_config") as mock_cfg, \
             patch("shared.pusher.push_alert") as mock_push, \
             patch("shared.sentiment_adapter.fetch_real_tweets") as mock_fetch:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(pushplus_token="dummy_token")
            mock_fetch.return_value = {"count": 0, "tweets": [], "source": "none"}
            r = client.post("/api/sentiment/push-high")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed_count"] == 0
            mock_push.assert_not_called()

    def test_pushes_high_level_tweets(self, client):
        """有 high 级别舆情时调用 push_alert"""
        with patch("shared.pusher.get_default_config") as mock_cfg, \
             patch("shared.pusher.push_alert") as mock_push, \
             patch("shared.sentiment_adapter.fetch_real_tweets") as mock_fetch, \
             patch("shared.sentiment_adapter._find_x_monitor_db", return_value=None):
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(pushplus_token="dummy_token")
            mock_fetch.return_value = {
                "count": 2,
                "tweets": [
                    {"username": "user1", "title": "Important news",
                     "impact_level": "high", "pushed": 0,
                     "category": "美联储", "summary": "Fed cuts rates"},
                    {"username": "user2", "title": "Less important",
                     "impact_level": "medium", "pushed": 0,
                     "category": "其他"},
                ],
                "source": "x-monitor-push",
            }
            mock_push.return_value = True
            r = client.post("/api/sentiment/push-high")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed_count"] == 1
            assert d["total_high"] == 1
            # 仅 high 级别被推送
            mock_push.assert_called_once()
            call = mock_push.call_args
            assert call.kwargs["level"] == PushLevel.HIGH
            assert "user1" in call.kwargs["title"]

    def test_skips_already_pushed_tweets(self, client):
        """pushed=1 的舆情不重复推送"""
        with patch("shared.pusher.get_default_config") as mock_cfg, \
             patch("shared.pusher.push_alert") as mock_push, \
             patch("shared.sentiment_adapter.fetch_real_tweets") as mock_fetch:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(pushplus_token="dummy_token")
            mock_fetch.return_value = {
                "count": 1,
                "tweets": [
                    {"username": "user1", "title": "Already pushed",
                     "impact_level": "high", "pushed": 1,  # 已推送
                     "category": "美联储"},
                ],
                "source": "x-monitor-push",
            }
            r = client.post("/api/sentiment/push-high")
            assert r.status_code == 200
            assert r.json()["pushed_count"] == 0
            mock_push.assert_not_called()


# ==================== 财报自动推送 ====================

class TestFilingsAutoPush:
    """/api/filings/auto-push 端点测试"""

    def test_returns_errors_when_no_token_configured(self, client):
        """未配置推送通道时返回 errors"""
        with patch("server.get_default_config") as mock_cfg:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(push_type="pushplus", pushplus_token="")
            r = client.post("/api/filings/auto-push")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed_count"] == 0
            assert "errors" in d

    def test_no_unpushed_filings(self, client):
        """所有财报已推送时返回 0"""
        # 先标记所有财报为已推送
        from store import mark_filing_pushed, get_unpushed_filings
        for f in get_unpushed_filings(limit=50):
            mark_filing_pushed(f["symbol"])

        with patch("server.get_default_config") as mock_cfg, \
             patch("server.push_alert") as mock_push, \
             patch("data_sources.sec_filings.analyze_company") as mock_analyze:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(push_type="wxpusher", wxpusher_token="dummy", wxpusher_uid="UID_dummy")
            mock_analyze.return_value = None  # SEC 无新数据
            r = client.post("/api/filings/auto-push")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed_count"] == 0
            assert d["total_unpushed"] == 0
            mock_push.assert_not_called()

    def test_auto_pushes_unpushed_filings(self, client):
        """有未推送财报时自动推送到微信"""
        from store import get_connection
        # 重置一条财报为未推送状态
        conn = get_connection()
        conn.execute("UPDATE filings SET pushed = 0 WHERE symbol = 'TESTF'")
        conn.commit()
        conn.close()

        with patch("server.get_default_config") as mock_cfg, \
             patch("server.push_alert") as mock_push, \
             patch("data_sources.sec_filings.analyze_company") as mock_analyze:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(push_type="wxpusher", wxpusher_token="dummy", wxpusher_uid="UID_dummy")
            mock_analyze.return_value = None  # 跳过 SEC 抓取
            mock_push.return_value = True

            r = client.post("/api/filings/auto-push")
            assert r.status_code == 200
            d = r.json()
            assert d["pushed_count"] >= 1
            assert d["total_unpushed"] >= 1
            assert mock_push.call_count >= 1

    def test_pushed_filings_not_re_pushed(self, client):
        """已推送的财报不重复推送"""
        from store import get_connection, mark_filing_pushed
        # 确保 TESTF 已推送
        mark_filing_pushed("TESTF")

        with patch("server.get_default_config") as mock_cfg, \
             patch("server.push_alert") as mock_push, \
             patch("data_sources.sec_filings.analyze_company") as mock_analyze:
            from shared.pusher import PushConfig
            mock_cfg.return_value = PushConfig(wxpusher_token="dummy", wxpusher_uid="UID_dummy")
            mock_analyze.return_value = None

            # 获取未推送列表（应不含 TESTF）
            from store import get_unpushed_filings
            unpushed = get_unpushed_filings(limit=20)
            symbols = [f["symbol"] for f in unpushed]
            assert "TESTF" not in symbols


class TestUnpushedFilingsAPI:
    """/api/filings/unpushed 端点测试"""

    def test_returns_unpushed_list(self, client):
        """返回未推送财报列表"""
        r = client.get("/api/filings/unpushed")
        assert r.status_code == 200
        d = r.json()
        assert "filings" in d
        assert "count" in d
        assert isinstance(d["filings"], list)

    def test_store_get_unpushed_filings(self):
        """store 层 get_unpushed_filings 正常工作"""
        from store import get_unpushed_filings, save_filing, mark_filing_pushed
        # 插入一条未推送财报
        save_filing(
            symbol="UNPU1",
            company="Unpushed Co",
            filing_type="10-Q",
            filing_date="2026-07-25",
            period="2026 Q2",
            signal="🟢 利好",
            summary="test",
            pushed=0,
        )
        result = get_unpushed_filings(limit=50)
        symbols = [f["symbol"] for f in result]
        assert "UNPU1" in symbols

        # 推送后不在列表中
        mark_filing_pushed("UNPU1")
        result = get_unpushed_filings(limit=50)
        symbols = [f["symbol"] for f in result]
        assert "UNPU1" not in symbols
