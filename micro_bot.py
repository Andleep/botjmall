import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import warnings
from scipy import stats
import requests
import json

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class MicroIntelligentTradingBot:
    """
    بوت تداول فائق الذكاء مخصص للرؤوس الصغيرة (10$+)
    مع ربح تراكمي فوري بعد كل صفقة ناجحة
    """
    
    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []
        self.selected_pairs = self.config.get("selected_pairs", [])
        
        # إحصائيات فورية
        self.real_time_metrics = {
            'total_trades': 0,
            'successful_trades': 0,
            'total_profit': 0.0,
            'current_streak': 0,
            'max_streak': 0,
            'compounded_profits': 0.0
        }
        
        # أنظمة التعلم
        self.learning_data = []
        self.adaptive_strategies = {}
        
        logger.info(f"🤖 البوت المصغر جاهز | رأس المال: ${self.balance:.2f}")
    
    def prepare_micro_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """تحضير بيانات سريعة للرؤوس الصغيرة"""
        df = df.copy()
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
        return df
    
    def calculate_fast_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """مؤشرات سريعة وفعالة للرؤوس الصغيرة"""
        df = df.copy()
        
        # مؤشرات أساسية سريعة
        df["ema9"] = talib.EMA(df["close"], 9)
        df["ema21"] = talib.EMA(df["close"], 21)
        df["rsi6"] = talib.RSI(df["close"], 6)
        df["rsi14"] = talib.RSI(df["close"], 14)
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(df["close"], 6, 13, 5)
        df["stoch_k"], df["stoch_d"] = talib.STOCH(df["high"], df["low"], df["close"], 5, 3, 0)
        df["atr"] = talib.ATR(df["high"], df["low"], df["close"], 7)
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(df["close"], 10, 2, 2)
        
        # مؤشرات مخصصة سريعة
        df['momentum_3'] = df['close'].pct_change(3)
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(10).mean()
        df['price_velocity'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5)
        
        # إشارات فورية
        df['oversold'] = ((df['rsi6'] < 25) & (df['rsi14'] < 35)).astype(int)
        df['overbought'] = ((df['rsi6'] > 75) & (df['rsi14'] > 65)).astype(int)
        df['bb_buy'] = (df['close'] < df['bb_lower']).astype(int)
        df['bb_sell'] = (df['close'] > df['bb_upper']).astype(int)
        df['macd_buy'] = ((df['macd'] > df['macd_signal']) & (df['macd_hist'] > 0)).astype(int)
        df['macd_sell'] = ((df['macd'] < df['macd_signal']) & (df['macd_hist'] < 0)).astype(int)
        
        return df
    
    def micro_ai_decision(self, df: pd.DataFrame, idx: int, symbol: str) -> Dict:
        """قرار ذكي سريع للرؤوس الصغيرة"""
        if idx < 20:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "بيانات غير كافية"}
        
        row = df.iloc[idx]
        
        # نظام تصويت سريع
        buy_signals = 0
        sell_signals = 0
        
        # إشارات شراء
        if row['oversold'] == 1:
            buy_signals += 2
        if row['bb_buy'] == 1:
            buy_signals += 2
        if row['macd_buy'] == 1:
            buy_signals += 1
        if row['stoch_k'] < 20 and row['stoch_d'] < 20:
            buy_signals += 1
        if row['momentum_3'] > 0.008 and row['volume_ratio'] > 1.2:
            buy_signals += 2
        if row['close'] > row['ema9'] and row['ema9'] > row['ema21']:
            buy_signals += 1
        
        # إشارات بيع
        if row['overbought'] == 1:
            sell_signals += 2
        if row['bb_sell'] == 1:
            sell_signals += 2
        if row['macd_sell'] == 1:
            sell_signals += 1
        if row['stoch_k'] > 80 and row['stoch_d'] > 80:
            sell_signals += 1
        if row['momentum_3'] < -0.008 and row['volume_ratio'] > 1.2:
            sell_signals += 2
        if row['close'] < row['ema9'] and row['ema9'] < row['ema21']:
            sell_signals += 1
        
        total_signals = buy_signals + sell_signals
        if total_signals == 0:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "لا توجد إشارات"}
        
        buy_ratio = buy_signals / total_signals
        sell_ratio = sell_signals / total_signals
        
        confidence = max(buy_ratio, sell_ratio) * 100
        
        # قرار ذكي مع عتبات مرنة
        if buy_ratio >= 0.6 and confidence >= 65:
            return {
                "signal": "BUY", 
                "confidence": confidence,
                "reason": f"إشارات شراء قوية ({buy_signals}/{total_signals})"
            }
        elif sell_ratio >= 0.6 and confidence >= 65:
            return {
                "signal": "SELL", 
                "confidence": confidence,
                "reason": f"إشارات بيع قوية ({sell_signals}/{total_signals})"
            }
        else:
            return {
                "signal": "HOLD", 
                "confidence": confidence,
                "reason": f"إشارات غير حاسمة (شراء: {buy_signals}, بيع: {sell_signals})"
            }
    
    def smart_micro_money_management(self, confidence: float, symbol: str) -> float:
        """إدارة أموال ذكية للرؤوس الصغيرة"""
        # قاعدة خطر ديناميكية
        base_risk = self.config.get("base_risk", 0.04)
        
        # تعديل بناءً على الأداء
        if self.real_time_metrics['current_streak'] >= 2:
            base_risk *= 1.3  # زيادة بعد صفقات رابحة
        elif self.real_time_metrics['current_streak'] <= -1:
            base_risk *= 0.7  # تقليل بعد خسائر
        
        # تعديل بناءً على الثقة
        risk_adjusted = base_risk * (confidence / 100.0)
        
        # حدود ذكية
        max_risk = self.config.get("max_risk", 0.08)
        min_risk = self.config.get("min_risk", 0.015)
        final_risk = np.clip(risk_adjusted, min_risk, max_risk)
        
        # حساب حجم المركز
        position_size = self.balance * final_risk
        
        # حدود الصفقات المصغرة
        min_trade = self.config.get("min_trade", 0.50)  # 50 سنت حد أدنى
        max_trade = self.config.get("max_trade", 3.00)  # 3 دولار حد أقصى
        
        # منع التداول إذا كان المبلغ صغير جداً
        if position_size < min_trade and self.balance > min_trade:
            position_size = min_trade
        elif position_size < min_trade:
            return 0.0
        
        return np.clip(position_size, min_trade, max_trade)
    
    def instant_profit_compounding(self, profit: float, trade_info: Dict):
        """ربح تراكمي فوري بعد كل صفقة ناجحة"""
        if profit > 0:
            # إضافة الربح إلى الرصيد فوراً
            old_balance = self.balance
            self.balance += profit
            
            # تحديث الإحصائيات
            self.real_time_metrics['total_profit'] += profit
            self.real_time_metrics['successful_trades'] += 1
            self.real_time_metrics['current_streak'] = max(self.real_time_metrics['current_streak'] + 1, 0)
            self.real_time_metrics['compounded_profits'] += profit
            self.real_time_metrics['max_streak'] = max(
                self.real_time_metrics['max_streak'], 
                self.real_time_metrics['current_streak']
            )
            
            logger.info(f"💰 ربح تراكمي فوري: +${profit:.4f} | {old_balance:.2f} → {self.balance:.2f}")
            
            # تعلم من النجاح
            self.learn_from_trade(trade_info, True)
        else:
            self.real_time_metrics['current_streak'] = min(self.real_time_metrics['current_streak'] - 1, 0)
            self.learn_from_trade(trade_info, False)
    
    def learn_from_trade(self, trade_info: Dict, successful: bool):
        """التعلم من كل صفقة"""
        learning_entry = {
            'timestamp': datetime.now(),
            'symbol': trade_info.get('symbol', ''),
            'decision': trade_info.get('decision', {}),
            'profit': trade_info.get('profit', 0),
            'successful': successful,
            'balance_after': self.balance
        }
        
        self.learning_data.append(learning_entry)
        
        # تحديث الاستراتيجيات التكيفية
        strategy_key = f"{trade_info.get('symbol', '')}_{trade_info.get('decision', {}).get('signal', 'HOLD')}"
        if strategy_key not in self.adaptive_strategies:
            self.adaptive_strategies[strategy_key] = {
                'attempts': 0,
                'successes': 0,
                'total_profit': 0.0,
                'last_used': datetime.now()
            }
        
        self.adaptive_strategies[strategy_key]['attempts'] += 1
        if successful:
            self.adaptive_strategies[strategy_key]['successes'] += 1
            self.adaptive_strategies[strategy_key]['total_profit'] += trade_info.get('profit', 0)
        self.adaptive_strategies[strategy_key]['last_used'] = datetime.now()
    
    def get_strategy_effectiveness(self, symbol: str, signal: str) -> float:
        """الحصول على فعالية الاستراتيجية"""
        strategy_key = f"{symbol}_{signal}"
        if strategy_key in self.adaptive_strategies:
            stats = self.adaptive_strategies[strategy_key]
            if stats['attempts'] > 0:
                return stats['successes'] / stats['attempts']
        return 0.5  # فعالية افتراضية
    
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
                
            df = self.prepare_micro_data(df)
            df = self.calculate_fast_indicators(df)
            
            pair_trades = 0
            
            for i in range(20, len(df)):
                # قرار الذكاء الاصطناعي السريع
                ai_decision = self.micro_ai_decision(df, i, symbol)
                signal = ai_decision["signal"]
                confidence = ai_decision["confidence"]
                
                # التحقق من فعالية الاستراتيجية
                strategy_effectiveness = self.get_strategy_effectiveness(symbol, signal)
                if strategy_effectiveness < 0.4 and self.real_time_metrics['total_trades'] > 10:
                    continue  # تخطي الاستراتيجيات غير الفعالة
                
                price = float(df["close"].iloc[i])
                ts = df.index[i]
                
                if signal in ["BUY", "SELL"] and confidence >= self.config.get("confidence_threshold", 65):
                    position_size = self.smart_micro_money_management(confidence, symbol)
                    
                    if position_size > 0 and signal == "BUY" and symbol not in self.positions:
                        # فتح صفقة شراء
                        qty = position_size / price
                        self.positions[symbol] = {
                            "entry_time": ts, 
                            "entry_price": price, 
                            "amount": position_size, 
                            "qty": qty,
                            "type": "LONG", 
                            "confidence": confidence,
                            "decision_data": ai_decision
                        }
                        self.balance -= position_size
                        
                        trade_record = {
                            "timestamp": ts, "symbol": symbol, "action": "BUY",
                            "price": price, "amount": position_size, "qty": qty,
                            "confidence": confidence, "status": "OPEN",
                            "balance_before": self.balance + position_size,
                            "balance_after": self.balance,
                            "decision_reason": ai_decision["reason"]
                        }
                        self.trade_history.append(trade_record)
                        pair_trades += 1
                        total_trades += 1
                        self.real_time_metrics['total_trades'] += 1
                        
                    elif signal == "SELL" and symbol in self.positions:
                        # إغلاق صفقة شراء
                        pos = self.positions.pop(symbol)
                        profit = (price - pos["entry_price"]) * pos["qty"]
                        
                        # ✅ تطبيق الربح التراكمي الفوري
                        self.instant_profit_compounding(profit, {
                            'symbol': symbol,
                            'decision': ai_decision,
                            'profit': profit,
                            'position_data': pos
                        })
                        
                        trade_record = {
                            "timestamp": ts, "symbol": symbol, "action": "SELL",
                            "price": price, "amount": pos["amount"], "qty": pos["qty"],
                            "profit": profit, "profit_pct": (profit / pos["amount"]) * 100,
                            "confidence": pos["confidence"], "status": "CLOSED",
                            "balance_before": self.balance,
                            "balance_after": self.balance + profit,
                            "decision_reason": ai_decision["reason"],
                            "compounded": True
                        }
                        self.trade_history.append(trade_record)
                        pair_trades += 1
                        total_trades += 1
            
            # إغلاق المراكز المتبقية
            if symbol in self.positions:
                pos = self.positions.pop(symbol)
                price = float(df["close"].iloc[-1])
                profit = (price - pos["entry_price"]) * pos["qty"]
                
                self.instant_profit_compounding(profit, {
                    'symbol': symbol,
                    'decision': {"signal": "CLOSE", "reason": "إغلاق نهائي"},
                    'profit': profit,
                    'position_data': pos
                })
                
                self.trade_history.append({
                    "timestamp": df.index[-1], "symbol": symbol, "action": "SELL",
                    "price": price, "amount": pos["amount"], "qty": pos["qty"],
                    "profit": profit, "profit_pct": (profit / pos["amount"]) * 100,
                    "confidence": pos["confidence"], "status": "CLOSED",
                    "balance_before": self.balance,
                    "balance_after": self.balance + profit,
                    "decision_reason": "إغلاق نهائي للمحاكاة",
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
        
        logger.info(f"🎯 انتهت المحاكاة المصغرة | الصفقات: {total_trades} | "
                   f"الربح: ${total_profit:.2f} ({profit_percentage:.2f}%) | "
                   f"معدل النجاح: {win_rate:.1f}% | "
                   f"الرصيد النهائي: ${self.balance:.2f}")
        
        return {
            "final_balance": self.balance,
            "total_profit": total_profit,
            "profit_percentage": profit_percentage,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "trade_history": self.trade_history,
            "initial_balance": self.initial_balance,
            "real_time_metrics": self.real_time_metrics,
            "adaptive_strategies": self.adaptive_strategies,
            "learning_data_size": len(self.learning_data)
        }
