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
    بوت تداول مُصَحَح مع إدارة مخاطر محكمة وربح تراكمي فعال
    """
    
    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []
        self.selected_pairs = self.config.get("selected_pairs", [])
        
        # 🔥 إضافة إحصائيات محسنة
        self.real_time_metrics = {
            'total_trades': 0,
            'successful_trades': 0,
            'total_profit': 0.0,
            'current_streak': 0,
            'max_streak': 0,
            'compounded_profits': 0.0,
            'daily_profit': 0.0,
            'daily_trades': 0,
            'consecutive_losses': 0  # 🔥 تتبع الخسائر المتتالية
        }
        
        # 🔥 إضافة أنظمة حماية
        self.protection_metrics = {
            'daily_stop_loss': False,
            'max_daily_loss': self.config.get("daily_loss_limit", 0.20) * self.initial_balance,
            'current_daily_loss': 0.0,
            'trading_enabled': True
        }
        
        self.learning_data = []
        self.adaptive_strategies = {}
        
        logger.info(f"🤖 البوت المُصَحَح جاهز | رأس المال: ${self.balance:.2f}")
    
    def check_trading_permission(self) -> bool:
        """🔥 فحص إذا كان التداول مسموح به"""
        if not self.protection_metrics['trading_enabled']:
            return False
            
        # فحص الخسارة اليومية
        daily_loss = abs(self.protection_metrics['current_daily_loss'])
        if daily_loss >= self.protection_metrics['max_daily_loss']:
            logger.warning("🛑 توقف التداول - وصلت للحد الأقصى للخسارة اليومية")
            self.protection_metrics['trading_enabled'] = False
            return False
            
        # فحص الخسائر المتتالية
        if self.real_time_metrics['consecutive_losses'] >= self.config.get("consecutive_loss_limit", 3):
            logger.warning("🛑 توقف مؤقت - 3 خسائر متتالية")
            return False
            
        return True
    
    def prepare_micro_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """تحضير بيانات محسنة"""
        df = df.copy()
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
        return df
    
    def calculate_enhanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """مؤشرات محسنة مع تصفية أفضل"""
        df = df.copy()
        
        # المؤشرات الأساسية
        df["ema9"] = talib.EMA(df["close"], 9)
        df["ema21"] = talib.EMA(df["close"], 21)
        df["rsi14"] = talib.RSI(df["close"], 14)
        df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(df["close"], 6, 13, 5)
        df["stoch_k"], df["stoch_d"] = talib.STOCH(df["high"], df["low"], df["close"], 5, 3, 0)
        df["atr"] = talib.ATR(df["high"], df["low"], df["close"], 7)
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(df["close"], 10, 2, 2)
        
        # 🔥 مؤشرات تصفية محسنة
        df['trend_strength'] = abs(df['ema9'] - df['ema21']) / df['atr']
        df['volume_surge'] = df['volume'] / df['volume'].rolling(10).mean()
        df['price_momentum'] = df['close'].pct_change(3)
        
        # 🔥 إشارات أكثر تحفظاً
        df['strong_buy'] = (
            (df['rsi14'] < 30) & 
            (df['close'] < df['bb_lower']) & 
            (df['macd_hist'] > 0) &
            (df['trend_strength'] > 0.5) &
            (df['volume_surge'] > 1.2)
        ).astype(int)
        
        df['strong_sell'] = (
            (df['rsi14'] > 70) & 
            (df['close'] > df['bb_upper']) & 
            (df['macd_hist'] < 0) &
            (df['trend_strength'] > 0.5) &
            (df['volume_surge'] > 1.2)
        ).astype(int)
        
        return df
    
    def enhanced_ai_decision(self, df: pd.DataFrame, idx: int, symbol: str) -> Dict:
        """🔥 قرار تداول محسَن مع تصفية صارمة"""
        if idx < 25:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "بيانات غير كافية"}
        
        row = df.iloc[idx]
        
        # 🔥 تصفية أولية - تأكد من وجود اتجاه قوي
        if row['trend_strength'] < 0.3:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "اتجاه ضعيف"}
        
        # 🔥 نظام تصويت مرجح
        buy_score = 0
        sell_score = 0
        
        # إشارات شراء مع أوزان
        if row['strong_buy'] == 1:
            buy_score += 3
        if row['rsi14'] < 30:
            buy_score += 2
        if row['macd_hist'] > 0 and row['macd'] > row['macd_signal']:
            buy_score += 1
        if row['stoch_k'] < 20:
            buy_score += 1
        if row['price_momentum'] > 0.01:  # زخم إيجابي قوي
            buy_score += 2
            
        # إشارات بيع مع أوزان  
        if row['strong_sell'] == 1:
            sell_score += 3
        if row['rsi14'] > 70:
            sell_score += 2
        if row['macd_hist'] < 0 and row['macd'] < row['macd_signal']:
            sell_score += 1
        if row['stoch_k'] > 80:
            sell_score += 1
        if row['price_momentum'] < -0.01:  # زخم سلبي قوي
            sell_score += 2
        
        total_score = buy_score + sell_score
        if total_score == 0:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "لا توجد إشارات قوية"}
        
        buy_ratio = buy_score / total_score
        sell_ratio = sell_score / total_score
        
        confidence = max(buy_ratio, sell_ratio) * 100
        
        # 🔥 عتبات أعلى لتحسين الدقة
        if buy_ratio >= 0.7 and confidence >= 75:  # كان 0.6 و65%
            return {
                "signal": "BUY", 
                "confidence": confidence,
                "reason": f"إشارات شراء قوية جداً ({buy_score}/{total_score})"
            }
        elif sell_ratio >= 0.7 and confidence >= 75:
            return {
                "signal": "SELL", 
                "confidence": confidence,
                "reason": f"إشارات بيع قوية جداً ({sell_score}/{total_score})"
            }
        else:
            return {
                "signal": "HOLD", 
                "confidence": confidence,
                "reason": f"إشارات غير كافية (شراء: {buy_score}, بيع: {sell_score})"
            }
    
    def safe_money_management(self, confidence: float, symbol: str) -> Tuple[float, float, float]:
        """🔥 إدارة أموال آمنة مع وقف خسارة وجني أرباح"""
        # حجم المركز الآمن
        base_risk = self.config.get("base_risk", 0.02)
        
        # تعديل بناءً على الأداء
        if self.real_time_metrics['consecutive_losses'] >= 2:
            base_risk *= 0.5  # تقليل المخاطرة بعد خسائر متتالية
        
        risk_adjusted = base_risk * (confidence / 100.0)
        
        # حدود آمنة
        max_risk = self.config.get("max_risk", 0.04)
        min_risk = self.config.get("min_risk", 0.008)
        final_risk = np.clip(risk_adjusted, min_risk, max_risk)
        
        position_size = self.balance * final_risk
        
        # حدود حجم الصفقة
        min_trade = self.config.get("min_trade", 1.00)
        max_trade = self.config.get("max_trade", 2.00)
        position_size = np.clip(position_size, min_trade, max_trade)
        
        # 🔥 وقف خسارة وجني أرباح ديناميكي
        stop_loss_pct = self.config.get("max_stop_loss", 0.015)  # 1.5%
        take_profit_pct = self.config.get("min_profit_target", 0.003)  # 0.3%
        
        # تعديل بناءً على الثقة
        if confidence > 80:
            take_profit_pct *= 1.5  # زيادة جني الأرباح للصفقات عالية الثقة
        
        return position_size, stop_loss_pct, take_profit_pct
    
    def calculate_trade_result(self, entry_price: float, exit_price: float, position_size: float, qty: float) -> float:
        """🔥 حساب نتيجة الصفقة مع عمولة Binance"""
        raw_profit = (exit_price - entry_price) * qty
        
        # 🔥 خصم عمولة Binance (0.1% تقريباً)
        commission = abs(raw_profit) * 0.001
        net_profit = raw_profit - commission
        
        return net_profit
    
    def instant_profit_compounding(self, profit: float, trade_info: Dict):
        """🔥 ربح تراكمي فوري مع تحديث الرصيد"""
        if profit > 0:
            # 🔥 تسجيل الرصيد القديم
            old_balance = self.balance
            
            # 🔥 إضافة الربح إلى الرصيد فوراً
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
            self.real_time_metrics['consecutive_losses'] = 0  # 🔥 إعادة تعيين الخسائر المتتالية
            
            logger.info(f"💰 ربح تراكمي فوري: +${profit:.4f} | {old_balance:.2f} → {self.balance:.2f}")
            
            # تعلم من النجاح
            self.learn_from_trade(trade_info, True)
        else:
            self.real_time_metrics['current_streak'] = 0
            self.real_time_metrics['consecutive_losses'] += 1  # 🔥 تتبع الخسائر المتتالية
            self.protection_metrics['current_daily_loss'] += profit  # 🔥 تحديث الخسارة اليومية
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
    
    def run_enhanced_backtest(self, klines_data: Dict, timeframe: str):
        """🔥 محاكاة محسنة مع أنظمة حماية"""
        results = {}
        total_trades = 0
        
        logger.info(f"🚀 بدء المحاكاة المحسنة على {len(self.selected_pairs)} أزواج")
        
        for symbol in self.selected_pairs:
            if symbol not in klines_data:
                continue
                
            logger.info(f"🔍 تحليل {symbol} بمؤشرات محسنة...")
            df = klines_data[symbol].copy()
            
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                df.set_index("timestamp", inplace=True)
                
            df = self.prepare_micro_data(df)
            df = self.calculate_enhanced_indicators(df)
            
            pair_trades = 0
            
            for i in range(25, len(df)):  # 🔥 بداية من 25 للحصول على بيانات أكثر
                # 🔥 فحص إذن التداول أولاً
                if not self.check_trading_permission():
                    break
                
                # قرار الذكاء الاصطناعي المحسَن
                ai_decision = self.enhanced_ai_decision(df, i, symbol)
                signal = ai_decision["signal"]
                confidence = ai_decision["confidence"]
                
                price = float(df["close"].iloc[i])
                ts = df.index[i]
                
                if signal in ["BUY", "SELL"] and confidence >= self.config.get("confidence_threshold", 75):
                    position_size, stop_loss_pct, take_profit_pct = self.safe_money_management(confidence, symbol)
                    
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
                            "stop_loss": price * (1 - stop_loss_pct),
                            "take_profit": price * (1 + take_profit_pct),
                            "decision_data": ai_decision
                        }
                        self.balance -= position_size
                        
                        trade_record = {
                            "timestamp": ts, "symbol": symbol, "action": "BUY",
                            "price": price, "amount": position_size, "qty": qty,
                            "confidence": confidence, "status": "OPEN",
                            "balance_before": self.balance + position_size,
                            "balance_after": self.balance,
                            "decision_reason": ai_decision["reason"],
                            "stop_loss": price * (1 - stop_loss_pct),
                            "take_profit": price * (1 + take_profit_pct)
                        }
                        self.trade_history.append(trade_record)
                        pair_trades += 1
                        total_trades += 1
                        self.real_time_metrics['total_trades'] += 1
                        self.real_time_metrics['daily_trades'] += 1
                        
                    elif signal == "SELL" and symbol in self.positions:
                        # إغلاق صفقة شراء
                        pos = self.positions.pop(symbol)
                        
                        # 🔥 حساب الربح مع العمولة
                        profit = self.calculate_trade_result(
                            pos["entry_price"], price, pos["amount"], pos["qty"]
                        )
                        
                        # 🔥 تطبيق الربح التراكمي الفوري
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
                        self.real_time_metrics['daily_trades'] += 1
            
            # إغلاق المراكز المتبقية
            if symbol in self.positions:
                pos = self.positions.pop(symbol)
                price = float(df["close"].iloc[-1])
                profit = self.calculate_trade_result(
                    pos["entry_price"], price, pos["amount"], pos["qty"]
                )
                
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
        
        logger.info(f"🎯 انتهت المحاكاة المحسنة | الصفقات: {total_trades} | "
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
            "protection_metrics": self.protection_metrics,
            "learning_data_size": len(self.learning_data)
        }
