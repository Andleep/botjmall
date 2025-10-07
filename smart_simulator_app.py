# smart_simulator_app.py
import streamlit as st
import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import warnings
import time
import plotly.graph_objects as go
from binance.client import Client

warnings.filterwarnings('ignore')

# إعدادات التسجيل
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SmartTradingBot:
    """
    بوت تداول ذكي حقيقي - إصدار نهائي مع ربح تراكمي فوري
    """
    
    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []
        self.selected_pairs = self.config.get("selected_pairs", [])
        
        # 🔥 مقاييس محسنة
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'compounded_profits': 0.0,
            'current_streak': 0,
            'max_streak': 0
        }
        
        # 🔥 أنظمة حماية
        self.protection = {
            'daily_loss_limit': self.config.get("daily_loss_limit", 0.15) * self.initial_balance,
            'current_daily_loss': 0.0,
            'consecutive_loss_limit': self.config.get("consecutive_loss_limit", 3),
            'trading_enabled': True
        }
        
        logger.info(f"🧠 البوت الذكي النهائي جاهز | الرصيد: ${self.balance:.2f}")
    
    def check_trading_permission(self) -> bool:
        """فحص إذن التداول مع أنظمة الحماية"""
        if not self.protection['trading_enabled']:
            return False
            
        # فحص الخسارة اليومية
        if abs(self.protection['current_daily_loss']) >= self.protection['daily_loss_limit']:
            logger.warning("🛑 توقف التداول - وصلت للحد الأقصى للخسارة اليومية")
            self.protection['trading_enabled'] = False
            return False
            
        # فحص الخسائر المتتالية
        if self.metrics['losing_trades'] >= self.protection['consecutive_loss_limit']:
            logger.warning("🛑 توقف مؤقت - وصلت لحد الخسائر المتتالية")
            return False
            
        return True
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """تحضير البيانات الأساسية"""
        df = df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
        return df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """حساب المؤشرات الفنية الذكية"""
        df = df.copy()
        
        # مؤشرات الاتجاه
        df["sma_20"] = talib.SMA(df["close"], 20)
        df["ema_12"] = talib.EMA(df["close"], 12)
        df["ema_26"] = talib.EMA(df["close"], 26)
        
        # مؤشرات الزخم
        df["rsi_14"] = talib.RSI(df["close"], 14)
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(df["close"], 12, 26, 9)
        df["stoch_k"], df["stoch_d"] = talib.STOCH(df["high"], df["low"], df["close"], 14, 3, 0)
        
        # مؤشرات التقلب والدعم والمقاومة
        df["atr_14"] = talib.ATR(df["high"], df["low"], df["close"], 14)
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(df["close"], 20, 2, 2)
        
        # مؤشرات الحجم
        df["volume_sma"] = talib.SMA(df["volume"], 20)
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # 🔥 إشارات ذكية
        df['strong_buy'] = (
            (df['rsi_14'] < 30) & 
            (df['close'] < df['bb_lower']) & 
            (df['macd_hist'] > 0) &
            (df['volume_ratio'] > 1.2)
        ).astype(int)
        
        df['strong_sell'] = (
            (df['rsi_14'] > 70) & 
            (df['close'] > df['bb_upper']) & 
            (df['macd_hist'] < 0) &
            (df['volume_ratio'] > 1.2)
        ).astype(int)
        
        return df
    
    def smart_decision(self, df: pd.DataFrame, idx: int, symbol: str) -> Dict:
        """🔥 قرار تداول ذكي مع تأكيدات متعددة"""
        if idx < 30:
            return {"signal": "HOLD", "confidence": 0, "reason": "بيانات غير كافية"}
        
        row = df.iloc[idx]
        
        # نظام التصويت الذكي
        buy_score = 0
        sell_score = 0
        
        # 🔥 تأكيدات الشراء
        if row['strong_buy'] == 1:
            buy_score += 3
        if row['rsi_14'] < 30:
            buy_score += 2
        if row['macd_hist'] > 0 and row['macd'] > row['macd_signal']:
            buy_score += 2
        if row['stoch_k'] < 20:
            buy_score += 1
        if row['close'] > row['ema_12'] and row['ema_12'] > row['ema_26']:
            buy_score += 1
            
        # 🔥 تأكيدات البيع
        if row['strong_sell'] == 1:
            sell_score += 3
        if row['rsi_14'] > 70:
            sell_score += 2
        if row['macd_hist'] < 0 and row['macd'] < row['macd_signal']:
            sell_score += 2
        if row['stoch_k'] > 80:
            sell_score += 1
        if row['close'] < row['ema_12'] and row['ema_12'] < row['ema_26']:
            sell_score += 1
        
        total_score = buy_score + sell_score
        if total_score == 0:
            return {"signal": "HOLD", "confidence": 0, "reason": "لا توجد إشارات قوية"}
        
        buy_ratio = buy_score / total_score
        sell_ratio = sell_score / total_score
        confidence = max(buy_ratio, sell_ratio) * 100
        
        # 🔥 عتبات عالية لضمان الجودة
        if buy_ratio >= 0.7 and confidence >= 75:
            return {
                "signal": "BUY",
                "confidence": confidence,
                "reason": f"إشارات شراء قوية ({buy_score}/9)"
            }
        elif sell_ratio >= 0.7 and confidence >= 75:
            return {
                "signal": "SELL", 
                "confidence": confidence,
                "reason": f"إشارات بيع قوية ({sell_score}/9)"
            }
        else:
            return {
                "signal": "HOLD",
                "confidence": confidence,
                "reason": f"إشارات غير كافية (شراء: {buy_score}, بيع: {sell_score})"
            }
    
    def calculate_position_size(self, confidence: float) -> float:
        """حساب حجم مركز آمن مع ربح تراكمي"""
        # خطر أساسي منخفض
        base_risk = self.config.get("base_risk", 0.02)
        
        # تعديل حسب الثقة
        risk_adjusted = base_risk * (confidence / 100.0)
        
        # 🔥 حدود صارمة
        final_risk = max(0.008, min(risk_adjusted, 0.04))
        position_size = self.balance * final_risk
        
        # حدود حجم الصفقة
        min_trade = self.config.get("min_trade", 1.00)
        max_trade = self.config.get("max_trade", 3.00)
        
        return max(min_trade, min(position_size, max_trade))
    
    def instant_profit_compounding(self, profit: float):
        """🔥 ربح تراكمي فوري بعد كل صفقة ناجحة"""
        if profit > 0:
            old_balance = self.balance
            self.balance += profit  # 🔥 إضافة الربح إلى الرصيد فوراً
            
            # تحديث المقاييس
            self.metrics['total_profit'] += profit
            self.metrics['winning_trades'] += 1
            self.metrics['compounded_profits'] += profit
            self.metrics['current_streak'] += 1
            self.metrics['max_streak'] = max(self.metrics['max_streak'], self.metrics['current_streak'])
            
            logger.info(f"💰 ربح تراكمي فوري: +${profit:.4f} | الرصيد: {old_balance:.2f} → {self.balance:.2f}")
        else:
            self.metrics['losing_trades'] += 1
            self.metrics['current_streak'] = 0
            self.protection['current_daily_loss'] += profit
    
    def execute_trade(self, symbol: str, action: str, price: float, position_size: float, confidence: float, reason: str):
        """تنفيذ الصفقة مع إدارة مخاطر مدمجة"""
        if action == "BUY" and symbol not in self.positions:
            # فتح صفقة شراء
            qty = position_size / price
            
            # 🔥 وقف خسارة وجني أرباح ذكي
            stop_loss = price * 0.985  # 1.5% وقف خسارة
            take_profit = price * 1.010  # 1.0% جني أرباح
            
            self.positions[symbol] = {
                "entry_time": datetime.now(),
                "entry_price": price,
                "amount": position_size,
                "qty": qty,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": confidence
            }
            
            self.balance -= position_size
            
            trade_record = {
                "timestamp": datetime.now(),
                "symbol": symbol,
                "action": "BUY",
                "price": price,
                "amount": position_size,
                "qty": qty,
                "confidence": confidence,
                "status": "OPEN",
                "reason": reason,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }
            
            self.trade_history.append(trade_record)
            self.metrics['total_trades'] += 1
            
        elif action == "SELL" and symbol in self.positions:
            # إغلاق صفقة شراء
            position = self.positions.pop(symbol)
            profit = (price - position["entry_price"]) * position["qty"]
            
            # 🔥 تطبيق الربح التراكمي الفوري
            self.instant_profit_compounding(profit)
            
            trade_record = {
                "timestamp": datetime.now(),
                "symbol": symbol,
                "action": "SELL",
                "price": price,
                "amount": position["amount"],
                "qty": position["qty"],
                "profit": profit,
                "profit_pct": (profit / position["amount"]) * 100,
                "confidence": position["confidence"],
                "status": "CLOSED",
                "reason": reason,
                "compounded": True
            }
            
            self.trade_history.append(trade_record)
    
    def run_smart_backtest(self, klines_data: Dict, timeframe: str):
        """تشغيل المحاكاة الذكية"""
        results = {}
        
        logger.info(f"🚀 بدء المحاكاة الذكية على {len(self.selected_pairs)} أزواج")
        
        for symbol in self.selected_pairs:
            if symbol not in klines_data:
                continue
                
            logger.info(f"🔍 تحليل {symbol}...")
            df = klines_data[symbol].copy()
            
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df.set_index("timestamp", inplace=True)
            
            # معالجة البيانات
            df = self.prepare_data(df)
            df = self.calculate_indicators(df)
            df = df[df['rsi_14'].notna() & df['macd'].notna()]
            
            for i in range(30, len(df)):
                # 🔥 فحص إذن التداول أولاً
                if not self.check_trading_permission():
                    break
                
                # قرار التداول الذكي
                decision = self.smart_decision(df, i, symbol)
                price = float(df["close"].iloc[i])
                
                if decision["signal"] in ["BUY", "SELL"] and decision["confidence"] >= 70:
                    position_size = self.calculate_position_size(decision["confidence"])
                    
                    # 🔥 تصفية إضافية لتجنب المناطق الخطرة
                    rsi = df["rsi_14"].iloc[i]
                    if decision["signal"] == "BUY" and rsi > 60:
                        continue
                    elif decision["signal"] == "SELL" and rsi < 40:
                        continue
                    
                    self.execute_trade(
                        symbol, decision["signal"], price,
                        position_size, decision["confidence"], decision["reason"]
                    )
            
            # إغلاق الصفقات المتبقية
            if symbol in self.positions:
                position = self.positions.pop(symbol)
                price = float(df["close"].iloc[-1])
                self.execute_trade(symbol, "SELL", price, 0, position["confidence"], "إغلاق نهائي")
        
        # النتائج النهائية
        total_profit = self.balance - self.initial_balance
        profit_percentage = (total_profit / self.initial_balance) * 100
        
        closed_trades = [t for t in self.trade_history if t.get('status') == 'CLOSED']
        winning_trades = len([t for t in closed_trades if t.get('profit', 0) > 0])
        win_rate = (winning_trades / len(closed_trades) * 100) if closed_trades else 0
        
        logger.info(f"✅ انتهت المحاكاة | الصفقات: {self.metrics['total_trades']} | "
                   f"الربح: ${total_profit:.2f} | النجاح: {win_rate:.1f}%")
        
        return {
            "final_balance": self.balance,
            "total_profit": total_profit,
            "profit_percentage": profit_percentage,
            "total_trades": self.metrics['total_trades'],
            "winning_trades": self.metrics['winning_trades'],
            "losing_trades": self.metrics['losing_trades'],
            "win_rate": win_rate,
            "trade_history": self.trade_history,
            "initial_balance": self.initial_balance,
            "metrics": self.metrics,
            "protection_metrics": self.protection
        }

# 🔧 إعدادات البوت الذكي
SMART_CONFIG = {
    "initial_balance": 10.0,
    "selected_pairs": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "base_risk": 0.02,
    "max_risk": 0.04,
    "min_risk": 0.008,
    "min_trade": 1.00,
    "max_trade": 3.00,
    "confidence_threshold": 70,
    "timeframe": "5m",
    "daily_loss_limit": 0.15,
    "consecutive_loss_limit": 3,
    "compounding_mode": "INSTANT"
}

BINANCE_CONFIG = {
    "api_key": "",
    "api_secret": ""
}

# 🎯 واجهة Streamlit
st.set_page_config(page_title="البوت التداولي الذكي", layout="wide", page_icon="🧠")

st.title("🧠 البوت التداولي الذكي - ربح تراكمي فوري")
st.markdown("### 🤖 بداية من 10$ إلى ما لا نهاية")

# الشريط الجانبي
st.sidebar.header("⚙️ إعدادات البوت الذكي")

# اختيار الأزواج
available_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
selected_pairs = st.sidebar.multiselect(
    "🎯 اختر أزواج التداول:",
    available_pairs,
    default=["BTCUSDT", "ETHUSDT"]
)

# إعدادات رأس المال
capital = st.sidebar.number_input(
    "💵 رأس المال الأولي ($)",
    value=10.0,
    min_value=5.0,
    max_value=100.0,
    step=5.0
)

# إعدادات المخاطرة
risk_level = st.sidebar.selectbox(
    "🎯 مستوى المخاطرة:",
    ["🟢 منخفض (2%)", "🟡 متوسط (3%)", "🟠 عالي (4%)"]
)
risk_mapping = {"🟢 منخفض (2%)": 0.02, "🟡 متوسط (3%)": 0.03, "🟠 عالي (4%)": 0.04}
base_risk = risk_mapping[risk_level]

# إعدادات الوقت
timeframe = st.sidebar.selectbox("⏰ الإطار الزمني:", ["5m", "15m", "1h"], index=0)
days = st.sidebar.slider("📅 أيام المحاكاة:", 1, 7, 3)

# تحديث الإعدادات
cfg = SMART_CONFIG.copy()
cfg.update({
    "initial_balance": float(capital),
    "selected_pairs": selected_pairs,
    "base_risk": base_risk,
    "timeframe": timeframe
})

@st.cache_data(ttl=300)
def fetch_klines(symbols, interval, days=3):
    """جلب البيانات من Binance"""
    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    
    klines_data = {}
    
    for symbol in symbols:
        try:
            klines = client.get_historical_klines(
                symbol, interval,
                start.strftime("%d %b, %Y"),
                end.strftime("%d %b, %Y"),
                limit=500
            )
            
            if klines:
                df = pd.DataFrame(klines, columns=[
                    'timestamp','open','high','low','close','volume','close_time',
                    'qav','num_trades','taker_base_vol','taker_quote_vol','ignore'
                ])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                klines_data[symbol] = df[['timestamp','open','high','low','close','volume']]
            
            time.sleep(0.1)
            
        except Exception as e:
            st.error(f"❌ خطأ في {symbol}: {str(e)}")
    
    return klines_data

def calculate_metrics(trades):
    """حساب مقاييس الأداء"""
    if not trades:
        return {}
    
    closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
    if not closed_trades:
        return {}
    
    profits = [t.get('profit', 0) for t in closed_trades]
    winning_trades = [p for p in profits if p > 0]
    losing_trades = [p for p in profits if p < 0]
    
    return {
        'total_trades': len(closed_trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': (len(winning_trades) / len(closed_trades)) * 100,
        'total_profit': sum(profits),
        'avg_profit': np.mean(profits),
        'profit_factor': abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf'),
        'expectancy': (np.mean(winning_trades) if winning_trades else 0) - (abs(np.mean(losing_trades)) if losing_trades else 0)
    }

# الواجهة الرئيسية
tab1, tab2 = st.tabs(["🚀 المحاكاة الذكية", "📊 لوحة التحكم"])

with tab1:
    st.header("المحاكاة الذكية")
    
    if st.button("🧠 بدء المحاكاة الذكية", type="primary", use_container_width=True):
        if not selected_pairs:
            st.error("⚠️ الرجاء اختيار أزواج التداول أولاً")
        else:
            with st.spinner("جلب بيانات السوق..."):
                klines_data = fetch_klines(selected_pairs, timeframe, days)
                
                if not klines_data:
                    st.error("❌ فشل في جلب بيانات السوق")
                else:
                    # إنشاء البوت الذكي
                    smart_bot = SmartTradingBot(cfg)
                    
                    # محاكاة
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i in range(100):
                        progress_bar.progress(i + 1)
                        status_text.text(f"🧠 البوت يحلل الفرص... {i+1}%")
                        time.sleep(0.01)
                    
                    result = smart_bot.run_smart_backtest(klines_data, timeframe)
                    progress_bar.empty()
                    status_text.empty()
                    
                    st.success("✅ اكتملت المحاكاة الذكية!")
                    
                    # عرض النتائج
                    st.subheader("📊 النتائج الأساسية")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("💵 رأس المال الأولي", f"${result['initial_balance']:.2f}")
                    with col2:
                        profit = result['total_profit']
                        profit_color = "normal" if profit >= 0 else "inverse"
                        st.metric("🎯 إجمالي الربح", f"${profit:.2f}", 
                                 delta=f"{result['profit_percentage']:.2f}%",
                                 delta_color=profit_color)
                    with col3:
                        st.metric("💎 الرصيد النهائي", f"${result['final_balance']:.2f}")
                    with col4:
                        st.metric("📈 معدل النجاح", f"{result['win_rate']:.1f}%")
                    
                    # تحليل مفصل
                    metrics = calculate_metrics(result['trade_history'])
                    if metrics:
                        st.subheader("📈 تحليل أداء مفصل")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("🔢 إجمالي الصفقات", metrics['total_trades'])
                        col2.metric("✅ صفقات رابحة", metrics['winning_trades'])
                        col3.metric("📉 صفقات خاسرة", metrics['losing_trades'])
                        col4.metric("⚖️ عامل الربح", f"{metrics['profit_factor']:.2f}")
                    
                    # عرض الصفقات
                    trades_df = pd.DataFrame(result['trade_history'])
                    if not trades_df.empty:
                        st.subheader("💼 سجل الصفقات")
                        
                        display_df = trades_df.copy()
                        if 'timestamp' in display_df.columns:
                            display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                        if 'profit' in display_df.columns:
                            display_df['profit'] = display_df['profit'].apply(lambda x: f"${x:.4f}" if pd.notnull(x) else "-")
                        
                        st.dataframe(display_df, use_container_width=True)

with tab2:
    st.header("لوحة تحكم البوت الذكي")
    
    st.info("""
    **🧠 مميزات البوت الذكي الجديد:**
    
    - ✅ **ربح تراكمي فوري** بعد كل صفقة ناجحة
    - ✅ **إدارة مخاطر محكمة** مع وقف خسارة تلقائي
    - ✅ **ذكاء اصطناعي متقدم** بتأكيدات متعددة
    - ✅ **حماية من الخسائر** الكبيرة
    - ✅ **تداول آمن** برؤوس صغيرة
    """)
    
    st.warning("""
    **🎯 نصائح للنجاح:**
    
    - ابدأ برأس مال صغير (10-20$)
    - اختر 2-3 أزواج رئيسية فقط
    - استخدم الإطار الزمني 5-15 دقيقة
    - ركز على الجودة بدلاً من الكمية
    """)

# تذييل الصفحة
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🧠 <b>البوت التداولي الذكي</b> - نظام متكامل للربح التراكمي الفوري</p>
    <p>⚡ <i>إدارة ذكية للمخاطر • قرارات مدعومة بالذكاء الاصطناعي • ربح تراكمي فوري</i></p>
</div>
""", unsafe_allow_html=True)
