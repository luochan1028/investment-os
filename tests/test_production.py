"""生产级优化专项测试

覆盖：缓存、重试、熔断、限流、健康检查、输入验证、配置校验
"""
import time
import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPricingCache:
    """行情缓存机制测试"""

    def setup_method(self):
        from pricing import clear_cache
        clear_cache()

    def test_quote_cache_ttl(self):
        """quote 缓存 TTL 生效"""
        from pricing import fetch_quote, _quote_cache, _quote_cache_lock, QUOTE_CACHE_TTL

        mock_data = {
            "results": [{
                "last_price": 150.0,
                "prev_close": 145.0,
                "high": 155.0,
                "low": 144.0,
                "volume": 1000000,
            }]
        }

        with patch("pricing._http_get_with_retry", return_value=mock_data):
            q1 = fetch_quote("AAPL")
            assert q1 is not None
            assert q1["price"] == 150.0

            q2 = fetch_quote("AAPL")
            assert q2 is not None
            assert q2["price"] == 150.0

            with _quote_cache_lock:
                assert "AAPL" in _quote_cache

    def test_history_cache_ttl(self):
        """history 缓存 TTL 生效"""
        from pricing import fetch_history, _history_cache, _history_cache_lock

        mock_data = {
            "results": [
                {"close": 100.0 + i} for i in range(10)
            ]
        }

        with patch("pricing._http_get_with_retry", return_value=mock_data):
            h1 = fetch_history("AAPL", 90)
            assert len(h1) == 10

            h2 = fetch_history("AAPL", 90)
            assert len(h2) == 10

            with _history_cache_lock:
                assert "AAPL:90" in _history_cache

    def test_cache_degradation_on_failure(self):
        """API 失败时降级返回缓存数据"""
        from pricing import fetch_quote, _quote_cache, _quote_cache_lock

        mock_data = {
            "results": [{
                "last_price": 150.0,
                "prev_close": 145.0,
            }]
        }

        with patch("pricing._http_get_with_retry", return_value=mock_data):
            fetch_quote("AAPL")

        with patch("pricing._http_get_with_retry", return_value=None):
            q = fetch_quote("AAPL")
            assert q is not None
            assert q["price"] == 150.0

    def test_clear_cache(self):
        """清空缓存功能正常"""
        from pricing import fetch_quote, clear_cache, _quote_cache, _quote_cache_lock

        mock_data = {
            "results": [{"last_price": 150.0, "prev_close": 145.0}]
        }

        with patch("pricing._http_get_with_retry", return_value=mock_data):
            fetch_quote("AAPL")

        clear_cache()

        with _quote_cache_lock:
            assert len(_quote_cache) == 0


class TestCircuitBreaker:
    """熔断机制测试"""

    def setup_method(self):
        from pricing import clear_cache
        clear_cache()

    def test_circuit_breaker_triggers(self):
        """连续失败触发熔断"""
        from pricing import _http_get_with_retry, _circuit_breaker, _circuit_lock, CIRCUIT_BREAKER_THRESHOLD

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = Exception("network error")
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_instance)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)

            for i in range(CIRCUIT_BREAKER_THRESHOLD + 1):
                _http_get_with_retry("http://test", {})

            with _circuit_lock:
                assert _circuit_breaker["failures"] >= CIRCUIT_BREAKER_THRESHOLD
                assert _circuit_breaker["open_until"] > time.time()

    def test_circuit_breaker_skips_requests(self):
        """熔断开启时跳过请求"""
        from pricing import _is_circuit_open, _circuit_breaker, _circuit_lock

        with _circuit_lock:
            _circuit_breaker["open_until"] = time.time() + 60

        assert _is_circuit_open() is True

    def test_circuit_breaker_resets_on_success(self):
        """成功请求重置熔断计数"""
        from pricing import _record_success, _circuit_breaker, _circuit_lock

        with _circuit_lock:
            _circuit_breaker["failures"] = 5

        _record_success()

        with _circuit_lock:
            assert _circuit_breaker["failures"] == 0


class TestRetryMechanism:
    """重试机制测试"""

    def test_exponential_backoff(self):
        """指数退避重试正常工作"""
        from pricing import _http_get_with_retry, MAX_RETRIES
        import httpx

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= MAX_RETRIES:
                raise httpx.HTTPStatusError(
                    "temporary error",
                    request=MagicMock(),
                    response=MagicMock(status_code=500),
                )
            resp = MagicMock()
            resp.json.return_value = {"results": [{"last_price": 100}]}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = mock_get
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_instance)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)

            with patch("pricing.time.sleep"):
                result = _http_get_with_retry("http://test", {})

            assert result is not None
            assert call_count == MAX_RETRIES + 1


class TestHealthCheck:
    """健康检查端点测试"""

    def test_health_endpoint_returns_status(self):
        """健康检查端点返回正确结构"""
        from fastapi.testclient import TestClient
        from server import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "components" in data
        assert "database" in data["components"]
        assert "openbb" in data["components"]
        assert "push" in data["components"]
        assert "holdings_count" in data

    def test_health_status_values(self):
        """健康状态值合法"""
        from fastapi.testclient import TestClient
        from server import app

        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert data["components"]["database"] in ("healthy", "unhealthy")
        assert data["components"]["openbb"] in ("healthy", "unhealthy")
        assert data["components"]["push"] in ("enabled", "disabled")


class TestInputValidation:
    """输入验证测试"""

    def test_invalid_symbol_rejected(self):
        """非法股票代码被拒绝"""
        from server import HoldingIn
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            HoldingIn(
                symbol="INVALID SYMBOL!",
                cost_price=100.0,
                shares=10,
            )

    def test_negative_cost_rejected(self):
        """负成本价被拒绝"""
        from server import HoldingIn
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            HoldingIn(
                symbol="AAPL",
                cost_price=-100.0,
                shares=10,
            )

    def test_zero_shares_rejected(self):
        """零股数被拒绝"""
        from server import HoldingIn
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            HoldingIn(
                symbol="AAPL",
                cost_price=100.0,
                shares=0,
            )

    def test_symbol_uppercased(self):
        """股票代码自动转大写"""
        from server import HoldingIn

        h = HoldingIn(
            symbol="aapl",
            cost_price=100.0,
            shares=10,
        )
        assert h.symbol == "AAPL"

    def test_trade_side_validation(self):
        """交易方向验证"""
        from server import TradeIn
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            TradeIn(
                symbol="AAPL",
                side="invalid",
                price=100.0,
                shares=10,
            )

    def test_knowledge_title_validation(self):
        """知识库标题验证"""
        from server import KnowledgeIn
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            KnowledgeIn(
                title="",
                category="test",
                content="test content",
            )


class TestConfigValidation:
    """配置校验测试"""

    def test_validate_config_runs(self):
        """配置校验函数正常执行"""
        from server import _validate_config
        _validate_config()

    def test_api_config_endpoint(self):
        """配置信息端点不暴露敏感信息"""
        from fastapi.testclient import TestClient
        from server import app

        client = TestClient(app)
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        assert "push_enabled" in data
        assert "stop_loss_pct" in data
        assert "rate_limit_enabled" in data
        assert "rate_limit_per_min" in data

        sensitive_keys = ["PUSHPLUS_TOKEN", "WXPUSHER_TOKEN", "token", "key", "password"]
        for key in data.keys():
            assert key.lower() not in [s.lower() for s in sensitive_keys], \
                f"敏感信息泄露: {key}"


class TestRateLimiting:
    """限流中间件测试"""

    def test_rate_limit_disabled_by_default(self):
        """默认限流关闭"""
        from config import Config
        assert Config.RATE_LIMIT_ENABLED is False

    def test_rate_limit_store_structure(self):
        """限流数据结构正确"""
        from server import _rate_limit_store, _rate_lock, RATE_LIMIT_PER_MIN

        assert RATE_LIMIT_PER_MIN == 120

        with _rate_lock:
            entry = _rate_limit_store["test_ip"]
            assert "count" in entry
            assert "window" in entry


class TestCORSConfig:
    """CORS 配置测试"""

    def test_cors_origins_config_exists(self):
        """CORS 配置存在"""
        from config import Config
        assert hasattr(Config, "CORS_ORIGINS")
        assert isinstance(Config.CORS_ORIGINS, list)

    def test_cors_middleware_added(self):
        """CORS 中间件已添加"""
        from server import app
        middleware_types = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_types


class TestBatchQuotes:
    """批量行情查询测试"""

    def test_fetch_quotes_batch(self):
        """批量查询返回字典"""
        from pricing import fetch_quotes_batch, clear_cache

        clear_cache()

        def mock_fetch(symbol):
            return {"symbol": symbol, "price": 100.0, "prev_close": 95.0}

        with patch("pricing.fetch_quote", side_effect=mock_fetch):
            result = fetch_quotes_batch(["AAPL", "MSFT", "NVDA"])
            assert isinstance(result, dict)
            assert len(result) == 3
            assert "AAPL" in result
            assert "MSFT" in result
            assert "NVDA" in result
