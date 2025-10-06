import os

BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", "")
}

MICRO_CONFIG = {
    "initial_balance": 10.0,
    "selected_pairs": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    
    # 🔥 إصلاح إدارة المخاطر
    "base_risk": 0.02,                 # 2% فقط للرؤوس الصغيرة
    "max_risk": 0.04,                  # 4% أقصى حد
    "min_risk": 0.008,                 # 0.8% أدنى حد
    "min_trade": 1.00,                 # 1$ حد أدنى (بدلاً من 0.50$)
    "max_trade": 2.00,                 # 2$ حد أقصى
    
    # 🔥 إصلاح قرارات التداول
    "confidence_threshold": 75,        # 75% ثقة أدنى (زيادة الدقة)
    "min_profit_target": 0.003,        # 0.3% أقل ربح مستهدف
    "max_stop_loss": 0.015,            # 1.5% أقصى خسارة للصفقة
    
    "timeframe": "3m",                 # 3 دقائق أفضل من 1m
    "max_trades_per_day": 200,
    "compounding_mode": "INSTANT",
    
    # 🔥 إضافة حماية جديدة
    "daily_loss_limit": 0.20,          # 20% أقصى خسارة يومية
    "consecutive_loss_limit": 3,       # توقف بعد 3 خسائر متتالية
    "profit_lock_in": 0.10,            # تأمين 10% ربح عند تحقيقها
}
