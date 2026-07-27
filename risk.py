"""风险计算引擎 - 盈亏、VaR、最大回撤、集中度

所有函数纯计算、无副作用，便于单测与复用。
"""
from config import Config


def compute_position_pnl(holding: dict, current_price: float) -> dict:
    """单标的盈亏"""
    cost_value = holding["cost_price"] * holding["shares"]
    market_value = current_price * holding["shares"]
    pnl = market_value - cost_value
    pnl_pct = (pnl / cost_value) if cost_value else 0.0
    return {
        "current_price": current_price,
        "cost_value": cost_value,
        "market_value": market_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }


def compute_portfolio(positions: list[dict]) -> dict:
    """组合汇总"""
    total_cost = sum(p["cost_value"] for p in positions)
    total_market = sum(p["market_value"] for p in positions)
    total_pnl = total_market - total_cost
    return {
        "total_cost": total_cost,
        "total_market": total_market,
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / total_cost) if total_cost else 0.0,
    }


def compute_concentration(positions: list[dict], total_market: float) -> dict:
    """集中度：按标的 + 按行业"""
    by_symbol: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for p in positions:
        sym = p["symbol"]
        sector = p.get("sector") or "未分类"
        weight = (p["market_value"] / total_market) if total_market else 0.0
        by_symbol[sym] = weight
        by_sector[sector] = by_sector.get(sector, 0.0) + weight
    return {"by_symbol": by_symbol, "by_sector": by_sector}


def compute_daily_returns(historical_prices: list[float]) -> list[float]:
    """日收益率序列"""
    returns = []
    for i in range(1, len(historical_prices)):
        prev = historical_prices[i - 1]
        if prev:
            returns.append((historical_prices[i] - prev) / prev)
    return returns


def compute_var(historical_returns: list[float],
                confidence: float = None) -> float | None:
    """历史 VaR（在险价值）

    返回损失分位数（负值代表损失），样本不足返回 None。
    """
    if confidence is None:
        confidence = Config.VAR_CONFIDENCE
    if len(historical_returns) < 10:
        return None
    sorted_returns = sorted(historical_returns)
    idx = int((1 - confidence) * len(sorted_returns))
    idx = min(max(idx, 0), len(sorted_returns) - 1)
    return sorted_returns[idx]


def compute_max_drawdown(historical_prices: list[float]) -> float:
    """最大回撤（0~1）"""
    if len(historical_prices) < 2:
        return 0.0
    peak = historical_prices[0]
    max_dd = 0.0
    for price in historical_prices:
        if price > peak:
            peak = price
        if peak:
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd
