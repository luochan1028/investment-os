"""投资研究操作系统 - 央行事件适配器

直接读取 us-stock-monitor 项目已修复的央行事件逻辑：
- _KNOWN_MEETINGS: FOMC/BOJ/ECB 等央行会议已知日期表
- get_next_event_datetime: 计算下次会议时间（北京时间）

整合 us-stock-monitor Bug 1 修复成果，避免代码重复。

降级策略：
1. us-stock-monitor 可 import → 用真实逻辑（_KNOWN_MEETINGS + 规则推算）
2. import 失败 → 用内置 fallback _KNOWN_MEETINGS 静态副本（仅央行事件）
"""
import datetime
import importlib
import importlib.util
import logging
import os
import sys
from typing import Optional

import pytz

logger = logging.getLogger("investment-os.central_bank")

# us-stock-monitor 项目根目录候选路径
_US_MONITOR_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "..", "_repos", "us-stock-monitor"),
    os.path.join(os.path.dirname(__file__), "..", "us-stock-monitor"),
    "/opt/us-stock-monitor",  # 生产部署路径
]

BJ = pytz.timezone("Asia/Shanghai")
ET = pytz.timezone("US/Eastern")

# 央行事件 ID → (schedule_rule, 中文名, 重要度, et_time, 影响描述)
# 对齐 us-stock-monitor/config/data_calendar.py 中的 ECONOMIC_CALENDAR
_CENTRAL_BANK_EVENTS = [
    {
        "event_id": "fomc_rate_decision",
        "name": "美联储利率决议",
        "schedule_rule": "fomc_meeting",
        "importance": "critical",
        "et_time": "14:00",
        "impact": "关注点阵图、鲍威尔新闻发布会（14:30）、措辞变化",
    },
    {
        "event_id": "fomc_minutes",
        "name": "美联储会议纪要",
        "schedule_rule": "fomc_minutes",
        "importance": "high",
        "et_time": "14:00",
        "impact": "揭示委员分歧和下一步政策倾向",
    },
    {
        "event_id": "boj_rate_decision",
        "name": "日本央行利率决议",
        "schedule_rule": "boj_meeting",
        "importance": "high",
        "et_time": "varies",
        "impact": "日元套利交易 unwind 风险，外溢影响美股",
    },
    {
        "event_id": "ecb_rate_decision",
        "name": "欧洲央行利率决议",
        "schedule_rule": "ecb_meeting",
        "importance": "high",
        "et_time": "varies",
        "impact": "欧元区政策外溢影响美股",
    },
]

# Fallback: 与 us-stock-monitor 的 _KNOWN_MEETINGS 保持同步
# 当 us-stock-monitor 不可 import 时使用（每年初更新一次）
_FALLBACK_KNOWN_MEETINGS = {
    "fomc_meeting": [
        "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
        "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-16",
    ],
    "fomc_minutes": [
        "2026-08-19", "2026-10-07", "2026-11-25", "2027-01-06",
        "2027-02-17", "2027-04-07", "2027-05-19", "2027-07-07",
    ],
    "boj_meeting": [
        "2026-07-30", "2026-09-19", "2026-10-29", "2026-12-18",
        "2027-01-19", "2027-03-18", "2027-04-29", "2027-06-15",
    ],
    "ecb_meeting": [
        "2026-07-23", "2026-09-10", "2026-10-29", "2026-12-17",
        "2027-02-04", "2027-03-12", "2027-04-23", "2027-06-11",
    ],
}

# 已加载的 us-stock-monitor 模块引用（懒加载）
_us_monitor_module = None
_us_monitor_load_attempted = False


def _load_us_monitor():
    """懒加载 us-stock-monitor 的 data_calendar 模块"""
    global _us_monitor_module, _us_monitor_load_attempted
    if _us_monitor_load_attempted:
        return _us_monitor_module
    _us_monitor_load_attempted = True

    for base in _US_MONITOR_CANDIDATES:
        base_abs = os.path.abspath(base)
        if not os.path.isdir(base_abs):
            continue
        config_dir = os.path.join(base_abs, "config")
        if not os.path.isfile(os.path.join(config_dir, "data_calendar.py")):
            continue
        try:
            if base_abs not in sys.path:
                sys.path.insert(0, base_abs)
            # 模块名带连字符需用 importlib 动态加载
            spec = importlib.util.spec_from_file_location(
                "us_stock_monitor_data_calendar",
                os.path.join(config_dir, "data_calendar.py"),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _us_monitor_module = mod
            logger.info("已加载 us-stock-monitor data_calendar: %s", base_abs)
            return mod
        except Exception as e:
            logger.warning("加载 us-stock-monitor (%s) 失败: %s", base_abs, e)

    logger.warning("us-stock-monitor 不可用，使用 fallback _KNOWN_MEETINGS")
    return None


def get_monitor_status() -> dict:
    """返回 us-stock-monitor 加载状态"""
    mod = _load_us_monitor()
    return {
        "available": mod is not None,
        "source": "us-stock-monitor" if mod else "fallback",
        "events_tracked": len(_CENTRAL_BANK_EVENTS),
        "loaded_path": getattr(mod, "__file__", None) if mod else None,
    }


def _next_known_meeting_fallback(schedule_rule: str, et_time_str: str,
                                  from_datetime: datetime.datetime) -> Optional[datetime.datetime]:
    """Fallback 实现：从 _FALLBACK_KNOWN_MEETINGS 查找下次会议"""
    dates = _FALLBACK_KNOWN_MEETINGS.get(schedule_rule, [])
    if not dates:
        return None

    try:
        hour, minute = map(int, et_time_str.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 14, 0

    for date_str in dates:
        try:
            y, m, d = map(int, date_str.split("-"))
            et_dt = ET.localize(datetime.datetime(y, m, d, hour, minute))
            if et_dt > from_datetime:
                return et_dt.astimezone(BJ)
        except ValueError:
            continue
    return None


def _compute_next_event(event_config: dict, from_dt: datetime.datetime,
                        us_monitor_mod) -> Optional[datetime.datetime]:
    """计算单个央行事件的下次发生时间（北京时间）"""
    schedule_rule = event_config["schedule_rule"]
    et_time_str = event_config["et_time"]

    if us_monitor_mod is not None:
        # 优先用 us-stock-monitor 的真实实现
        try:
            dt = us_monitor_mod.get_next_event_datetime(event_config["event_id"], from_dt)
            if dt is not None:
                return dt
        except Exception as e:
            logger.warning("us-stock-monitor get_next_event_datetime 失败 (%s): %s",
                          event_config["event_id"], e)

    # Fallback: 用本地 _FALLBACK_KNOWN_MEETINGS
    return _next_known_meeting_fallback(schedule_rule, et_time_str, from_dt)


def _format_countdown(td: datetime.timedelta) -> str:
    """格式化倒计时为 'X天 Y小时 Z分钟'"""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "已过期"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    if days > 0:
        return f"{days}天 {hours}小时"
    if hours > 0:
        return f"{hours}小时 {minutes}分钟"
    return f"{minutes}分钟"


def get_central_bank_events(lookahead_days: int = 120) -> dict:
    """获取未来 lookahead_days 天内的央行事件

    Returns:
        {
            "events": [
                {
                    "event_id": "fomc_rate_decision",
                    "name": "美联储利率决议",
                    "importance": "critical",
                    "et_time": "14:00",
                    "event_datetime_bj": "2026-07-30 02:00",  # 北京时间
                    "event_datetime_et": "2026-07-29 14:00",  # 美东时间
                    "countdown": "5天 8小时",
                    "days_until": 5,
                    "impact": "...",
                    "source": "us-stock-monitor" | "fallback",
                },
                ...
            ],
            "source": "us-stock-monitor" | "fallback",
            "fetched_at": "2026-07-25 18:00:00",
        }
    """
    us_monitor_mod = _load_us_monitor()
    now_bj = datetime.datetime.now(BJ)
    source = "us-stock-monitor" if us_monitor_mod is not None else "fallback"

    events = []
    for cfg in _CENTRAL_BANK_EVENTS:
        try:
            next_dt = _compute_next_event(cfg, now_bj, us_monitor_mod)
            if next_dt is None:
                continue
            days_until = (next_dt - now_bj).days
            if days_until > lookahead_days:
                continue
            countdown = _format_countdown(next_dt - now_bj)
            events.append({
                "event_id": cfg["event_id"],
                "name": cfg["name"],
                "importance": cfg["importance"],
                "et_time": cfg["et_time"],
                "event_datetime_bj": next_dt.strftime("%Y-%m-%d %H:%M"),
                "event_datetime_et": next_dt.astimezone(ET).strftime("%Y-%m-%d %H:%M"),
                "countdown": countdown,
                "days_until": days_until,
                "impact": cfg["impact"],
                "source": source,
            })
        except Exception as e:
            logger.warning("计算央行事件 %s 失败: %s", cfg["event_id"], e)

    # 按时间升序
    events.sort(key=lambda e: e["event_datetime_bj"])

    return {
        "events": events,
        "source": source,
        "fetched_at": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
    }
