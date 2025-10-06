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

class MicroTradingBot:
    """
    بوت تداول مصمم خصيصاً للرؤوس الصغيرة (10$ فما فوق)
    مع ربح تراكمي فوري بعد كل صفقة
    """
    
    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []
        self.selected_pairs = self.config.get("selected_pairs", [])
        
        # إحصائيات فورية
        self.live_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_profit': 0.0,
            'current_streak': 0,
            'max_streak': 0
        }
        
        logger.info(f"🤖 البوت المصغر جاهز | رأس المال: ${self.balance:.2f}")
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """تحضير بيانات سريعة للرؤوس الصغيرة"""
        df = df.copy()
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
        return df
    
    def add_fast_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """مؤشرات سريعة ومثبتة للرؤوس الصغيرة"""
        df = df.copy()
        
        # مؤشرات أساسية سريعة
        df["ema_9"] = talib.EMA(df["close"], 9)
        df["ema_21"] = talib.EMA(df["close"], 21)
        df["rsi_6"] = talib.RSI(df["close"], 6)
        df["rsi_14"] = talib.RSI(df["close"], 14)
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(df["close"], 6, 13, 5)
        df["stoch_k"], df["stoch_d"] = talib.STOCH(df["high"], df["low"], df["close"], 5, 3, 0)
        df["atr"] = talib.ATR(df["high"], df["low"], df["close"], 7)
        
        # بولنجر باند سريع
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(df["close"], 10, 2, 2)
        
        # مؤشرات مخصصة للرؤوس الصغيرة
        df["momentum_3"] = df["close"].pct_change(3)
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(10).mean()
        df["price_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        
        return df
    
    def micro_signal_detection(self, df: pd.DataFrame, idx: int) -> Dict:
        """كشف إشارات مخصص للرؤوس الصغيرة"""
        if idx < 20:
            return {"signal": "HOLD", "confidence": 0, "reason": "بيانات غير كافية"}
        
        row = df.iloc[idx]
        
        buy_signals = 0
        sell_signals = 0
        
        # إشارات شراء قوية للرؤوس الصغيرة
        if row["rsi_6"] < 25 and row["rsi_14"] < 35:
            buy_signals += 3
        if row["close"] < row["bb_lower"] and row["rsi_6"] < 30:
            buy_signals += 2
        if row["macd_hist"] > 0 and row["macd"] > row["macd_signal"]:
            buy_signals += 2
        if row["stoch_k"] < 20 and row["stoch_d"] < 20:
            buy_signals += 1
        if row["momentum_3"] > 0.008 and row["volume_ratio"] > 1.2:
            buy_signals += 2
        
        # إشارات بيع قوية للرؤوس الصغيرة
        if row["rsi_6"] > 75 and row["rsi_14"] > 65:
            sell_signals += 3
        if row["close"] > row["bb_upper"] and row["rsi_6"] > 70:
            sell_signals += 2
        if row["macd_hist"] < 0 and row["macd"] < row["macd_signal"]:
            sell_signals += 2
        if row["stoch_k"] > 80 and row["stoch_d"] > 80:
            sell_signals += 1
        if row["momentum_3"] < -0.008 and row["volume_ratio"] > 1.2:
            sell_signals += 2
        
        total_signals = buy_signals + sell_signals
        if total_signals == 0:
            return {"signal": "HOLD", "confidence": 0, "reason": "لا توجد إشارات"}
        
        confidence = (max(buy_signals, sell_signals) / total_signals) * 100
        
        if buy_signals >= 4 and confidence >= 65:
            return {
                "signal": "BUY", 
                "confidence": confidence,
                "reason": f"إشارات شراء قوية ({buy_signals}/8)"
            }
        elif sell_signals >= 4 and confidence >= 65:
            return {
                "signal": "SELL", 
                "confidence": confidence,
                "reason": f"إشارات بيع قوية ({sell_signals}/8)"
            }
        else:
            return {
                "signal": "HOLD", 
                "confidence": confidence,
                "reason": f"إشارات غير كافية (شراء: {buy_signals}, بيع: {sell_signals})"
            }
    
    def micro_money_management(self, confidence: float, symbol: str) -> float:
        """إدارة أموال ذكية للرؤوس الصغيرة"""
        # قاعدة مخاطرة ديناميكية
        base_risk = self.config.get("base_risk", 0.03)  # 3% أساسي
        
        # تعديل بناءً على الثقة
        confidence_multiplier = confidence / 100.0
        
        # تعديل بناءً على الأداء
        performance_multiplier = 1.0
        if self.live_metrics['current_streak'] >= 2:
            performance_multiplier = 1.3  # زيادة بعد صفقات رابحة
        elif self.live_metrics['current_streak'] <= -1:
            performance_multiplier = 0.7  # تقليل بعد خسائر
        
        risk_adjusted = base_risk * confidence_multiplier * performance_multiplier
        
        # حدود المخاطرة للرؤوس الصغيرة
        max_risk = self.config.get("max_risk", 0.06)   # 6% أقصى
        min_risk = self.config.get("min_risk", 0.015)  # 1.5% أدنى
        
        final_risk = np.clip(risk_adjusted, min_risk, max_risk)
        
        # حساب حجم المركز
        position_size = self.balance * final_risk
        
        # حدود الصفقة للرؤوس الصغيرة
        min_trade = self.config.get("min_trade", 0.20)  # 20 سنت أدنى صفقة
        max_trade = self.config.get("max_trade", self.balance * 0.25)  # 25% كحد أقصى
        
        return np.clip(position_size, min_trade, max_trade)
    
    def instant_profit_compounding(self, profit: float):
        """ربح تراكمي فوري بعد كل صفقة ناجحة"""
        if profit > 0:
            # إضافة الربح إلى الرصيد فوراً
            old_balance = self.balance
            self.balance += profit
            
            # تحديث الإحصائيات
            self.live_metrics['total_profit'] += profit
            self.live_metrics['winning_trades'] += 1
            self.live_metrics['current_streak'] = max(self.live_metrics['current_streak'] + 1, 0)
            self.live_metrics['max_streak'] = max(self.live_metrics['max_streak'], self.live_metrics['current_streak'])
            
            logger.info(f"💰 ربح تراكمي فوري: +${profit:.4f} | ${old_balance:.2f} → ${self.balance:.2f}")
        else:
            self.live_metrics['current_streak'] = min(self.live_metrics['current_streak'] - 1, 0)
    
    def run_micro_backtest(self, klines_data: Dict, timeframe: str):
        """محاكاة مخصصة للرؤوس الصغيرة"""
        results = {}
        total_trades = 0
        
        logger.info(f"🚀 بدء المحاكاة المصغرة على {len(self.selected_pairs)} أزواج")
        
        for symbol in self.selected_pairs:
            if symbol not in klines_data:
                continue
                
            logger.info(f"🔍 تحليل {symbol}...")
            df = klines_data[symbol].copy()
            
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df.set_index("timestamp", inplace=True)
                
            df = self.prepare_data(df)
            df = self.add_fast_indicators(df)
            
            pair_trades = 0
            
            for i in range(20, len(df)):
                # قرار التداول
                signal_data = self.micro_signal_detection(df, i)
                signal = signal_data["signal"]
                confidence = signal_data["confidence"]
                
                price = float(df["close"].iloc[i])
                ts = df.index[i]
                
                if signal in ["BUY", "SELL"] and confidence >= 65:
                    position_size = self.micro_money_management(confidence, symbol)
                    
                    if signal == "BUY" and symbol not in self.positions:
                        # فتح صفقة شراء
                        qty = position_size / price
                        self.positions[symbol] = {
                            "entry_time": ts, 
                            "entry_price": price, 
                            "amount": position_size, 
                            "qty": qty,
                            "type": "LONG", 
                            "confidence": confidence
                        }
                        self.balance -= position_size
                        
                        self.trade_history.append({
                            "timestamp": ts, "symbol": symbol, "action": "BUY",
                            "price": price, "amount": position_size, "qty": qty,
                            "confidence": confidence, "status": "OPEN",
                            "balance_before": self.balance + position_size,
                            "balance_after": self.balance,
                            "reason": signal_data["reason"]
                        })
                        pair_trades += 1
                        total_trades += 1
                        self.live_metrics['total_trades'] += 1
                        
                    elif signal == "SELL" and symbol in self.positions:
                        # إغلاق صفقة شراء
                        pos = self.positions.pop(symbol)
                        profit = (price - pos["entry_price"]) * pos["qty"]
                        
                        # تطبيق الربح التراكمي الفوري
                        self.instant_profit_compounding(profit)
                        
                        self.trade_history.append({
                            "timestamp": ts, "symbol": symbol, "action": "SELL",
                            "price": price, "amount": pos["amount"], "qty": pos["qty"],
                            "profit": profit, "profit_pct": (profit / pos["amount"]) * 100,
                            "confidence": pos["confidence"], "status": "CLOSED",
                            "balance_before": self.balance,
                            "balance_after": self.balance + profit,
                            "reason": signal_data["reason"],
                            "compounded": True
                        })
                        pair_trades += 1
                        total_trades += 1
            
            # إغلاق المراكز المتبقية
            if symbol in self.positions:
                pos = self.positions.pop(symbol)
                price = float(df["close"].iloc[-1])
                profit = (price - pos["entry_price"]) * pos["qty"]
                
                self.instant_profit_compounding(profit)
                
                self.trade_history.append({
                    "timestamp": df.index[-1], "symbol": symbol, "action": "SELL",
                    "price": price, "amount": pos["amount"], "qty": pos["qty"],
                    "profit": profit, "profit_pct": (profit / pos["amount"]) * 100,
                    "confidence": pos["confidence"], "status": "CLOSED",
                    "balance_before": self.balance,
                    "balance_after": self.balance + profit,
                    "reason": "إغلاق نهائي للمحاكاة",
                    "compounded": True
                })
                total_trades += 1
            
            results[symbol] = {"trades": pair_trades}
        
        # النتائج النهائية
        total_profit = self.balance - self.initial_balance
        profit_percentage = (total_profit / self.initial_balance) * 100
        
        closed_trades = [t for t in self.trade_history if t.get('status') == 'CLOSED']
        winning_trades = len([t for t in closed_trades if t.get('profit', 0) > 0])
        win_rate = (winning_trades / len(closed_trades)) * 100 if closed_trades else 0
        
        logger.info(f"🎯 انتهت المحاكاة | الصفقات: {total_trades} | "
                   f"الربح: ${total_profit:.2f} ({profit_percentage:.2f}%) | "
                   f"معدل النجاح: {win_rate:.1f}%")
        
        return {
            "final_balance": self.balance,
            "total_profit": total_profit,
            "profit_percentage": profit_percentage,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "trade_history": self.trade_history,
            "initial_balance": self.initial_balance,
            "live_metrics": self.live_metrics,
            "compounding_effect": self.live_metrics['total_profit']
        }
