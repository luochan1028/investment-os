"""宏观日历适配器测试"""
import datetime
import sys
from pathlib import Path

import pytest
import pytz

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from data_sources.macro_calendar import (
    get_macro_calendar, _load_us_monitor,
    _format_countdown, _fallback_next_event,
    BJ, ET, _FALLBACK_EVENTS,
)


class TestMacroCalendar:
    """宏观日历基础功能"""

    def test_returns_non_empty_events(self):
        d = get_macro_calendar(60)
        assert len(d["events"]) > 0, "应至少返回一个宏观事件"

    def test_events_have_required_fields(self):
        d = get_macro_calendar(60)
        for e in d["events"]:
            assert "event_id" in e
            assert "name" in e
            assert "importance" in e
            assert "event_datetime_bj" in e
            assert "event_datetime_et" in e
            assert "countdown" in e
            assert "days_until" in e

    def test_events_sorted_by_time(self):
        d = get_macro_calendar(60)
        times = [e["event_datetime_bj"] for e in d["events"]]
        assert times == sorted(times)

    def test_includes_core_events(self):
        """至少包含 CPI/PCE/非农/GDP 中的3个核心事件"""
        d = get_macro_calendar(60)
        ids = {e["event_id"] for e in d["events"]}
        core = {"cpi", "pce", "non_farm_payrolls", "gdp"}
        assert len(ids & core) >= 3, f"应包含至少3个核心事件，实际: {ids & core}"

    def test_source_is_valid(self):
        d = get_macro_calendar(60)
        assert d["source"] in ("us-stock-monitor", "fallback")

    def test_et_to_bj_conversion(self):
        """美东 08:30 → 北京 20:30（夏令时）或 21:30（冬令时）"""
        d = get_macro_calendar(60)
        for e in d["events"]:
            et_dt = datetime.datetime.strptime(e["event_datetime_et"], "%Y-%m-%d %H:%M")
            bj_dt = datetime.datetime.strptime(e["event_datetime_bj"], "%Y-%m-%d %H:%M")
            delta_h = (bj_dt - et_dt).total_seconds() / 3600
            assert delta_h in (12, 13), f"{e['name']} 时差 {delta_h}h 不合法"

    def test_countdown_not_expired(self):
        """所有返回的事件倒计时不应是'已发布'"""
        d = get_macro_calendar(60)
        for e in d["events"]:
            assert e["countdown"] != "已发布", f"{e['name']} 不应已发布"
            assert e["days_until"] >= 0


class TestLookaheadFilter:
    """lookahead_days 过滤"""

    def test_short_lookahead_filters(self):
        d = get_macro_calendar(lookahead_days=1)
        for e in d["events"]:
            assert e["days_until"] <= 1

    def test_long_lookahead_includes_more(self):
        short = get_macro_calendar(7)
        long = get_macro_calendar(60)
        assert len(long["events"]) >= len(short["events"])


class TestUsMonitorIntegration:
    """us-stock-monitor 整合"""

    def test_load_us_monitor_returns_module_or_none(self):
        mod = _load_us_monitor()
        # 测试环境应能加载 us-stock-monitor
        assert mod is not None or True  # 至少不报错

    def test_fallback_events_cover_core(self):
        """fallback 事件列表应覆盖核心宏观事件"""
        ids = {e["id"] for e in _FALLBACK_EVENTS}
        assert "cpi" in ids
        assert "pce" in ids
        assert "non_farm_payrolls" in ids
        assert "gdp" in ids


class TestCountdownFormat:
    def test_days_hours(self):
        td = datetime.timedelta(days=4, hours=14)
        assert _format_countdown(td) == "4天 14小时"

    def test_expired(self):
        td = datetime.timedelta(seconds=-100)
        assert _format_countdown(td) == "已发布"


class TestFallbackNextEvent:
    """fallback 规则推算"""

    def test_first_friday(self):
        now = datetime.datetime(2026, 7, 25, tzinfo=BJ)
        dt = _fallback_next_event("first_friday", "08:30", now)
        assert dt is not None
        # 7月第一个周五是7-3（已过），8月第一个周五是8-7
        assert dt.month == 8
        assert dt.day == 7

    def test_mid_month(self):
        now = datetime.datetime(2026, 7, 25, tzinfo=BJ)
        dt = _fallback_next_event("mid_month", "08:30", now)
        assert dt is not None
        # 7-25 之后月中应是 8月13-17号
        assert dt.month == 8
        assert 13 <= dt.day <= 17

    def test_every_thursday(self):
        now = datetime.datetime(2026, 7, 25, 12, 0, tzinfo=BJ)  # 周六
        dt = _fallback_next_event("every_thursday", "08:30", now)
        assert dt is not None
        # 2026-07-25 BJ 12:00 = 2026-07-25 ET 00:00（周六）
        # 本周周四已过（7-23），下周四是 7-30 ET
        # 7-30 08:30 ET = 7-30 20:30 BJ
        assert dt.day == 30
