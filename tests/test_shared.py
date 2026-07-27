"""investment-os shared 模块测试 - pusher + sentiment_adapter

覆盖：
- PushConfig.from_env / validate
- init_push_tables 幂等
- 冷却与频控（is_in_cooldown / _update_cooldown）
- push_alert 冷却 / force / HIGH 豁免 / 每日上限 / 自动 high / 无通道 / 统计
- sentiment_adapter: _find_x_monitor_db / _parse_impact / _extract_category
                    / fetch_real_tweets / get_monitor_status

运行:
    cd d:\\software\\investment-os && python -m pytest tests/test_shared.py -v
"""
import os
import sqlite3
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

# 确保能 import shared.* (项目根在 tests/ 上一级)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import shared.pusher as pusher_mod
from shared.pusher import (
    PushConfig,
    PushLevel,
    init_push_tables,
    is_in_cooldown,
    _update_cooldown,
    _is_auto_high,
    push_alert,
    get_push_stats,
)
from shared import sentiment_adapter
from shared.sentiment_adapter import (
    _find_x_monitor_db,
    _parse_impact_from_analysis,
    _extract_category,
    fetch_real_tweets,
    get_monitor_status,
)


# ==================== 公共 fixture ====================

@pytest.fixture(autouse=True)
def _reset_default_config():
    """每个测试前后重置 pusher 的默认配置单例，避免测试间泄漏。"""
    pusher_mod._default_config = None
    yield
    pusher_mod._default_config = None


@pytest.fixture
def cfg(tmp_path):
    """使用临时数据库的 PushConfig（pushplus 通道，token 已配置）。"""
    return PushConfig(
        push_type="pushplus",
        pushplus_token="test-token",
        wxpusher_token="",
        wxpusher_uid="",
        serverchan_key="",
        db_path=str(tmp_path / "test.db"),
        max_daily_push=50,
        auto_high_threshold=40,
        cooldown_minutes=60,
    )


@pytest.fixture
def mock_httpx(monkeypatch):
    """mock pusher._get_client，避免真实 httpx 网络调用。

    返回 (fake_client, fake_resp)；测试可调整 fake_resp.json.return_value
    控制 pushplus(200) / wxpusher(1000) / serverchan(0) 的成功失败。
    """
    fake_resp = MagicMock()
    fake_client = MagicMock()
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = False
    fake_client.post.return_value = fake_resp
    monkeypatch.setattr("shared.pusher._get_client", lambda _cfg: fake_client)
    return fake_client, fake_resp


def _ok_resp():
    return {"code": 200, "msg": "ok"}


def _query_one(db_path, sql, args=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(sql, args).fetchone()
    conn.close()
    return row


# ==================== PushConfig ====================

class TestPushConfig:
    def test_from_env(self, monkeypatch):
        """from_env() 能从环境变量加载所有配置字段。"""
        # 屏蔽真实 .env 文件加载，保证测试 hermetic
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setenv("PUSH_TYPE", "wxpusher")
        monkeypatch.setenv("PUSHPLUS_TOKEN", "pp-token")
        monkeypatch.setenv("WXPUSHER_TOKEN", "wx-token")
        monkeypatch.setenv("WXPUSHER_UID", "uid-abc")
        monkeypatch.setenv("SERVERCHAN_KEY", "sc-key")
        monkeypatch.setenv("PROXY_URL", "http://127.0.0.1:7890")
        monkeypatch.setenv("MAX_DAILY_PUSH", "30")
        monkeypatch.setenv("AUTO_HIGH_THRESHOLD", "25")
        monkeypatch.setenv("ALERT_COOLDOWN_MINUTES", "15")
        monkeypatch.setenv("PORTFOLIO_DB_PATH", "/tmp/xyz.db")

        c = PushConfig.from_env()
        assert c.push_type == "wxpusher"
        assert c.pushplus_token == "pp-token"
        assert c.wxpusher_token == "wx-token"
        assert c.wxpusher_uid == "uid-abc"
        assert c.serverchan_key == "sc-key"
        assert c.proxy_url == "http://127.0.0.1:7890"
        assert c.max_daily_push == 30
        assert c.auto_high_threshold == 25
        assert c.cooldown_minutes == 15
        assert c.db_path == "/tmp/xyz.db"

    def test_from_env_defaults(self, monkeypatch):
        """未设置环境变量时使用默认值。"""
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        # 清掉可能存在的环境变量
        for k in ("PUSH_TYPE", "PUSHPLUS_TOKEN", "WXPUSHER_TOKEN", "WXPUSHER_UID",
                  "SERVERCHAN_KEY", "PROXY_URL", "MAX_DAILY_PUSH",
                  "AUTO_HIGH_THRESHOLD", "ALERT_COOLDOWN_MINUTES", "PORTFOLIO_DB_PATH"):
            monkeypatch.delenv(k, raising=False)
        c = PushConfig.from_env()
        assert c.push_type == "pushplus"
        assert c.max_daily_push == 50
        assert c.auto_high_threshold == 40
        assert c.cooldown_minutes == 60
        assert c.db_path == "data/investment_os.db"

    def test_validate_pushplus_no_token(self):
        c = PushConfig(push_type="pushplus", pushplus_token="")
        errs = c.validate()
        assert any("PUSHPLUS_TOKEN" in e for e in errs)

    def test_validate_pushplus_ok(self):
        c = PushConfig(push_type="pushplus", pushplus_token="t")
        assert c.validate() == []

    def test_validate_wxpusher_no_token(self):
        c = PushConfig(push_type="wxpusher", wxpusher_token="", wxpusher_uid="u")
        errs = c.validate()
        assert any("WXPUSHER_TOKEN" in e for e in errs)

    def test_validate_wxpusher_no_uid(self):
        c = PushConfig(push_type="wxpusher", wxpusher_token="t", wxpusher_uid="")
        errs = c.validate()
        assert any("WXPUSHER_UID" in e for e in errs)

    def test_validate_wxpusher_ok(self):
        c = PushConfig(push_type="wxpusher", wxpusher_token="t", wxpusher_uid="u")
        assert c.validate() == []

    def test_validate_serverchan_no_key(self):
        c = PushConfig(push_type="serverchan", serverchan_key="")
        errs = c.validate()
        assert any("SERVERCHAN_KEY" in e for e in errs)

    def test_validate_serverchan_ok(self):
        c = PushConfig(push_type="serverchan", serverchan_key="k")
        assert c.validate() == []


# ==================== init_push_tables ====================

class TestInitTables:
    def test_idempotent(self, cfg):
        """init_push_tables() 多次调用不报错且表存在。"""
        init_push_tables(cfg)
        init_push_tables(cfg)  # 第二次应幂等
        conn = sqlite3.connect(cfg.db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "push_log" in tables
        assert "push_cooldown" in tables
        assert "push_daily_stats" in tables

    def test_creates_db_file(self, cfg):
        init_push_tables(cfg)
        assert os.path.exists(cfg.db_path)

    def test_creates_index(self, cfg):
        init_push_tables(cfg)
        conn = sqlite3.connect(cfg.db_path)
        idx = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()]
        conn.close()
        assert "idx_push_log_created" in idx


# ==================== 冷却与频控 ====================

class TestCooldown:
    def test_is_in_cooldown_first_time_false(self, cfg):
        """首次查询无记录，返回 False。"""
        init_push_tables(cfg)
        assert is_in_cooldown("k1", cfg) is False

    def test_is_in_cooldown_after_update_true(self, cfg):
        """记录后同 key 在冷却期内返回 True。"""
        init_push_tables(cfg)
        _update_cooldown("k1", cfg)
        assert is_in_cooldown("k1", cfg) is True

    def test_is_in_cooldown_different_key_independent(self, cfg):
        """不同 key 互相独立。"""
        init_push_tables(cfg)
        _update_cooldown("k1", cfg)
        assert is_in_cooldown("k1", cfg) is True
        assert is_in_cooldown("k2", cfg) is False

    def test_update_cooldown_increments_atomically(self, cfg):
        """_update_cooldown 原子 upsert：多次调用 push_count 递增。"""
        init_push_tables(cfg)
        _update_cooldown("k1", cfg)
        _update_cooldown("k1", cfg)
        _update_cooldown("k1", cfg)
        row = _query_one(
            cfg.db_path,
            "SELECT push_count FROM push_cooldown WHERE key=?",
            ("k1",),
        )
        assert row["push_count"] == 3

    def test_update_cooldown_upserts(self, cfg):
        """同 key 第二次走 UPDATE 分支而非 INSERT。"""
        init_push_tables(cfg)
        _update_cooldown("k1", cfg)
        _update_cooldown("k1", cfg)
        conn = sqlite3.connect(cfg.db_path)
        n = conn.execute(
            "SELECT COUNT(*) FROM push_cooldown WHERE key=?", ("k1",)
        ).fetchone()[0]
        conn.close()
        assert n == 1


# ==================== push_alert ====================

class TestPushAlert:
    def test_cooldown_skips_second(self, cfg, mock_httpx):
        """同 key 第二次（非 high、非 force）被冷却跳过。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = _ok_resp()
        r1 = push_alert(PushLevel.MEDIUM, "t1", "c1", alert_type="stop", symbol="AAPL", cfg=cfg)
        assert r1 is True
        r2 = push_alert(PushLevel.MEDIUM, "t1", "c1", alert_type="stop", symbol="AAPL", cfg=cfg)
        assert r2 is False  # 冷却中

    def test_force_skips_cooldown(self, cfg, mock_httpx):
        """force=True 跳过冷却。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = _ok_resp()
        assert push_alert(PushLevel.MEDIUM, "t", "c", symbol="AAPL", cfg=cfg) is True
        # 同 key 第二次被冷却
        assert push_alert(PushLevel.MEDIUM, "t", "c", symbol="AAPL", cfg=cfg) is False
        # force=True 跳过冷却，再次推送
        assert push_alert(PushLevel.MEDIUM, "t", "c", symbol="AAPL", force=True, cfg=cfg) is True

    def test_high_level_exempt_cooldown(self, cfg, mock_httpx):
        """HIGH 级别豁免冷却。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = _ok_resp()
        assert push_alert(PushLevel.MEDIUM, "t", "c", symbol="AAPL", cfg=cfg) is True
        # HIGH 豁免冷却，同 key 仍能推送
        assert push_alert(PushLevel.HIGH, "t", "c", symbol="AAPL", cfg=cfg) is True

    def test_high_level_exempt_daily_limit(self, cfg, mock_httpx):
        """HIGH 级别也豁免每日上限。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = _ok_resp()
        cfg.max_daily_push = 0  # 立即触达上限
        # 非-high 会被上限拦下
        assert push_alert(PushLevel.MEDIUM, "t1", "c1", symbol="AAPL", cfg=cfg) is False
        # HIGH 仍能推送
        assert push_alert(PushLevel.HIGH, "t2", "c2", symbol="AAPL", cfg=cfg) is True

    def test_daily_limit_triggers_auto_high(self, cfg, mock_httpx):
        """每日上限触发后非 high 被跳过，并启用 auto_high。"""
        cfg.max_daily_push = 0
        r = push_alert(PushLevel.MEDIUM, "t", "c", symbol="AAPL", cfg=cfg)
        assert r is False
        assert _is_auto_high(cfg) is True

    def test_auto_high_mode_enable_and_skip(self, cfg, mock_httpx):
        """auto_high_threshold 达阈值后启用 high 模式，后续非 high 被跳过。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = _ok_resp()
        cfg.auto_high_threshold = 1
        # 第一次成功推送 → 当日计数=1 ≥ 阈值 1 → 启用 high 模式
        assert push_alert(PushLevel.MEDIUM, "t1", "c1", symbol="AAPL", cfg=cfg) is True
        assert _is_auto_high(cfg) is True
        # 后续非 high 被 auto_high 跳过（不同 key，避免冷却干扰）
        assert push_alert(PushLevel.MEDIUM, "t2", "c2", symbol="MSFT", cfg=cfg) is False

    def test_no_channel_returns_false(self, tmp_path, mock_httpx):
        """推送通道未配置时返回 False，不抛异常、不发 http。"""
        fake_client, _ = mock_httpx
        c = PushConfig(push_type="pushplus", pushplus_token="", db_path=str(tmp_path / "test.db"))
        assert push_alert(PushLevel.MEDIUM, "t", "c", cfg=c) is False
        # 未配置 token，_get_client 不应被调用
        fake_client.post.assert_not_called()

    def test_no_channel_logs_failure(self, tmp_path, mock_httpx):
        """无通道时 push_log 仍记录一次失败。"""
        c = PushConfig(push_type="pushplus", pushplus_token="", db_path=str(tmp_path / "test.db"))
        push_alert(PushLevel.MEDIUM, "t", "c", cfg=c)
        row = _query_one(
            c.db_path,
            "SELECT success, level FROM push_log ORDER BY id DESC LIMIT 1",
        )
        assert row["success"] == 0
        assert row["level"] == "medium"

    def test_failed_push_not_counted_daily(self, cfg, mock_httpx):
        """推送失败不计入每日计数（不占额度、不触发冷却）。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = {"code": 500, "msg": "fail"}
        assert push_alert(PushLevel.MEDIUM, "t1", "c1", symbol="AAPL", cfg=cfg) is False
        from shared.pusher import _get_daily_count
        assert _get_daily_count(cfg) == 0
        # 失败不写冷却：push_cooldown 表应为空
        row = _query_one(cfg.db_path, "SELECT COUNT(*) AS n FROM push_cooldown")
        assert row["n"] == 0

    def test_get_push_stats(self, cfg, mock_httpx):
        """get_push_stats 返回正确统计。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = {"code": 200}
        # 一次成功
        assert push_alert(PushLevel.MEDIUM, "t1", "c1", symbol="AAPL", cfg=cfg) is True
        # 一次失败（pushplus code != 200）
        fake_resp.json.return_value = {"code": 500, "msg": "fail"}
        assert push_alert(PushLevel.MEDIUM, "t2", "c2", symbol="MSFT", cfg=cfg) is False

        stats = get_push_stats(cfg)
        assert stats["total"] == 2
        assert stats["today_pushed"] == 1
        assert stats["today_failed"] == 1
        assert stats["auto_high_mode"] is False
        assert stats["max_daily"] == 50
        assert isinstance(stats["recent"], list)
        assert len(stats["recent"]) == 2
        # recent 按 created_at DESC，最新失败在前
        assert stats["recent"][0]["success"] == 0

    def test_push_alert_writes_cooldown_key(self, cfg, mock_httpx):
        """push_alert 用 alert_type:symbol 作为 cooldown_key 写入日志。"""
        _, fake_resp = mock_httpx
        fake_resp.json.return_value = _ok_resp()
        push_alert(PushLevel.MEDIUM, "t", "c", alert_type="stop_loss", symbol="AAPL", cfg=cfg)
        row = _query_one(
            cfg.db_path,
            "SELECT cooldown_key FROM push_log ORDER BY id DESC LIMIT 1",
        )
        assert row["cooldown_key"] == "stop_loss:AAPL"


# ==================== sentiment_adapter: _find_x_monitor_db ====================

class TestFindXMonitorDb:
    def test_finds_existing_candidate(self, tmp_path, monkeypatch):
        """候选路径存在时返回其 abspath。"""
        fake_db = tmp_path / "monitor.db"
        fake_db.write_text("")
        monkeypatch.setattr(sentiment_adapter, "_X_MONITOR_DB_CANDIDATES", [str(fake_db)])
        result = _find_x_monitor_db()
        assert result == os.path.abspath(str(fake_db))

    def test_returns_none_when_no_candidate(self, tmp_path, monkeypatch):
        """所有候选都不存在时返回 None。"""
        monkeypatch.setattr(
            sentiment_adapter, "_X_MONITOR_DB_CANDIDATES",
            [str(tmp_path / "nope1.db"), str(tmp_path / "nope2.db")],
        )
        assert _find_x_monitor_db() is None

    def test_picks_first_existing(self, tmp_path, monkeypatch):
        """多个候选时返回第一个存在的。"""
        a = tmp_path / "a.db"
        b = tmp_path / "b.db"
        a.write_text("")
        b.write_text("")
        monkeypatch.setattr(
            sentiment_adapter, "_X_MONITOR_DB_CANDIDATES",
            [str(a), str(b)],
        )
        assert _find_x_monitor_db() == os.path.abspath(str(a))

    def test_real_local_db_if_exists(self):
        """如果 d:\\software\\x-monitor-push\\data\\monitor.db 存在，应被找到。"""
        real = r"d:\software\x-monitor-push\data\monitor.db"
        if not os.path.exists(real):
            pytest.skip("x-monitor-push data/monitor.db 不存在，跳过真实路径校验")
        result = _find_x_monitor_db()
        assert result is not None
        assert os.path.samefile(result, real)


# ==================== sentiment_adapter: _parse_impact_from_analysis ====================

class TestParseImpact:
    @pytest.mark.parametrize("text,expected", [
        ("high impact event", "high"),
        ("This is HIGH priority", "high"),
        ("重大利好消息", "high"),
        ("高优先级处理", "high"),
        ("medium attention needed", "medium"),
        ("MEDIUM risk", "medium"),
        ("中优先级", "medium"),
        ("请关注此事件", "medium"),
        ("", "low"),
        (None, "low"),
        ("普通市场动态", "low"),
        ("no keyword here", "low"),
    ])
    def test_parse(self, text, expected):
        assert _parse_impact_from_analysis(text) == expected


# ==================== sentiment_adapter: _extract_category ====================

class TestExtractCategory:
    @pytest.mark.parametrize("analysis,title,expected", [
        ("", "美国宣布关税政策", "关税"),
        ("", "new tariff on goods", "关税"),
        ("", "Fed rate decision", "美联储"),
        ("", "利率决议出炉", "美联储"),
        ("", "interest rate hike", "美联储"),
        ("", "Bitcoin surges past 100k", "加密"),
        ("", "BTC ETF approved", "加密"),
        ("", "crypto market rally", "加密"),
        ("", "AI demand soars", "AI"),
        ("", "chip shortage continues", "半导体"),
        ("", "芯片产能受限", "半导体"),
        ("", "公司财报超预期", "财报"),
        ("", "Q3 earnings beat", "财报"),
        ("", "Tesla launches new model", "特斯拉"),
        ("", "EV sales grow", "新能源"),
        ("普通新闻无关键词", "随便标题", "综合"),
    ])
    def test_extract(self, analysis, title, expected):
        assert _extract_category(analysis, title) == expected


# ==================== sentiment_adapter: fetch_real_tweets ====================

def _make_x_monitor_schema(conn):
    """构造与 x-monitor-push 一致的 tweets 表结构。"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            title TEXT,
            link TEXT,
            published TEXT,
            summary TEXT,
            ai_analysis TEXT,
            pushed INTEGER DEFAULT 0,
            push_time TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)


class TestFetchRealTweets:
    def test_no_db_returns_none_source(self, monkeypatch):
        """无 db 时返回 source=none。"""
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: None)
        result = fetch_real_tweets()
        assert result == {"source": "none", "db_path": None, "count": 0, "tweets": []}

    def test_empty_db_returns_none_source(self, tmp_path, monkeypatch):
        """db 存在但无数据 → 降级返回 source=none。"""
        db = tmp_path / "monitor.db"
        conn = sqlite3.connect(db)
        _make_x_monitor_schema(conn)
        conn.commit()
        conn.close()
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: str(db))
        result = fetch_real_tweets()
        assert result["source"] == "none"
        assert result["count"] == 0
        assert result["tweets"] == []

    def test_reads_from_x_monitor_db(self, tmp_path, monkeypatch):
        """db 有数据 → 返回 source=x-monitor-push 且字段映射正确。"""
        db = tmp_path / "monitor.db"
        conn = sqlite3.connect(db)
        _make_x_monitor_schema(conn)
        conn.execute(
            "INSERT INTO tweets (tweet_id, username, title, link, published, summary, ai_analysis, pushed, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("id_1", "elonmusk", "Tesla AI day", "https://x.com/elonmusk/status/1",
             "2026-07-25 10:00:00", "summary text", "high impact AI chip", 0,
             "2026-07-25 10:00:00"),
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: str(db))

        result = fetch_real_tweets()
        assert result["source"] == "x-monitor-push"
        assert result["db_path"] == str(db)
        assert result["count"] == 1
        t = result["tweets"][0]
        assert t["username"] == "elonmusk"
        assert t["title"] == "Tesla AI day"
        assert t["link"] == "https://x.com/elonmusk/status/1"
        assert t["impact_level"] == "high"
        assert t["category"] == "AI"
        assert t["source"] == "x-monitor-push"
        assert t["pushed"] == 0

    def test_limit_respected(self, tmp_path, monkeypatch):
        """limit 参数生效。"""
        db = tmp_path / "monitor.db"
        conn = sqlite3.connect(db)
        _make_x_monitor_schema(conn)
        for i in range(5):
            conn.execute(
                "INSERT INTO tweets (tweet_id, username, created_at) VALUES (?,?,?)",
                (f"id_{i}", "u", "2026-07-25 10:00:00"),
            )
        conn.commit()
        conn.close()
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: str(db))
        result = fetch_real_tweets(limit=3)
        assert result["count"] == 3


# ==================== sentiment_adapter: get_monitor_status ====================

class TestGetMonitorStatus:
    def test_no_db(self, monkeypatch):
        """无 db 时返回 running=False 结构。"""
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: None)
        s = get_monitor_status()
        assert s["running"] is False
        assert s["db_path"] is None
        assert "msg" in s

    def test_with_db_structure(self, tmp_path, monkeypatch):
        """db 存在时返回完整运行状态结构。"""
        db = tmp_path / "monitor.db"
        conn = sqlite3.connect(db)
        _make_x_monitor_schema(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO tweets (tweet_id, username, pushed, created_at) VALUES (?,?,?,?)",
            ("id_1", "u1", 1, today + " 10:00:00"),
        )
        conn.execute(
            "INSERT INTO tweets (tweet_id, username, pushed, created_at) VALUES (?,?,?,?)",
            ("id_2", "u2", 0, today + " 11:00:00"),
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: str(db))

        s = get_monitor_status()
        assert s["running"] is True
        assert s["db_path"] == str(db)
        assert s["total_tweets"] == 2
        assert s["today_tweets"] == 2
        assert s["pushed_tweets"] == 1
        assert s["last_fetch"] is not None

    def test_empty_db_status(self, tmp_path, monkeypatch):
        """db 存在但表空 → total=0, last_fetch=None。"""
        db = tmp_path / "monitor.db"
        conn = sqlite3.connect(db)
        _make_x_monitor_schema(conn)
        conn.commit()
        conn.close()
        monkeypatch.setattr(sentiment_adapter, "_find_x_monitor_db", lambda: str(db))
        s = get_monitor_status()
        assert s["running"] is True
        assert s["total_tweets"] == 0
        assert s["last_fetch"] is None
