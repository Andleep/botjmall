import os
BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY",""),
    "api_secret": os.getenv("BINANCE_API_SECRET","")
}

LORENTZIAN_CONFIG = {
    "initial_balance": 10.0,
    "risk_per_trade": 0.02,
    "min_trade_amount": 0.5,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "adx_threshold": 20,
    "min_atr_ratio": 0.0005,
    "max_bars_back": 500
}
