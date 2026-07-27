"""投资研究操作系统 - 宏观日历适配器

复用 us-stock-monitor 的 ECONOMIC_CALENDAR（14 个事件的真实发布规则），
计算每个事件下次发布时间（北京时间）和倒计时。

数据源：
1. us-stock-monitor 可 import → 用真实 ECONOMIC_CALENDAR + get_next_event_datetime
2. import 失败 → 用内置 fallback 配置（覆盖核心事件）
"""
import datetime
import importlib
import importlib.util
import logging
import os
from typing import Optional

import pytz

logger = logging.getLogger("investment-os.macro_calendar")

_US_MONITOR_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "..", "_repos", "us-stock-monitor"),
    os.path.join(os.path.dirname(__file__), "..", "us-stock-monitor"),
    "/opt/us-stock-monitor",
]

BJ = pytz.timezone("Asia/Shanghai")
ET = pytz.timezone("US/Eastern")

# Fallback: 核心宏观事件配置（与 us-stock-monitor ECONOMIC_CALENDAR 对齐）
_FALLBACK_EVENTS = [
    {"id": "non_farm_payrolls", "name": "非农就业报告", "importance": "critical",
     "schedule_rule": "first_friday", "et_time": "08:30",
     "impact": "关注失业率、劳动参与率、平均时薪增速",
     "bullish": "非农大幅高于预期时：可适当加仓，关注金融、消费板块",
     "bearish": "非农大幅低于预期时：减仓至6成以下，增加防御性仓位"},
    {"id": "cpi", "name": "消费者物价指数 CPI", "importance": "critical",
     "schedule_rule": "mid_month", "et_time": "08:30",
     "impact": "核心CPI（剔除食品能源）更受关注，美联储目标2%",
     "bullish": "CPI回落至3%以下：可加仓至8成以上，成长股受益",
     "bearish": "CPI高于预期且核心CPI持续在3%以上：减仓至5成"},
    {"id": "pce", "name": "PCE 物价指数", "importance": "critical",
     "schedule_rule": "end_of_month", "et_time": "08:30",
     "impact": "美联储货币政策最核心的参考指标",
     "bullish": "核心PCE降至2.5%以下：大幅加仓，降息周期确认",
     "bearish": "核心PCE高于3%：减仓至4-5成，防御为主"},
    {"id": "gdp", "name": "国内生产总值 GDP", "importance": "critical",
     "schedule_rule": "quarterly", "et_time": "08:30",
     "impact": "关注初值、修正值、终值三版数据",
     "bullish": "GDP强劲：利好周期股，金融、工业、材料板块受益",
     "bearish": "连续两个季度负增长 = 技术性衰退"},
    {"id": "unemployment_rate", "name": "失业率", "importance": "high",
     "schedule_rule": "first_friday", "et_time": "08:30",
     "impact": "4%以下是健康水平，超过5%需警惕",
     "bearish": "失业率连续上升，接近4.5%：减仓至5成，警惕Sahm Rule触发"},
    {"id": "ppi", "name": "生产者物价指数 PPI", "importance": "high",
     "schedule_rule": "mid_month", "et_time": "08:30",
     "impact": "领先CPI，是通胀先行指标"},
    {"id": "adp_employment", "name": "ADP就业报告", "importance": "medium",
     "schedule_rule": "first_wednesday", "et_time": "08:15",
     "impact": "非农前两天发布，是重要前瞻指标"},
    {"id": "jobless_claims", "name": "初请失业金人数", "importance": "medium",
     "schedule_rule": "every_thursday", "et_time": "08:30",
     "impact": "关注四周移动平均值，22万以下为健康"},
]

_us_monitor_module = None
_us_monitor_load_attempted = False


def _load_us_monitor():
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
    logger.warning("us-stock-monitor 不可用，使用 fallback 宏观事件配置")
    return None


def _format_countdown(td: datetime.timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "已发布"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    if days > 0:
        return f"{days}天 {hours}小时"
    if hours > 0:
        return f"{hours}小时 {minutes}分钟"
    return f"{minutes}分钟"


def _fallback_next_event(schedule_rule: str, et_time_str: str,
                          from_datetime: datetime.datetime) -> Optional[datetime.datetime]:
    """Fallback: 简单规则推算（不如 us-stock-monitor 准确，但覆盖核心场景）"""
    try:
        hour, minute = map(int, et_time_str.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 8, 30

    now_et = from_datetime.astimezone(ET)
    y, mo = now_et.year, now_et.month

    import calendar

    candidates = []  # 全部用 naive datetime（视为 ET）

    if schedule_rule == "first_friday":
        for d in range(1, 8):
            if datetime.date(y, mo, d).weekday() == 4:
                candidates.append(datetime.datetime(y, mo, d, hour, minute))
                break
        nm, ny = (mo+1, y) if mo < 12 else (1, y+1)
        for d in range(1, 8):
            if datetime.date(ny, nm, d).weekday() == 4:
                candidates.append(datetime.datetime(ny, nm, d, hour, minute))
                break

    elif schedule_rule == "mid_month":
        for d in [13, 14, 15, 16, 17]:
            candidates.append(datetime.datetime(y, mo, d, hour, minute))
        nm, ny = (mo+1, y) if mo < 12 else (1, y+1)
        for d in [13, 14, 15, 16, 17]:
            candidates.append(datetime.datetime(ny, nm, d, hour, minute))

    elif schedule_rule == "end_of_month":
        last_day = calendar.monthrange(y, mo)[1]
        for d in [last_day, last_day-1, last_day-2, last_day-3]:
            if d >= 1:
                candidates.append(datetime.datetime(y, mo, d, hour, minute))
        nm, ny = (mo+1, y) if mo < 12 else (1, y+1)
        nlast = calendar.monthrange(ny, nm)[1]
        for d in [nlast, nlast-1, nlast-2, nlast-3]:
            if d >= 1:
                candidates.append(datetime.datetime(ny, nm, d, hour, minute))

    elif schedule_rule == "quarterly":
        for qm in [1, 4, 7, 10]:
            if qm >= mo:
                ld = calendar.monthrange(y, qm)[1]
                candidates.append(datetime.datetime(y, qm, ld, hour, minute))
        for qm in [1, 4, 7, 10]:
            ld = calendar.monthrange(y+1, qm)[1]
            candidates.append(datetime.datetime(y+1, qm, ld, hour, minute))

    elif schedule_rule == "first_wednesday":
        for d in range(1, 8):
            if datetime.date(y, mo, d).weekday() == 2:
                candidates.append(datetime.datetime(y, mo, d, hour, minute))
                break
        nm, ny = (mo+1, y) if mo < 12 else (1, y+1)
        for d in range(1, 8):
            if datetime.date(ny, nm, d).weekday() == 2:
                candidates.append(datetime.datetime(ny, nm, d, hour, minute))
                break

    elif schedule_rule == "every_thursday":
        # 本周周四（naive，视为 ET）
        days_ahead = (3 - now_et.weekday()) % 7
        if days_ahead == 0 and now_et.hour >= hour:
            days_ahead = 7
        thursday = datetime.datetime(y, mo, now_et.day, hour, minute) + datetime.timedelta(days=days_ahead)
        candidates.append(thursday)
        candidates.append(thursday + datetime.timedelta(days=7))

    # 找第一个 > from_datetime 的候选（统一 localize naive datetime）
    for cdt in candidates:
        try:
            et_dt = ET.localize(cdt)
            if et_dt > from_datetime:
                return et_dt.astimezone(BJ)
        except Exception:
            continue
    return None


def get_macro_calendar(lookahead_days: int = 60) -> dict:
    """获取未来 lookahead_days 天内的宏观事件

    Returns:
        {
            "events": [
                {
                    "event_id": "cpi",
                    "name": "消费者物价指数 CPI",
                    "importance": "critical",
                    "et_time": "08:30",
                    "event_datetime_bj": "2026-08-13 20:30",
                    "event_datetime_et": "2026-08-13 08:30",
                    "countdown": "19天 8小时",
                    "days_until": 19,
                    "impact": "...",
                    "position_advice": {"bullish": "...", "bearish": "..."},
                    "source": "us-stock-monitor" | "fallback",
                },
            ],
            "source": "us-stock-monitor" | "fallback",
            "fetched_at": "...",
        }
    """
    us_monitor_mod = _load_us_monitor()
    now_bj = datetime.datetime.now(BJ)
    source = "us-stock-monitor" if us_monitor_mod is not None else "fallback"

    # 获取事件列表
    if us_monitor_mod is not None:
        events_cfg = []
        for eid, cfg in us_monitor_mod.ECONOMIC_CALENDAR.items():
            if cfg.get("schedule_rule") == "varies":
                continue  # 跳过无固定规则的事件（如 fed_speech）
            events_cfg.append({
                "id": eid,
                "name": cfg["name"],
                "importance": cfg["importance"],
                "schedule_rule": cfg["schedule_rule"],
                "et_time": cfg.get("et_time", "08:30"),
                "impact": cfg.get("impact_analysis", {}).get("key_point", ""),
                "position_advice": cfg.get("position_advice", {}),
            })
    else:
        events_cfg = _FALLBACK_EVENTS

    events = []
    for cfg in events_cfg:
        try:
            if us_monitor_mod is not None:
                dt = us_monitor_mod.get_next_event_datetime(cfg["id"], now_bj)
            else:
                dt = _fallback_next_event(cfg["schedule_rule"], cfg["et_time"], now_bj)

            if dt is None:
                continue
            days_until = (dt - now_bj).days
            if days_until > lookahead_days:
                continue

            event = {
                "event_id": cfg["id"],
                "name": cfg["name"],
                "importance": cfg["importance"],
                "et_time": cfg["et_time"],
                "event_datetime_bj": dt.strftime("%Y-%m-%d %H:%M"),
                "event_datetime_et": dt.astimezone(ET).strftime("%Y-%m-%d %H:%M"),
                "countdown": _format_countdown(dt - now_bj),
                "days_until": days_until,
                "impact": cfg.get("impact", ""),
                "source": source,
            }
            pa = cfg.get("position_advice", {})
            if pa:
                event["position_advice"] = pa
            events.append(event)
        except Exception as e:
            logger.warning("计算宏观事件 %s 失败: %s", cfg["id"], e)

    # 按时间升序
    events.sort(key=lambda e: e["event_datetime_bj"])

    return {
        "events": events,
        "source": source,
        "fetched_at": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
    }
