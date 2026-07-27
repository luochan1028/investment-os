"""告警生成与推送模块

- 存储：写本地 SQLite（告警历史）
- 推送：走统一推送层 shared.pusher（三通道+冷却+每日上限+自动high）
- 三级告警 high/medium/low 对应 P0/P1/P2
"""
import logging
from datetime import datetime

from config import Config
from store import save_alert, is_alert_in_cooldown, update_alert_cooldown
from shared.pusher import push_alert as unified_push, PushLevel, PushConfig

logger = logging.getLogger(__name__)

LEVEL_ICON = {"high": "🔴", "medium": "🟡", "low": "⚪"}
LEVEL_LABEL = {"high": "P0 重大", "medium": "P1 关注", "low": "P2 提示"}
LEVEL_MAP = {"high": PushLevel.HIGH, "medium": PushLevel.MEDIUM, "low": PushLevel.LOW}


def push_alert(title: str, content: str, level: str = "medium") -> bool:
    """兼容旧接口 - 转发到统一推送层"""
    return unified_push(LEVEL_MAP.get(level, PushLevel.LOW), title, content)


def emit_alert(alert_type: str, level: str, title: str, detail: str,
               symbol: str = "") -> bool:
    """生成告警：存储 → 统一推送层（含冷却/上限/分级）

    推送层的冷却独立于 store.is_alert_in_cooldown，这里仍存本地用于历史展示。
    Returns: 是否成功推送
    """
    # 1. 存本地（无论是否推送成功，都留历史）
    save_alert(alert_type, level, title, detail, symbol)

    # 2. 构造推送内容
    icon = LEVEL_ICON.get(level, "⚪")
    content = (
        f"## {icon} 持仓风控告警\n\n"
        f"**级别**: {LEVEL_LABEL.get(level, level)}\n"
        f"**类型**: {alert_type}\n"
        f"**标的**: {symbol or '组合'}\n\n"
        f"---\n\n{detail}\n\n---\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🤖 investment-os"
    )

    # 3. 走统一推送层（内部含冷却、每日上限、自动high模式）
    pushed = unified_push(
        LEVEL_MAP.get(level, PushLevel.LOW),
        f"{icon} {title}",
        content,
        symbol=symbol,
        alert_type=alert_type,
    )

    # 4. 兼容旧冷却表（前端可能读这个）
    if pushed:
        update_alert_cooldown(alert_type, symbol)
    return pushed
