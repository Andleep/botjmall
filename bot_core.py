import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class LorentzianStrategyBot:
    """
    Core bot implementing a Lorentzian-style classifier + filters.
    Designed for simulation/backtesting on historical klines (Binance format).
    """

    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}  # symbol -> position dict
        self.trade_history = []

    def prepare_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        # ensure numeric types and hlc3
        df = df.copy()
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3.0
        return df

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # EMA200
        df["ema200"] = talib.EMA(df["close"].values, timeperiod=200)
        # ADX
        df["adx"] = talib.ADX(df["high"].values, df["low"].values, df["close"].values, timeperiod=14)
        # ATR
        df["atr"] = talib.ATR(df["high"].values, df["low"].values, df["close"].values, timeperiod=14)
        # RSI
        df["rsi"] = talib.RSI(df["close"].values, timeperiod=14)
        # CCI
        df["cci"] = talib.CCI(df["high"].values, df["low"].values, df["close"].values, timeperiod=20)
        # simple WaveTrend approximation using EMA on hlc3
        try:
            esa = talib.EMA(df["hlc3"].values, timeperiod=10)
            de = talib.EMA(np.abs(df["hlc3"].values - esa), timeperiod=10)
            ci = (df["hlc3"].values - esa) / (0.015 * de)
            wt1 = talib.EMA(ci, timeperiod=21)
            wt2 = talib.SMA(wt1, timeperiod=4)
            df["wt"] = wt1 - wt2
        except Exception:
            df["wt"] = 0.0
        # VWAP (rolling typical price * vol / cumvol)
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        df["vwap"] = (tp * df["volume"]).cumsum() / (df["volume"].cumsum() + 1e-9)
        return df

    def lorentzian_score(self, row, hist_rows) -> float:
        # simplified distance-based score comparing current features to a sample of historical rows
        features = ["rsi","wt","cci","adx","rsi"]
        vals = []
        for f in features:
            vals.append(row.get(f, 0.0))
        # sample some historical rows evenly
        if len(hist_rows) == 0:
            return 0.0
        dists = []
        for r in hist_rows:
            dist = 0.0
            for i, f in enumerate(features):
                a = vals[i] if not np.isnan(vals[i]) else 0.0
                b = r.get(f, 0.0) if not np.isnan(r.get(f,0.0)) else 0.0
                dist += np.log(1 + abs(a - b))
            dists.append(dist)
        # lower distance -> more similar; compute pseudo-prediction as sign of future (use median)
        median = np.median(dists) if len(dists)>0 else 0.0
        # return inverse of median (normalized)
        return 1.0 / (1.0 + median)

    def decide_signal(self, df: pd.DataFrame, idx:int) -> Tuple[str, float]:
        """
        Decide BUY/SELL/HOLD at index idx using indicators + lorentzian scoring and filters.
        """
        row = df.iloc[idx]
        # filters
        # time filter: avoid first/last 2 minutes of hour
        ts = pd.to_datetime(row.name)
        minute = ts.minute
        if (minute % 60) in (0,1,58,59):
            return "HOLD", 0.0
        # require enough history
        if idx < 50:
            return "HOLD", 0.0

        is_uptrend = row["close"] > row.get("ema200", row["close"])
        is_downtrend = row["close"] < row.get("ema200", row["close"])
        adx_ok = row.get("adx",0) >= self.config.get("adx_threshold", 20)
        atr = row.get("atr", 0.0)
        if np.isnan(atr) or atr==0:
            atr_ok = True
        else:
            atr_ok = (atr / row["close"]) > self.config.get("min_atr_ratio", 0.0005)

        # lorentzian pseudo-score using last N historical sample points
        hist_sample = []
        step = max(1, int(len(df)/min(len(df), self.config.get("max_bars_back", 500))))
        # collect last 200 prior rows evenly spaced
        start = max(0, idx - self.config.get("max_bars_back", 500))
        subset = df.iloc[start:idx]
        if len(subset) > 0:
            sample = subset.tail(200).to_dict("records") if len(subset)>200 else subset.to_dict("records")
        else:
            sample = []
        score = self.lorentzian_score(row.to_dict(), sample)

        # simple voting rules using indicators
        buy_votes = 0
        sell_votes = 0
        if row.get("rsi",50) < 35: buy_votes += 1
        if row.get("wt",0) < -8: buy_votes += 1
        if row.get("cci",0) < -100: buy_votes += 1
        if row.get("adx",0) > 25: buy_votes += 1
        if row.get("rsi",50) > 65: sell_votes += 1
        if row.get("wt",0) > 8: sell_votes += 1
        if row.get("cci",0) > 100: sell_votes += 1

        # apply trend filter
        if is_uptrend and adx_ok and atr_ok and buy_votes >= 2 and score > 0.01:
            return "BUY", score
        if is_downtrend and adx_ok and atr_ok and sell_votes >= 2 and score > 0.01:
            return "SELL", score
        return "HOLD", score

    def run_backtest(self, klines: pd.DataFrame, symbol:str, timeframe:str, demo=True):
        """
        Run simulation over klines DataFrame (must have datetime index or column 'timestamp')
        """
        df = klines.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", origin="unix", utc=True)
            df.set_index("timestamp", inplace=True)
        df = self.prepare_ohlcv(df)
        df = self.add_indicators(df)
        # add rsi2 used earlier
        try:
            df["rsi2"] = talib.RSI(df["close"].values, timeperiod=9)
        except Exception:
            df["rsi2"] = df.get("rsi",0)
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []

        for i in range(len(df)):
            sig, conf = self.decide_signal(df, i)
            price = float(df["close"].iloc[i])
            ts = df.index[i]
            # Manage positions: simple long-only for demo (open on BUY, close on SELL)
            if sig == "BUY":
                # open if no position
                if symbol not in self.positions:
                    # compute trade size using risk per trade (percentage of balance)
                    risk = float(self.config.get("risk_per_trade", 0.02))
                    trade_amt = max(self.config.get("min_trade_amount", 0.5), min(self.balance * risk, self.balance * 0.1))
                    qty = trade_amt / price
                    pos = {"entry_time":ts, "entry_price":price, "amount":trade_amt, "qty":qty, "status":"OPEN"}
                    self.positions[symbol] = pos
                    # deduct balance (simulate locked capital)
                    self.balance -= trade_amt
                    self.trade_history.append({"timestamp":ts, "symbol":symbol, "action":"BUY", "price":price, "amount":trade_amt, "qty":qty, "status":"OPEN"})
            elif sig == "SELL":
                if symbol in self.positions:
                    pos = self.positions.pop(symbol)
                    profit = (price - pos["entry_price"]) * pos["qty"]
                    self.balance += pos["amount"] + profit
                    rec = {"timestamp":ts, "symbol":symbol, "action":"SELL", "price":price, "amount":pos["amount"], "qty":pos["qty"], "profit":profit, "status":"CLOSED"}
                    self.trade_history.append(rec)
            # allow manual close on last bar
            if i == len(df)-1 and symbol in self.positions:
                pos = self.positions.pop(symbol)
                price = float(df["close"].iloc[i])
                profit = (price - pos["entry_price"]) * pos["qty"]
                self.balance += pos["amount"] + profit
                rec = {"timestamp":df.index[i], "symbol":symbol, "action":"SELL", "price":price, "amount":pos["amount"], "qty":pos["qty"], "profit":profit, "status":"CLOSED"}
                self.trade_history.append(rec)
        return {"final_balance":self.balance, "trade_history":self.trade_history, "initial_balance":self.initial_balance}
