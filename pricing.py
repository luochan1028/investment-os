"""行情获取模块 - 通过 OpenBB API（生产级优化）

优化项：
- 内存缓存（quote 15秒，history 5分钟）
- 指数退避重试
- 批量查询合并
- 熔断机制（连续失败后降级）
"""
import logging
import time
from threading import Lock
from typing import Optional

import httpx

from config import Config

logger = logging.getLogger(__name__)

_quote_cache = {}
_quote_cache_lock = Lock()
QUOTE_CACHE_TTL = 15

_history_cache = {}
_history_cache_lock = Lock()
HISTORY_CACHE_TTL = 300

_circuit_breaker = {
    "failures": 0,
    "last_failure": 0,
    "open_until": 0,
}
_circuit_lock = Lock()
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 60

MAX_RETRIES = 2
RETRY_BACKOFF = 1.0


def _is_circuit_open() -> bool:
    with _circuit_lock:
        if _circuit_breaker["open_until"] > time.time():
            return True
        if _circuit_breaker["open_until"] > 0:
            _circuit_breaker["failures"] = 0
            _circuit_breaker["open_until"] = 0
        return False


def _record_failure():
    with _circuit_lock:
        _circuit_breaker["failures"] += 1
        _circuit_breaker["last_failure"] = time.time()
        if _circuit_breaker["failures"] >= CIRCUIT_BREAKER_THRESHOLD:
            _circuit_breaker["open_until"] = time.time() + CIRCUIT_BREAKER_TIMEOUT
            logger.warning(f"熔断触发！{CIRCUIT_BREAKER_TIMEOUT}秒内跳过OpenBB调用")


def _record_success():
    with _circuit_lock:
        if _circuit_breaker["failures"] > 0:
            _circuit_breaker["failures"] = 0


def _http_get_with_retry(url: str, params: dict, timeout: int = 15) -> Optional[dict]:
    if _is_circuit_open():
        logger.debug("熔断开启，跳过请求")
        return None

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                _record_success()
                return data
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * (2 ** attempt)
                logger.warning(f"请求失败（第{attempt+1}次），{wait:.1f}秒后重试: {e}")
                time.sleep(wait)
            else:
                logger.error(f"请求最终失败（{MAX_RETRIES+1}次尝试）: {e}")
        except Exception as e:
            last_error = e
            logger.error(f"请求异常: {e}")
            break

    _record_failure()
    return None


def fetch_quote(symbol: str) -> dict | None:
    """获取实时报价（带15秒缓存 + 重试 + 熔断）

    Returns:
        {symbol, price, prev_close, high, low, volume} 或 None
    """
    now = time.time()
    cache_key = symbol.upper()

    with _quote_cache_lock:
        cached = _quote_cache.get(cache_key)
        if cached and (now - cached["_ts"]) < QUOTE_CACHE_TTL:
            return {k: v for k, v in cached.items() if k != "_ts"}

    url = f"{Config.OPENBB_BASE_URL}/equity/price/quote"
    params = {"symbol": symbol, "provider": Config.OPENBB_PROVIDER}

    data = _http_get_with_retry(url, params, timeout=15)
    if not data:
        with _quote_cache_lock:
            if cached:
                return {k: v for k, v in cached.items() if k != "_ts"}
        return None

    results = data.get("results")
    if not results:
        return None

    r = results[0] if isinstance(results, list) else results
    price = r.get("last_price") or r.get("close") or 0
    if not price:
        return None

    result = {
        "symbol": symbol.upper(),
        "price": price,
        "prev_close": r.get("prev_close") or 0,
        "high": r.get("high"),
        "low": r.get("low"),
        "volume": r.get("volume"),
    }

    with _quote_cache_lock:
        _quote_cache[cache_key] = {**result, "_ts": now}

    return result


def fetch_history(symbol: str, days: int = 90) -> list[float]:
    """获取历史收盘价序列（升序，带5分钟缓存 + 重试 + 熔断）"""
    now = time.time()
    cache_key = f"{symbol.upper()}:{days}"

    with _history_cache_lock:
        cached = _history_cache.get(cache_key)
        if cached and (now - cached["_ts"]) < HISTORY_CACHE_TTL:
            return list(cached["prices"])

    url = f"{Config.OPENBB_BASE_URL}/equity/price/historical"
    params = {"symbol": symbol, "provider": Config.OPENBB_PROVIDER}

    data = _http_get_with_retry(url, params, timeout=20)
    if not data:
        with _history_cache_lock:
            if cached:
                return list(cached["prices"])
        return []

    results = data.get("results") or []
    if isinstance(results, dict):
        results = [results]

    closes = [r.get("close") for r in results if r.get("close")]
    prices = closes[-days:] if closes else []

    with _history_cache_lock:
        _history_cache[cache_key] = {"prices": prices, "_ts": now}

    return prices


def fetch_quotes_batch(symbols: list[str]) -> dict[str, dict]:
    """批量并发获取报价（复用缓存，减少API调用时间）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    # 先检查缓存命中的
    cached = []
    uncached = []
    for sym in symbols:
        key = sym.upper()
        now = time.time()
        with _quote_cache_lock:
            entry = _quote_cache.get(key)
        if entry and now - entry["_ts"] < QUOTE_CACHE_TTL:
            results[key] = {k: v for k, v in entry.items() if k != "_ts"}
            cached.append(sym)
        else:
            uncached.append(sym)

    # 并发请求未缓存的
    if uncached:
        with ThreadPoolExecutor(max_workers=min(8, len(uncached))) as executor:
            future_map = {executor.submit(fetch_quote, sym): sym for sym in uncached}
            for future in as_completed(future_map):
                sym = future_map[future]
                try:
                    q = future.result()
                    if q:
                        results[sym.upper()] = q
                except Exception as e:
                    logger.warning(f"批量查询 {sym} 失败: {e}")

    return results


def fetch_history_batch(symbols: list[str], days: int = 90) -> dict[str, list[float]]:
    """批量并发获取历史价格（复用缓存）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    # 检查缓存
    uncached = []
    for sym in symbols:
        key = f"{sym.upper()}:{days}"
        now = time.time()
        with _history_cache_lock:
            entry = _history_cache.get(key)
        if entry and now - entry["_ts"] < HISTORY_CACHE_TTL:
            results[sym.upper()] = list(entry["prices"])
        else:
            uncached.append(sym)

    if uncached:
        with ThreadPoolExecutor(max_workers=min(8, len(uncached))) as executor:
            future_map = {executor.submit(fetch_history, sym, days): sym for sym in uncached}
            for future in as_completed(future_map):
                sym = future_map[future]
                try:
                    hist = future.result()
                    if hist:
                        results[sym.upper()] = hist
                except Exception as e:
                    logger.warning(f"批量历史查询 {sym} 失败: {e}")

    return results


def clear_cache():
    """清空所有缓存（测试用）"""
    with _quote_cache_lock:
        _quote_cache.clear()
    with _history_cache_lock:
        _history_cache.clear()
    with _circuit_lock:
        _circuit_breaker["failures"] = 0
        _circuit_breaker["last_failure"] = 0
        _circuit_breaker["open_until"] = 0
