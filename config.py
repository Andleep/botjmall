# config.py
import os

BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", "")
}

LORENTZIAN_CONFIG = {
    "initial_balance": 10.0,
    "risk_per_trade": 0.05,
    "min_trade_amount": 0.01,
    "stop_loss_pct": 0.015,
    "take_profit_pct": 0.03,
    "adx_threshold": 8,
    "min_atr_ratio": 0.00005,
    "max_bars_back": 1000,
    "use_time_filter": False,
    "allow_multiple_positions": True,
    "reentry_bars": 0,
    "score_threshold": 0.0005,
    # Websocket / cache settings
    "klines_cache_dir": ".klines_cache",
    "klines_cache_ttl_secs": 60 * 60  # 1 hour
}
