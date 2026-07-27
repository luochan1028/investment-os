"""每日报告 API 测试"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_daily_report_cache():
    """每个测试前清除日报缓存，避免缓存干扰"""
    import server
    server._daily_report_cache["data"] = None
    server._daily_report_cache["last_gen"] = 0
    yield


class TestDailyReportAPI:
    """每日报告 API 测试"""

    @patch("server._build_positions")
    @patch("server.api_cross_market")
    @patch("data_sources.news_fetcher.httpx.Client")
    @patch("data_sources.macro_calendar.get_macro_calendar")
    def test_returns_required_fields(self, mock_macro, mock_news_http, mock_cross, mock_positions):
        mock_positions.return_value = [
            {"symbol": "AAPL", "pnl": 500, "pnl_pct": 5.0, "cost_price": 200, "shares": 10},
            {"symbol": "TSLA", "pnl": -200, "pnl_pct": -2.0, "cost_price": 300, "shares": 5},
        ]
        mock_cross.return_value = {
            "markets": [
                {"market": "美股", "change": "+1.5%", "change_pct": 1.5, "price": 5000, "name": "标普500"},
                {"market": "A股", "change": "+0.3%", "change_pct": 0.3, "price": 3000, "name": "上证指数"},
            ]
        }
        mock_macro.return_value = {
            "events": [
                {"name": "美国CPI", "days_until": 2, "countdown": "2天 8小时", "event_datetime_bj": "2026-07-27 20:30"},
                {"name": "美联储利率决议", "days_until": 5, "countdown": "5天", "event_datetime_bj": "2026-07-30 02:00"},
            ],
            "source": "us-stock-monitor",
        }
        mock_news_http.return_value.__enter__.return_value.get.return_value.status_code = 200
        mock_news_http.return_value.__enter__.return_value.get.return_value.text = """<?xml version="1.0"?><rss><channel>
            <item><title>Test news 1</title><link>http://a.com</link><pubDate>Mon, 25 Jul 2026 10:00:00 +0000</pubDate></item>
            <item><title>Test news 2</title><link>http://b.com</link><pubDate>Mon, 25 Jul 2026 09:00:00 +0000</pubDate></item>
        </channel></rss>"""

        r = client.get("/api/daily-report")
        assert r.status_code == 200
        d = r.json()
        assert "date" in d
        assert "market_overview" in d
        assert "key_events" in d
        assert "portfolio_movement" in d
        assert "tomorrow_focus" in d
        assert "generated_at" in d
        assert "data_source" in d

    @patch("server._build_positions")
    @patch("server.api_cross_market")
    @patch("data_sources.news_fetcher.httpx.Client")
    @patch("data_sources.macro_calendar.get_macro_calendar")
    def test_portfolio_pnl_text(self, mock_macro, mock_news_http, mock_cross, mock_positions):
        mock_positions.return_value = [
            {"symbol": "AAPL", "pnl": 500, "pnl_pct": 5.0, "cost_price": 200, "shares": 10},
        ]
        mock_cross.return_value = {"markets": []}
        mock_macro.return_value = {"events": []}
        mock_news_http.return_value.__enter__.return_value.get.return_value.status_code = 404

        r = client.get("/api/daily-report")
        d = r.json()
        assert "浮盈" in d["portfolio_movement"]
        assert "¥" in d["portfolio_movement"]

    @patch("server._build_positions")
    @patch("server.api_cross_market")
    @patch("data_sources.news_fetcher.httpx.Client")
    @patch("data_sources.macro_calendar.get_macro_calendar")
    def test_empty_positions(self, mock_macro, mock_news_http, mock_cross, mock_positions):
        mock_positions.return_value = []
        mock_cross.return_value = {"markets": []}
        mock_macro.return_value = {"events": []}
        mock_news_http.return_value.__enter__.return_value.get.return_value.status_code = 404

        r = client.get("/api/daily-report")
        d = r.json()
        assert "暂无持仓" in d["portfolio_movement"]

    @patch("server._build_positions")
    @patch("server.api_cross_market")
    @patch("data_sources.news_fetcher.httpx.Client")
    @patch("data_sources.macro_calendar.get_macro_calendar")
    def test_market_overview_from_cross_market(self, mock_macro, mock_news_http, mock_cross, mock_positions):
        mock_positions.return_value = []
        mock_cross.return_value = {
            "markets": [
                {"market": "美股", "change": "+1.5%", "change_pct": 1.5, "price": 5000},
                {"market": "A股", "change": "+0.3%", "change_pct": 0.3, "price": 3000},
            ]
        }
        mock_macro.return_value = {"events": []}
        mock_news_http.return_value.__enter__.return_value.get.return_value.status_code = 404

        r = client.get("/api/daily-report")
        d = r.json()
        assert "美股" in d["market_overview"]
        assert "+1.5%" in d["market_overview"]

    @patch("server._build_positions")
    @patch("server.api_cross_market")
    @patch("data_sources.news_fetcher.httpx.Client")
    @patch("data_sources.macro_calendar.get_macro_calendar")
    def test_key_events_not_empty(self, mock_macro, mock_news_http, mock_cross, mock_positions):
        mock_positions.return_value = []
        mock_cross.return_value = {"markets": []}
        mock_macro.return_value = {"events": []}
        mock_news_http.return_value.__enter__.return_value.get.return_value.status_code = 200
        mock_news_http.return_value.__enter__.return_value.get.return_value.text = """<?xml version="1.0"?><rss><channel>
            <item><title>Breaking: Major event</title><link>http://a.com</link><pubDate>Mon, 25 Jul 2026 10:00:00 +0000</pubDate></item>
        </channel></rss>"""

        r = client.get("/api/daily-report")
        d = r.json()
        assert len(d["key_events"]) > 0

    @patch("server._build_positions")
    @patch("server.api_cross_market")
    @patch("data_sources.news_fetcher.httpx.Client")
    @patch("data_sources.macro_calendar.get_macro_calendar")
    def test_tomorrow_focus_from_macro(self, mock_macro, mock_news_http, mock_cross, mock_positions):
        mock_positions.return_value = []
        mock_cross.return_value = {"markets": []}
        mock_macro.return_value = {
            "events": [
                {"name": "美国CPI", "days_until": 2, "countdown": "2天", "event_datetime_bj": "2026-07-27 20:30"},
            ],
        }
        mock_news_http.return_value.__enter__.return_value.get.return_value.status_code = 404

        r = client.get("/api/daily-report")
        d = r.json()
        assert len(d["tomorrow_focus"]) > 0
        assert "CPI" in d["tomorrow_focus"][0]
