import os

BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", "")
}

MICRO_CONFIG = {
    "initial_balance": 10.0,           # رأس المال الابتدائي
    "selected_pairs": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],  # 3 أزواج للبداية
    "base_risk": 0.04,                 # 4% مخاطرة أساسية
    "max_risk": 0.08,                  # 8% أقصى مخاطرة
    "min_risk": 0.015,                 # 1.5% أدنى مخاطرة
    "min_trade": 0.50,                 # 50 سنت أقل صفقة
    "max_trade": 3.00,                 # 3 دولار أقصى صفقة
    "confidence_threshold": 65,        # 65% ثقة أدنى
    "timeframe": "1m",                 # إطار دقيقة واحدة
    "max_trades_per_day": 300,         # 300 صفقة يومياً كحد أقصى
    "compounding_mode": "INSTANT",     # ربح تراكمي فوري
    "risk_multiplier_win": 1.3,        # زيادة المخاطرة بعد الربح
    "risk_multiplier_loss": 0.7,       # تقليل المخاطرة بعد الخسارة
    "adaptive_learning": True,         # تفعيل التعلم التكيفي
    "fast_calculation": True           # حسابات سريعة
}
