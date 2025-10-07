import os

BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", "")
}

SMART_CONFIG = {
    "initial_balance": 10.0,
    "selected_pairs": ["BTCUSDT", "ETHUSDT"],  # زوجين فقط للتركيز
    "base_risk": 0.015,      # 1.5% مخاطرة
    "min_trade": 1.00,       # 1$ حد أدنى
    "max_trade": 3.00,       # 3$ حد أقصى
    "confidence_threshold": 70,  # 70% ثقة أدنى
    "timeframe": "5m",       # 5 دقائق لإطار أكثر استقراراً
    "stop_loss_pct": 0.015,  # 1.5% وقف خسارة
    "take_profit_pct": 0.010, # 1.0% جني أرباح
    "max_trades_per_day": 50, # 50 صفقة كحد أقصى
    "compounding_mode": "INSTANT"
}
