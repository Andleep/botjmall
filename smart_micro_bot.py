import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SmartMicroTradingBot:
    """
    بوت تداول ذكي حقيقي - معاد كتابته من الصفر
    يركز على الجودة بدلاً من الكمية
    """
    
    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []
        self.selected_pairs = self.config.get("selected_pairs", [])
        
        # إحصائيات محسنة
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'max_profit': 0.0,
            'max_loss': 0.0,
            'compounded_profits': 0.0
        }
        
        logger.info(f"🎯 البوت الذكي الجاهز | رأس المال: ${self.balance:.2f}")
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """تحضير بيانات دقيقة"""
        df = df.copy()
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # إزالة القيم غير الصالحة
        df = df.dropna()
        
        return df
    
    def calculate_smart_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """مؤشرات ذكية تركز على الدقة"""
        df = df.copy()
        
        # مؤشرات الاتجاه الأساسية
        df["sma_20"] = talib.SMA(df["close"], 20)
        df["ema_12"] = talib.EMA(df["close"], 12)
        df["ema_26"] = talib.EMA(df["close"], 26)
        
        # مؤشرات الزخم
        df["rsi_14"] = talib.RSI(df["close"], 14)
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(df["close"], 12, 26, 9)
        df["stoch_k"], df["stoch_d"] = talib.STOCH(df["high"], df["low"], df["close"], 14, 3, 0)
        
        # مؤشرات التقلب
        df["atr_14"] = talib.ATR(df["high"], df["low"], df["close"], 14)
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(df["close"], 20, 2, 2)
        
        # مؤشرات الحجم
        df["volume_sma"] = talib.SMA(df["volume"], 20)
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # اتجاه السعر
        df["price_above_sma"] = (df["close"] > df["sma_20"]).astype(int)
        df["ema_bullish"] = (df["ema_12"] > df["ema_26"]).astype(int)
        
        return df
    
    def smart_trading_decision(self, df: pd.DataFrame, idx: int, symbol: str) -> Dict:
        """قرار تداول ذكي يعتمد على تأكيدات متعددة"""
        if idx < 30:  # تحتاج بيانات أكثر
            return {"signal": "HOLD", "confidence": 0, "reason": "بيانات غير كافية"}
        
        current_data = df.iloc[:idx+1]
        current_row = df.iloc[idx]
        
        # 🔥 نظام التأكيدات المتعددة
        confirmations = {
            'trend': 0,
            'momentum': 0, 
            'volume': 0,
            'volatility': 0,
            'pattern': 0
        }
        
        # 1. تأكيد الاتجاه
        if current_row['price_above_sma'] == 1 and current_row['ema_bullish'] == 1:
            confirmations['trend'] += 2
        elif current_row['price_above_sma'] == 0 and current_row['ema_bullish'] == 0:
            confirmations['trend'] -= 2
        
        # 2. تأكيد الزخم
        if 30 < current_row['rsi_14'] < 70:  # منطقة آمنة
            confirmations['momentum'] += 1
            
        if current_row['macd_hist'] > 0 and current_row['macd'] > current_row['macd_signal']:
            confirmations['momentum'] += 2
        elif current_row['macd_hist'] < 0 and current_row['macd'] < current_row['macd_signal']:
            confirmations['momentum'] -= 2
        
        # 3. تأكيد الحجم
        if current_row['volume_ratio'] > 1.2:
            confirmations['volume'] += 1
        
        # 4. تأكيد التقلب
        atr_percentage = current_row['atr_14'] / current_row['close']
        if 0.005 < atr_percentage < 0.03:  # تقلب معقول
            confirmations['volatility'] += 1
        
        # 5. أنماط بولنجر باند
        if current_row['close'] < current_row['bb_lower'] and current_row['rsi_14'] < 35:
            confirmations['pattern'] += 2  # شراء عند الدعم
        elif current_row['close'] > current_row['bb_upper'] and current_row['rsi_14'] > 65:
            confirmations['pattern'] -= 2  # بيع عند المقاومة
        
        # حساب النتيجة النهائية
        total_score = sum(confirmations.values())
        
        # 🔥 قرار ذكي مع عتبات عالية
        if total_score >= 4:  # يحتاج 4 تأكيدات على الأقل
            confidence = min((total_score / 8) * 100, 95)
            return {
                "signal": "BUY",
                "confidence": confidence,
                "reason": f"تأكيدات شراء قوية ({total_score}/8)",
                "confirmations": confirmations
            }
        elif total_score <= -4:
            confidence = min((abs(total_score) / 8) * 100, 95)
            return {
                "signal": "SELL", 
                "confidence": confidence,
                "reason": f"تأكيدات بيع قوية ({abs(total_score)}/8)",
                "confirmations": confirmations
            }
        else:
            return {
                "signal": "HOLD",
                "confidence": abs(total_score) * 10,
                "reason": f"تأكيدات غير كافية ({total_score}/8)",
                "confirmations": confirmations
            }
    
    def calculate_position_size(self, confidence: float) -> float:
        """حساب حجم مركز آمن"""
        # خطر أساسي منخفض
        base_risk = 0.015  # 1.5% فقط
        
        # تعديل حسب الثقة
        risk_adjusted = base_risk * (confidence / 100.0)
        
        # حدود صارمة
        final_risk = max(0.005, min(risk_adjusted, 0.025))  # بين 0.5% و2.5%
        
        position_size = self.balance * final_risk
        
        # حدود حجم الصفقة
        min_trade = 1.00  # 1$ حد أدنى
        max_trade = 3.00  # 3$ حد أقصى
        
        return max(min_trade, min(position_size, max_trade))
    
    def execute_trade(self, symbol: str, signal: str, price: float, position_size: float, confidence: float, reason: str):
        """تنفيذ صفقة مع إدارة مخاطر مدمجة"""
        if signal == "BUY" and symbol not in self.positions:
            # فتح صفقة شراء
            qty = position_size / price
            
            # 🔥 وقف خسارة وجني أرباح ذكي
            atr = (price * 0.01)  # استخدام 1% تقريباً كوقف
            stop_loss = price * 0.985  # وقف خسارة 1.5%
            take_profit = price * 1.01  # جني أرباح 1.0%
            
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
            
            logger.info(f"📈 فتح صفقة شراء: {symbol} | السعر: ${price:.4f} | المبلغ: ${position_size:.2f}")
            
        elif signal == "SELL" and symbol in self.positions:
            # إغلاق صفقة شراء
            position = self.positions.pop(symbol)
            profit = (price - position["entry_price"]) * position["qty"]
            
            # 🔥 تطبيق الربح التراكمي الفوري
            if profit > 0:
                old_balance = self.balance
                self.balance += profit + position["amount"]  # العودة + الربح
                
                self.metrics['winning_trades'] += 1
                self.metrics['total_profit'] += profit
                self.metrics['compounded_profits'] += profit
                self.metrics['max_profit'] = max(self.metrics['max_profit'], profit)
                
                logger.info(f"💰 ربح تراكمي: +${profit:.4f} | الرصيد: {old_balance:.2f} → {self.balance:.2f}")
            else:
                self.balance += position["amount"] + profit  # العودة + الخسارة
                self.metrics['losing_trades'] += 1
                self.metrics['max_loss'] = min(self.metrics['max_loss'], profit)
                
                logger.info(f"📉 خسارة محققة: ${profit:.4f} | الرصيد: ${self.balance:.2f}")
            
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
    
    def check_exit_conditions(self, df: pd.DataFrame, idx: int, symbol: str):
        """فحص شروط الخروج من الصفقات المفتوحة"""
        if symbol not in self.positions:
            return
            
        position = self.positions[symbol]
        current_price = float(df["close"].iloc[idx])
        current_time = df.index[idx]
        
        # 🔥 فحص وقف الخسارة وجني الأرباح
        if current_price <= position["stop_loss"]:
            self.execute_trade(symbol, "SELL", current_price, 0, position["confidence"], "وقف خسارة")
        elif current_price >= position["take_profit"]:
            self.execute_trade(symbol, "SELL", current_price, 0, position["confidence"], "جني أرباح")
        
        # 🔥 فحص الخروج بالوقت (أقصى مدة 30 شمعة)
        entry_index = df.index.get_loc(position["entry_time"]) if position["entry_time"] in df.index else -1
        if entry_index != -1 and (idx - entry_index) >= 30:
            self.execute_trade(symbol, "SELL", current_price, 0, position["confidence"], "انتهاء الوقت")
    
    def run_smart_backtest(self, klines_data: Dict, timeframe: str):
        """محاكاة ذكية تركز على الجودة"""
        results = {}
        
        logger.info(f"🎯 بدء المحاكاة الذكية على {len(self.selected_pairs)} أزواج")
        
        for symbol in self.selected_pairs:
            if symbol not in klines_data:
                continue
                
            logger.info(f"🔍 تحليل {symbol} بمنهجية ذكية...")
            df = klines_data[symbol].copy()
            
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df.set_index("timestamp", inplace=True)
            
            # تحضير البيانات والمؤشرات
            df = self.prepare_data(df)
            df = self.calculate_smart_indicators(df)
            
            # 🔥 ترشيح البيانات الجيدة فقط
            df = df[df['rsi_14'].notna() & df['macd'].notna() & df['sma_20'].notna()]
            
            pair_trades = 0
            
            for i in range(30, len(df)):  # بداية من 30 للحصول على بيانات كافية
                # 1. فحص الخروج أولاً من الصفقات المفتوحة
                self.check_exit_conditions(df, i, symbol)
                
                # 2. قرار الدخول الذكي
                decision = self.smart_trading_decision(df, i, symbol)
                
                if decision["signal"] in ["BUY", "SELL"] and decision["confidence"] >= 70:
                    price = float(df["close"].iloc[i])
                    position_size = self.calculate_position_size(decision["confidence"])
                    
                    # 🔥 تأكيد إضافي: لا تداول إذا كان السعر عند أطراف المدى
                    rsi = df["rsi_14"].iloc[i]
                    if decision["signal"] == "BUY" and rsi > 60:
                        continue  # لا تشتري عند ذروة الشراء
                    elif decision["signal"] == "SELL" and rsi < 40:
                        continue  # لا تبيع عند ذروة البيع
                    
                    self.execute_trade(
                        symbol, decision["signal"], price, 
                        position_size, decision["confidence"], decision["reason"]
                    )
                    pair_trades += 1
            
            # إغلاق أي صفقات متبقية في النهاية
            if symbol in self.positions:
                position = self.positions.pop(symbol)
                price = float(df["close"].iloc[-1])
                self.execute_trade(symbol, "SELL", price, 0, position["confidence"], "إغلاق نهائي")
            
            results[symbol] = {"trades": pair_trades}
        
        # حساب النتائج النهائية
        total_profit = self.balance - self.initial_balance
        profit_percentage = (total_profit / self.initial_balance) * 100
        
        win_rate = (self.metrics['winning_trades'] / self.metrics['total_trades'] * 100) if self.metrics['total_trades'] > 0 else 0
        
        logger.info(f"✅ انتهت المحاكاة الذكية | الصفقات: {self.metrics['total_trades']} | "
                   f"الربح: ${total_profit:.2f} ({profit_percentage:.2f}%) | "
                   f"معدل النجاح: {win_rate:.1f}%")
        
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
            "metrics": self.metrics
        }

    # دالة التوافق مع الواجهة
    def run_micro_backtest(self, klines_data: Dict, timeframe: str):
        """دالة التوافق مع الواجهة الحالية"""
        return self.run_smart_backtest(klines_data, timeframe)
