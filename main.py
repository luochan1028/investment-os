"""个人持仓风控 - 主程序

用法:
    python main.py add AAPL --cost 150 --shares 50 --name Apple --sector 科技
    python main.py list
    python main.py rm AAPL
    python main.py run-once     # 扫描一次风控（止损/集中度/组合回撤）
    python main.py loop         # 持续监控
    python main.py status       # 查看持仓与风险概览（含 VaR / 回撤）
"""
import argparse
import logging
import time
from datetime import datetime

from config import Config
from store import (
    init_db, add_holding, remove_holding, get_holdings,
    save_price,
    save_nav_snapshot, get_portfolio_drawdown,
)
from pricing import fetch_quote, fetch_history
from risk import (
    compute_position_pnl, compute_portfolio, compute_concentration,
    compute_daily_returns, compute_var, compute_max_drawdown,
)
from alerter import emit_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("portfolio-risk")


def _build_positions() -> list[dict]:
    """拉取行情并构造 positions 列表（holding + pnl + current_price）"""
    holdings = get_holdings()
    positions = []
    for h in holdings:
        q = fetch_quote(h["symbol"])
        if not q or not q["price"]:
            logger.error(f"❌ {h['symbol']} 行情获取失败，跳过")
            continue
        save_price(h["symbol"], q["price"])
        pnl = compute_position_pnl(h, q["price"])
        positions.append({**h, **pnl})
    return positions


def scan_once():
    """执行一次风控扫描：止损 → 集中度 → 组合回撤"""
    positions = _build_positions()
    if not positions:
        logger.warning("⚠️ 无可扫描持仓")
        return

    # 1. 单标的止损
    for p in positions:
        if p["pnl_pct"] <= -Config.STOP_LOSS_PCT:
            emit_alert(
                alert_type="stop_loss",
                level="high",
                title=f"{p['symbol']} 触及止损线",
                detail=(
                    f"亏损 **{p['pnl_pct']*100:.2f}%**（止损线 -{Config.STOP_LOSS_PCT*100:.0f}%）\n"
                    f"成本 {p['cost_price']} → 现价 {p['current_price']}\n"
                    f"持仓市值 {p['market_value']:.2f}，浮亏 {p['pnl']:.2f}"
                ),
                symbol=p["symbol"],
            )

    # 2. 组合层
    portfolio = compute_portfolio(positions)
    concentration = compute_concentration(positions, portfolio["total_market"])

    # 2.1 记录当日净值快照（用于真实回撤计算）
    save_nav_snapshot(
        total_market=portfolio["total_market"],
        total_cost=portfolio["total_cost"],
        cash=0.0,
        note=f"{len(positions)} holdings",
    )

    for sym, weight in concentration["by_symbol"].items():
        if weight >= Config.CONCENTRATION_PCT:
            emit_alert(
                alert_type="concentration",
                level="medium",
                title=f"{sym} 集中度过高",
                detail=(
                    f"{sym} 占组合 **{weight*100:.1f}%**"
                    f"（阈值 {Config.CONCENTRATION_PCT*100:.0f}%）"
                ),
                symbol=sym,
            )

    # 3. 组合回撤（基于净值序列的真实回撤，替代浮亏代理）
    dd_info = get_portfolio_drawdown(days=90)
    real_dd = dd_info.get("max_drawdown")
    if real_dd is not None and real_dd >= Config.PORTFOLIO_DD_PCT:
        emit_alert(
            alert_type="portfolio_drawdown",
            level="high",
            title="组合回撤触及阈值",
            detail=(
                f"近 90 天最大回撤 **{real_dd*100:.2f}%**"
                f"（阈值 {Config.PORTFOLIO_DD_PCT*100:.0f}%）\n"
                f"峰值净值 {dd_info['peak_nav']:.4f}（{dd_info['peak_date']}）\n"
                f"当前回撤 {dd_info['current_drawdown']*100:.2f}%\n"
                f"总市值 {portfolio['total_market']:.2f}，总浮亏 {portfolio['total_pnl']:.2f}"
            ),
        )
    elif real_dd is None and portfolio["total_pnl_pct"] <= -Config.PORTFOLIO_DD_PCT:
        # 净值序列不足2天时，降级用浮亏代理
        emit_alert(
            alert_type="portfolio_drawdown",
            level="high",
            title="组合浮亏触及回撤阈值",
            detail=(
                f"组合整体浮亏 **{portfolio['total_pnl_pct']*100:.2f}%**"
                f"（阈值 -{Config.PORTFOLIO_DD_PCT*100:.0f}%）\n"
                f"注：净值序列不足，暂用浮亏代理。累计净值后将切换为真实回撤。"
            ),
        )

    _log_scan_summary(positions, portfolio)


def _log_scan_summary(positions: list[dict], portfolio: dict):
    logger.info("=" * 60)
    logger.info(f"📊 风控扫描完成 - {datetime.now().strftime('%H:%M:%S')}")
    logger.info(
        f"   持仓 {len(positions)} 只 | "
        f"总市值 {portfolio['total_market']:.2f} | "
        f"浮盈亏 {portfolio['total_pnl']:.2f} "
        f"({portfolio['total_pnl_pct']*100:.2f}%)"
    )
    for p in positions:
        icon = "🟢" if p["pnl"] >= 0 else "🔴"
        logger.info(
            f"   {icon} {p['symbol']}: 现价 {p['current_price']} | "
            f"浮盈亏 {p['pnl']:.2f} ({p['pnl_pct']*100:.2f}%)"
        )
    logger.info("=" * 60)


def show_status():
    """持仓 + 风险概览（含 VaR / 最大回撤）"""
    positions = _build_positions()
    if not positions:
        print("无持仓或行情获取失败")
        return

    portfolio = compute_portfolio(positions)
    concentration = compute_concentration(positions, portfolio["total_market"])

    print("\n" + "=" * 60)
    print("📊 持仓风控概览")
    print("=" * 60)
    print(
        f"\n总成本: {portfolio['total_cost']:.2f} | "
        f"总市值: {portfolio['total_market']:.2f} | "
        f"浮盈亏: {portfolio['total_pnl']:.2f} "
        f"({portfolio['total_pnl_pct']*100:.2f}%)"
    )

    print("\n持仓明细:")
    print(f"  {'标的':<8} {'成本':>8} {'现价':>8} {'仓位':>6} {'浮盈亏':>12} {'VaR(日)':>10} {'最大回撤':>8}")
    for p in positions:
        weight = (p["market_value"] / portfolio["total_market"] * 100
                  if portfolio["total_market"] else 0)
        # VaR / 回撤基于该标的的历史序列
        hist = fetch_history(p["symbol"], Config.VAR_LOOKBACK_DAYS)
        returns = compute_daily_returns(hist)
        var = compute_var(returns)
        mdd = compute_max_drawdown(hist)
        var_str = f"{var*100:.2f}%" if var is not None else "N/A"
        print(
            f"  {p['symbol']:<8} {p['cost_price']:>8} {p['current_price']:>8} "
            f"{weight:>5.1f}% {p['pnl']:>12.2f} {var_str:>10} {mdd*100:>7.2f}%"
        )

    print("\n行业集中度:")
    for sec, w in sorted(concentration["by_sector"].items(), key=lambda x: -x[1]):
        print(f"  {sec}: {w*100:.1f}%")

    print("\n配置:")
    for k, v in Config.summary().items():
        print(f"  {k}: {v}")
    print()


def loop():
    logger.info(f"🔄 持仓风控持续监控，间隔 {Config.POLL_INTERVAL}秒")
    while True:
        try:
            scan_once()
        except Exception as e:
            logger.error(f"❌ 扫描异常: {e}", exc_info=True)
        try:
            time.sleep(Config.POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("👋 退出监控")
            break


def main():
    parser = argparse.ArgumentParser(description="个人持仓风控")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="录入持仓")
    p_add.add_argument("symbol")
    p_add.add_argument("--cost", type=float, required=True, help="成本价")
    p_add.add_argument("--shares", type=float, required=True, help="持仓数量")
    p_add.add_argument("--name", default="", help="名称")
    p_add.add_argument("--sector", default="", help="行业/板块")
    p_add.add_argument("--note", default="", help="备注")

    sub.add_parser("list", help="查看持仓")

    p_rm = sub.add_parser("rm", help="删除持仓")
    p_rm.add_argument("symbol")

    sub.add_parser("run-once", help="扫描一次风控")
    sub.add_parser("loop", help="持续监控")
    sub.add_parser("status", help="持仓与风险概览")

    args = parser.parse_args()
    init_db()

    if args.cmd == "add":
        add_holding(args.symbol, args.cost, args.shares,
                    args.name, args.sector, args.note)
        print(f"✅ 已录入 {args.symbol} (成本{args.cost} × {args.shares}股)")
    elif args.cmd == "list":
        holdings = get_holdings()
        if not holdings:
            print("（无持仓）")
        for h in holdings:
            print(f"  {h['symbol']:<8} 成本{h['cost_price']:>8} "
                  f"数量{h['shares']:>8} {h['name']} [{h['sector'] or '-'}]")
    elif args.cmd == "rm":
        n = remove_holding(args.symbol)
        print(f"{'✅ 已删除' if n else '❌ 未找到'} {args.symbol}")
    elif args.cmd == "run-once":
        scan_once()
    elif args.cmd == "loop":
        loop()
    elif args.cmd == "status":
        show_status()


if __name__ == "__main__":
    main()
