"""地缘政治新闻模块测试"""
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from data_sources.news_fetcher import (
    _parse_rss, _classify_news, fetch_geopolitical_news,
)


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Test News</title>
  <item>
    <title>US and China agree on trade deal to reduce tariffs</title>
    <link>http://example.com/1</link>
    <description>Major breakthrough in trade negotiations between the two countries.</description>
    <pubDate>Mon, 25 Jul 2026 10:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Fed raises interest rates to combat inflation</title>
    <link>http://example.com/2</link>
    <description>The Federal Reserve announced a 25 basis point rate hike.</description>
    <pubDate>Mon, 25 Jul 2026 09:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Local festival attracts thousands of visitors</title>
    <link>http://example.com/3</link>
    <description>A community event in a small town.</description>
    <pubDate>Mon, 25 Jul 2026 08:00:00 +0000</pubDate>
  </item>
</channel>
</rss>"""


class TestParseRss:
    """RSS 解析"""

    def test_parses_items_correctly(self):
        items = _parse_rss(SAMPLE_RSS, "TestSource")
        assert len(items) == 3

    def test_extracts_title(self):
        items = _parse_rss(SAMPLE_RSS, "TestSource")
        assert items[0]["title"] == "US and China agree on trade deal to reduce tariffs"

    def test_extracts_link(self):
        items = _parse_rss(SAMPLE_RSS, "TestSource")
        assert items[0]["link"] == "http://example.com/1"

    def test_strips_html_from_description(self):
        items = _parse_rss(SAMPLE_RSS, "TestSource")
        assert "<" not in items[0]["description"]

    def test_sets_source_name(self):
        items = _parse_rss(SAMPLE_RSS, "TestSource")
        assert items[0]["source"] == "TestSource"

    def test_handles_invalid_xml(self):
        items = _parse_rss("not valid xml", "TestSource")
        assert items == []

    def test_handles_empty_xml(self):
        items = _parse_rss("", "TestSource")
        assert items == []


class TestClassifyNews:
    """新闻分类"""

    def test_geopolitical_trade_conflict(self):
        result = _classify_news(
            "US China trade war tariffs increase",
            "New sanctions announced by both countries"
        )
        assert result["category"] == "地缘冲突"
        assert result["importance"] in ("high", "medium")
        assert "原油" in result["affected_assets"]

    def test_economic_policy(self):
        result = _classify_news(
            "Fed interest rate inflation hike",
            "Central bank monetary policy announcement"
        )
        assert result["category"] == "经济政策"
        assert "股市" in result["affected_assets"]

    def test_geopolitical_region_detection(self):
        result = _classify_news(
            "Middle East Israel Iran conflict oil",
            "Military strike in the region"
        )
        assert "中东" in result["regions"]

    def test_geopolitical_china_us(self):
        result = _classify_news(
            "US China trade deal agreement",
            "Economic cooperation between the two nations"
        )
        assert "美国" in result["regions"]
        assert "中国" in result["regions"]

    def test_default_regions_global(self):
        result = _classify_news("Global market update", "General news")
        assert "全球" in result["regions"]

    def test_other_category(self):
        result = _classify_news(
            "Local weather forecast sunny day",
            "Nice weather expected"
        )
        assert result["category"] == "其他"
        assert result["importance"] == "low"


class TestFetchGeopoliticalNews:
    """新闻抓取集成（mock 网络）"""

    @patch("data_sources.news_fetcher.httpx.Client")
    def test_fetches_from_sources(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.text = SAMPLE_RSS
        mock_client_cls.return_value.__enter__.return_value = mock_client

        news = fetch_geopolitical_news(limit=10)
        assert len(news) > 0

    @patch("data_sources.news_fetcher.httpx.Client")
    def test_deduplicates_by_title(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.text = SAMPLE_RSS
        mock_client_cls.return_value.__enter__.return_value = mock_client

        news = fetch_geopolitical_news(limit=10)
        titles = [n["title"] for n in news]
        assert len(titles) == len(set(titles))

    @patch("data_sources.news_fetcher.httpx.Client")
    def test_sorted_by_date_descending(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.text = SAMPLE_RSS
        mock_client_cls.return_value.__enter__.return_value = mock_client

        news = fetch_geopolitical_news(limit=10)
        dates = [n["pub_date"] for n in news]
        assert dates == sorted(dates, reverse=True)

    @patch("data_sources.news_fetcher.httpx.Client")
    def test_respects_limit(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.text = SAMPLE_RSS
        mock_client_cls.return_value.__enter__.return_value = mock_client

        news = fetch_geopolitical_news(limit=2)
        assert len(news) <= 2


class TestGeopoliticsAPI:
    """地缘政治 API 测试"""

    def setup_method(self):
        from server import app
        self.client = TestClient(app)

    @patch("data_sources.news_fetcher.httpx.Client")
    def test_api_returns_events(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.text = SAMPLE_RSS
        mock_client_cls.return_value.__enter__.return_value = mock_client

        r = self.client.get("/api/geopolitics")
        assert r.status_code == 200
        d = r.json()
        assert "events" in d
        assert "total" in d
        assert "data_source" in d

    @patch("data_sources.news_fetcher.httpx.Client")
    def test_api_sync_endpoint(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.text = SAMPLE_RSS
        mock_client_cls.return_value.__enter__.return_value = mock_client

        r = self.client.post("/api/geopolitics/sync")
        assert r.status_code == 200
        d = r.json()
        assert "success" in d
