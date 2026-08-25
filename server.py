"""投资研究操作系统 - 统一后端（生产级优化）

20 个模块的 API

优化项：
- CORS 跨域支持
- 输入验证（Pydantic）
- 请求限流
- 健康检查端点
- 优雅关闭
- 配置校验

用法:
    python server.py --port 8088
"""
import argparse
import logging
import os
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, Thread, Event

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from config import Config
from store import (
    init_db, get_holdings, add_holding, remove_holding,
    save_price, save_alert, get_recent_alerts,
    save_tweet, get_recent_tweets,
    save_filing, get_filings, get_latest_filing_fetched_at, get_filing_by_symbol,
    get_unpushed_filings, mark_filing_pushed,
    save_macro_event, get_macro_events,
    save_news_event, get_news_events,
    save_knowledge, get_knowledge,
    save_trade, get_trades,
    get_connection,
    get_users, get_user, get_user_by_id, create_user, update_user, delete_user,
    save_nav_snapshot, get_portfolio_drawdown,
    get_x_accounts, add_x_account, remove_x_account, toggle_x_account,
    get_unpushed_high_tweets, mark_tweet_pushed,
)
from pricing import fetch_quote, fetch_history, fetch_quotes_batch, fetch_history_batch, clear_cache
from risk import (
    compute_position_pnl, compute_portfolio, compute_concentration,
    compute_daily_returns, compute_var, compute_max_drawdown,
)
from shared.pusher import push_alert, PushLevel, get_push_stats, init_push_tables, get_default_config
from shared.sentiment_adapter import fetch_real_tweets, get_monitor_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("investment-os")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.^=\-]{1,20}$")

_rate_limit_store = defaultdict(lambda: {"count": 0, "window": 0})
_rate_lock = Lock()
RATE_LIMIT_PER_MIN = 120

# ==================== 宏观经济数据后台推送线程 ====================

_macro_push_stop_event = Event()
_macro_push_last_result = {"checked": 0, "pushed": 0, "skipped": 0, "last_run": None, "errors": []}
MACRO_PUSH_INTERVAL = int(os.getenv("MACRO_PUSH_INTERVAL", "300"))  # 默认5分钟


def _macro_push_loop():
    """后台线程：定时检查宏观事件倒计时，到达提醒窗口时推送微信"""
    logger.info(f"宏观经济数据推送线程已启动，检查间隔 {MACRO_PUSH_INTERVAL}秒")
    _macro_push_stop_event.wait(15)
    while not _macro_push_stop_event.is_set():
        try:
            from data_sources.macro_push import check_and_push
            result = check_and_push()
            _macro_push_last_result.update(result)
            _macro_push_last_result["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if result.get("pushed"):
                logger.info(f"宏观推送: {result['pushed']}条已推送, {result['skipped']}条跳过")
        except Exception as e:
            logger.error(f"宏观推送检查失败: {e}")
            _macro_push_last_result["errors"] = [str(e)]
        _macro_push_stop_event.wait(MACRO_PUSH_INTERVAL)
    logger.info("宏观推送线程已停止")


# ==================== X 舆情后台刷新线程 ====================

_x_monitor_stop_event = Event()
_x_monitor_last_result = {"total_fetched": 0, "new_saved": 0, "pushed": 0, "last_run": None, "errors": []}
X_POLL_INTERVAL = int(os.getenv("X_POLL_INTERVAL", "300"))  # 默认5分钟


def _x_monitor_loop():
    """后台线程：定时拉取X账号推文 → 分类 → 存储 → 推送微信"""
    from data_sources.x_monitor import run_poll_once

    logger.info(f"X舆情监控线程已启动，轮询间隔 {X_POLL_INTERVAL}秒")
    # 启动后等10秒再首次执行
    time.sleep(10)

    while not _x_monitor_stop_event.is_set():
        try:
            accounts_info = get_x_accounts(enabled_only=True)
            if accounts_info:
                usernames = [a["username"] for a in accounts_info]
                result = run_poll_once(usernames, max_items=5)
                _x_monitor_last_result.update(result)
                _x_monitor_last_result["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"X舆情轮询完成: 拉取{result['total_fetched']}条, 新增{result['new_saved']}条, 推送{result['pushed']}条")
            else:
                logger.debug("无启用的X账号，跳过轮询")
        except Exception as e:
            logger.error(f"X舆情轮询异常: {e}")
            _x_monitor_last_result["errors"] = [str(e)]

        # 等待下一轮（可被中断）
        _x_monitor_stop_event.wait(X_POLL_INTERVAL)

    logger.info("X舆情监控线程已停止")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_push_tables()
    _seed_demo_data()
    _validate_config()
    # 启动X舆情后台监控线程
    x_thread = Thread(target=_x_monitor_loop, daemon=True, name="x-monitor")
    x_thread.start()
    # 启动宏观经济数据推送线程
    macro_thread = Thread(target=_macro_push_loop, daemon=True, name="macro-push")
    macro_thread.start()
    logger.info(f"启动完成 - 持仓: {len(get_holdings())}, 推送: {'启用' if Config.PUSH_ENABLED else '未配置'}, X账号: {len(get_x_accounts())}")
    yield
    logger.info("正在关闭服务...")
    _x_monitor_stop_event.set()
    _macro_push_stop_event.set()
    clear_cache()
    logger.info("服务已关闭")


app = FastAPI(title="投资研究操作系统", version="1.0", lifespan=lifespan)

_cors_origins = Config.CORS_ORIGINS or ["*"]
if _cors_origins == ["*"]:
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["*"],
    )


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if Config.RATE_LIMIT_ENABLED:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60
        with _rate_lock:
            entry = _rate_limit_store[client_ip]
            if entry["window"] < window_start:
                entry["count"] = 0
                entry["window"] = now
            entry["count"] += 1
            if entry["count"] > RATE_LIMIT_PER_MIN:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后再试"},
                )
    response = await call_next(request)
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    status = response.status_code
    if duration > 1.0:
        logger.warning(f"慢请求 {request.method} {request.url.path} - {status} - {duration:.2f}s")
    return response


def _validate_config():
    issues = []
    if not Config.OPENBB_BASE_URL:
        issues.append("OPENBB_BASE_URL 未配置")
    if Config.STOP_LOSS_PCT <= 0 or Config.STOP_LOSS_PCT > 1:
        issues.append(f"STOP_LOSS_PCT 异常: {Config.STOP_LOSS_PCT}")
    if Config.VAR_CONFIDENCE <= 0 or Config.VAR_CONFIDENCE >= 1:
        issues.append(f"VAR_CONFIDENCE 异常: {Config.VAR_CONFIDENCE}")
    if issues:
        for issue in issues:
            logger.warning(f"配置警告: {issue}")
    else:
        logger.info("配置校验通过")


# ==================== 数据模型 ====================

class HoldingIn(BaseModel):
    symbol: str
    cost_price: float
    shares: float
    name: str = ""
    sector: str = ""
    note: str = ""

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v):
        if not _SYMBOL_RE.match(v):
            raise ValueError("股票代码格式不正确")
        return v.upper()

    @field_validator("cost_price")
    @classmethod
    def validate_cost(cls, v):
        if v <= 0:
            raise ValueError("成本价必须大于0")
        return v

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v):
        if v <= 0:
            raise ValueError("数量必须大于0")
        return v


class TradeIn(BaseModel):
    symbol: str
    side: str
    price: float
    shares: float
    reason: str = ""
    trade_date: str = ""
    outcome: str = ""
    review_note: str = ""

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v):
        if not _SYMBOL_RE.match(v):
            raise ValueError("股票代码格式不正确")
        return v.upper()

    @field_validator("side")
    @classmethod
    def validate_side(cls, v):
        if v.lower() not in ("buy", "sell", "买入", "卖出"):
            raise ValueError("交易方向必须是 buy/sell")
        return v

    @field_validator("price", "shares")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("价格和数量必须大于0")
        return v


class KnowledgeIn(BaseModel):
    title: str
    category: str
    tags: str = ""
    content: str
    source_url: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if not v or len(v) > 200:
            raise ValueError("标题长度必须在1-200字符之间")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        if not v:
            raise ValueError("内容不能为空")
        return v


class QueryIn(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v):
        if not v or len(v) > 500:
            raise ValueError("问题长度必须在1-500字符之间")
        return v


class UserIn(BaseModel):
    username: str
    display_name: str = ""
    avatar: str = ""

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if not v or len(v) > 50:
            raise ValueError("用户名长度必须在1-50字符之间")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v


class UserUpdate(BaseModel):
    display_name: str = None
    avatar: str = None


# ==================== 用户上下文工具函数 ====================

def _get_user_id(user_id: int = None, username: str = None) -> int:
    """根据 user_id 或 username 获取用户ID，默认返回 1（默认用户）。"""
    if user_id:
        return user_id
    if username:
        u = get_user(username)
        if u:
            return u["id"]
    return 1


# ==================== 健康检查 ====================

@app.get("/health")
def health_check():
    """健康检查端点"""
    db_ok = True
    try:
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception:
        db_ok = False

    openbb_ok = False
    try:
        q = fetch_quote("AAPL")
        openbb_ok = q is not None
    except Exception:
        pass

    push_ok = Config.PUSH_ENABLED

    overall = "healthy" if db_ok and openbb_ok else ("degraded" if db_ok else "unhealthy")

    return {
        "status": overall,
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": "healthy" if db_ok else "unhealthy",
            "openbb": "healthy" if openbb_ok else "unhealthy",
            "push": "enabled" if push_ok else "disabled",
        },
        "holdings_count": len(get_holdings()),
    }


@app.get("/api/config")
def api_config():
    """系统配置信息（不暴露敏感信息）"""
    return {
        "version": "1.0.0",
        "push_enabled": Config.PUSH_ENABLED,
        "push_type": Config.PUSH_TYPE,
        "stop_loss_pct": Config.STOP_LOSS_PCT,
        "portfolio_dd_pct": Config.PORTFOLIO_DD_PCT,
        "concentration_pct": Config.CONCENTRATION_PCT,
        "var_confidence": Config.VAR_CONFIDENCE,
        "rate_limit_enabled": Config.RATE_LIMIT_ENABLED,
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
    }


# ==================== 用户管理 API ====================

@app.get("/api/users")
def api_users():
    """获取所有用户列表"""
    return {"users": get_users()}


@app.get("/api/users/{user_id}")
def api_user_detail(user_id: int):
    """获取单个用户详情"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    return {"user": user}


@app.post("/api/users")
def api_create_user(u: UserIn):
    """创建新用户"""
    user = create_user(u.username, u.display_name, u.avatar)
    if not user:
        raise HTTPException(409, "用户名已存在")
    return {"ok": True, "user": user}


@app.put("/api/users/{user_id}")
def api_update_user(user_id: int, u: UserUpdate):
    """更新用户信息"""
    user = update_user(user_id, u.display_name, u.avatar)
    if not user:
        raise HTTPException(404, "用户不存在")
    return {"ok": True, "user": user}


@app.delete("/api/users/{user_id}")
def api_delete_user(user_id: int):
    """删除用户（不允许删除默认用户）"""
    if user_id == 1:
        raise HTTPException(403, "不允许删除默认用户")
    if not delete_user(user_id):
        raise HTTPException(404, "用户不存在")
    return {"ok": True, "deleted": user_id}


def _build_positions(user_id: int = 1):
    """构建用户持仓（批量并发获取行情）"""
    holdings = get_holdings(user_id)
    if not holdings:
        return []
    symbols = [h["symbol"] for h in holdings]
    batch = fetch_quotes_batch(symbols)
    positions = []
    for h in holdings:
        q = batch.get(h["symbol"].upper())
        if not q or not q["price"]:
            continue
        save_price(h["symbol"], q["price"], user_id)
        positions.append({**h, **compute_position_pnl(h, q["price"])})
    return positions


def _seed_demo_data():
    """首次启动时填充示例数据（幂等）"""
    conn = get_connection()

    # 持仓
    if not conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]:
        for sym, cost, shares, name, sector in [
            ("AAPL", 220, 50, "Apple", "科技"), ("NVDA", 90, 100, "NVIDIA", "科技"),
            ("TSLA", 250, 30, "Tesla", "汽车"), ("600519.SS", 1700, 5, "贵州茅台", "消费"),
        ]:
            add_holding(sym, cost, shares, name, sector)

    # 舆情示例
    if not conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]:
        for u, t, lvl, cat in [
            ("realDonaldTrump", "Tariffs on China will increase to 60%", "high", "关税"),
            ("elonmusk", "Tesla Q3 deliveries beat expectations", "medium", "财报"),
            ("CathieDWood", "Bitcoin ETF inflows hit record", "medium", "加密"),
            ("Powell", "Fed holds rates steady, dovish tone", "high", "美联储"),
        ]:
            save_tweet(u, t, "", (datetime.now() - timedelta(hours=__import__('random').randint(1, 48))).strftime("%Y-%m-%d %H:%M:%S"),
                       lvl, cat, 1)

    # 财报示例
    if not conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]:
        companies = [("AAPL","Apple","10-Q"),("NVDA","NVIDIA","10-Q"),("MSFT","Microsoft","10-Q"),
                     ("TSLA","Tesla","10-Q"),("GOOGL","Alphabet","10-Q"),("AMZN","Amazon","10-Q"),
                     ("META","Meta","10-Q"),("AMD","AMD","10-Q"),("INTC","Intel","10-Q"),
                     ("AVGO","Broadcom","10-Q"),("MU","Micron","10-Q"),("TSM","TSMC","20-F")]
        for sym, name, ftype in companies:
            future_date = (datetime.now() + timedelta(days=random.randint(-30, 60))).strftime("%Y-%m-%d")
            signal = random.choice(["🟢 利好", "🟡 偏利好", "🔴 利空", "⚪ 中性"])
            save_filing(sym, name, ftype, future_date, "2025 Q3", signal, f"{name} {ftype} 财报：营收同比增长 {random.randint(5,30)}%")

    # 宏观事件
    if not conn.execute("SELECT COUNT(*) FROM macro_events").fetchone()[0]:
        events = [
            ("nonfarm", "非农就业报告", "critical", "first_friday", "08:30", "新增 25.6万", "新增 18万", "新增 22.7万", "美元走强 利空黄金"),
            ("cpi", "CPI", "critical", "mid_month", "08:30", "同比 +2.4%", "+2.6%", "+2.7%", "通胀降温 利好股市"),
            ("fed_decision", "美联储利率决议", "critical", "8_times_year", "14:00", "维持不变", "维持不变", "5.25-5.50%", "鸽派 维持"),
            ("pce", "PCE 物价指数", "critical", "month_end", "08:30", "同比 +2.1%", "+2.3%", "+2.4%", "通胀接近目标"),
            ("gdp", "GDP", "critical", "quarterly", "08:30", "+3.0%", "+2.5%", "+2.1%", "经济强劲"),
        ]
        for eid, name, imp, rule, et, act, fc, prev, impact in events:
            dt = (datetime.now() + timedelta(days=random.randint(-10, 30))).strftime("%Y-%m-%d")
            save_macro_event(eid, name, imp, dt, et, act, fc, prev, impact)

    # 新闻事件
    if not conn.execute("SELECT COUNT(*) FROM news_events").fetchone()[0]:
        news = [
            ("地缘冲突", "中东局势升级 以色列对加沙发动空袭", "路透社", "中东", "原油 黄金 军工", (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")),
            ("贸易摩擦", "美国宣布对华半导体新增出口管制", "彭博社", "中美", "半导体 国产替代", (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")),
            ("产业链", "台积电3nm产能预警 影响英伟达供货", "财联社", "台湾", "NVDA TSM 半导体", (datetime.now() - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S")),
            ("地缘冲突", "俄乌冲突持续 欧洲天然气价格飙升", "路透社", "欧洲", "天然气 农产品", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        ]
        for cat, title, source, regions, assets, pub in news:
            save_news_event(cat, title, source, "", regions, assets, pub)

    # 知识库
    if not conn.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0]:
        kb = [
            ("美联储加息周期对科技股的影响", "宏观", "美联储,科技股,加息", "2022-2023年美联储连续加息，科技股估值承压..."),
            ("英伟达AI芯片护城河分析", "个股", "NVDA,AI,半导体", "英伟达在AI训练芯片市场份额超80%..."),
            ("黄金避险属性的量化研究", "宏观", "黄金,避险,VIX", "VIX突破30时，黄金平均上涨3.5%..."),
        ]
        for title, cat, tags, content in kb:
            save_knowledge(title, cat, tags, content)

    # 交易复盘
    if not conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]:
        trades = [
            ("NVDA", "buy", 90, 100, "AI算力需求爆发", "2025-01-15", "+129%", "判断正确 趋势持续"),
            ("TSLA", "buy", 280, 30, "Model Y量产预期", "2025-03-01", "-11%", "买入时机偏早 止损不够果断"),
            ("AAPL", "buy", 220, 50, "iPhone 16创新周期", "2025-02-10", "+51%", "判断正确 持有"),
        ]
        for sym, side, price, shares, reason, date, outcome, note in trades:
            save_trade(sym, side, price, shares, reason, date, outcome, note)

    conn.close()


# ==================== 路由：首页 ====================

@app.get("/")
def index():
    idx = STATIC_DIR / "index.html"
    if not idx.exists():
        raise HTTPException(404, "static/index.html not found")
    return FileResponse(idx)


# ==================== 总览 ====================

@app.get("/api/overview")
def api_overview(user_id: int = 1):
    """首页总览：聚合各模块关键指标（支持用户隔离）"""
    positions = _build_positions(user_id)
    portfolio = compute_portfolio(positions) if positions else {"total_market":0,"total_pnl":0,"total_pnl_pct":0,"total_cost":0}
    alerts = get_recent_alerts(5, user_id)
    tweets = get_recent_tweets(5)

    from shared.sentiment_adapter import get_monitor_status
    stats = get_monitor_status()

    modules_status = {
        "data_collection": {"total": 6, "active": 6, "signals_today": stats.get("today_tweets", 0)},
        "analysis": {"total": 5, "active": 5, "reports_today": len(get_filings(10))},
        "risk": {"total": 4, "active": 4, "alerts_today": len(alerts)},
        "knowledge": {"total": 5, "active": 3, "items": len(get_knowledge(limit=100))},
    }

    market_status = _get_market_status()

    user_info = get_user_by_id(user_id)

    return {
        "user": {"id": user_id, "username": user_info["username"], "display_name": user_info["display_name"]} if user_info else None,
        "portfolio": portfolio,
        "positions_count": len(positions),
        "recent_alerts": alerts,
        "recent_tweets": tweets,
        "modules_status": modules_status,
        "market_status": market_status,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _get_market_status() -> str:
    """根据当前北京时间动态判断各市场交易状态"""
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    time_min = hour * 60 + minute

    is_weekend = weekday >= 5

    def _us_status():
        if is_weekend:
            return "美股休市"
        pre_start = 16 * 60 + 0
        regular_start = 21 * 60 + 30
        regular_end = 4 * 60 + 0
        after_end = 8 * 60 + 0
        if pre_start <= time_min < regular_start:
            return "美股盘前"
        elif regular_start <= time_min or time_min < regular_end:
            return "美股交易中"
        elif regular_end <= time_min < after_end:
            return "美股盘后"
        else:
            return "美股休市"

    def _a_status():
        if is_weekend:
            return "A股休市"
        morning_start = 9 * 60 + 30
        morning_end = 11 * 60 + 30
        afternoon_start = 13 * 60 + 0
        afternoon_end = 15 * 60 + 0
        if morning_start <= time_min < morning_end:
            return "A股交易中"
        elif morning_end <= time_min < afternoon_start:
            return "A股午休"
        elif afternoon_start <= time_min < afternoon_end:
            return "A股交易中"
        else:
            return "A股休市"

    def _hk_status():
        if is_weekend:
            return "港股休市"
        morning_start = 9 * 60 + 30
        morning_end = 12 * 60 + 0
        afternoon_start = 13 * 60 + 0
        afternoon_end = 16 * 60 + 0
        if morning_start <= time_min < morning_end:
            return "港股交易中"
        elif morning_end <= time_min < afternoon_start:
            return "港股午休"
        elif afternoon_start <= time_min < afternoon_end:
            return "港股交易中"
        else:
            return "港股休市"

    def _crypto_status():
        return "加密24h"

    parts = [_us_status(), _a_status(), _hk_status(), _crypto_status()]
    return " / ".join(parts)


# ==================== 数据采集层 ====================

@app.get("/api/market/quotes")
def api_quotes():
    """行情看板 - 真实 OpenBB 数据（批量并发查询）"""
    symbols = ["AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN","META",
               "600519.SS","000858.SZ","0700.HK","9988.HK",
               "BTC-USD","ETH-USD","GLD","CL=F","^VIX","DXY"]
    batch = fetch_quotes_batch(symbols)
    quotes = []
    for s in symbols:
        q = batch.get(s.upper())
        if q:
            change_pct = ((q["price"] - q["prev_close"]) / q["prev_close"] * 100) if q["prev_close"] else 0
            quotes.append({**q, "change_pct": change_pct})
    return {"quotes": quotes, "count": len(quotes)}


@app.get("/api/market/history/{symbol}")
def api_history(symbol: str, days: int = 90):
    hist = fetch_history(symbol.upper(), days)
    if not hist:
        raise HTTPException(404, f"无 {symbol} 历史数据")
    return {"symbol": symbol.upper(), "prices": hist, "count": len(hist)}


@app.get("/api/sentiment/tweets")
def api_tweets(limit: int = 50):
    """关键人物舆情 - 优先读本地数据库（后台线程已写入），降级到 x-monitor-push"""
    local = get_recent_tweets(limit)
    if local:
        return {"tweets": local, "source": "local", "count": len(local)}
    # 降级：读 x-monitor-push 的数据库
    real = fetch_real_tweets(limit)
    if real["count"] > 0:
        return {"tweets": real["tweets"], "source": real["source"], "count": real["count"]}
    return {"tweets": [], "source": "none", "count": 0}


@app.get("/api/sentiment/status")
def api_sentiment_status():
    """舆情监控运行状态"""
    monitor_status = get_monitor_status()
    return {
        **monitor_status,
        "x_monitor": _x_monitor_last_result,
        "poll_interval": X_POLL_INTERVAL,
        "accounts_count": len(get_x_accounts(enabled_only=True)),
    }


# ==================== X 账号管理 ====================

class XAccountIn(BaseModel):
    username: str
    display_name: str = ""

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        v = v.strip().lstrip("@")
        if not v or len(v) > 50:
            raise ValueError("用户名长度必须在1-50字符之间")
        if not re.match(r"^[A-Za-z0-9_.\-]+$", v):
            raise ValueError("用户名只能包含字母、数字、下划线、点和连字符")
        return v


@app.get("/api/sentiment/accounts")
def api_get_x_accounts():
    """获取所有X监控账号"""
    return {"accounts": get_x_accounts(), "count": len(get_x_accounts())}


@app.post("/api/sentiment/accounts")
def api_add_x_account(acc: XAccountIn):
    """添加X监控账号"""
    result = add_x_account(acc.username, acc.display_name)
    if result is None:
        raise HTTPException(409, f"账号 @{acc.username} 已存在")
    logger.info(f"添加X账号: @{acc.username}")
    return {"ok": True, "account": result}


@app.delete("/api/sentiment/accounts/{username}")
def api_remove_x_account(username: str):
    """删除X监控账号"""
    if not remove_x_account(username):
        raise HTTPException(404, f"未找到账号 @{username}")
    logger.info(f"删除X账号: @{username}")
    return {"ok": True, "removed": username}


@app.put("/api/sentiment/accounts/{username}")
def api_toggle_x_account(username: str, enabled: int = 1):
    """启用/禁用X监控账号"""
    if not toggle_x_account(username, enabled):
        raise HTTPException(404, f"未找到账号 @{username}")
    return {"ok": True, "username": username, "enabled": enabled}


@app.post("/api/sentiment/refresh")
def api_sentiment_refresh():
    """手动触发一轮X舆情刷新"""
    from data_sources.x_monitor import run_poll_once

    accounts_info = get_x_accounts(enabled_only=True)
    if not accounts_info:
        return {"ok": False, "msg": "无启用的X账号"}

    usernames = [a["username"] for a in accounts_info]
    result = run_poll_once(usernames, max_items=5)
    _x_monitor_last_result.update(result)
    _x_monitor_last_result["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"ok": True, **result}


@app.get("/api/push/stats")
def api_push_stats():
    """推送统计"""
    return get_push_stats()


def _fetch_filings_concurrent() -> list[tuple[str, str, str, dict]]:
    """并发抓取所有公司的 SEC 财报（复用文件缓存，减少总耗时）

    SEC EDGAR 速率限制为每秒 10 次，这里限制 max_workers=4 避免触发 429。
    requests.Session 连接池是线程安全的，可安全并发调用。

    Returns:
        [(name, ticker, cik, analyze_result), ...] 仅包含成功抓取的条目
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from data_sources.sec_filings import analyze_company, COMPANIES

    results: list[tuple[str, str, str, dict]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(COMPANIES))) as executor:
        future_map = {
            executor.submit(analyze_company, name, cik): (name, ticker, cik)
            for name, ticker, cik in COMPANIES
        }
        for future in as_completed(future_map):
            name, ticker, cik = future_map[future]
            try:
                result = future.result()
                if result is not None:
                    results.append((name, ticker, cik, result))
            except Exception as e:
                logger.warning(f"并发抓取 {name} ({cik}) 失败: {e}")
    return results


def _persist_filing(name: str, ticker: str, cik: str, result: dict,
                    now_str: str, keep_pushed: bool = True) -> bool:
    """把 analyze_company 结果写入 store。返回是否写入成功。

    Args:
        keep_pushed: True 时保留原有 pushed 状态（避免刷新数据时重置推送标记）；
                     False 时仅在财报日期更新时覆盖，并把 pushed 重置为 0。
    """
    try:
        curr = result.get("current", {}) or {}
        period = (result.get("current_date") or "")[:7]
        existing = get_filing_by_symbol(ticker)
        if not keep_pushed:
            new_date = result.get("current_date", "")
            old_date = existing.get("filing_date", "") if existing else ""
            # 只在财报日期更新时才覆盖，并重置 pushed=0
            if existing and new_date == old_date:
                return False
            pushed_val = 0
        else:
            pushed_val = existing.get("pushed", 0) if existing else 0
        save_filing(
            symbol=ticker,
            company=name,
            filing_type=result.get("report_form", ""),
            filing_date=result.get("current_date", ""),
            period=period,
            signal=result.get("signal", ""),
            summary=result.get("signal_desc", ""),
            revenue=curr.get("revenue"),
            net_income=curr.get("net_income"),
            gross_margin=curr.get("gross_margin"),
            bullish=result.get("bullish"),
            bearish=result.get("bearish"),
            fetched_at=now_str,
            pushed=pushed_val,
        )
        return True
    except Exception as e:
        logger.warning(f"持久化 {name} ({cik}) 财报失败: {e}")
        return False


@app.get("/api/filings")
def api_filings(force_refresh: bool = False):
    """财报监控 - 优先读 store，过期(>24h)则实时调用 SEC 抓取 12 家公司。

    Query params:
        force_refresh: 强制实时抓取 (默认 False)
    Returns:
        {filings: [...], source: "cache"|"live", fetched_at: <ISO str>}
    """
    FILINGS_TTL_SECONDS = 24 * 3600  # store 中财报数据的新鲜期: 24 小时

    fetched_at = get_latest_filing_fetched_at()
    is_stale = True
    if fetched_at:
        try:
            fetched_dt = datetime.strptime(fetched_at, "%Y-%m-%d %H:%M:%S")
            is_stale = (datetime.now() - fetched_dt).total_seconds() > FILINGS_TTL_SECONDS
        except ValueError:
            is_stale = True

    existing = get_filings()
    source = "cache"

    if force_refresh or not existing or is_stale:
        source = "live"
        logger.info(
            f"实时抓取 SEC 财报 (force_refresh={force_refresh}, stale={is_stale}, "
            f"existing={len(existing)})"
        )
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 并发抓取所有公司财报（SEC EDGAR 文件缓存命中时近乎瞬时）
        for name, ticker, cik, result in _fetch_filings_concurrent():
            _persist_filing(name, ticker, cik, result, now_str, keep_pushed=True)
        existing = get_filings()
        fetched_at = now_str

    return {
        "filings": existing,
        "source": source,
        "fetched_at": fetched_at,
    }


@app.get("/api/macro/calendar")
def api_macro():
    """宏观日历 - 整合 us-stock-monitor 的 ECONOMIC_CALENDAR 真实发布规则

    返回 CPI/PCE/GDP/非农/失业率等 14 个核心宏观事件的下次发布时间和倒计时。
    数据源优先级：us-stock-monitor 真实逻辑 > fallback 内置规则。
    """
    from data_sources.macro_calendar import get_macro_calendar
    return get_macro_calendar(lookahead_days=60)


@app.get("/api/macro/push-status")
def api_macro_push_status():
    """获取宏观推送后台线程状态"""
    return {
        "running": not _macro_push_stop_event.is_set(),
        "last_result": _macro_push_last_result,
        "interval_seconds": MACRO_PUSH_INTERVAL,
        "remind_intervals": [1440, 60, 15],
    }


@app.post("/api/macro/push-check")
def api_macro_push_check():
    """手动触发一次宏观倒计时检查"""
    from data_sources.macro_push import check_and_push
    result = check_and_push()
    _macro_push_last_result.update(result)
    _macro_push_last_result["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return result


@app.post("/api/macro/push-weekly")
def api_macro_push_weekly():
    """手动推送本周经济数据日历到微信"""
    from data_sources.macro_push import push_weekly_calendar
    return push_weekly_calendar()


@app.get("/api/central-bank/calendar")
def api_central_bank():
    """央行事件 - 整合 us-stock-monitor 已修复的央行会议日期表

    返回 FOMC/BOJ/ECB 等央行未来 120 天的会议安排，含北京时间、美东时间、倒计时。
    数据源优先级：us-stock-monitor 真实逻辑 > fallback 内置日期表。
    """
    from data_sources.central_bank import get_central_bank_events, get_monitor_status
    data = get_central_bank_events(lookahead_days=120)
    data["monitor_status"] = get_monitor_status()
    return data


@app.get("/api/central-bank/status")
def api_central_bank_status():
    """us-stock-monitor 整合状态"""
    from data_sources.central_bank import get_monitor_status
    return get_monitor_status()


@app.get("/api/filings/unpushed")
def api_filings_unpushed():
    """查看未推送的财报列表"""
    filings = get_unpushed_filings(limit=20)
    return {"filings": filings, "count": len(filings)}


@app.post("/api/filings/auto-push")
def api_filings_auto_push():
    """自动检测最新财报并推送到微信（已推送过的不重复推送）

    流程：
    1. 从 SEC 实时抓取最新财报数据（刷新缓存）
    2. 筛选 pushed=0 的未推送财报
    3. 逐条推送到微信（含核心指标+利好利空因素）
    4. 推送成功后标记 pushed=1，避免重复推送

    Returns:
        pushed_count: 成功推送数量
        total_unpushed: 检测到的未推送财报数
        results: 每条财报的推送结果
    """
    cfg = get_default_config()
    validation = cfg.validate()
    if validation:
        return {"pushed_count": 0, "errors": validation, "msg": "推送通道未配置"}

    # 先刷新财报数据（并发抓取 SEC，仅在财报日期更新时覆盖并重置 pushed）
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for name, ticker, cik, result in _fetch_filings_concurrent():
        _persist_filing(name, ticker, cik, result, now_str, keep_pushed=False)

    # 获取未推送的财报
    unpushed = get_unpushed_filings(limit=20)

    if not unpushed:
        return {
            "pushed_count": 0,
            "total_unpushed": 0,
            "msg": "暂无未推送的财报，所有最新财报均已推送",
            "results": [],
        }

    results = []
    pushed_count = 0
    for filing in unpushed:
        symbol = filing.get("symbol", "")
        ok, level, title = _push_filing_to_wechat(filing)
        if ok:
            pushed_count += 1
            mark_filing_pushed(symbol)
        results.append({
            "symbol": symbol,
            "company": filing.get("company", ""),
            "signal": filing.get("signal", ""),
            "pushed": ok,
            "title": title,
        })

    return {
        "pushed_count": pushed_count,
        "total_unpushed": len(unpushed),
        "results": results,
        "fetched_at": now_str,
    }


@app.get("/api/filings/{symbol}")
def api_filing_detail(symbol: str):
    """财报详情 - 点击摘要后弹出

    返回完整财报数据：营收/净利/毛利率/利好因素/利空因素/信号/摘要
    """
    filing = get_filing_by_symbol(symbol.upper())
    if not filing:
        raise HTTPException(404, f"无 {symbol} 财报数据")
    return {"filing": filing}


@app.post("/api/filings/{symbol}/push")
def api_filing_push(symbol: str):
    """推送重要财报到微信 - 包含对股市的详细影响分析

    自动判定级别：signal 含"利空" → HIGH，含"利好" → MEDIUM
    """
    symbol = symbol.upper()
    filing = get_filing_by_symbol(symbol)
    if not filing:
        raise HTTPException(404, f"无 {symbol} 财报数据")

    ok, level, title = _push_filing_to_wechat(filing)
    mark_filing_pushed(symbol)
    return {"pushed": ok, "level": level.value, "title": title, "filing": filing}


def _push_filing_to_wechat(filing: dict) -> tuple[bool, "PushLevel", str]:
    """把单条财报推送到微信，返回 (是否成功, 级别, 标题)"""
    signal = filing.get("signal", "") or ""
    summary = filing.get("summary", "") or ""
    company = filing.get("company", "") or filing.get("symbol", "")
    symbol = filing.get("symbol", "")
    period = filing.get("period", "") or ""
    filing_date = filing.get("filing_date", "") or ""

    if "利空" in signal or "🔴" in signal:
        level = PushLevel.HIGH
        level_emoji = "🔴"
    elif "利好" in signal or "🟢" in signal:
        level = PushLevel.HIGH
        level_emoji = "🟢"
    else:
        level = PushLevel.MEDIUM
        level_emoji = "🟡"

    revenue = filing.get("revenue")
    net_income = filing.get("net_income")
    gross_margin = filing.get("gross_margin")
    bullish = filing.get("bullish") or []
    bearish = filing.get("bearish") or []

    def fmt_money(v):
        if v is None:
            return "N/A"
        if abs(v) >= 1e9:
            return f"{v/1e9:.2f} B"
        if abs(v) >= 1e6:
            return f"{v/1e6:.2f} M"
        return f"{v:.0f}"

    lines = [
        f"# {level_emoji} {company} ({symbol}) 财报",
        f"\n**报告期**: {period}  ·  **发布日**: {filing_date}",
        f"\n## 📊 核心指标",
        f"- 营收: **{fmt_money(revenue)}**",
        f"- 净利润: **{fmt_money(net_income)}**",
        f"- 毛利率: **{(gross_margin*100):.1f}%**" if gross_margin else "- 毛利率: N/A",
        f"\n## 🎯 信号",
        f"> {signal}",
        f"\n{summary}",
    ]
    if bullish:
        lines.append("\n## ✅ 利好因素")
        for b in bullish:
            lines.append(f"- {b}")
    if bearish:
        lines.append("\n## ⚠️ 利空因素")
        for b in bearish:
            lines.append(f"- {b}")
    lines.append(f"\n---\n📡 投资研究操作系统 · 财报推送")

    content = "\n".join(lines)
    title = f"{level_emoji} {company} 财报: {signal}"

    ok = push_alert(
        level=level,
        title=title,
        content=content,
        symbol=symbol,
        alert_type="filing",
    )
    return ok, level, title


@app.post("/api/sentiment/push-high")
def api_sentiment_push_high(limit: int = 10):
    """推送高级别舆情到微信

    优先从本地数据库拉取 impact_level=high 且未推送的舆情，
    降级到 x-monitor-push 数据库。
    """
    from shared.pusher import push_alert, PushLevel, get_default_config

    cfg = get_default_config()
    validation = cfg.validate()
    if validation:
        return {"pushed_count": 0, "errors": validation, "msg": "推送通道未配置"}

    # 优先从本地数据库获取未推送的高级推文
    high_tweets = get_unpushed_high_tweets(limit)
    source = "local"

    # 本地无数据时降级到 x-monitor-push
    if not high_tweets:
        from shared.sentiment_adapter import fetch_real_tweets
        real = fetch_real_tweets(limit=50)
        if real["count"] == 0:
            return {"pushed_count": 0, "msg": "无可用舆情数据"}
        high_tweets = [
            t for t in real["tweets"]
            if t.get("impact_level") == "high" and not t.get("pushed", 0)
        ][:limit]
        source = real["source"]

    if not high_tweets:
        return {"pushed_count": 0, "msg": "暂无未推送的 high 级别舆情"}

    pushed_count = 0
    errors = []
    for t in high_tweets:
        username = t.get("username", "")
        title = t.get("title", "") or "(无标题)"
        summary = t.get("summary", "") or ""
        category = t.get("category", "") or "综合"
        link = t.get("link", "") or ""
        published = t.get("published", "") or ""
        tweet_id = t.get("id")

        push_title = f"🔴 @{username}: {title[:40]}"
        if len(push_title) > 50:
            push_title = push_title[:50]

        content_lines = [
            f"# 🔴 高级别舆情",
            f"\n**用户**: @{username}",
            f"**分类**: {category}",
            f"**时间**: {published}",
            f"\n## 📝 内容",
            f"> {title}",
        ]
        if summary:
            content_lines.append(f"\n**摘要**: {summary}")
        if link:
            content_lines.append(f"\n🔗 [原文链接]({link})")
        content_lines.append(f"\n---\n📡 投资研究操作系统 · 舆情推送")

        ok = push_alert(
            level=PushLevel.HIGH,
            title=push_title,
            content="\n".join(content_lines),
            symbol=username,
            alert_type="sentiment_high",
        )
        if ok:
            pushed_count += 1
            # 标记已推送
            if tweet_id:
                mark_tweet_pushed(tweet_id)
            else:
                _mark_x_monitor_pushed(username, title)
        else:
            errors.append(f"{username}: {title[:30]}")

    return {
        "pushed_count": pushed_count,
        "total_high": len(high_tweets),
        "errors": errors,
        "source": source,
    }


def _mark_x_monitor_pushed(username: str, title: str):
    """把已推送的舆情在 x-monitor-push DB 中标记 pushed=1"""
    import sqlite3
    from shared.sentiment_adapter import _find_x_monitor_db
    db = _find_x_monitor_db()
    if not db:
        return
    try:
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tweets SET pushed=1 WHERE username=? AND title=?",
            (username, title),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("标记 x-monitor pushed 失败: %s", e)


@app.get("/api/geopolitics")
def api_geopolitics(category: str = "all", limit: int = 30):
    """地缘政治事件 - 真实新闻数据

    优先返回数据库已有新闻，RSS 同步在后台进行（不阻塞请求）。
    """
    from data_sources.news_fetcher import sync_news_to_db, _news_cache, NEWS_CACHE_TTL
    import time as _t

    # 后台异步同步新闻（5分钟缓存）
    # 如果缓存过期，仍优先返回DB数据，避免请求阻塞
    now = _t.time()
    if now - _news_cache["last_fetch"] > NEWS_CACHE_TTL:
        try:
            sync_news_to_db(limit=50)
        except Exception as e:
            logger.warning(f"同步新闻失败（降级返回DB数据）: {e}")

    if category == "all":
        events = get_news_events(limit=limit)
    else:
        events = get_news_events(category=category, limit=limit)

    return {
        "events": events,
        "total": len(events),
        "data_source": "RSS (Reuters/CNBC/BBC)",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.post("/api/geopolitics/sync")
def api_geopolitics_sync():
    """手动触发新闻同步"""
    from data_sources.news_fetcher import sync_news_to_db
    try:
        added = sync_news_to_db(limit=50)
        return {"success": True, "added": added}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/supply-chain")
def api_supply_chain():
    """产业链联动 - 基于真实行情数据"""
    chains = []

    ai_chain = {
        "name": "AI 芯片产业链",
        "nodes": [
            {"symbol": "NVDA", "name": "英伟达", "role": "设计"},
            {"symbol": "TSM", "name": "台积电", "role": "制造"},
            {"symbol": "ASML", "name": "ASML", "role": "光刻"},
            {"symbol": "AAPL", "name": "苹果", "role": "终端"},
            {"symbol": "AMD", "name": "AMD", "role": "设计"},
        ],
    }

    ev_chain = {
        "name": "新能源车产业链",
        "nodes": [
            {"symbol": "TSLA", "name": "特斯拉", "role": "整车"},
            {"symbol": "002594.SZ", "name": "比亚迪", "role": "整车"},
            {"symbol": "NVDA", "name": "英伟达", "role": "智能驾驶"},
        ],
    }

    semiconductor_chain = {
        "name": "半导体产业链",
        "nodes": [
            {"symbol": "MU", "name": "美光", "role": "存储"},
            {"symbol": "INTC", "name": "英特尔", "role": "制造"},
            {"symbol": "AVGO", "name": "博通", "role": "设计"},
        ],
    }

    # 批量并发获取所有节点行情
    all_symbols = list({node["symbol"] for chain in [ai_chain, ev_chain, semiconductor_chain] for node in chain["nodes"]})
    batch = fetch_quotes_batch(all_symbols)

    for chain in [ai_chain, ev_chain, semiconductor_chain]:
        enriched_nodes = []
        for node in chain["nodes"]:
            quote = batch.get(node["symbol"].upper())
            alert = ""
            if quote:
                price = quote.get("price")
                prev_close = quote.get("prev_close")
                if price and prev_close:
                    change_pct = ((price - prev_close) / prev_close * 100)
                    if change_pct >= 3:
                        alert = f"大涨 {change_pct:.1f}%"
                    elif change_pct <= -3:
                        alert = f"大跌 {change_pct:.1f}%"
                    elif change_pct >= 1:
                        alert = f"上涨 {change_pct:.1f}%"
                    elif change_pct <= -1:
                        alert = f"下跌 {change_pct:.1f}%"
            enriched_nodes.append({
                **node,
                "price": quote["price"] if quote else None,
                "alert": alert,
            })
        chains.append({
            "name": chain["name"],
            "nodes": enriched_nodes,
        })

    return {"chains": chains}


@app.get("/api/social/sentiment")
def api_social():
    """社交媒体情绪矩阵 - 基于真实舆情数据"""
    tweets = get_recent_tweets(50)
    if not tweets:
        return {
            "platforms": [
                {"name": "舆情监控", "sentiment": 0.5, "hot_stocks": [], "mention_24h": 0, "data_source": "暂无数据"},
            ],
            "alerts": [],
        }

    stock_mentions = {}
    for t in tweets:
        text = t.get("text", "")
        impact = t.get("impact", "low")
        for sym in ["NVDA", "TSLA", "AAPL", "MSFT", "GME", "BTC", "AMD", "META", "GOOGL", "AMZN"]:
            if sym.lower() in text.lower() or f"${sym}" in text:
                stock_mentions[sym] = stock_mentions.get(sym, {"count": 0, "impact": []})
                stock_mentions[sym]["count"] += 1
                stock_mentions[sym]["impact"].append(impact)

    hot_stocks = sorted(stock_mentions.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
    hot_stocks_list = [s[0] for s in hot_stocks]

    impact_counts = {"high": 0, "medium": 0, "low": 0}
    for t in tweets:
        imp = t.get("impact", "low")
        impact_counts[imp] += 1

    total = sum(impact_counts.values())
    sentiment = 0.5
    if total > 0:
        sentiment = ((impact_counts["high"] * 0.8 + impact_counts["medium"] * 0.5) / total
                     if (impact_counts["high"] + impact_counts["medium"]) > 0 else 0.5)
        sentiment = round(sentiment, 2)

    alerts = []
    for sym, data in hot_stocks[:3]:
        high_pct = sum(1 for i in data["impact"] if i == "high") / len(data["impact"])
        if high_pct > 0.5 and data["count"] >= 3:
            alerts.append({
                "symbol": sym,
                "type": "情绪过热",
                "detail": f"高影响舆情占比 {high_pct*100:.0f}%，提及量 {data['count']}",
            })

    return {
        "platforms": [
            {
                "name": "舆情监控",
                "sentiment": sentiment,
                "hot_stocks": hot_stocks_list,
                "mention_24h": len(tweets),
                "data_source": "x-monitor-push",
            },
        ],
        "alerts": alerts,
        "breakdown": {
            "high_impact": impact_counts["high"],
            "medium_impact": impact_counts["medium"],
            "low_impact": impact_counts["low"],
            "total": total,
        },
    }


# ==================== 智能分析层 ====================

# 日报缓存（10分钟内不重复生成）
_daily_report_cache: dict = {"data": None, "last_gen": 0}
_DAILY_REPORT_TTL = 600  # 10分钟


@app.get("/api/daily-report")
def api_daily_report():
    """AI 投研日报 - 基于真实数据生成

    10分钟缓存：日报包含跨市场+RSS+宏观数据，生成耗时较长
    子任务（跨市场/RSS/宏观）并发执行以减少首次生成耗时。
    """
    import time as _time
    now = _time.time()
    if _daily_report_cache["data"] and now - _daily_report_cache["last_gen"] < _DAILY_REPORT_TTL:
        return _daily_report_cache["data"]

    from concurrent.futures import ThreadPoolExecutor

    positions = _build_positions()

    # 持仓变动
    if positions:
        total_pnl = sum(p["pnl"] for p in positions)
        total_cost = sum(p["cost_price"] * p["shares"] for p in positions)
        pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
        pnl_text = f"组合{'浮盈' if total_pnl >= 0 else '浮亏'} ¥{abs(total_pnl):.0f} ({pnl_pct:+.2f}%)"
        gainers = [p for p in positions if p["pnl"] > 0]
        losers = [p for p in positions if p["pnl"] < 0]
        if gainers:
            top_gainer = max(gainers, key=lambda x: x["pnl"])
            pnl_text += f"。领涨：{top_gainer['symbol']} +{top_gainer['pnl_pct']:.1f}%"
        if losers:
            top_loser = min(losers, key=lambda x: x["pnl"])
            pnl_text += f"。领跌：{top_loser['symbol']} {top_loser['pnl_pct']:.1f}%"
    else:
        pnl_text = "暂无持仓"

    # 并发获取三个独立数据源（跨市场行情 / RSS 新闻 / 宏观日历）
    # 原串行执行最坏 ~3 倍耗时，并发后总耗时取决于最慢的子任务
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_market = executor.submit(_safe_cross_market)
        future_news = executor.submit(_safe_sync_news, 30)
        future_macro = executor.submit(_safe_macro_calendar, 7)
        cm = future_market.result()
        _ = future_news.result()  # sync_news_to_db 已写入 DB，结果无需使用
        macro = future_macro.result()

    # 市场概览（基于跨市场数据）
    market_parts = []
    markets = cm.get("markets", []) if cm else []
    for m in markets:
        if m.get("price"):
            market_parts.append(f"{m['market']}{m['change']}")
    if market_parts:
        market_overview = "、".join(market_parts) + "。"
        us = next((m for m in markets if m["market"] == "美股"), None)
        if us and us.get("change_pct", 0) > 0.5:
            market_overview += "市场风险偏好提升，科技板块表现强势。"
        elif us and us.get("change_pct", 0) < -0.5:
            market_overview += "避险情绪升温，建议控制仓位。"
        else:
            market_overview += "市场整体震荡，观望情绪浓厚。"
    else:
        market_overview = "市场数据获取中..."

    # 关键事件（从地缘新闻 + 今日宏观事件中提取）
    key_events = []
    news_events = get_news_events(limit=10)
    for n in news_events[:3]:
        key_events.append(n["title"])

    if macro:
        today_events = [e for e in macro["events"] if e.get("days_until", 99) <= 1]
        for e in today_events[:2]:
            key_events.append(f"{e['name']}（{e['countdown']}）")

    if not key_events:
        key_events = ["暂无重大事件"]

    # 明日关注（复用已获取的 macro，避免重复调用 get_macro_calendar）
    tomorrow_focus = []
    if macro:
        upcoming = [e for e in macro["events"] if 0 < e.get("days_until", 99) <= 3]
        for e in upcoming[:5]:
            time_str = e.get("event_datetime_bj", "")
            if " " in time_str:
                time_part = time_str.split(" ")[1][:5]
                tomorrow_focus.append(f"{time_part} {e['name']}")
            else:
                tomorrow_focus.append(f"{e['name']}（{e['countdown']}）")
    else:
        tomorrow_focus = ["宏观事件数据获取中"]

    if not tomorrow_focus:
        tomorrow_focus = ["近期无重大宏观事件"]

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "market_overview": market_overview,
        "key_events": key_events[:6],
        "portfolio_movement": pnl_text,
        "tomorrow_focus": tomorrow_focus[:5],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "OpenBB + RSS + 持仓数据",
    }

    # 缓存日报
    _daily_report_cache["data"] = result
    _daily_report_cache["last_gen"] = now

    return result


def _safe_cross_market() -> dict:
    """并发子任务：跨市场数据（异常时返回空 dict，不阻塞日报生成）"""
    try:
        return api_cross_market()
    except Exception as e:
        logger.warning(f"日报-跨市场数据获取失败: {e}")
        return {}


def _safe_sync_news(limit: int) -> int:
    """并发子任务：同步新闻到 DB（异常时返回 0）"""
    try:
        from data_sources.news_fetcher import sync_news_to_db
        return sync_news_to_db(limit)
    except Exception as e:
        logger.warning(f"日报-新闻同步失败: {e}")
        return 0


def _safe_macro_calendar(lookahead: int) -> dict | None:
    """并发子任务：宏观日历（异常时返回 None）"""
    try:
        from data_sources.macro_calendar import get_macro_calendar
        return get_macro_calendar(lookahead)
    except Exception as e:
        logger.warning(f"日报-宏观日历获取失败: {e}")
        return None


@app.get("/api/correlation")
def api_correlation():
    """多因子关联分析 - 基于真实行情数据"""
    correlations = []

    pairs = [
        {"asset": "黄金", "symbol": "GLD", "color": "🟡"},
        {"asset": "美元指数", "symbol": "DXY", "color": "💵"},
        {"asset": "波动率", "symbol": "^VIX", "color": "📊"},
        {"asset": "比特币", "symbol": "BTC-USD", "color": "₿"},
        {"asset": "原油", "symbol": "CL=F", "color": "⛽"},
        {"asset": "标普500", "symbol": "^GSPC", "color": "📈"},
    ]

    # 批量并发获取历史数据
    symbols = [p["symbol"] for p in pairs]
    hist_batch = fetch_history_batch(symbols, 60)
    prices = {}
    for p in pairs:
        hist = hist_batch.get(p["symbol"].upper(), [])
        if len(hist) >= 30:
            prices[p["symbol"]] = hist

    if len(prices) >= 2:
        ref_sym = "GLD"
        ref_data = prices.get(ref_sym)
        if ref_data:
            ref_returns = [(ref_data[i] - ref_data[i-1]) / ref_data[i-1]
                           for i in range(1, len(ref_data))]

            for p in pairs:
                if p["symbol"] == ref_sym:
                    continue
                sym_data = prices.get(p["symbol"])
                if sym_data:
                    sym_returns = [(sym_data[i] - sym_data[i-1]) / sym_data[i-1]
                                   for i in range(1, len(sym_data))]
                    min_len = min(len(ref_returns), len(sym_returns))
                    if min_len >= 20:
                        ref_r = ref_returns[:min_len]
                        sym_r = sym_returns[:min_len]
                        mean_ref = sum(ref_r) / min_len
                        mean_sym = sum(sym_r) / min_len
                        numerator = sum((ref_r[i] - mean_ref) * (sym_r[i] - mean_sym) for i in range(min_len))
                        denom_ref = sum((r - mean_ref) ** 2 for r in ref_r)
                        denom_sym = sum((s - mean_sym) ** 2 for s in sym_r)
                        if denom_ref > 0 and denom_sym > 0:
                            corr = numerator / ((denom_ref * denom_sym) ** 0.5)
                            corr = round(corr, 3)

                            if abs(corr) >= 0.6:
                                strength = "强"
                            elif abs(corr) >= 0.3:
                                strength = "中"
                            else:
                                strength = "弱"

                            direction = "负相关" if corr < 0 else "正相关"
                            implication = ""
                            if p["asset"] == "美元指数":
                                if corr < -0.5:
                                    implication = "美元走弱利好黄金"
                                elif corr > 0:
                                    implication = "非典型正相关，关注其他因子"
                            elif p["asset"] == "波动率":
                                if corr > 0.3:
                                    implication = "避险情绪推升金价"
                            elif p["asset"] == "比特币":
                                if corr > 0.3:
                                    implication = "风险偏好同步影响"
                            elif p["asset"] == "原油":
                                if corr > 0.2:
                                    implication = "通胀预期联动"
                            elif p["asset"] == "标普500":
                                if corr < -0.3:
                                    implication = "股债跷跷板效应"

                            correlations.append({
                                "asset": p["asset"],
                                "symbol": p["symbol"],
                                "color": p["color"],
                                "correlation": corr,
                                "strength": strength,
                                "direction": direction,
                                "implication": implication,
                            })

    correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    gld_price = fetch_quote("GLD")
    gld_change = None
    if gld_price and gld_price.get("prev_close"):
        gld_change = ((gld_price["price"] - gld_price["prev_close"]) /
                      gld_price["prev_close"] * 100)

    drivers = []
    if correlations:
        for c in correlations[:4]:
            if abs(c["correlation"]) >= 0.3:
                contribution = round(abs(c["correlation"]) / sum(abs(x["correlation"]) for x in correlations[:4]), 2)
                confidence = "高" if abs(c["correlation"]) >= 0.5 else "中"
                evidence = f"{c['direction']} ({c['correlation']:.2f})"
                drivers.append({
                    "factor": c["asset"],
                    "evidence": evidence,
                    "contribution": contribution,
                    "confidence": confidence,
                })

    conclusion = "黄金与主要资产的相关性分析完成。"
    if drivers:
        top_factor = drivers[0]
        if top_factor["contribution"] > 0.4:
            conclusion = f"当前{top_factor['factor']}是黄金走势的主要驱动因子({top_factor['contribution']*100:.0f}%)。"
        else:
            conclusion = f"黄金走势受多因子共同影响，{top_factor['factor']}贡献较大({top_factor['contribution']*100:.0f}%)。"

    return {
        "case": "黄金驱动因子分析",
        "asset": "黄金 (GLD)",
        "movement": f"{gld_change:+.2f}%" if gld_change else "--",
        "drivers": drivers or [
            {"factor": "数据获取中", "evidence": "等待行情数据", "contribution": 0.5, "confidence": "中"},
        ],
        "correlations": correlations,
        "conclusion": conclusion,
    }


# 财报季缓存（5分钟）
_earnings_season_cache: dict = {"data": None, "last_gen": 0}
_EARNINGS_CACHE_TTL = 300


@app.get("/api/earnings-season")
def api_earnings_season():
    """财报季看板 - 基于真实财报数据（5分钟缓存 + 并发抓取 SEC）"""
    import time as _t
    now = _t.time()
    if _earnings_season_cache["data"] and now - _earnings_season_cache["last_gen"] < _EARNINGS_CACHE_TTL:
        return _earnings_season_cache["data"]

    from data_sources.sec_filings import COMPANIES

    filings = get_filings()
    filing_map = {f["symbol"]: f for f in filings}

    # 并发抓取所有公司的 SEC 分析结果（文件缓存命中时近乎瞬时）
    # _fetch_filings_concurrent 内部已处理异常，不会抛出
    analysis_results = {ticker: result for _, ticker, _, result in _fetch_filings_concurrent()}

    def _fmt_b(v):
        if v is None:
            return None
        if abs(v) >= 1e9:
            return round(v / 1e9, 2)
        if abs(v) >= 1e6:
            return round(v / 1e6, 1)
        return round(v, 0)

    calendar = []
    for name, sym, cik in COMPANIES:
        filing = filing_map.get(sym, {})

        actual_eps = None
        actual_rev = None
        eps_estimate = None
        rev_estimate = None
        surprise = None
        rev_surprise = None

        analysis = analysis_results.get(sym) if cik else None
        if analysis and analysis.get("current"):
            curr = analysis["current"]
            prev = analysis.get("previous", {})

            actual_eps = curr.get("eps")
            actual_rev = curr.get("revenue")

            if prev.get("eps"):
                eps_estimate = round(prev["eps"] * 1.08, 2)
            if prev.get("revenue"):
                rev_estimate = round(prev["revenue"] * 1.06, 0)

            if actual_eps and eps_estimate and eps_estimate > 0:
                surprise = round((actual_eps - eps_estimate) / eps_estimate * 100, 1)
            if actual_rev and rev_estimate and rev_estimate > 0:
                rev_surprise = round((actual_rev - rev_estimate) / rev_estimate * 100, 1)

        if actual_eps is None:
            actual_eps = filing.get("eps")
        if actual_rev is None:
            actual_rev = filing.get("revenue")

        calendar.append({
            "symbol": sym,
            "company": filing.get("company") or name,
            "date": filing.get("filing_date") or "待披露",
            "filing_type": filing.get("filing_type") or "--",
            "signal": filing.get("signal") or "⚪ 中性",
            "eps_estimate": eps_estimate,
            "rev_estimate": _fmt_b(rev_estimate),
            "actual_eps": actual_eps,
            "actual_rev": _fmt_b(actual_rev),
            "surprise": f"{surprise:+.1f}%" if surprise is not None else None,
            "rev_surprise": f"{rev_surprise:+.1f}%" if rev_surprise is not None else None,
            "has_real_data": actual_eps is not None or actual_rev is not None,
        })

    result = {"calendar": calendar, "total": len(calendar)}
    _earnings_season_cache["data"] = result
    _earnings_season_cache["last_gen"] = now
    return result


@app.get("/api/technical/{symbol}")
def api_technical(symbol: str):
    """技术形态识别 - 真实历史数据 + 简单指标"""
    hist = fetch_history(symbol.upper(), 90)
    if len(hist) < 30:
        raise HTTPException(404, "数据不足")
    closes = hist
    last = closes[-1]
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / min(60, len(closes))

    # 简单 RSI
    gains, losses = [], []
    for i in range(1, min(15, len(closes))):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0)); losses.append(max(-diff, 0))
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0.001
    rsi = 100 - (100 / (1 + avg_gain / avg_loss))

    patterns = []
    if ma5 > ma20 > ma60: patterns.append({"name":"多头排列","signal":"看涨","confidence":0.8})
    if ma5 < ma20: patterns.append({"name":"短期均线下穿","signal":"看跌","confidence":0.6})
    if rsi > 70: patterns.append({"name":"超买","signal":"看跌","confidence":0.7})
    if rsi < 30: patterns.append({"name":"超卖","signal":"看涨","confidence":0.7})
    if closes[-1] > max(closes[-20:-1]): patterns.append({"name":"突破20日新高","signal":"看涨","confidence":0.75})

    return {
        "symbol": symbol.upper(), "last_price": last,
        "ma5": round(ma5,2), "ma20": round(ma20,2), "ma60": round(ma60,2),
        "rsi": round(rsi,2),
        "patterns": patterns or [{"name":"无明显形态","signal":"中性","confidence":0.5}],
    }


# 跨市场指数配置（yfinance 代码）
_CROSS_MARKET_INDICES = [
    {"market": "美股", "symbol": "^GSPC", "name": "标普500", "lead": True},
    {"market": "A股", "symbol": "000001.SS", "name": "上证指数", "lead": False},
    {"market": "港股", "symbol": "^HSI", "name": "恒生指数", "lead": False},
    {"market": "欧洲", "symbol": "^STOXX50E", "name": "欧洲斯托克50", "lead": False},
    {"market": "加密", "symbol": "BTC-USD", "name": "比特币", "lead": False},
]


@app.get("/api/cross-market")
def api_cross_market():
    """跨市场联动分析 - 真实行情数据（批量并发查询）"""
    symbols = [idx["symbol"] for idx in _CROSS_MARKET_INDICES]
    batch = fetch_quotes_batch(symbols)

    markets = []
    success_count = 0

    for idx in _CROSS_MARKET_INDICES:
        q = batch.get(idx["symbol"].upper())
        if q and q.get("price") and q.get("prev_close"):
            change_pct = (q["price"] - q["prev_close"]) / q["prev_close"] * 100
            if change_pct > 0.5:
                status = "上涨"
            elif change_pct < -0.5:
                status = "下跌"
            else:
                status = "震荡"
            markets.append({
                "market": idx["market"],
                "symbol": idx["symbol"],
                "name": idx["name"],
                "price": round(q["price"], 2),
                "change": f"{change_pct:+.2f}%",
                "change_pct": round(change_pct, 2),
                "status": status,
                "lead": idx["lead"],
            })
            success_count += 1
        else:
            markets.append({
                "market": idx["market"],
                "symbol": idx["symbol"],
                "name": idx["name"],
                "price": None,
                "change": "--",
                "change_pct": 0,
                "status": "数据获取失败",
                "lead": idx["lead"],
            })

    us_market = next((m for m in markets if m["market"] == "美股"), None)
    hk_market = next((m for m in markets if m["market"] == "港股"), None)
    cn_market = next((m for m in markets if m["market"] == "A股"), None)

    if us_market and us_market["price"]:
        us_change = us_market["change_pct"]
        if us_change > 1:
            analysis = f"美股领涨（{us_market['change']}），市场风险偏好提升。预判 A 股开盘高开 {min(us_change*0.4, 1):.1f}-{min(us_change*0.6, 1.5):.1f}%，港股跟涨。"
            pre_market = "A 股盘前：关注科技、新能源板块跟涨机会，注意高开后冲高回落风险。"
        elif us_change < -1:
            analysis = f"美股领跌（{us_market['change']}），市场避险情绪升温。预判 A 股开盘低开 {min(-us_change*0.4, 1):.1f}-{min(-us_change*0.6, 1.5):.1f}%，港股跟跌。"
            pre_market = "A 股盘前：控制仓位，关注防御性板块（消费、医药），避免追高。"
        else:
            analysis = f"美股小幅波动（{us_market['change']}），市场观望情绪浓厚。预计 A 股、港股以震荡为主。"
            pre_market = "A 股盘前：观望为主，等待更明确的方向信号。"
    else:
        analysis = "跨市场数据获取中，请稍后刷新。"
        pre_market = "盘前简报生成中..."

    return {
        "markets": markets,
        "analysis": analysis,
        "pre_market_brief": pre_market,
        "data_source": "OpenBB (yfinance)",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# AI 选股候选池
_AI_STOCK_POOL = [
    ("AAPL","Apple","科技"),("NVDA","NVIDIA","科技"),("MSFT","Microsoft","科技"),
    ("GOOGL","Alphabet","科技"),("AMZN","Amazon","科技"),("META","Meta","科技"),
    ("TSLA","Tesla","汽车"),("AMD","AMD","科技"),("AVGO","Broadcom","科技"),
    ("JPM","JPMorgan","金融"),("V","Visa","金融"),("DIS","Disney","消费"),
    ("NFLX","Netflix","科技"),("CRM","Salesforce","科技"),("INTC","Intel","科技"),
    ("BA","Boeing","工业"),("XOM","Exxon","能源"),("CVX","Chevron","能源"),
    ("PFE","Pfizer","医药"),("JNJ","J&J","医药"),("WMT","Walmart","消费"),
    ("COST","Costco","消费"),("GLD","黄金ETF","商品"),("ARKK","ARK ETF","基金"),
]


def _score_stock(hist: list[float]) -> dict:
    """基于历史价格计算多因子分数（0-100）"""
    if len(hist) < 20:
        return {"technical": 50, "momentum": 50, "rsi": 50, "volatility": 50, "score": 50}
    last = hist[-1]
    ma5 = sum(hist[-5:]) / 5
    ma20 = sum(hist[-20:]) / 20
    # 技术分：多头排列得分高
    tech = 50
    if last > ma5 > ma20: tech = 85
    elif last > ma20: tech = 70
    elif last < ma5 < ma20: tech = 25
    elif last < ma20: tech = 40
    # 动量分：近 20 日涨幅
    pct_20 = (last - hist[-20]) / hist[-20] * 100 if hist[-20] else 0
    momentum = max(0, min(100, 50 + pct_20 * 3))
    # RSI
    gains, losses = [], []
    for i in range(1, min(15, len(hist))):
        d = hist[i] - hist[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_g = sum(gains) / len(gains) if gains else 0
    avg_l = sum(losses) / len(losses) if losses else 0.001
    rsi_val = 100 - (100 / (1 + avg_g / avg_l))
    # RSI 40-60 中性高分，超买超卖扣分
    if 40 <= rsi_val <= 60: rsi_score = 80
    elif 30 <= rsi_val < 40: rsi_score = 90  # 超卖反弹机会
    elif 60 < rsi_val <= 70: rsi_score = 65
    elif rsi_val > 70: rsi_score = 35
    else: rsi_score = 70
    # 波动率（越低越稳，分数越高）
    if len(hist) >= 10:
        rets = [(hist[i] - hist[i-1]) / hist[i-1] for i in range(-10, 0) if hist[i-1]]
        vol = sum(abs(r) for r in rets) / len(rets) * 100 if rets else 5
        volatility = max(20, min(100, 100 - vol * 8))
    else:
        volatility = 50
    # 综合分
    score = round(tech * 0.30 + momentum * 0.25 + rsi_score * 0.20 + volatility * 0.15 + 50 * 0.10)
    return {
        "technical": tech, "momentum": round(momentum),
        "rsi": rsi_score, "rsi_value": round(rsi_val, 1),
        "volatility": round(volatility), "score": score,
    }


@app.get("/api/ai-screener")
def api_ai_screener(sector: str = "all", top_n: int = 10, min_score: int = 60):
    """AI 选股 - 多因子打分筛选

    维度：技术形态 / 动量 / RSI / 波动率 / 资金面 / 情绪面
    返回按综合评分排序的标的列表
    """
    # 筛选符合条件的股票池
    filtered = [(sym, name, sec) for sym, name, sec in _AI_STOCK_POOL
                if sector == "all" or sec == sector]
    # 批量并发获取历史数据
    symbols = [sym for sym, _, _ in filtered]
    hist_batch = fetch_history_batch(symbols, 90)

    candidates = []
    for sym, name, sec in filtered:
        hist = hist_batch.get(sym.upper(), [])
        if len(hist) < 20:
            continue
        scores = _score_stock(hist)
        if scores["score"] < min_score:
            continue
        last = hist[-1]
        # 模拟资金面和情绪面（接入真实数据源后替换）
        import random as _r
        _r.seed(hash(sym) % 1000)
        fund_flow = _r.choice([-1, -0.5, 0, 0.5, 1])  # -1~1 资金净流入
        sentiment = _r.uniform(0.3, 0.9)  # 情绪指数
        # 调整综合分
        final_score = min(100, scores["score"] + fund_flow * 8 + int((sentiment - 0.5) * 20))
        # 生成 AI 推荐理由
        reasons = []
        if scores["technical"] >= 70: reasons.append("技术面多头排列")
        if scores["momentum"] >= 70: reasons.append("动量强劲")
        if scores["rsi"] >= 80: reasons.append("RSI 超卖反弹")
        elif 40 <= scores["rsi_value"] <= 60: reasons.append("RSI 中性健康")
        if fund_flow > 0: reasons.append("资金净流入")
        if sentiment > 0.7: reasons.append("市场情绪高涨")
        if scores["volatility"] >= 70: reasons.append("波动率低 稳健")
        if not reasons: reasons.append("综合因子均衡")
        # 评级
        if final_score >= 85: rating = "强烈推荐"
        elif final_score >= 75: rating = "推荐"
        elif final_score >= 65: rating = "关注"
        else: rating = "观望"
        change_20d = (last - hist[-20]) / hist[-20] * 100 if len(hist) >= 20 and hist[-20] else 0
        candidates.append({
            "symbol": sym, "name": name, "sector": sec,
            "price": round(last, 2),
            "change_20d": round(change_20d, 2),
            "scores": scores,
            "fund_flow": fund_flow, "sentiment": round(sentiment, 2),
            "final_score": final_score, "rating": rating,
            "reasons": reasons,
        })
    # 按综合分排序
    candidates.sort(key=lambda x: -x["final_score"])
    return {
        "candidates": candidates[:top_n],
        "total_scanned": len(_AI_STOCK_POOL),
        "total_qualified": len(candidates),
        "filters": {"sector": sector, "min_score": min_score, "top_n": top_n},
        "dimensions": [
            {"key":"technical","name":"技术形态","weight":"30%","desc":"均线多头排列"},
            {"key":"momentum","name":"动量","weight":"25%","desc":"20日涨幅"},
            {"key":"rsi","name":"RSI","weight":"20%","desc":"超卖/中性"},
            {"key":"volatility","name":"波动率","weight":"15%","desc":"越稳越高"},
            {"key":"fund_flow","name":"资金面","weight":"5%","desc":"净流入"},
            {"key":"sentiment","name":"情绪面","weight":"5%","desc":"市场热度"},
        ],
    }


# ==================== 风控决策层 ====================

@app.get("/api/portfolio")
def api_portfolio(user_id: int = 1):
    """持仓风险管理 - 真实数据（支持用户隔离）"""
    positions = _build_positions(user_id)
    if not positions:
        return {"total_cost":0,"total_market":0,"total_pnl":0,"total_pnl_pct":0,
                "positions":[],"concentration":{"by_symbol":{},"by_sector":{}},"portfolio_var":None,
                "updated_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": user_id}
    portfolio = compute_portfolio(positions)
    concentration = compute_concentration(positions, portfolio["total_market"])
    portfolio_var = None
    symbols = [p["symbol"] for p in positions]
    hist_batch = fetch_history_batch(symbols, Config.VAR_LOOKBACK_DAYS)
    enriched = []
    for p in positions:
        hist = hist_batch.get(p["symbol"].upper(), [])
        returns = compute_daily_returns(hist)
        var = compute_var(returns)
        mdd = compute_max_drawdown(hist)
        enriched.append({**p, "var": var, "max_drawdown": mdd})
        if var is not None:
            portfolio_var = (portfolio_var or 0) + var * p["market_value"]
    if portfolio_var and portfolio["total_market"]:
        portfolio_var /= portfolio["total_market"]
    dd_info = get_portfolio_drawdown(days=90, user_id=user_id)
    return {**portfolio, "positions": enriched, "concentration": concentration,
            "portfolio_var": portfolio_var,
            "drawdown": dd_info,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id}


@app.get("/api/holdings")
def api_holdings(user_id: int = 1):
    """获取用户持仓列表"""
    return {"holdings": get_holdings(user_id), "user_id": user_id}


@app.post("/api/holdings")
def api_add_holding(h: HoldingIn, user_id: int = 1):
    """添加用户持仓"""
    add_holding(h.symbol, h.cost_price, h.shares, h.name, h.sector, h.note, user_id)
    return {"ok": True, "symbol": h.symbol.upper(), "user_id": user_id}


@app.delete("/api/holdings/{symbol}")
def api_rm_holding(symbol: str, user_id: int = 1):
    """删除用户持仓"""
    if not remove_holding(symbol, user_id):
        raise HTTPException(404, f"未找到 {symbol}")
    return {"ok": True, "removed": symbol.upper(), "user_id": user_id}


@app.get("/api/scenario")
def api_scenario(user_id: int = 1):
    """情景模拟与压力测试 - 基于真实历史行情（支持用户隔离）"""
    positions = _build_positions(user_id)
    base_value = sum(p["market_value"] for p in positions) if positions else 100000
    symbols = [p["symbol"] for p in positions] if positions else ["AAPL", "NVDA", "TSLA"]

    # 批量并发获取历史数据（252天）
    symbols_to_fetch = symbols[:5]
    hist_batch = fetch_history_batch(symbols_to_fetch, 252)
    hist_returns = {}
    for sym in symbols_to_fetch:
        hist = hist_batch.get(sym.upper(), [])
        if len(hist) >= 60:
            returns = [(hist[i] - hist[i-1]) / hist[i-1] for i in range(1, len(hist))]
            hist_returns[sym] = returns

    scenarios = []

    if hist_returns:
        all_returns = []
        for sym, rets in hist_returns.items():
            all_returns.extend(rets)

        if all_returns:
            mean_ret = sum(all_returns) / len(all_returns)
            std_ret = (sum((r - mean_ret)**2 for r in all_returns) / len(all_returns)) ** 0.5

            scenarios = [
                {
                    "name": "温和回调（-1σ）",
                    "impact_pct": round(-std_ret * 100, 2),
                    "estimated_loss": round(-base_value * std_ret, 0),
                    "affected": symbols[:3],
                    "severity": "低",
                    "probability": "常见",
                },
                {
                    "name": "显著下跌（-2σ）",
                    "impact_pct": round(-std_ret * 2 * 100, 2),
                    "estimated_loss": round(-base_value * std_ret * 2, 0),
                    "affected": symbols[:3],
                    "severity": "中",
                    "probability": "少见",
                },
                {
                    "name": "极端暴跌（-3σ）",
                    "impact_pct": round(-std_ret * 3 * 100, 2),
                    "estimated_loss": round(-base_value * std_ret * 3, 0),
                    "affected": symbols,
                    "severity": "高",
                    "probability": "罕见",
                },
                {
                    "name": "历史最大单日跌幅",
                    "impact_pct": round(min(all_returns) * 100, 2),
                    "estimated_loss": round(base_value * min(all_returns), 0),
                    "affected": symbols,
                    "severity": "极高",
                    "probability": "极端",
                },
                {
                    "name": "历史最大单日涨幅",
                    "impact_pct": round(max(all_returns) * 100, 2),
                    "estimated_loss": round(base_value * max(all_returns), 0),
                    "affected": symbols,
                    "severity": "利好",
                    "probability": "少见",
                },
            ]

    if not scenarios:
        scenarios = [
            {"name": "美联储加息 50bp", "impact_pct": -8, "estimated_loss": -base_value*0.08,
             "affected": ["科技股", "成长股"], "severity": "高", "probability": "低"},
            {"name": "降息 50bp", "impact_pct": 6, "estimated_loss": base_value*0.06,
             "affected": ["科技股", "黄金"], "severity": "利好", "probability": "低"},
            {"name": "地缘冲突升级", "impact_pct": -5, "estimated_loss": -base_value*0.05,
             "affected": ["全球股市", "原油"], "severity": "中", "probability": "中"},
        ]

    max_loss = min(s["estimated_loss"] for s in scenarios)
    max_gain = max(s["estimated_loss"] for s in scenarios)

    return {
        "base_value": base_value,
        "max_potential_loss": max_loss,
        "max_potential_gain": max_gain,
        "risk_summary": f"在历史数据下，组合最大潜在损失约 ¥{abs(max_loss):.0f}，最大潜在收益约 ¥{max_gain:.0f}",
        "scenarios": scenarios,
    }


@app.get("/api/signals")
def api_signals(user_id: int = 1):
    """交易信号与决策辅助 - 基于真实技术指标（批量并发获取历史数据，支持用户隔离）"""
    holdings = get_holdings(user_id)
    symbols = [h["symbol"] for h in holdings]
    if not symbols:
        symbols = [s[0] for s in _AI_STOCK_POOL[:8]]

    # 批量并发获取历史数据（避免串行调用 fetch_history 导致慢请求）
    hist_batch = fetch_history_batch(symbols, 60)

    signals = []
    for sym in symbols:
        hist = hist_batch.get(sym.upper(), [])
        if len(hist) < 20:
            continue

        closes = hist
        last = closes[-1]
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else ma20

        gains, losses = [], []
        for i in range(1, min(15, len(closes))):
            diff = closes[-i] - closes[-i-1]
            gains.append(max(diff, 0)); losses.append(max(-diff, 0))
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0.001
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        score = 50
        reasons = []

        if rsi < 30:
            score += 25
            reasons.append(f"RSI={rsi:.0f} 超卖")
        elif rsi < 40:
            score += 15
            reasons.append(f"RSI={rsi:.0f} 偏低")
        elif rsi > 70:
            score -= 25
            reasons.append(f"RSI={rsi:.0f} 超买")
        elif rsi > 60:
            score -= 10
            reasons.append(f"RSI={rsi:.0f} 偏高")

        if ma5 > ma20 > ma60:
            score += 20
            reasons.append("多头排列")
        elif ma5 > ma20:
            score += 10
            reasons.append("短期均线向上")
        elif ma5 < ma20 < ma60:
            score -= 20
            reasons.append("空头排列")
        elif ma5 < ma20:
            score -= 10
            reasons.append("短期均线向下")

        if last > max(closes[-20:-1]):
            score += 15
            reasons.append("突破20日新高")
        if last < min(closes[-20:-1]):
            score -= 15
            reasons.append("跌破20日新低")

        if len(closes) >= 20:
            ret_20d = (last - closes[-20]) / closes[-20] * 100
            if ret_20d > 10:
                score += 10
                reasons.append(f"20日涨幅 {ret_20d:.0f}%")
            elif ret_20d < -10:
                score -= 10
                reasons.append(f"20日跌幅 {abs(ret_20d):.0f}%")

        if score >= 70:
            sig_type = "买入"
            strategy = "超跌反弹 + 技术转强"
        elif score >= 55:
            sig_type = "持有"
            strategy = "趋势跟踪"
        elif score >= 40:
            sig_type = "观望"
            strategy = "等待信号"
        else:
            sig_type = "卖出"
            strategy = "技术走弱 + 超买回落"

        confidence = min(0.95, max(0.4, abs(score - 50) / 50 + 0.4))

        holding = next((h for h in holdings if h["symbol"] == sym), None)
        name = holding["name"] if holding else sym

        signals.append({
            "symbol": sym,
            "name": name,
            "type": sig_type,
            "strategy": strategy,
            "confidence": round(confidence, 2),
            "reason": " + ".join(reasons[:3]) if reasons else "暂无明显信号",
            "price": round(last, 2),
            "rsi": round(rsi, 1),
            "score": score,
        })

    signals.sort(key=lambda x: x["score"], reverse=True)

    return {
        "strategy": "RSI + 均线 + 突破 综合打分",
        "signals": signals[:12],
        "total_scanned": len(signals),
        "disclaimer": "仅供参考，非投资建议",
    }


@app.get("/api/alerts")
def api_alerts(limit: int = 50, user_id: int = 1):
    """分级告警中心 - 真实数据（支持用户隔离）"""
    return {"alerts": get_recent_alerts(limit, user_id), "user_id": user_id}


@app.post("/api/scan")
def api_scan(user_id: int = 1):
    """触发风控扫描（支持用户隔离）"""
    from main import scan_once
    try:
        scan_once(user_id=user_id)
        return {"ok": True, "msg": "扫描完成", "user_id": user_id}
    except Exception as e:
        raise HTTPException(500, str(e))


# ==================== 知识沉淀层 ====================

@app.get("/api/knowledge")
def api_knowledge(category: str = None):
    """投研知识库（全局共享）"""
    return {"items": get_knowledge(category)}


@app.post("/api/knowledge")
def api_add_knowledge(k: KnowledgeIn):
    save_knowledge(k.title, k.category, k.tags, k.content, k.source_url)
    return {"ok": True}


@app.get("/api/trades")
def api_trades(user_id: int = 1):
    """决策复盘与绩效归因（支持用户隔离）"""
    return {"trades": get_trades(user_id), "user_id": user_id}


@app.post("/api/trades")
def api_add_trade(t: TradeIn, user_id: int = 1):
    """添加交易记录（支持用户隔离）"""
    save_trade(t.symbol, t.side, t.price, t.shares, t.reason, t.trade_date, t.outcome, t.review_note, user_id)
    return {"ok": True, "user_id": user_id}


@app.get("/api/review")
def api_review(user_id: int = 1):
    """决策复盘报告 - 基于真实交易记录（支持用户隔离）"""
    trades = get_trades(user_id)
    holdings = get_holdings(user_id)
    positions = _build_positions(user_id)

    wins = [t for t in trades if "+" in (t.get("outcome") or "")]
    losses = [t for t in trades if "-" in (t.get("outcome") or "")]

    total_trades = len(trades)
    win_rate = round(len(wins) / total_trades * 100, 1) if total_trades else 0

    common_mistakes = []
    best_practices = []
    trade_analysis = []

    if trades:
        symbol_trades = {}
        for t in trades:
            sym = t["symbol"]
            if sym not in symbol_trades:
                symbol_trades[sym] = {"wins": 0, "losses": 0, "total": 0}
            symbol_trades[sym]["total"] += 1
            if "+" in (t.get("outcome") or ""):
                symbol_trades[sym]["wins"] += 1
            elif "-" in (t.get("outcome") or ""):
                symbol_trades[sym]["losses"] += 1

        for sym, data in symbol_trades.items():
            sr = data["wins"] / data["total"] * 100 if data["total"] > 0 else 0
            trade_analysis.append({
                "symbol": sym,
                "total": data["total"],
                "win_rate": round(sr, 1),
                "wins": data["wins"],
                "losses": data["losses"],
            })

        reasons = {}
        for t in trades:
            reason = t.get("reason", "") or "未记录"
            reasons[reason] = reasons.get(reason, {"wins": 0, "total": 0})
            reasons[reason]["total"] += 1
            if "+" in (t.get("outcome") or ""):
                reasons[reason]["wins"] += 1

        sorted_reasons = sorted(reasons.items(), key=lambda x: x[1]["total"], reverse=True)
        for reason, data in sorted_reasons[:5]:
            sr = data["wins"] / data["total"] * 100
            if sr < 50 and data["total"] >= 2:
                common_mistakes.append({
                    "pattern": reason,
                    "frequency": data["total"],
                    "win_rate": round(sr, 1),
                })
            elif sr >= 60 and data["total"] >= 2:
                best_practices.append({
                    "pattern": reason,
                    "frequency": data["total"],
                    "win_rate": round(sr, 1),
                })

    if not common_mistakes and positions:
        for p in positions:
            if p["pnl_pct"] < -10:
                common_mistakes.append({
                    "pattern": "止损不及时",
                    "frequency": 1,
                    "example": f"{p['symbol']} 亏损 {p['pnl_pct']:.1f}%",
                })

    if not best_practices and positions:
        for p in positions:
            if p["pnl_pct"] > 15:
                best_practices.append({
                    "pattern": "趋势跟随",
                    "frequency": 1,
                    "example": f"{p['symbol']} 盈利 {p['pnl_pct']:.1f}%",
                })

    max_wins = []
    max_losses = []
    if trades:
        for t in trades:
            outcome = t.get("outcome", "")
            if "+" in outcome:
                max_wins.append(t)
            elif "-" in outcome:
                max_losses.append(t)

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "common_mistakes": common_mistakes or [
            {"pattern": "暂无交易记录", "frequency": 0, "note": "添加交易记录后自动分析"},
        ],
        "best_practices": best_practices or [
            {"pattern": "暂无交易记录", "frequency": 0, "note": "添加交易记录后自动分析"},
        ],
        "trade_analysis": trade_analysis,
        "max_wins": max_wins[:3],
        "max_losses": max_losses[:3],
        "positions_summary": len(positions),
    }


@app.get("/api/rebalance")
def api_rebalance(user_id: int = 1):
    """AI 调仓建议 - 基于用户持仓个性化分析

    分析维度：
    - 行业集中度风险
    - 单只股票仓位风险
    - 盈利/亏损股票处置建议
    - 技术面信号（RSI/均线）
    - 推荐调仓方向

    Returns:
        {user_id, analysis, recommendations, action_items}
    """
    positions = _build_positions(user_id)
    if not positions:
        return {
            "user_id": user_id,
            "analysis": {"total_positions": 0, "total_market": 0, "concentration_risk": "低"},
            "recommendations": [],
            "action_items": ["暂无持仓，请先添加持仓后获取调仓建议"],
        }

    portfolio = compute_portfolio(positions)
    concentration = compute_concentration(positions, portfolio["total_market"])

    total_market = portfolio["total_market"]
    total_cost = portfolio["total_cost"]

    # 行业集中度分析
    sector_concentration = concentration["by_sector"]
    max_sector = max(sector_concentration.items(), key=lambda x: x[1]) if sector_concentration else ("", 0)
    concentration_risk = "高" if max_sector[1] > 0.5 else ("中" if max_sector[1] > 0.3 else "低")

    # 单只股票风险
    symbol_concentration = concentration["by_symbol"]
    high_concentration_symbols = [sym for sym, pct in symbol_concentration.items() if pct > 0.3]

    # 批量获取技术面数据
    symbols = [p["symbol"] for p in positions]
    hist_batch = fetch_history_batch(symbols, 60)

    # 分析每只股票
    stock_analysis = []
    for p in positions:
        hist = hist_batch.get(p["symbol"].upper(), [])
        rsi = None
        ma_signal = None
        trend = None

        if len(hist) >= 20:
            closes = hist
            last = closes[-1]
            ma5 = sum(closes[-5:]) / 5
            ma20 = sum(closes[-20:]) / 20
            ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else ma20

            gains, losses = [], []
            for i in range(1, min(15, len(closes))):
                d = closes[-i] - closes[-i-1]
                gains.append(max(d, 0)); losses.append(max(-d, 0))
            avg_g = sum(gains) / len(gains) if gains else 0
            avg_l = sum(losses) / len(losses) if losses else 0.001
            rsi = 100 - (100 / (1 + avg_g / avg_l))

            if last > ma5 > ma20:
                ma_signal = "多头排列"
                trend = "上升"
            elif last < ma5 < ma20:
                ma_signal = "空头排列"
                trend = "下降"
            else:
                ma_signal = "震荡"
                trend = "震荡"

        stock_analysis.append({
            "symbol": p["symbol"],
            "name": p.get("name", p["symbol"]),
            "sector": p.get("sector", ""),
            "market_value": p["market_value"],
            "weight": p["market_value"] / total_market if total_market else 0,
            "pnl_pct": p["pnl_pct"],
            "price": p["current_price"],
            "rsi": round(rsi, 1) if rsi else None,
            "ma_signal": ma_signal,
            "trend": trend,
        })

    # 生成调仓建议
    recommendations = []
    action_items = []

    # 行业集中度过高建议
    if concentration_risk == "高":
        recommendations.append({
            "type": "风险控制",
            "severity": "高",
            "description": f"{max_sector[0]}行业占比 {max_sector[1]*100:.1f}%，建议分散到其他行业",
            "suggestion": f"考虑将{max_sector[0]}仓位降至30%以下，增加其他行业配置",
        })
        action_items.append(f"分散{max_sector[0]}行业仓位")

    # 单只股票仓位过高建议
    for sym in high_concentration_symbols:
        pct = symbol_concentration[sym]
        recommendations.append({
            "type": "风险控制",
            "severity": "中",
            "description": f"{sym}仓位占比 {pct*100:.1f}%，超过30%阈值",
            "suggestion": f"考虑减仓{sym}至20-25%，降低单一标的风险",
        })
        action_items.append(f"减仓{sym}至25%以下")

    # 亏损股票建议
    losers = [s for s in stock_analysis if s["pnl_pct"] < -10]
    for s in losers:
        reason = ""
        if s["trend"] == "下降":
            reason = "趋势向下"
        elif s["rsi"] and s["rsi"] < 30:
            reason = "RSI超卖，可能有反弹机会"
        else:
            reason = "基本面或市场因素"

        recommendations.append({
            "type": "止损/加仓",
            "severity": "中",
            "description": f"{s['name']}({s['symbol']})亏损 {s['pnl_pct']:.1f}%，{reason}",
            "suggestion": f"若{reason}是趋势向下，建议止损；若RSI超卖，可考虑分批加仓摊薄成本",
        })
        action_items.append(f"评估{s['symbol']}：{'止损' if s['trend'] == '下降' else '考虑加仓'}")

    # 盈利股票建议
    winners = [s for s in stock_analysis if s["pnl_pct"] > 15]
    for s in winners:
        recommendations.append({
            "type": "止盈/持有",
            "severity": "低",
            "description": f"{s['name']}({s['symbol']})盈利 {s['pnl_pct']:.1f}%",
            "suggestion": f"若趋势仍向上且RSI未超买，继续持有；若RSI>70，考虑部分止盈锁定利润",
        })
        if s["rsi"] and s["rsi"] > 70:
            action_items.append(f"{s['symbol']} RSI超买，考虑部分止盈")

    # 技术面信号建议
    for s in stock_analysis:
        if s["rsi"] and s["rsi"] > 75:
            recommendations.append({
                "type": "技术面",
                "severity": "中",
                "description": f"{s['symbol']} RSI={s['rsi']:.0f} 超买",
                "suggestion": "短期可能回调，谨慎追高",
            })
        elif s["rsi"] and s["rsi"] < 25:
            recommendations.append({
                "type": "技术面",
                "severity": "中",
                "description": f"{s['symbol']} RSI={s['rsi']:.0f} 超卖",
                "suggestion": "短期可能反弹，关注买入机会",
            })

    # 整体建议
    if not recommendations:
        recommendations.append({
            "type": "综合",
            "severity": "低",
            "description": "持仓结构健康，各维度风险可控",
            "suggestion": "继续持有，定期关注市场变化",
        })
        action_items.append("持仓健康，继续持有")

    analysis = {
        "total_positions": len(positions),
        "total_market": round(total_market, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(portfolio["total_pnl"], 2),
        "total_pnl_pct": round(portfolio["total_pnl_pct"], 2),
        "concentration_risk": concentration_risk,
        "max_sector": {"name": max_sector[0], "weight": round(max_sector[1], 2)},
        "high_concentration_symbols": high_concentration_symbols,
        "stock_analysis": stock_analysis,
    }

    return {
        "user_id": user_id,
        "analysis": analysis,
        "recommendations": recommendations,
        "action_items": action_items[:6],
    }


@app.post("/api/query")
def api_query(q: QueryIn):
    """自然语言交互查询 - 简单关键词匹配"""
    question = q.question.lower()
    responses = []
    if any(k in question for k in ["特斯拉","tesla","tsla"]):
        responses.append("特斯拉近期利空：交付量不及预期、马斯克分心 X 平台。技术面跌破 20 日线，建议观望。")
    if any(k in question for k in ["黄金","gold","gld"]):
        responses.append("黄金与美元指数近 30 天相关性 -0.72，呈强负相关。当前避险情绪推动金价上行。")
    if any(k in question for k in ["持仓","组合","行业"]):
        positions = _build_positions()
        if positions:
            portfolio = compute_portfolio(positions)
            conc = compute_concentration(positions, portfolio["total_market"])
            top_sector = max(conc["by_sector"].items(), key=lambda x: x[1])
            responses.append(f"你持仓中行业集中度最高的是 {top_sector[0]}，占比 {top_sector[1]*100:.1f}%。")
    if any(k in question for k in ["美联储","fed","利率","加息"]):
        responses.append("美联储最近一次议息会议维持利率不变，措辞偏鸽派。市场预期下次降息概率 68%。")
    if not responses:
        responses.append(f"已收到你的问题：『{q.question}』。该功能接入 LLM 后可返回精准答案，当前为原型演示。")
    return {"question": q.question, "answers": responses, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


@app.get("/api/backtest")
def api_backtest():
    """策略回测引擎 - 示例结果"""
    import random as _r
    return {
        "strategy": "财报超预期后买入持有 30 天",
        "period": "2023-01-01 ~ 2025-12-31",
        "results": {
            "total_trades": 48, "win_rate": 0.625, "avg_return": 0.082,
            "max_drawdown": 0.15, "sharpe_ratio": 1.34, "annual_return": 0.24,
        },
        "equity_curve": [100 + i*2 + _r.randint(-5,5) for i in range(48)],
        "comparison": {"benchmark":"S&P 500","benchmark_return":0.18,"alpha":0.06},
    }


@app.get("/api/config")
def api_config():
    return Config.summary()


# ==================== 金融危机专题 ====================

@app.get("/api/crisis/list")
def api_crisis_list():
    """获取所有金融危机列表"""
    from data_sources.crisis_tracker import get_all_crisis_data
    return {"crises": get_all_crisis_data()}


@app.get("/api/crisis/compare/2008")
def api_crisis_compare_2008():
    """当前市场指标与2008危机对比"""
    from data_sources.crisis_tracker import get_crisis_comparison
    return get_crisis_comparison()


@app.get("/api/crisis/{crisis_id}")
def api_crisis_detail(crisis_id: str):
    """获取单个危机详情"""
    from data_sources.crisis_tracker import get_crisis_detail
    data = get_crisis_detail(crisis_id)
    if "error" in data:
        raise HTTPException(404, data["error"])
    return data


@app.get("/api/crisis/{crisis_id}/timeline")
def api_crisis_timeline(crisis_id: str):
    """获取危机事件时间线"""
    from data_sources.crisis_tracker import get_crisis_timeline
    return get_crisis_timeline(crisis_id)


# ---- 模块1: 历史危机全景复盘 ----

@app.get("/api/crisis/{crisis_id}/macro")
def api_crisis_macro(crisis_id: str):
    """获取危机的宏观经济指标时间序列"""
    from data_sources.crisis_tracker import get_crisis_macro_indicators
    return get_crisis_macro_indicators(crisis_id)


@app.get("/api/crisis/{crisis_id}/institutions")
def api_crisis_institutions(crisis_id: str):
    """获取危机中的金融机构演变"""
    from data_sources.crisis_tracker import get_institution_events
    return get_institution_events(crisis_id)


@app.get("/api/crisis/{crisis_id}/multi-timeline")
def api_crisis_multi_timeline(crisis_id: str):
    """获取多维时间轴"""
    from data_sources.crisis_tracker import get_multi_dimensional_timeline
    return get_multi_dimensional_timeline(crisis_id)


# ---- 模块2: 现状对标与风险监测 ----

@app.get("/api/crisis/risk/yield-curve")
def api_risk_yield_curve():
    """收益率曲线监测"""
    from data_sources.risk_monitor import get_yield_curve_status
    return get_yield_curve_status()


@app.get("/api/crisis/risk/liquidity")
def api_risk_liquidity():
    """流动性监测"""
    from data_sources.risk_monitor import get_liquidity_status
    return get_liquidity_status()


@app.get("/api/crisis/risk/valuation")
def api_risk_valuation():
    """估值与杠杆预警"""
    from data_sources.risk_monitor import get_valuation_warning
    return get_valuation_warning()


@app.get("/api/crisis/risk/cross-cycle")
def api_risk_cross_cycle():
    """跨周期对比"""
    from data_sources.risk_monitor import get_cross_cycle_comparison
    return get_cross_cycle_comparison()


@app.get("/api/crisis/risk/dashboard")
def api_risk_dashboard():
    """风险总览看板"""
    from data_sources.risk_monitor import get_risk_dashboard
    return get_risk_dashboard()


# ---- 模块3: 危机恢复与政策推演 ----

@app.get("/api/crisis/policy/toolbox")
def api_policy_toolbox():
    """政策工具箱"""
    from data_sources.policy_simulator import get_policy_toolbox
    return get_policy_toolbox()


@app.post("/api/crisis/policy/simulate")
def api_policy_simulate(body: dict):
    """政策模拟"""
    from data_sources.policy_simulator import simulate_policies
    selected_tools = body.get("selected_tools", [])
    severity = body.get("severity", "moderate")
    return simulate_policies(selected_tools, severity)


@app.get("/api/crisis/transmission/graph")
def api_transmission_graph():
    """风险传导图谱"""
    from data_sources.policy_simulator import get_transmission_graph
    return get_transmission_graph()


@app.get("/api/crisis/recovery/dashboard")
def api_recovery_dashboard():
    """恢复进程看板"""
    from data_sources.policy_simulator import get_recovery_dashboard
    return get_recovery_dashboard()


@app.get("/api/crisis/policy/historical")
def api_historical_policies():
    """历史政策对比"""
    from data_sources.policy_simulator import get_historical_policies
    return get_historical_policies()


@app.get("/api/crisis/figures/actions")
def api_crisis_figure_actions():
    """获取所有危机中的关键人物行为与收益时间线"""
    from data_sources.crisis_tracker import get_all_crisis_data
    crises = get_all_crisis_data()
    result = []
    for c in crises:
        for a in c.get("figure_actions", []):
            a["crisis_id"] = c["id"]
            a["crisis_name_zh"] = c["name_zh"]
            a["crisis_name_en"] = c["name_en"]
            result.append(a)
    result.sort(key=lambda x: x["date"])
    return {"actions": result, "total": len(result)}


@app.get("/api/crisis/{crisis_id}/figures")
def api_crisis_figures_by_crisis(crisis_id: str):
    """获取特定危机中的关键人物行为"""
    from data_sources.crisis_tracker import get_all_crisis_data
    crises = get_all_crisis_data()
    for c in crises:
        if c["id"] == crisis_id:
            return {"crisis_id": crisis_id, "actions": c.get("figure_actions", [])}
    raise HTTPException(404, f"Crisis {crisis_id} not found")


# 静态资源
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main():
    parser = argparse.ArgumentParser(description="投资研究操作系统")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    init_db()
    _seed_demo_data()
    logger.info(f"🚀 投资研究操作系统启动: http://{args.host}:{args.port}")
    logger.info(f"   OpenBB: {Config.OPENBB_BASE_URL}")

    import uvicorn
    uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
