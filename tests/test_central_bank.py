"""central_bank.py 适配器测试

验证 us-stock-monitor 整合到 investment-os 的央行 Tab：
- 优先加载 us-stock-monitor 真实逻辑
- Fallback 到内置 _KNOWN_MEETINGS
- 返回结构正确（含倒计时、北京时间、美东时间）
"""
import datetime
import sys
from pathlib import Path

import pytest
import pytz

# 把 investment-os 加入 path
REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from data_sources.central_bank import (
    get_central_bank_events,
    get_monitor_status,
    _FALLBACK_KNOWN_MEETINGS,
    _CENTRAL_BANK_EVENTS,
    _next_known_meeting_fallback,
    _format_countdown,
    BJ, ET,
)


class TestMonitorStatus:
    """us-stock-monitor 加载状态"""

    def test_status_has_required_fields(self):
        s = get_monitor_status()
        assert "available" in s
        assert "source" in s
        assert "events_tracked" in s
        assert s["events_tracked"] == 4

    def test_source_is_valid_value(self):
        s = get_monitor_status()
        assert s["source"] in ("us-stock-monitor", "fallback")


class TestCentralBankEvents:
    """央行事件列表"""

    def test_returns_four_central_bank_events(self):
        d = get_central_bank_events(lookahead_days=120)
        assert len(d["events"]) == 4, f"应有4个央行事件，实际: {len(d['events'])}"

    def test_events_have_required_fields(self):
        d = get_central_bank_events(120)
        for e in d["events"]:
            assert "event_id" in e
            assert "name" in e
            assert "importance" in e
            assert "et_time" in e
            assert "event_datetime_bj" in e
            assert "event_datetime_et" in e
            assert "countdown" in e
            assert "days_until" in e
            assert "impact" in e
            assert "source" in e

    def test_events_sorted_by_time_ascending(self):
        d = get_central_bank_events(120)
        times = [e["event_datetime_bj"] for e in d["events"]]
        assert times == sorted(times), f"事件应按时间升序，实际: {times}"

    def test_fomc_is_critical_importance(self):
        d = get_central_bank_events(120)
        fomc = [e for e in d["events"] if e["event_id"] == "fomc_rate_decision"]
        assert fomc, "应包含 FOMC 利率决议"
        assert fomc[0]["importance"] == "critical"

    def test_event_ids_match_central_banks(self):
        d = get_central_bank_events(120)
        ids = {e["event_id"] for e in d["events"]}
        expected = {"fomc_rate_decision", "fomc_minutes", "boj_rate_decision", "ecb_rate_decision"}
        assert ids == expected, f"事件ID不匹配，实际: {ids}"

    def test_et_to_bj_conversion_correct(self):
        """美东 14:00 → 北京 次日 02:00"""
        d = get_central_bank_events(120)
        fomc = next(e for e in d["events"] if e["event_id"] == "fomc_rate_decision")
        # FOMC et_time=14:00，北京时间应为次日 02:00
        assert fomc["event_datetime_et"].endswith("14:00")
        # 北京时间比美东时间晚 12 小时（夏令时）或 13 小时（冬令时）
        et_dt = datetime.datetime.strptime(fomc["event_datetime_et"], "%Y-%m-%d %H:%M")
        bj_dt = datetime.datetime.strptime(fomc["event_datetime_bj"], "%Y-%m-%d %H:%M")
        delta_hours = (bj_dt - et_dt).total_seconds() / 3600
        assert delta_hours in (12, 13), f"BJ-ET 时差应为 12 或 13 小时，实际: {delta_hours}"

    def test_source_consistent_with_status(self):
        d = get_central_bank_events(120)
        s = get_monitor_status()
        assert d["source"] == s["source"], \
            f"事件source ({d['source']}) 应与 status source ({s['source']}) 一致"


class TestCountdownFormat:
    """倒计时格式"""

    def test_days_hours_format(self):
        td = datetime.timedelta(days=4, hours=14, minutes=30)
        assert _format_countdown(td) == "4天 14小时"

    def test_hours_minutes_format(self):
        td = datetime.timedelta(hours=5, minutes=30)
        assert _format_countdown(td) == "5小时 30分钟"

    def test_minutes_only_format(self):
        td = datetime.timedelta(minutes=45)
        assert _format_countdown(td) == "45分钟"

    def test_expired(self):
        td = datetime.timedelta(seconds=-100)
        assert _format_countdown(td) == "已过期"


class TestFallbackKnownMeetings:
    """Fallback 日期表完整性"""

    def test_fallback_has_all_central_banks(self):
        for key in ("fomc_meeting", "fomc_minutes", "boj_meeting", "ecb_meeting"):
            assert key in _FALLBACK_KNOWN_MEETINGS
            assert len(_FALLBACK_KNOWN_MEETINGS[key]) >= 4, \
                f"{key} 至少应有4个未来会议日期"

    def test_fallback_dates_are_future(self):
        """fallback 日期至少有一个在当前时间之后"""
        now_bj = datetime.datetime.now(BJ)
        for key, dates in _FALLBACK_KNOWN_MEETINGS.items():
            future_count = 0
            for date_str in dates:
                y, m, d = map(int, date_str.split("-"))
                et_dt = ET.localize(datetime.datetime(y, m, d, 14, 0))
                if et_dt.astimezone(BJ) > now_bj:
                    future_count += 1
            assert future_count > 0, f"{key} 应至少有一个未来日期"

    def test_fallback_lookup_returns_datetime(self):
        now = datetime.datetime(2026, 7, 25, tzinfo=BJ)
        dt = _next_known_meeting_fallback("fomc_meeting", "14:00", now)
        assert dt is not None
        assert dt.tzinfo is not None
        # FOMC 2026-07-29 14:00 ET = 2026-07-30 02:00 BJ
        assert dt.day == 30
        assert dt.hour == 2

    def test_fallback_handles_varies_et_time(self):
        """et_time='varies' 应回退到默认 14:00"""
        now = datetime.datetime(2026, 7, 25, tzinfo=BJ)
        dt = _next_known_meeting_fallback("boj_meeting", "varies", now)
        assert dt is not None
        # BOJ 2026-07-30 14:00 ET = 2026-07-31 02:00 BJ
        assert dt.day == 31
        assert dt.hour == 2


class TestCentralBankEventsConfig:
    """_CENTRAL_BANK_EVENTS 配置完整性"""

    def test_all_events_have_required_fields(self):
        for cfg in _CENTRAL_BANK_EVENTS:
            assert "event_id" in cfg
            assert "name" in cfg
            assert "schedule_rule" in cfg
            assert "importance" in cfg
            assert "et_time" in cfg
            assert "impact" in cfg

    def test_schedule_rules_match_known_meetings(self):
        for cfg in _CENTRAL_BANK_EVENTS:
            assert cfg["schedule_rule"] in _FALLBACK_KNOWN_MEETINGS, \
                f"schedule_rule {cfg['schedule_rule']} 不在 _FALLBACK_KNOWN_MEETINGS"

    def test_importance_values_valid(self):
        valid = {"critical", "high", "medium"}
        for cfg in _CENTRAL_BANK_EVENTS:
            assert cfg["importance"] in valid


class TestLookaheadFilter:
    """lookahead_days 过滤"""

    def test_short_lookahead_filters_events(self):
        # 只看未来 1 天，应该没有事件（最近的 FOMC 在 4 天后）
        d = get_central_bank_events(lookahead_days=1)
        assert len(d["events"]) == 0

    def test_medium_lookahead_includes_some(self):
        # 6 天能涵盖 FOMC(4天) + BOJ(5天)
        d = get_central_bank_events(lookahead_days=6)
        ids = {e["event_id"] for e in d["events"]}
        assert "fomc_rate_decision" in ids
        assert "boj_rate_decision" in ids
        assert "fomc_minutes" not in ids  # 25天后


class TestFetchedAtTimestamp:
    """fetched_at 时间戳"""

    def test_fetched_at_is_recent(self):
        d = get_central_bank_events(120)
        fetched = datetime.datetime.strptime(d["fetched_at"], "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        delta = (now - fetched).total_seconds()
        assert abs(delta) < 10, f"fetched_at 应在10秒内，实际差: {delta}s"
