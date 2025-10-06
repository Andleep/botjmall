# bot_core.py  (AdvancedLorentzianBot with optimizer)
import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, List
from math import sqrt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AdvancedLorentzianBot:
    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.reset_state()

    def reset_state(self):
        self.balance = float(self.initial_balance)
        self.positions = {}      # symbol -> list of pos
        self.trade_history = []
        self.equity_curve = []

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in ['open','high','low','close','volume']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df['hlc3'] = (df['high']+df['low']+df['close'])/3.0
        # indicators
        try:
            df['ema50'] = talib.EMA(df['close'].values, timeperiod=50)
        except:
            df['ema50'] = df['close']
        try:
            macd, macdsig, macdhist = talib.MACD(df['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
            df['macdh'] = macdhist
        except:
            df['macdh'] = 0.0
        try:
            df['adx'] = talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
        except:
            df['adx'] = 0.0
        try:
            df['atr'] = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
        except:
            df['atr'] = 0.0
        try:
            df['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
        except:
            df['rsi'] = 50.0
        try:
            df['cci'] = talib.CCI(df['high'].values, df['low'].values, df['close'].values, timeperiod=20)
        except:
            df['cci'] = 0.0
        # wave trend approx
        try:
            esa = talib.EMA(df['hlc3'].values, timeperiod=10)
            de = talib.EMA(np.abs(df['hlc3'].values - esa), timeperiod=10)
            ci = (df['hlc3'].values - esa) / (0.015 * de)
            wt1 = talib.EMA(ci, timeperiod=21)
            wt2 = talib.SMA(wt1, timeperiod=4)
            df['wt'] = wt1 - wt2
        except:
            df['wt'] = 0.0
        return df

    def lorentzian_score(self, features_cur: List[float], hist_feats: List[List[float]]) -> float:
        if len(hist_feats) == 0:
            return 0.0
        d = np.array([np.sum(np.log1p(np.abs(np.array(features_cur) - np.array(h)))) for h in hist_feats])
        median = np.median(d)
        return 1.0/(1.0+median)

    def kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 0.0
        R = avg_win / abs(avg_loss) if avg_loss != 0 else 0
        k = win_rate - (1-win_rate)/R if R>0 else 0.0
        return max(0.0, min(k, 0.5))

    def compute_position_size(self, balance: float, risk_per_trade: float, kelly_frac: float, price: float, min_amount: float):
        alpha = float(self.config.get('kelly_weight', 0.6))
        frac = risk_per_trade*(1-alpha) + kelly_frac*alpha
        trade_amt = max(min_amount, min(balance * frac, balance*0.5))
        qty = trade_amt / price if price>0 else 0.0
        return trade_amt, qty

    def simulate(self, klines: pd.DataFrame, symbol: str, params: Dict) -> Dict:
        df = self.prepare(klines)
        n = len(df)
        self.reset_state()
        score_th = params.get('score_th', 0.0005)
        adx_th = params.get('adx_th', 8)
        tp_pct = params.get('tp_pct', 0.03)
        sl_pct = params.get('sl_pct', 0.015)
        risk_per_trade = params.get('risk_per_trade', 0.05)
        commission = params.get('commission', 0.0008)
        slippage = params.get('slippage', 0.0005)
        lookback = params.get('lookback', 500)
        min_amount = params.get('min_amount', 0.01)

        wins = []
        losses = []

        for i in range(n):
            row = df.iloc[i]
            price = float(row['close'])
            # check TP/SL intra-bar
            cur_pos = self.positions.get(symbol, [])
            closed_this_bar = False
            for pos in list(cur_pos):
                entry = pos['entry_price']
                tp_price = entry*(1+tp_pct)
                sl_price = entry*(1-sl_pct)
                if row['high'] >= tp_price:
                    fill = tp_price*(1 - slippage)
                    profit = (fill - entry)*pos['qty'] - pos['amount']*commission
                    self.balance += pos['amount'] + profit
                    self.trade_history.append({'timestamp': df.index[i], 'action':'TP','price':fill,'profit':profit,'amount':pos['amount']})
                    cur_pos.remove(pos)
                    wins.append(profit)
                    closed_this_bar = True
                    break
                elif row['low'] <= sl_price:
                    fill = sl_price*(1 + slippage)
                    profit = (fill - entry)*pos['qty'] - pos['amount']*commission
                    self.balance += pos['amount'] + profit
                    self.trade_history.append({'timestamp': df.index[i], 'action':'SL','price':fill,'profit':profit,'amount':pos['amount']})
                    cur_pos.remove(pos)
                    losses.append(profit)
                    closed_this_bar = True
                    break
            if closed_this_bar:
                if cur_pos:
                    self.positions[symbol] = cur_pos
                else:
                    self.positions.pop(symbol, None)
            if i < 5:
                # warmup
                self.equity_curve.append(self.balance)
                continue

            start = max(0, i - lookback)
            subset = df.iloc[start:i]
            hist_feats = []
            for _, r in subset.iterrows():
                hist_feats.append([r.get('rsi',50.0), r.get('wt',0.0), r.get('cci',0.0), r.get('adx',0.0), r.get('macdh',0.0)])
            cur_feats = [row.get('rsi',50.0), row.get('wt',0.0), row.get('cci',0.0), row.get('adx',0.0), row.get('macdh',0.0)]
            score = self.lorentzian_score(cur_feats, hist_feats)

            is_up = row['close'] > row.get('ema50', row['close']) and row.get('macdh',0.0) > 0 and row.get('adx',0.0) > adx_th
            # compute kelly
            avg_win = np.mean(wins) if len(wins)>0 else 0.0
            avg_loss = np.mean(losses) if len(losses)>0 else 0.0
            win_rate = (np.sum(np.array(wins)>0)/len(wins)) if len(wins)>0 else 0.5
            kelly = self.kelly_fraction(win_rate, avg_win, avg_loss) if len(wins)+len(losses)>5 else 0.0

            if score > score_th and is_up:
                trade_amt, qty = self.compute_position_size(self.balance, risk_per_trade, kelly, price, min_amount)
                if trade_amt <= 0 or trade_amt > self.balance:
                    self.equity_curve.append(self.balance)
                    continue
                self.balance -= trade_amt
                pos = {'entry_time': df.index[i], 'entry_price': price*(1+slippage), 'qty': qty, 'amount': trade_amt}
                self.positions.setdefault(symbol, []).append(pos)
                self.trade_history.append({'timestamp': df.index[i], 'action':'BUY','price':pos['entry_price'],'amount':trade_amt})
            # snapshot equity
            unreal = sum([(row['close'] - p['entry_price'])*p['qty'] + p['amount'] for p in self.positions.get(symbol,[])])
            self.equity_curve.append(self.balance + unreal)

        # final close
        if self.positions.get(symbol):
            last_price = float(df['close'].iloc[-1])
            for pos in list(self.positions[symbol]):
                fill = last_price*(1 - slippage)
                profit = (fill - pos['entry_price'])*pos['qty'] - pos['amount']*commission
                self.balance += pos['amount'] + profit
                self.trade_history.append({'timestamp': df.index[-1], 'action':'CLOSE','price':fill,'profit':profit,'amount':pos['amount']})
            self.positions.pop(symbol, None)

        closed = [t for t in self.trade_history if t['action'] in ('TP','SL','CLOSE')]
        profits = [t.get('profit',0) for t in closed]
        total_trades = len(closed)
        win_trades = sum(1 for p in profits if p>0)
        lose_trades = sum(1 for p in profits if p<0)
        win_rate = win_trades/total_trades if total_trades>0 else 0
        total_profit = sum(profits)
        final_balance = self.balance
        eq = np.array(self.equity_curve) if len(self.equity_curve)>0 else np.array([self.initial_balance])
        peak = -np.inf
        max_dd = 0.0
        for v in eq:
            if v>peak: peak=v
            dd = (peak - v)/peak if peak>0 else 0
            if dd>max_dd: max_dd=dd
        sharpe = 0.0
        if len(profits)>1:
            sharpe = (np.mean(profits)/ (np.std(profits)+1e-9)) * sqrt(252)
        return {
            'final_balance': final_balance,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'max_drawdown': max_dd,
            'sharpe': sharpe,
            'trade_history': self.trade_history,
            'equity_curve': self.equity_curve
        }

    def optimize_params(self, klines: pd.DataFrame, symbol: str, n_iter:int=50):
        best = None
        for _ in range(n_iter):
            params = {
                'score_th': 10**np.random.uniform(-5, -2),
                'adx_th': int(np.random.choice([6,8,10,12,15])),
                'tp_pct': float(np.random.choice([0.02,0.03,0.04,0.05])),
                'sl_pct': float(np.random.choice([0.01,0.015,0.02,0.025])),
                'risk_per_trade': float(np.random.choice([0.02,0.03,0.05,0.08])),
                'commission': 0.0008,
                'slippage': 0.0005,
                'lookback': int(np.random.choice([200,400,800])),
                'min_amount': self.config.get('min_trade_amount',0.01)
            }
            perf = self.simulate(klines, symbol, params)
            score = perf['final_balance']
            if best is None or score > best['score']:
                best = {'score': score, 'params': params, 'perf': perf}
        return best
