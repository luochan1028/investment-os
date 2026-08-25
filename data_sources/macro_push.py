"""经济数据倒计时推送模块

集成 us-stock-monitor 的多级提醒功能：
- 提前1天/1小时/15分钟推送倒计时提醒
- SQLite 防重复（当日有效）
- 复用 investment-os 的统一推送层
"""
import datetime
import logging
import os
import sqlite3
from typing import Optional

import pytz

from .macro_calendar import get_macro_calendar, _load_us_monitor

logger = logging.getLogger("investment-os.macro_push")

BJ = pytz.timezone("Asia/Shanghai")

# 提醒时间点（分钟）
REMIND_INTERVALS = [1440, 60, 15]

# 推送记录数据库
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "macro_push.db")


def _init_db():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pushed_events (
            push_key TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            remind_minutes INTEGER NOT NULL,
            pushed_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pushed_at ON pushed_events(pushed_at)")
    conn.commit()
    conn.close()


def _is_pushed(push_key: str) -> bool:
    today = datetime.datetime.now(BJ).strftime("%Y-%m-%d")
    conn = sqlite3.connect(_DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM pushed_events WHERE push_key=? AND date(pushed_at)=?",
        (push_key, today),
    ).fetchone()
    conn.close()
    return row is not None


def _mark_pushed(push_key: str, event_id: str, remind_minutes: int):
    now = datetime.datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO pushed_events (push_key, event_id, remind_minutes, pushed_at) VALUES (?, ?, ?, ?)",
        (push_key, event_id, remind_minutes, now),
    )
    conn.commit()
    conn.close()


def _clean_old_records():
    cutoff = (datetime.datetime.now(BJ) - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("DELETE FROM pushed_events WHERE pushed_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def _build_reminder_content(event: dict, minutes_remaining: int) -> str:
    """构建推送消息内容（Markdown格式）"""
    importance_emoji = {"critical": "🔴", "high": "🟡", "medium": "🟢"}
    emoji = importance_emoji.get(event.get("importance", ""), "⚪")

    if minutes_remaining >= 1440:
        time_label = "**明天**"
    elif minutes_remaining >= 60:
        time_label = "**1小时后**"
    else:
        time_label = "**15分钟后**"

    content = f"## {emoji} 数据发布提醒\n\n"
    content += f"### {event.get('name', '')} ({event.get('name_en', '')})\n\n"
    content += f"⏰ 发布时间: {time_label}\n"
    content += f"📅 北京时间: {event.get('event_datetime_bj', '')}\n"
    content += f"⚡ 重要程度: {event.get('importance', '').upper()}\n\n"

    # 市场影响分析
    impact = event.get("impact_analysis", {})
    if impact:
        content += "---\n\n### 可能的市场影响\n\n"
        if "key_point" in impact:
            content += f"**核心关注**: {impact['key_point']}\n\n"
        if "better_than_expected" in impact:
            content += "**好于预期**:\n"
            for p in impact["better_than_expected"]:
                content += f"- {p}\n"
            content += "\n"
        if "worse_than_expected" in impact:
            content += "**差于预期**:\n"
            for p in impact["worse_than_expected"]:
                content += f"- {p}\n"
            content += "\n"

    # 历史数据
    hist = event.get("historical_data", [])
    if hist:
        content += "---\n\n### 上次数据\n\n"
        h = hist[0]
        content += f"- 日期: {h.get('date', '')}\n"
        content += f"- 实际值: {h.get('actual', '')}\n"
        content += f"- 预期值: {h.get('expected', '')}\n"
        content += f"- 前值: {h.get('previous', '')}\n"
        if h.get("market_reaction"):
            content += f"- 市场反应: {h['market_reaction']}\n"
        content += "\n"

    # 仓位建议
    pa = event.get("position_advice", {})
    if pa:
        content += "---\n\n### 仓位建议\n\n"
        if pa.get("bullish"):
            content += f"🟢 **看涨**: {pa['bullish']}\n\n"
        if pa.get("bearish"):
            content += f"🔴 **看跌**: {pa['bearish']}\n\n"
        if pa.get("neutral"):
            content += f"🟡 **中性**: {pa['neutral']}\n\n"

    content += "---\n> 以上分析仅供参考，不构成投资建议\n"
    return content


def check_and_push() -> dict:
    """检查所有宏观事件，在到达提醒时间点时推送

    Returns:
        {"checked": N, "pushed": N, "skipped": N, "errors": [...]}
    """
    _init_db()
    _clean_old_records()

    from shared.pusher import push_alert, PushLevel

    now = datetime.datetime.now(BJ)
    data = get_macro_calendar(lookahead_days=7)
    events = data.get("events", [])

    result = {"checked": len(events), "pushed": 0, "skipped": 0, "errors": []}

    for event in events:
        try:
            dt_str = event.get("event_datetime_bj", "")
            if not dt_str:
                continue
            event_dt = BJ.localize(datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M"))
            delta_minutes = (event_dt - now).total_seconds() / 60

            for remind_min in REMIND_INTERVALS:
                # 允许 ±5 分钟误差窗口
                if abs(delta_minutes - remind_min) <= 5:
                    push_key = f"{event['event_id']}_{remind_min}_{now.strftime('%Y%m%d')}"
                    if _is_pushed(push_key):
                        result["skipped"] += 1
                        continue

                    level_map = {
                        "critical": PushLevel.P0,
                        "high": PushLevel.P1,
                        "medium": PushLevel.P2,
                    }
                    push_level = level_map.get(event.get("importance", ""), PushLevel.P2)

                    title = f"{event.get('name', '')} - {'明天发布' if remind_min >= 1440 else f'{remind_min}分钟后发布'}"
                    content = _build_reminder_content(event, remind_min)

                    ok = push_alert(
                        level=push_level,
                        title=title,
                        content=content,
                        alert_type="macro_reminder",
                        symbol=event["event_id"],
                        force=(push_level == PushLevel.P0),
                    )

                    if ok:
                        _mark_pushed(push_key, event["event_id"], remind_min)
                        result["pushed"] += 1
                        logger.info("已推送 %s 倒计时提醒 (%dmin)", event["event_id"], remind_min)
        except Exception as e:
            result["errors"].append(f"{event.get('event_id', '?')}: {e}")
            logger.warning("推送宏观事件 %s 失败: %s", event.get("event_id"), e)

    return result


def push_weekly_calendar() -> dict:
    """推送本周经济数据日历"""
    _init_db()
    from shared.pusher import push_alert, PushLevel

    data = get_macro_calendar(lookahead_days=7)
    events = data.get("events", [])
    if not events:
        return {"pushed": False, "reason": "本周无事件"}

    importance_emoji = {"critical": "🔴", "high": "🟡", "medium": "🟢"}

    content = "## 本周美股关键数据日历\n\n"
    content += f"> 共 {len(events)} 个重要数据发布\n\n---\n\n"

    for e in events:
        emoji = importance_emoji.get(e.get("importance", ""), "⚪")
        content += f"### {emoji} {e.get('name', '')} ({e.get('name_en', '')})\n"
        content += f"📅 {e.get('event_datetime_bj', '')}\n"
        content += f"⏰ 倒计时: {e.get('countdown', '')}\n"
        if e.get("impact"):
            content += f"📊 {e['impact']}\n"
        content += "\n"

    content += "---\n> - 🔴 极度重要 | 🟡 重要 | 🟢 一般\n"
    content += "> - 仓位建议仅供参考，不构成投资建议\n"

    ok = push_alert(
        level=PushLevel.P1,
        title="本周美股数据日历",
        content=content,
        alert_type="macro_weekly",
        force=True,
    )

    return {"pushed": ok, "events_count": len(events)}
