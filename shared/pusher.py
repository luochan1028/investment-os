"""投资研究操作系统 - 统一推送层

从 x-monitor-push 生产代码抽取并解耦，提供：
- 三通道：PushPlus / WxPusher / Server酱
- 三级告警：high(红) / medium(黄) / low(灰)
- 冷却机制：同 key 在冷却期内不重复推
- 每日上限：超限自动降级
- 无外部耦合：不依赖 x-monitor-push 的 Config/TweetItem

用法:
    from shared.pusher import push_alert, PushLevel
    push_alert(PushLevel.HIGH, "AAPL 跌破止损线", "持仓 AAPL 亏损 15%", symbol="AAPL")
"""
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger("investment-os.pusher")


class PushLevel(str, Enum):
    HIGH = "high"      # P0 红色 紧急
    MEDIUM = "medium"  # P1 黄色 关注
    LOW = "low"        # P2 灰色 提示


@dataclass
class PushConfig:
    """推送配置 - 可独立注入，便于测试"""
    push_type: str = "pushplus"  # pushplus / wxpusher / serverchan
    pushplus_token: str = ""
    wxpusher_token: str = ""
    wxpusher_uid: str = ""
    serverchan_key: str = ""
    proxy_url: str = ""
    max_daily_push: int = 50
    auto_high_threshold: int = 40
    cooldown_minutes: int = 60
    db_path: str = "data/investment_os.db"

    @classmethod
    def from_env(cls):
        """从环境变量加载（兼容 investment-os 的 Config 字段名）"""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return cls(
            push_type=os.getenv("PUSH_TYPE", "pushplus"),
            pushplus_token=os.getenv("PUSHPLUS_TOKEN", ""),
            wxpusher_token=os.getenv("WXPUSHER_TOKEN", ""),
            wxpusher_uid=os.getenv("WXPUSHER_UID", ""),
            serverchan_key=os.getenv("SERVERCHAN_KEY", ""),
            proxy_url=os.getenv("PROXY_URL", ""),
            max_daily_push=int(os.getenv("MAX_DAILY_PUSH", "50")),
            auto_high_threshold=int(os.getenv("AUTO_HIGH_THRESHOLD", "40")),
            cooldown_minutes=int(os.getenv("ALERT_COOLDOWN_MINUTES", "60")),
            db_path=os.getenv("PORTFOLIO_DB_PATH", "data/investment_os.db"),
        )

    def validate(self) -> list[str]:
        errs = []
        if self.push_type == "pushplus" and not self.pushplus_token:
            errs.append("PUSH_TYPE=pushplus 需配置 PUSHPLUS_TOKEN")
        if self.push_type == "wxpusher" and not (self.wxpusher_token and self.wxpusher_uid):
            errs.append("PUSH_TYPE=wxpusher 需配置 WXPUSHER_TOKEN + WXPUSHER_UID")
        if self.push_type == "serverchan" and not self.serverchan_key:
            errs.append("PUSH_TYPE=serverchan 需配置 SERVERCHAN_KEY")
        return errs


# ==================== 默认配置单例（延迟加载）====================

_default_config: Optional[PushConfig] = None


def get_default_config() -> PushConfig:
    global _default_config
    if _default_config is None:
        _default_config = PushConfig.from_env()
    return _default_config


def set_default_config(cfg: PushConfig):
    """注入自定义配置（测试用）"""
    global _default_config
    _default_config = cfg


# ==================== 数据库初始化 ====================

def _get_conn(cfg: PushConfig) -> sqlite3.Connection:
    import os
    db_dir = os.path.dirname(cfg.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(cfg.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_push_tables(cfg: Optional[PushConfig] = None):
    """初始化推送相关表（幂等）。可与 investment-os 的 store.init_db 并存。"""
    cfg = cfg or get_default_config()
    conn = _get_conn(cfg)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS push_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            title TEXT,
            content TEXT,
            channel TEXT,
            success INTEGER DEFAULT 0,
            cooldown_key TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS push_cooldown (
            key TEXT PRIMARY KEY,
            last_push_time TEXT NOT NULL,
            push_count INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS push_daily_stats (
            date TEXT PRIMARY KEY,
            push_count INTEGER DEFAULT 0,
            auto_high_mode INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_push_log_created ON push_log(created_at);
    """)
    conn.commit()
    conn.close()


# ==================== 冷却与频控 ====================

def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_in_cooldown(key: str, cfg: Optional[PushConfig] = None) -> bool:
    """检查 key 是否在冷却期内"""
    cfg = cfg or get_default_config()
    conn = _get_conn(cfg)
    row = conn.execute("SELECT last_push_time FROM push_cooldown WHERE key=?", (key,)).fetchone()
    conn.close()
    if not row:
        return False
    try:
        last = datetime.strptime(row["last_push_time"], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - last).total_seconds() / 60 < cfg.cooldown_minutes
    except ValueError:
        return False


def _update_cooldown(key: str, cfg: PushConfig):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn(cfg)
    conn.execute(
        """INSERT INTO push_cooldown (key, last_push_time, push_count, updated_at) VALUES (?,?,1,?)
           ON CONFLICT(key) DO UPDATE SET last_push_time=?, push_count=push_count+1, updated_at=?""",
        (key, now, now, now, now),
    )
    conn.commit()
    conn.close()


def _get_daily_count(cfg: PushConfig) -> int:
    conn = _get_conn(cfg)
    row = conn.execute("SELECT push_count FROM push_daily_stats WHERE date=?", (_today_str(),)).fetchone()
    conn.close()
    return row["push_count"] if row else 0


def _incr_daily_count(cfg: PushConfig) -> int:
    conn = _get_conn(cfg)
    conn.execute(
        """INSERT INTO push_daily_stats (date, push_count, updated_at) VALUES (?,1,?)
           ON CONFLICT(date) DO UPDATE SET push_count=push_count+1, updated_at=?""",
        (_today_str(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    row = conn.execute("SELECT push_count FROM push_daily_stats WHERE date=?", (_today_str(),)).fetchone()
    conn.close()
    return row["push_count"] if row else 0


def _is_auto_high(cfg: PushConfig) -> bool:
    conn = _get_conn(cfg)
    row = conn.execute("SELECT auto_high_mode FROM push_daily_stats WHERE date=?", (_today_str(),)).fetchone()
    conn.close()
    return bool(row and row["auto_high_mode"])


def _enable_auto_high(cfg: PushConfig):
    conn = _get_conn(cfg)
    conn.execute(
        """INSERT INTO push_daily_stats (date, auto_high_mode, updated_at) VALUES (?,1,?)
           ON CONFLICT(date) DO UPDATE SET auto_high_mode=1, updated_at=?""",
        (_today_str(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


# ==================== HTTP 客户端 ====================

def _get_client(cfg: PushConfig) -> httpx.Client:
    kwargs = {"timeout": 15.0}
    if cfg.proxy_url:
        kwargs["proxy"] = cfg.proxy_url
    return httpx.Client(**kwargs)


# ==================== 三通道实现 ====================

def _push_serverchan(title: str, content: str, cfg: PushConfig) -> bool:
    if not cfg.serverchan_key:
        logger.error("❌ Server酱 Key 未配置")
        return False
    url = f"https://sctapi.ftqq.com/{cfg.serverchan_key}.send"
    try:
        with _get_client(cfg) as c:
            r = c.post(url, data={"title": title, "desp": content})
            j = r.json()
            if j.get("code") == 0:
                logger.info("✅ Server酱推送成功: %s", title)
                return True
            logger.error("❌ Server酱失败: %s", j.get("message"))
            return False
    except Exception as e:
        logger.error("❌ Server酱异常: %s", e)
        return False


def _push_wxpusher(title: str, content: str, cfg: PushConfig, content_type: int = 1) -> bool:
    if not cfg.wxpusher_token or not cfg.wxpusher_uid:
        logger.error("❌ WxPusher Token/UID 未配置")
        return False
    url = "https://wxpusher.zjiecode.com/api/send/message"
    payload = {
        "appToken": cfg.wxpusher_token, "content": content,
        "summary": title[:50], "contentType": content_type, "uids": [cfg.wxpusher_uid],
    }
    try:
        with _get_client(cfg) as c:
            r = c.post(url, json=payload)
            j = r.json()
            if j.get("code") == 1000:
                logger.info("✅ WxPusher推送成功: %s", title)
                return True
            logger.error("❌ WxPusher失败: %s", j.get("msg"))
            return False
    except Exception as e:
        logger.error("❌ WxPusher异常: %s", e)
        return False


def _push_pushplus(title: str, content: str, cfg: PushConfig, template: str = "markdown") -> bool:
    if not cfg.pushplus_token:
        logger.error("❌ PushPlus Token 未配置")
        return False
    url = "https://www.pushplus.plus/send"
    payload = {"token": cfg.pushplus_token, "title": title, "content": content, "template": template}
    try:
        with _get_client(cfg) as c:
            r = c.post(url, json=payload)
            j = r.json()
            if j.get("code") == 200:
                logger.info("✅ PushPlus推送成功: %s", title)
                return True
            logger.error("❌ PushPlus失败: %s", j.get("msg"))
            return False
    except Exception as e:
        logger.error("❌ PushPlus异常: %s", e)
        return False


def _send(title: str, content: str, cfg: PushConfig) -> bool:
    """根据 push_type 路由到具体通道"""
    if cfg.push_type == "serverchan":
        return _push_serverchan(title, content, cfg)
    if cfg.push_type == "wxpusher":
        return _push_wxpusher(title, content, cfg)
    return _push_pushplus(title, content, cfg)


# ==================== 统一入口 ====================

def push_alert(
    level: PushLevel,
    title: str,
    content: str,
    symbol: str = "",
    alert_type: str = "",
    force: bool = False,
    cfg: Optional[PushConfig] = None,
) -> bool:
    """统一推送入口

    Args:
        level: 告警级别
        title: 标题（≤50字）
        content: 内容（markdown）
        symbol: 关联标的（用于冷却 key）
        alert_type: 告警类型（用于冷却 key）
        force: True 跳过冷却和每日上限（仅 P0 紧急用）
        cfg: 推送配置，默认用环境变量

    Returns:
        bool 是否推送成功
    """
    cfg = cfg or get_default_config()
    init_push_tables(cfg)

    cooldown_key = f"{alert_type}:{symbol}" if alert_type or symbol else f"misc:{title[:20]}"

    # 自动 high 模式：当日推送超阈值后，非 high 一律不推
    if not force and level != PushLevel.HIGH and _is_auto_high(cfg):
        logger.info("🔇 自动 high 模式，跳过 %s: %s", level, title)
        return False

    # 冷却检查（high 和 force 豁免）
    if not force and level != PushLevel.HIGH and is_in_cooldown(cooldown_key, cfg):
        logger.info("🔇 冷却中，跳过: %s", cooldown_key)
        return False

    # 每日上限检查（high 和 force 豁免）
    if not force and level != PushLevel.HIGH:
        today_count = _get_daily_count(cfg)
        if today_count >= cfg.max_daily_push:
            logger.warning("⚠️ 达每日上限 %d，启用 high 模式", cfg.max_daily_push)
            _enable_auto_high(cfg)
            return False

    # 执行推送
    ok = _send(title, content, cfg)

    # 记录日志
    conn = _get_conn(cfg)
    conn.execute(
        "INSERT INTO push_log (level, title, content, channel, success, cooldown_key) VALUES (?,?,?,?,?,?)",
        (level.value, title, content, cfg.push_type, int(ok), cooldown_key),
    )
    conn.commit()
    conn.close()

    if ok:
        _update_cooldown(cooldown_key, cfg)
        new_count = _incr_daily_count(cfg)
        if new_count >= cfg.auto_high_threshold and not _is_auto_high(cfg):
            logger.info("📊 当日推送 %d 达阈值 %d，启用 high 模式", new_count, cfg.auto_high_threshold)
            _enable_auto_high(cfg)

    return ok


def get_push_stats(cfg: Optional[PushConfig] = None) -> dict:
    """推送统计"""
    cfg = cfg or get_default_config()
    init_push_tables(cfg)
    conn = _get_conn(cfg)
    today = _today_str()
    total = conn.execute("SELECT COUNT(*) FROM push_log").fetchone()[0]
    today_pushed = conn.execute("SELECT COUNT(*) FROM push_log WHERE date(created_at)=? AND success=1", (today,)).fetchone()[0]
    today_failed = conn.execute("SELECT COUNT(*) FROM push_log WHERE date(created_at)=? AND success=0", (today,)).fetchone()[0]
    _ah_row = conn.execute("SELECT auto_high_mode FROM push_daily_stats WHERE date=?", (today,)).fetchone()
    auto_high = bool(_ah_row and _ah_row["auto_high_mode"])
    recent = conn.execute(
        "SELECT * FROM push_log ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {
        "total": total, "today_pushed": today_pushed, "today_failed": today_failed,
        "auto_high_mode": auto_high, "max_daily": cfg.max_daily_push,
        "recent": [dict(r) for r in recent],
    }
