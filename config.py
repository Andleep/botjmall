# config.py
import os

BINANCE_CONFIG = {
    "api_key": os.getenv("BINANCE_API_KEY",""),
    "api_secret": os.getenv("BINANCE_API_SECRET","")
}

# الإعدادات الافتراضية للاستراتيجية — يمكنك تغييرها من الواجهة أيضاً
LORENTZIAN_CONFIG = {
    "initial_balance": 10.0,       # رصيد بداية التجربة
    "risk_per_trade": 0.05,        # نسبة المخاطرة لكل صفقة (مثلاً 5%)
    "min_trade_amount": 0.01,      # أقل مبلغ للفتح (دولار)
    "stop_loss_pct": 0.015,        # وقف خسارة 1.5%
    "take_profit_pct": 0.03,       # جني ربح 3%
    "adx_threshold": 8,            # عتبة ADX (أخففناها لتكرار إشارات أعلى)
    "min_atr_ratio": 0.00005,      # حد ATR/price
    "max_bars_back": 1000,         # عدد البارات المستخدمة للعينة
    "use_time_filter": False,      # فلتر وقت بداية/نهاية الساعة
    "allow_multiple_positions": True,
    "reentry_bars": 0,
    "score_threshold": 0.0005      # عتبة لورنتزي المصغرة لقبول إشارات
}
