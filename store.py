"""数据存储模块 - SQLite

表结构：
  holdings         持仓明细（复用 portfolio-risk）
  price_history    价格快照
  alerts           告警历史
  alert_cooldown   告警冷却
  tweets           舆情推文（来自 x-monitor-push 同构）
  filings          财报日历
  macro_events     宏观事件日历
  news_events      新闻事件（地缘/产业链）
  knowledge_base   投研知识库
  trades           交易记录（用于复盘）
"""
import json
import os
import sqlite3
from datetime import datetime

from config import Config


def _ensure_db_dir():
    db_dir = os.path.dirname(Config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            avatar TEXT,
            settings_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            symbol TEXT NOT NULL,
            name TEXT,
            cost_price REAL NOT NULL,
            shares REAL NOT NULL,
            sector TEXT,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(user_id) REFERENCES users(id),
            UNIQUE(user_id, symbol)
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            snapshot_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            alert_type TEXT NOT NULL,
            symbol TEXT,
            level TEXT NOT NULL,
            title TEXT,
            detail TEXT,
            pushed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS alert_cooldown (
            key TEXT PRIMARY KEY,
            last_alert_time TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT,
            link TEXT,
            published TEXT,
            impact_level TEXT,
            category TEXT,
            pushed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            tweet_id TEXT,
            summary TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at);

        CREATE TABLE IF NOT EXISTS x_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_x_accounts_username ON x_accounts(username);

        CREATE TABLE IF NOT EXISTS filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            company TEXT,
            filing_type TEXT,
            filing_date TEXT,
            period TEXT,
            signal TEXT,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS macro_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            name TEXT,
            importance TEXT,
            event_date TEXT,
            et_time TEXT,
            actual TEXT,
            forecast TEXT,
            previous TEXT,
            impact TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            title TEXT,
            source TEXT,
            url TEXT,
            regions TEXT,
            affected_assets TEXT,
            published_at TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_news_created ON news_events(created_at);

        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            tags TEXT,
            content TEXT,
            source_url TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            symbol TEXT,
            side TEXT,
            price REAL,
            shares REAL,
            reason TEXT,
            trade_date TEXT,
            outcome TEXT,
            review_note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS nav_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            date TEXT NOT NULL,
            total_market REAL NOT NULL,
            total_cost REAL NOT NULL,
            cash REAL DEFAULT 0,
            nav REAL NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        );
    """)
    _migrate_users_table(conn)
    _migrate_add_user_id_columns(conn)
    _migrate_filings_columns(conn)
    _migrate_tweets_columns(conn)
    _seed_default_x_accounts(conn)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_holdings_user ON holdings(user_id)")
    except:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_user_symbol ON price_history(user_id, symbol, snapshot_at)")
    except:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_user_created ON alerts(user_id, created_at)")
    except:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_date ON trades(user_id, trade_date)")
    except:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nav_user_date ON nav_history(user_id, date)")
    except:
        pass
    conn.commit()
    conn.close()


def _migrate_users_table(conn: sqlite3.Connection) -> None:
    """确保默认用户 'default' 存在。"""
    conn.execute(
        """INSERT OR IGNORE INTO users (id, username, display_name, avatar)
           VALUES (1, 'default', '默认用户', '')"""
    )


def _migrate_add_user_id_columns(conn: sqlite3.Connection) -> None:
    """为旧表添加 user_id 字段（兼容旧数据库迁移）。"""
    tables = [
        ("holdings", "INTEGER DEFAULT 1"),
        ("price_history", "INTEGER DEFAULT 1"),
        ("alerts", "INTEGER DEFAULT 1"),
        ("trades", "INTEGER DEFAULT 1"),
        ("nav_history", "INTEGER DEFAULT 1"),
    ]
    for table, col_def in tables:
        try:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "user_id" not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id {col_def}")
        except Exception:
            pass


def _migrate_filings_columns(conn: sqlite3.Connection) -> None:
    """幂等添加 filings 表的新字段。

    新增: revenue / net_income / gross_margin / bullish / bearish / fetched_at / pushed
    其中 bullish / bearish 存为 JSON 字符串; signal 字段在原 schema 已存在。
    使用 PRAGMA table_info 检查后 ALTER TABLE ADD COLUMN (SQLite 不支持 IF NOT EXISTS)。
    """
    needed = [
        ("revenue", "REAL"),
        ("net_income", "REAL"),
        ("gross_margin", "REAL"),
        ("bullish", "TEXT"),     # JSON list[str]
        ("bearish", "TEXT"),     # JSON list[str]
        ("fetched_at", "TEXT"),  # 上次实时抓取时间 (server 路由用于判断新鲜度)
        ("pushed", "INTEGER DEFAULT 0"),  # 是否已推送 0=未推送 1=已推送
    ]
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(filings)").fetchall()}
    for col, typ in needed:
        if col not in existing:
            conn.execute(f"ALTER TABLE filings ADD COLUMN {col} {typ}")


def _migrate_tweets_columns(conn: sqlite3.Connection) -> None:
    """幂等为 tweets 表添加 tweet_id / summary 字段。"""
    needed = [("tweet_id", "TEXT"), ("summary", "TEXT")]
    try:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(tweets)").fetchall()}
        for col, typ in needed:
            if col not in existing:
                conn.execute(f"ALTER TABLE tweets ADD COLUMN {col} {typ}")
    except Exception:
        pass


_DEFAULT_X_ACCOUNTS = [
    ("realDonaldTrump", "唐纳德·特朗普"),
    ("elonmusk", "埃隆·马斯克"),
    ("CathieDWood", "Cathie Wood"),
    ("saylor", "Michael Saylor"),
    ("VitalikButerin", "Vitalik Buterin"),
    ("cz_binance", "赵长鹏 CZ"),
    ("PeterNavarro45", "Peter Navarro"),
    ("HowardLutnick", "Howard Lutnick"),
]


def _seed_default_x_accounts(conn: sqlite3.Connection) -> None:
    """首次启动时写入默认监控账号。"""
    for username, display_name in _DEFAULT_X_ACCOUNTS:
        conn.execute(
            "INSERT OR IGNORE INTO x_accounts (username, display_name, enabled) VALUES (?, ?, 1)",
            (username, display_name),
        )


# ==================== 用户管理 ====================

def get_user(username: str):
    """按用户名获取用户信息。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    """按 ID 获取用户信息。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_users():
    """获取所有用户列表。"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username: str, display_name: str = "", avatar: str = ""):
    """创建新用户（username 唯一）。"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, display_name, avatar) VALUES (?, ?, ?)",
            (username, display_name or username, avatar),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def update_user(user_id: int, display_name: str = None, avatar: str = None):
    """更新用户信息。"""
    conn = get_connection()
    updates = []
    params = []
    if display_name is not None:
        updates.append("display_name = ?")
        params.append(display_name)
    if avatar is not None:
        updates.append("avatar = ?")
        params.append(avatar)
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id: int):
    """删除用户（不允许删除默认用户）。"""
    if user_id == 1:
        return False
    conn = get_connection()
    conn.execute("DELETE FROM holdings WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM trades WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM alerts WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM price_history WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM nav_history WHERE user_id = ?", (user_id,))
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ==================== 持仓 CRUD ====================

def add_holding(symbol, cost_price, shares, name="", sector="", note="", user_id: int = 1):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO holdings (user_id, symbol, name, cost_price, shares, sector, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, symbol.upper(), name, cost_price, shares, sector, note),
        )
        conn.commit()
    finally:
        conn.close()


def remove_holding(symbol, user_id: int = 1):
    conn = get_connection()
    cur = conn.execute("DELETE FROM holdings WHERE user_id = ? AND symbol = ?", (user_id, symbol.upper()))
    conn.commit()
    conn.close()
    return cur.rowcount


def get_holdings(user_id: int = 1):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM holdings WHERE user_id = ? ORDER BY symbol", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_price(symbol, price, user_id: int = 1):
    conn = get_connection()
    conn.execute("INSERT INTO price_history (user_id, symbol, price) VALUES (?, ?, ?)", (user_id, symbol.upper(), price))
    conn.commit()
    conn.close()


# ==================== 告警 ====================

def save_alert(alert_type, level, title, detail, symbol="", user_id: int = 1):
    conn = get_connection()
    conn.execute(
        "INSERT INTO alerts (user_id, alert_type, symbol, level, title, detail) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, alert_type, symbol, level, title, detail),
    )
    conn.commit()
    conn.close()


def get_recent_alerts(limit=50, user_id: int = 1):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_alert_in_cooldown(alert_type, symbol=""):
    key = f"{alert_type}:{symbol}"
    conn = get_connection()
    row = conn.execute("SELECT last_alert_time FROM alert_cooldown WHERE key = ?", (key,)).fetchone()
    conn.close()
    if not row:
        return False
    try:
        last = datetime.strptime(row["last_alert_time"], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - last).total_seconds() / 60 < Config.ALERT_COOLDOWN_MINUTES
    except ValueError:
        return False


def update_alert_cooldown(alert_type, symbol=""):
    key = f"{alert_type}:{symbol}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute(
        """INSERT INTO alert_cooldown (key, last_alert_time, updated_at) VALUES (?, ?, datetime('now','localtime'))
           ON CONFLICT(key) DO UPDATE SET last_alert_time = ?, updated_at = datetime('now','localtime')""",
        (key, now, now),
    )
    conn.commit()
    conn.close()


# ==================== 舆情推文 ====================

def save_tweet(username, title, link, published, impact_level, category, pushed=0, summary="", tweet_id=""):
    """保存推文，基于 tweet_id 去重（无 tweet_id 时按 link 去重）"""
    conn = get_connection()
    dedup_key = tweet_id or link
    if tweet_id:
        existing = conn.execute("SELECT id FROM tweets WHERE tweet_id = ?", (tweet_id,)).fetchone()
    else:
        existing = conn.execute("SELECT id FROM tweets WHERE link = ? AND link != ''", (link,)).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute(
        """INSERT OR IGNORE INTO tweets (username, title, link, published, impact_level, category, pushed, summary, tweet_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (username, title, link, published, impact_level, category, pushed, summary, tweet_id),
    )
    conn.commit()
    conn.close()
    return True


def get_recent_tweets(limit=50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tweets ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== X 账号管理 ====================

def get_x_accounts(enabled_only: bool = False):
    """获取所有X监控账号"""
    conn = get_connection()
    sql = "SELECT * FROM x_accounts"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY created_at ASC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_x_account(username: str, display_name: str = "") -> dict:
    """添加X监控账号"""
    username = username.strip().lstrip("@")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO x_accounts (username, display_name, enabled) VALUES (?, ?, 1)",
            (username, display_name or username),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM x_accounts WHERE username = ?", (username,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.IntegrityError:
        conn.close()
        return None


def remove_x_account(username: str) -> bool:
    """删除X监控账号"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM x_accounts WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def toggle_x_account(username: str, enabled: int) -> bool:
    """启用/禁用X监控账号"""
    conn = get_connection()
    cur = conn.execute("UPDATE x_accounts SET enabled = ? WHERE username = ?", (enabled, username))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def mark_tweet_pushed(tweet_id: int) -> None:
    """标记推文已推送"""
    conn = get_connection()
    conn.execute("UPDATE tweets SET pushed = 1 WHERE id = ?", (tweet_id,))
    conn.commit()
    conn.close()


def get_unpushed_high_tweets(limit: int = 20) -> list[dict]:
    """获取未推送的高级别推文"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tweets WHERE impact_level = 'high' AND pushed = 0 ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 财报 ====================

def save_filing(symbol, company, filing_type, filing_date, period, signal, summary,
                revenue=None, net_income=None, gross_margin=None,
                bullish=None, bearish=None, fetched_at=None, pushed=0):
    """Upsert (by symbol) 一条财报记录。

    新增的可选字段默认 None, 兼容旧调用方 (7 位置参数)。
    bullish / bearish 接受 list, 内部存为 JSON 字符串。
    同 symbol 旧记录会被先 DELETE 再 INSERT, 避免重复堆积。
    pushed: 0=未推送 1=已推送（新财报默认未推送）。
    """
    conn = get_connection()
    bullish_json = json.dumps(bullish, ensure_ascii=False) if bullish else None
    bearish_json = json.dumps(bearish, ensure_ascii=False) if bearish else None
    conn.execute("DELETE FROM filings WHERE symbol = ?", (symbol,))
    conn.execute(
        """INSERT INTO filings
           (symbol, company, filing_type, filing_date, period, signal, summary,
            revenue, net_income, gross_margin, bullish, bearish, fetched_at, pushed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (symbol, company, filing_type, filing_date, period, signal, summary,
         revenue, net_income, gross_margin, bullish_json, bearish_json, fetched_at, pushed),
    )
    conn.commit()
    conn.close()


def get_filings(limit=50):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM filings ORDER BY filing_date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [_decode_filing(dict(r)) for r in rows]


def get_filing_by_symbol(symbol: str):
    """按 symbol 查询单条财报详情（含 revenue/net_income/gross_margin/bullish/bearish）

    Returns:
        dict | None: 财报详情（_decode_filing 已反序列化 JSON 字段），无则 None
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM filings WHERE symbol = ? ORDER BY filing_date DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    conn.close()
    return _decode_filing(dict(row)) if row else None


def _decode_filing(row: dict) -> dict:
    """把 JSON 字符串字段 (bullish/bearish) 反序列化为 list。"""
    for k in ("bullish", "bearish"):
        v = row.get(k)
        if isinstance(v, str) and v:
            try:
                row[k] = json.loads(v)
            except json.JSONDecodeError:
                pass
    return row


def get_latest_filing_fetched_at():
    """返回 filings 表中最新的 fetched_at, 用于 server 路由判断数据是否过期。

    优先返回有 fetched_at 的最新记录; 若全部为旧记录 (无 fetched_at), 回退到 max(created_at)。
    无任何记录时返回 None。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT fetched_at FROM filings WHERE fetched_at IS NOT NULL "
        "ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()
    if row:
        conn.close()
        return row["fetched_at"]
    row = conn.execute("SELECT MAX(created_at) AS c FROM filings").fetchone()
    conn.close()
    return row["c"] if row and row["c"] else None


def get_unpushed_filings(limit: int = 20) -> list[dict]:
    """获取未推送的财报列表（pushed=0），按财报日期降序"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM filings WHERE pushed = 0 OR pushed IS NULL "
        "ORDER BY filing_date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_decode_filing(dict(r)) for r in rows]


def mark_filing_pushed(symbol: str):
    """标记某股票的财报为已推送"""
    conn = get_connection()
    conn.execute(
        "UPDATE filings SET pushed = 1 WHERE symbol = ?",
        (symbol,),
    )
    conn.commit()
    conn.close()


# ==================== 宏观事件 ====================

def save_macro_event(event_id, name, importance, event_date, et_time, actual="", forecast="", previous="", impact=""):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO macro_events
           (event_id, name, importance, event_date, et_time, actual, forecast, previous, impact)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, name, importance, event_date, et_time, actual, forecast, previous, impact),
    )
    conn.commit()
    conn.close()


def get_macro_events(limit=50):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM macro_events ORDER BY event_date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 新闻事件 ====================

def save_news_event(category, title, source, url, regions, affected_assets, published_at):
    conn = get_connection()
    conn.execute(
        """INSERT INTO news_events (category, title, source, url, regions, affected_assets, published_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (category, title, source, url, regions, affected_assets, published_at),
    )
    conn.commit()
    conn.close()


def get_news_events(category=None, limit=50):
    conn = get_connection()
    if category:
        rows = conn.execute(
            "SELECT * FROM news_events WHERE category = ? ORDER BY published_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM news_events ORDER BY published_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 知识库 ====================

def save_knowledge(title, category, tags, content, source_url=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO knowledge_base (title, category, tags, content, source_url) VALUES (?, ?, ?, ?, ?)",
        (title, category, tags, content, source_url),
    )
    conn.commit()
    conn.close()


def get_knowledge(category=None, limit=50):
    conn = get_connection()
    if category:
        rows = conn.execute(
            "SELECT * FROM knowledge_base WHERE category = ? ORDER BY created_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM knowledge_base ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 交易复盘 ====================

def save_trade(symbol, side, price, shares, reason, trade_date, outcome="", review_note="", user_id: int = 1):
    conn = get_connection()
    conn.execute(
        """INSERT INTO trades (user_id, symbol, side, price, shares, reason, trade_date, outcome, review_note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, symbol, side, price, shares, reason, trade_date, outcome, review_note),
    )
    conn.commit()
    conn.close()


def get_trades(limit=50, user_id: int = 1):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades WHERE user_id = ? ORDER BY trade_date DESC LIMIT ?", (user_id, limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 净值序列（组合回撤生产化）====================

def save_nav_snapshot(total_market: float, total_cost: float, cash: float = 0.0, note: str = "", user_id: int = 1) -> None:
    """记录当日净值快照（按日期去重，同日覆盖）。

    nav = (total_market + cash) / total_cost  归一化到成本=1 的净值
    """
    nav = (total_market + cash) / total_cost if total_cost else 0.0
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        """INSERT INTO nav_history (user_id, date, total_market, total_cost, cash, nav, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, date) DO UPDATE SET
             total_market=excluded.total_market,
             total_cost=excluded.total_cost,
             cash=excluded.cash,
             nav=excluded.nav,
             note=excluded.note""",
        (user_id, today, total_market, total_cost, cash, nav, note),
    )
    conn.commit()
    conn.close()


def get_nav_history(days: int = 90, user_id: int = 1) -> list[dict]:
    """获取最近 N 天的净值序列（按日期升序，用于回撤计算）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT date, total_market, total_cost, cash, nav FROM nav_history WHERE user_id = ? "
        "ORDER BY date DESC LIMIT ?",
        (user_id, days,),
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))  # 升序返回


def get_portfolio_drawdown(days: int = 90, user_id: int = 1) -> dict:
    """基于净值序列计算真实最大回撤

    Returns:
        {max_drawdown, current_drawdown, peak_nav, peak_date, nav_series}
        无数据时 max_drawdown=None
    """
    history = get_nav_history(days, user_id)
    if len(history) < 2:
        return {"max_drawdown": None, "current_drawdown": None,
                "peak_nav": None, "peak_date": None, "nav_series": []}
    navs = [h["nav"] for h in history]
    peak = navs[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_idx = 0
    for i, n in enumerate(navs):
        if n > peak:
            peak = n
            peak_idx = i
        if peak > 0:
            dd = (peak - n) / peak
            if dd > max_dd:
                max_dd = dd
                max_dd_idx = i
    current_dd = (peak - navs[-1]) / peak if peak > 0 else 0.0
    return {
        "max_drawdown": max_dd,
        "current_drawdown": current_dd,
        "peak_nav": peak,
        "peak_date": history[peak_idx]["date"] if peak_idx < len(history) else None,
        "max_dd_date": history[max_dd_idx]["date"] if max_dd_idx < len(history) else None,
        "nav_series": [{"date": h["date"], "nav": h["nav"]} for h in history],
    }
