"""持仓风控配置 - 从环境变量加载

复用 x-monitor-push 的 .env 模式与 PushPlus 推送通道。
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """全局配置"""

    # OpenBB 行情接口（与 stock_dashboard.html 共用同一实例）
    OPENBB_BASE_URL: str = os.getenv(
        "OPENBB_BASE_URL", "http://159.138.92.82:6900/api/v1"
    )
    OPENBB_PROVIDER: str = os.getenv("OPENBB_PROVIDER", "yfinance")

    # 数据库
    DB_PATH: str = os.getenv("PORTFOLIO_DB_PATH", "data/portfolio.db")

    # 推送（支持 PushPlus / WxPusher / Server酱；未配置则仅写日志）
    PUSH_TYPE: str = os.getenv("PUSH_TYPE", "pushplus")
    PUSHPLUS_TOKEN: str = os.getenv("PUSHPLUS_TOKEN", "")
    WXPUSHER_TOKEN: str = os.getenv("WXPUSHER_TOKEN", "")
    WXPUSHER_UID: str = os.getenv("WXPUSHER_UID", "")
    SERVERCHAN_KEY: str = os.getenv("SERVERCHAN_KEY", "")
    PUSH_ENABLED: bool = any([
        bool(PUSHPLUS_TOKEN),
        bool(WXPUSHER_TOKEN) and bool(WXPUSHER_UID),
        bool(SERVERCHAN_KEY),
    ])

    # 风险阈值
    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "0.15"))          # 单标的止损线 15%
    PORTFOLIO_DD_PCT: float = float(os.getenv("PORTFOLIO_DD_PCT", "0.10"))    # 组合浮亏阈值 10%
    CONCENTRATION_PCT: float = float(os.getenv("CONCENTRATION_PCT", "0.30"))  # 单标的集中度 30%
    VAR_CONFIDENCE: float = float(os.getenv("VAR_CONFIDENCE", "0.95"))        # VaR 置信度
    VAR_LOOKBACK_DAYS: int = int(os.getenv("VAR_LOOKBACK_DAYS", "60"))        # VaR 回看天数

    # 轮询
    POLL_INTERVAL: int = int(os.getenv("PORTFOLIO_POLL_INTERVAL", "300"))

    # 告警冷却（分钟）：同一告警类型 × 同一标的的最小间隔
    ALERT_COOLDOWN_MINUTES: int = int(os.getenv("ALERT_COOLDOWN_MINUTES", "60"))

    # Web 服务
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8188"))

    # CORS 跨域（逗号分隔，* 表示允许所有）
    CORS_ORIGINS: list = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
    ]

    # 限流
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "false").lower() in ("true", "1", "yes")

    @classmethod
    def summary(cls) -> dict:
        return {
            "openbb_url": cls.OPENBB_BASE_URL,
            "openbb_provider": cls.OPENBB_PROVIDER,
            "db_path": cls.DB_PATH,
            "push_enabled": cls.PUSH_ENABLED,
            "stop_loss_pct": f"{cls.STOP_LOSS_PCT*100:.0f}%",
            "portfolio_dd_pct": f"{cls.PORTFOLIO_DD_PCT*100:.0f}%",
            "concentration_pct": f"{cls.CONCENTRATION_PCT*100:.0f}%",
            "var_confidence": cls.VAR_CONFIDENCE,
            "poll_interval": cls.POLL_INTERVAL,
        }
