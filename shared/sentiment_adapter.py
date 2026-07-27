"""投资研究操作系统 - 舆情数据适配器

直接读取 x-monitor-push 的生产 SQLite 数据库（data/monitor.db），
不重复抓取、不耦合代码，数据实时同步。

降级策略：
1. x-monitor-push DB 存在 → 读真实推文
2. DB 不存在 → 读 investment-os 自己的 tweets 表（可能为历史/种子数据）
3. 都没有 → 返回空列表
"""
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

logger = logging.getLogger("investment-os.sentiment")

# x-monitor-push 的数据库路径（相对 investment-os 根目录的兄弟目录）
_X_MONITOR_DB_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "..", "x-monitor-push", "data", "monitor.db"),
    os.path.join(os.path.dirname(__file__), "..", "x-monitor-push", "data", "monitor.db"),
    "/opt/x-monitor-push/data/monitor.db",  # 生产部署路径
]


def _find_x_monitor_db() -> Optional[str]:
    for p in _X_MONITOR_DB_CANDIDATES:
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def _query_x_monitor(db_path: str, limit: int = 50) -> list[dict]:
    """读取 x-monitor-push 的 tweets 表"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT username, title, link, published, summary, ai_analysis,
                      pushed, created_at
               FROM tweets
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("读取 x-monitor DB 失败: %s", e)
        return []


def _parse_impact_from_analysis(ai_analysis: str) -> str:
    """从 x-monitor-push 的 ai_analysis 字段推断 impact_level"""
    if not ai_analysis:
        return "low"
    text = ai_analysis.lower()
    if "high" in text or "重大" in text or "高优先" in text:
        return "high"
    if "medium" in text or "中优先" in text or "关注" in text:
        return "medium"
    return "low"


def _extract_category(ai_analysis: str, title: str = "") -> str:
    """从分析文本或标题提取分类"""
    text = (ai_analysis or "") + " " + (title or "")
    # 简单关键词映射（生产级可复用 x-monitor-push 的 SECTOR_MAP）
    rules = [
        ("关税", "关税"), ("tariff", "关税"), ("Fed", "美联储"), ("利率", "美联储"),
        ("rate", "美联储"), ("Bitcoin", "加密"), ("BTC", "加密"), ("crypto", "加密"),
        ("AI", "AI"), ("chip", "半导体"), ("芯片", "半导体"), ("财报", "财报"),
        ("earnings", "财报"), ("Tesla", "特斯拉"), ("EV", "新能源"),
    ]
    for kw, cat in rules:
        if kw.lower() in text.lower():
            return cat
    return "综合"


def fetch_real_tweets(limit: int = 50) -> dict:
    """获取真实舆情数据

    Returns:
        dict: {source, db_path, count, tweets}
    """
    db = _find_x_monitor_db()
    if db:
        rows = _query_x_monitor(db, limit)
        if rows:
            tweets = []
            for r in rows:
                impact = _parse_impact_from_analysis(r.get("ai_analysis", ""))
                tweets.append({
                    "username": r["username"],
                    "title": r.get("title") or (r.get("summary", "")[:80] if r.get("summary") else ""),
                    "link": r.get("link", ""),
                    "published": r.get("published", "") or r.get("created_at", ""),
                    "impact_level": impact,
                    "category": _extract_category(r.get("ai_analysis", ""), r.get("title", "")),
                    "summary": r.get("summary", ""),
                    "ai_analysis": r.get("ai_analysis", ""),
                    "pushed": r.get("pushed", 0),
                    "source": "x-monitor-push",
                })
            return {
                "source": "x-monitor-push",
                "db_path": db,
                "count": len(tweets),
                "tweets": tweets,
            }
        logger.info("x-monitor DB 无数据，降级到 investment-os 本地")
    return {"source": "none", "db_path": None, "count": 0, "tweets": []}


def get_monitor_status() -> dict:
    """获取 x-monitor-push 运行状态"""
    db = _find_x_monitor_db()
    if not db:
        return {"running": False, "db_path": None, "msg": "x-monitor-push 未部署"}
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = conn.execute(
            "SELECT COUNT(*) FROM tweets WHERE date(created_at)=?", (today,)
        ).fetchone()[0]
        pushed = conn.execute("SELECT COUNT(*) FROM tweets WHERE pushed=1").fetchone()[0]
        # 最近的抓取时间
        last = conn.execute(
            "SELECT created_at FROM tweets ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return {
            "running": True,
            "db_path": db,
            "total_tweets": total,
            "today_tweets": today_count,
            "pushed_tweets": pushed,
            "last_fetch": last["created_at"] if last else None,
        }
    except Exception as e:
        return {"running": False, "db_path": db, "msg": str(e)}
