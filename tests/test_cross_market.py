"""跨市场联动分析测试"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from server import app


client = TestClient(app)


def _mock_quote(symbol, price, prev_close):
    return {
        "symbol": symbol,
        "price": price,
        "prev_close": prev_close,
        "high": price * 1.01,
        "low": price * 0.99,
        "volume": 1000000,
    }


def _mock_batch(symbols, price, prev_close):
    """模拟 fetch_quotes_batch 返回值"""
    return {s.upper(): _mock_quote(s, price, prev_close) for s in symbols}


class TestCrossMarketAPI:
    """跨市场联动 API 测试"""

    @patch("server.fetch_quotes_batch")
    def test_returns_markets_list(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5000, 4950)
        r = client.get("/api/cross-market")
        assert r.status_code == 200
        d = r.json()
        assert "markets" in d
        assert len(d["markets"]) == 5

    @patch("server.fetch_quotes_batch")
    def test_markets_have_required_fields(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5000, 4950)
        d = client.get("/api/cross-market").json()
        for m in d["markets"]:
            assert "market" in m
            assert "symbol" in m
            assert "name" in m
            assert "price" in m
            assert "change" in m
            assert "status" in m
            assert "lead" in m

    @patch("server.fetch_quotes_batch")
    def test_positive_change_status_up(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5100, 5000)
        d = client.get("/api/cross-market").json()
        for m in d["markets"]:
            assert m["status"] == "上涨"
            assert m["change"].startswith("+")

    @patch("server.fetch_quotes_batch")
    def test_negative_change_status_down(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 4900, 5000)
        d = client.get("/api/cross-market").json()
        for m in d["markets"]:
            assert m["status"] == "下跌"
            assert m["change"].startswith("-")

    @patch("server.fetch_quotes_batch")
    def test_small_change_status_sideways(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5010, 5000)
        d = client.get("/api/cross-market").json()
        for m in d["markets"]:
            assert m["status"] == "震荡"

    @patch("server.fetch_quotes_batch")
    def test_us_is_leader(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5000, 4950)
        d = client.get("/api/cross-market").json()
        us = next(m for m in d["markets"] if m["market"] == "美股")
        assert us["lead"] is True

    @patch("server.fetch_quotes_batch")
    def test_analysis_generated(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5200, 5000)
        d = client.get("/api/cross-market").json()
        assert "analysis" in d
        assert len(d["analysis"]) > 10

    @patch("server.fetch_quotes_batch")
    def test_pre_market_brief_generated(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5200, 5000)
        d = client.get("/api/cross-market").json()
        assert "pre_market_brief" in d
        assert len(d["pre_market_brief"]) > 10

    @patch("server.fetch_quotes_batch")
    def test_data_source_field(self, mock_batch):
        mock_batch.side_effect = lambda syms: _mock_batch(syms, 5000, 4950)
        d = client.get("/api/cross-market").json()
        assert "data_source" in d
        assert "updated_at" in d

    @patch("server.fetch_quotes_batch")
    def test_graceful_failure_when_quote_fails(self, mock_batch):
        mock_batch.return_value = {}
        d = client.get("/api/cross-market").json()
        assert len(d["markets"]) == 5
        for m in d["markets"]:
            assert m["price"] is None
            assert m["change"] == "--"
        assert "analysis" in d
