import pandas as pd
import numpy as np
import talib
from datetime import datetime
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LorentzianTradingBot:
    def __init__(self, config: Dict, binance_client=None):
        self.config = config
        self.client = binance_client
        self.balance = config.get('initial_balance', 1000.0)
        self.initial_balance = self.balance
        self.positions = {}
        self.trade_history = []
        self.cumulative_profit = 0.0
        self.win_count = 0
        self.loss_count = 0

    def calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        try:
            df['rsi'] = talib.RSI(df['close'].astype('float'), timeperiod=14)
            df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
            df['wt'] = self.calculate_wave_trend(df['hlc3'])
            df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=20)
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
            df['rsi2'] = talib.RSI(df['close'].astype('float'), timeperiod=9)
        except Exception as e:
            logger.warning("TA-Lib calculation issue: %s", e)
        return df

    def calculate_wave_trend(self, hlc3):
        try:
            esa = talib.EMA(hlc3, timeperiod=10)
            de = talib.EMA(abs(hlc3 - esa), timeperiod=10)
            ci = (hlc3 - esa) / (0.015 * de)
            wt1 = talib.EMA(ci, timeperiod=21)
            wt2 = talib.SMA(wt1, timeperiod=4)
            return wt1 - wt2
        except Exception:
            return hlc3 * 0

    def lorentzian_classification(self, df: pd.DataFrame) -> Dict:
        # simplified classifier: use a vote of indicators
        if df is None or len(df) < 30:
            return {'signal': 'HOLD', 'confidence': 0.0}
        cur = df.iloc[-1]
        score = 0
        if cur.get('rsi', 50) < 30:
            score += 1
        if cur.get('wt', 0) < -10:
            score += 1
        if cur.get('cci', 0) < -100:
            score += 1
        if cur.get('adx', 0) > 25:
            score += 1
        if cur.get('rsi2', 50) < 35:
            score += 1
        if score >= 3:
            return {'signal': 'BUY', 'confidence': score/5}
        # symmetrical sell
        score_s = 0
        if cur.get('rsi', 50) > 70:
            score_s += 1
        if cur.get('wt', 0) > 10:
            score_s += 1
        if cur.get('cci', 0) > 100:
            score_s += 1
        if score_s >= 3:
            return {'signal': 'SELL', 'confidence': score_s/5}
        return {'signal': 'HOLD', 'confidence': 0.0}

    def advanced_risk_management(self, signal: str, current_price: float) -> Tuple[float, Dict]:
        risk_amount = self.balance * self.config.get('risk_per_trade', 0.02)
        trade_amount = max(self.config.get('min_trade_amount', 1.0), min(risk_amount, self.balance * 0.1))
        quantity = trade_amount / current_price if current_price>0 else 0
        risk_info = {
            'risk_amount': risk_amount,
            'trade_amount': trade_amount,
            'quantity': quantity,
            'stop_loss': current_price * (1 - self.config.get('stop_loss_pct', 0.02)),
            'take_profit': current_price * (1 + self.config.get('take_profit_pct', 0.04))
        }
        return trade_amount, risk_info

    def execute_trade(self, symbol: str, signal: str, amount: float, price: float, risk_info: Dict, demo_mode: bool = True):
        t = datetime.utcnow()
        trade = {
            'timestamp': t,
            'symbol': symbol,
            'action': signal,
            'amount': amount,
            'price': price,
            'profit': 0.0,
            'status': 'OPEN' if signal=='BUY' else 'CLOSED'
        }
        if signal == 'BUY':
            if demo_mode:
                self.balance -= amount
            self.positions[symbol] = trade
        elif signal == 'SELL' and symbol in self.positions:
            entry = self.positions.pop(symbol)
            profit = (price - entry['price']) * (entry['amount']/entry['price'])
            if demo_mode:
                self.balance += entry['amount'] + profit
            trade['profit'] = profit
            trade['status'] = 'CLOSED'
            self.cumulative_profit += profit
            if profit>0:
                self.win_count += 1
            else:
                self.loss_count += 1
        self.trade_history.append(trade)
        return trade

    def get_performance_metrics(self):
        closed = [t for t in self.trade_history if t.get('status')=='CLOSED']
        if not closed:
            return {}
        profits = [t.get('profit',0) for t in closed]
        total = sum(profits)
        win = sum(1 for p in profits if p>0)
        loss = sum(1 for p in profits if p<=0)
        return {
            'total_trades': len(closed),
            'winning_trades': win,
            'losing_trades': loss,
            'total_profit': total,
            'cumulative_profit': self.cumulative_profit,
            'current_balance': self.balance
        }

    def run_bot_cycle_with_df(self, symbol: str, df: pd.DataFrame, demo_mode=True):
        df = self.calculate_features(df)
        cls = self.lorentzian_classification(df)
        signal = cls['signal']
        price = float(df['close'].iloc[-1])
        trade_amount, risk_info = self.advanced_risk_management(signal, price)
        result = {'signal': signal, 'confidence': cls.get('confidence',0)}
        if signal in ['BUY','SELL'] and trade_amount>0:
            trade = self.execute_trade(symbol, signal, trade_amount, price, risk_info, demo_mode)
            result['trade'] = trade
        result['metrics'] = self.get_performance_metrics()
        return result
