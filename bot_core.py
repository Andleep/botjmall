# bot_core.py
import pandas as pd
import numpy as np
import talib
from datetime import datetime
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class LorentzianStrategyBot:
    """
    Bot core — Lorentzian-like classifier + filters + immediate TP/SL + cumulative equity.
    Designed for simulation (historical klines) and live-readonly demo.
    """

    def __init__(self, config: Dict):
        self.config = config.copy()
        self.initial_balance = float(self.config.get("initial_balance", 10.0))
        self.balance = float(self.initial_balance)
        self.positions = {}  # symbol -> list of open positions
        self.trade_history = []
        self._last_entry_index = {}

    def prepare_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3.0
        return df

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # EMA50 and EMA200
        try:
            df["ema50"] = talib.EMA(df["close"].values, timeperiod=50)
        except:
            df["ema50"] = df["close"]
        try:
            df["ema200"] = talib.EMA(df["close"].values, timeperiod=200)
        except:
            df["ema200"] = df["close"]
        # ADX, ATR, RSI, CCI
        try:
            df["adx"] = talib.ADX(df["high"].values, df["low"].values, df["close"].values, timeperiod=14)
        except:
            df["adx"] = 0.0
        try:
            df["atr"] = talib.ATR(df["high"].values, df["low"].values, df["close"].values, timeperiod=14)
        except:
            df["atr"] = 0.0
        try:
            df["rsi"] = talib.RSI(df["close"].values, timeperiod=14)
        except:
            df["rsi"] = 50.0
        try:
            df["cci"] = talib.CCI(df["high"].values, df["low"].values, df["close"].values, timeperiod=20)
        except:
            df["cci"] = 0.0
        # WaveTrend approximation
        try:
            esa = talib.EMA(df["hlc3"].values, timeperiod=10)
            de = talib.EMA(np.abs(df["hlc3"].values - esa), timeperiod=10)
            ci = (df["hlc3"].values - esa) / (0.015 * de)
            wt1 = talib.EMA(ci, timeperiod=21)
            wt2 = talib.SMA(wt1, timeperiod=4)
            df["wt"] = wt1 - wt2
        except Exception:
            df["wt"] = 0.0
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        df["vwap"] = (tp * df["volume"]).cumsum() / (df["volume"].cumsum() + 1e-9)
        return df

    def lorentzian_score(self, row, hist_rows) -> float:
        # simplified lorentzian distance-based score
        features = ["rsi","wt","cci","adx","rsi"]
        vals = [row.get(f, 0.0) for f in features]
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
        median = np.median(dists) if len(dists) > 0 else 0.0
        return 1.0 / (1.0 + median)

    def decide_signal(self, df: pd.DataFrame, idx:int) -> Tuple[str, float]:
        row = df.iloc[idx]
        ts = pd.to_datetime(row.name) if row.name is not None else pd.Timestamp.utcnow()
        minute = ts.minute if hasattr(ts, "minute") else 0

        # optional time filter
        if self.config.get("use_time_filter", False):
            if minute in (0,1,58,59):
                return "HOLD", 0.0

        # need some history
        if idx < 20:
            return "HOLD", 0.0

        # Trend filter: use EMA50 for quicker trend recognition on 1m
        is_uptrend = row["close"] > row.get("ema50", row["close"])
        is_downtrend = row["close"] < row.get("ema50", row["close"])

        adx_ok = row.get("adx", 0) >= int(self.config.get("adx_threshold", 8))
        atr = row.get("atr", 0.0)
        if np.isnan(atr) or atr == 0:
            atr_ok = True
        else:
            atr_ok = (atr / row["close"]) > float(self.config.get("min_atr_ratio", 1e-5))

        # sample history for lorentzian score
        start = max(0, idx - int(self.config.get("max_bars_back", 500)))
        subset = df.iloc[start:idx]
        sample = subset.tail(200).to_dict("records") if len(subset) > 0 else []
        score = self.lorentzian_score(row.to_dict(), sample)

        # softened votes (to produce more signals)
        buy_votes = 0
        sell_votes = 0
        if row.get("rsi",50) < 45: buy_votes += 1
        if row.get("wt",0) < -4: buy_votes += 1
        if row.get("cci",0) < -80: buy_votes += 1
        if row.get("adx",0) > 8: buy_votes += 1

        if row.get("rsi",50) > 55: sell_votes += 1
        if row.get("wt",0) > 4: sell_votes += 1
        if row.get("cci",0) > 80: sell_votes += 1

        score_threshold = float(self.config.get("score_threshold", 0.0005))

        if is_uptrend and adx_ok and atr_ok and buy_votes >= 1 and score > score_threshold:
            return "BUY", score
        if is_downtrend and adx_ok and atr_ok and sell_votes >= 1 and score > score_threshold:
            return "SELL", score
        return "HOLD", score

    def _close_position(self, symbol: str, pos: Dict, close_price: float, close_time, reason="SELL"):
        profit = (close_price - pos["entry_price"]) * pos["qty"]
        # credit locked amount + profit immediately
        self.balance += pos["amount"] + profit
        rec = {
            "timestamp": close_time,
            "symbol": symbol,
            "action": reason,
            "price": close_price,
            "amount": pos["amount"],
            "qty": pos["qty"],
            "profit": profit,
            "status": "CLOSED"
        }
        self.trade_history.append(rec)
        return profit

    def run_backtest(self, klines: pd.DataFrame, symbol:str, timeframe:str, demo=True):
        df = klines.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df.set_index("timestamp", inplace=True)
        df = self.prepare_ohlcv(df)
        df = self.add_indicators(df)
        try:
            df["rsi2"] = talib.RSI(df["close"].values, timeperiod=9)
        except:
            df["rsi2"] = df.get("rsi", 0)

        # reset
        self.balance = float(self.initial_balance)
        self.positions = {}
        self.trade_history = []
        self._last_entry_index = {}

        stop_pct = float(self.config.get("stop_loss_pct", 0.015))
        tp_pct = float(self.config.get("take_profit_pct", 0.03))

        for i in range(len(df)):
            loops = 0
            max_loops_per_bar = 6
            while loops < max_loops_per_bar:
                loops += 1
                sig, conf = self.decide_signal(df, i)
                price = float(df["close"].iloc[i])
                high = float(df["high"].iloc[i])
                low = float(df["low"].iloc[i])
                ts = df.index[i]

                # 1) Check intra-bar TP/SL for existing positions
                current_positions = self.positions.get(symbol, [])
                closed_any = False
                for pos in list(current_positions):
                    entry_price = pos["entry_price"]
                    take_price = entry_price * (1 + tp_pct)
                    stop_price = entry_price * (1 - stop_pct)
                    if high >= take_price:
                        self._close_position(symbol, pos, take_price, ts, reason="TP")
                        current_positions.remove(pos)
                        closed_any = True
                        break
                    elif low <= stop_price:
                        self._close_position(symbol, pos, stop_price, ts, reason="SL")
                        current_positions.remove(pos)
                        closed_any = True
                        break
                if closed_any:
                    if current_positions:
                        self.positions[symbol] = current_positions
                    else:
                        self.positions.pop(symbol, None)
                    # after close, continue loop to allow immediate re-entry using updated balance
                    continue

                # recompute positions
                current_positions = self.positions.get(symbol, [])

                # re-entry control
                allow_reentry = True
                last_idx = self._last_entry_index.get(symbol, -99999)
                if i - last_idx < int(self.config.get("reentry_bars", 0)):
                    allow_reentry = False

                # 2) Manage openings/closings based on signal
                if sig == "BUY":
                    if (not current_positions) or self.config.get("allow_multiple_positions", True):
                        if (not allow_reentry) and current_positions:
                            pass
                        else:
                            risk = float(self.config.get("risk_per_trade", 0.05))
                            trade_amt = max(float(self.config.get("min_trade_amount", 0.01)), min(self.balance * risk, self.balance * 0.5))
                            if trade_amt <= 0 or trade_amt > self.balance:
                                pass
                            else:
                                qty = trade_amt / price
                                pos = {"entry_time": ts, "entry_price": price, "amount": trade_amt, "qty": qty, "status": "OPEN", "entry_index": i}
                                self.positions.setdefault(symbol, []).append(pos)
                                self.balance -= trade_amt
                                self.trade_history.append({"timestamp": ts, "symbol": symbol, "action": "BUY", "price": price, "amount": trade_amt, "qty": qty, "status": "OPEN"})
                                self._last_entry_index[symbol] = i
                                # after opening, allow immediate TP/SL check in same bar
                                continue

                elif sig == "SELL":
                    if current_positions:
                        pos = current_positions.pop(0)
                        profit = (price - pos["entry_price"]) * pos["qty"]
                        self.balance += pos["amount"] + profit
                        rec = {"timestamp": ts, "symbol": symbol, "action": "SELL", "price": price, "amount": pos["amount"], "qty": pos["qty"], "profit": profit, "status": "CLOSED"}
                        self.trade_history.append(rec)
                        if current_positions:
                            self.positions[symbol] = current_positions
                        else:
                            self.positions.pop(symbol, None)
                        # allow immediate re-entry after close
                        continue

                break  # break loop for this bar (no more immediate changes)

        # final bar: ensure closing any remaining opens at last price
        if self.positions:
            last_price = float(df["close"].iloc[-1])
            last_ts = df.index[-1]
            for sym, pos_list in list(self.positions.items()):
                while pos_list:
                    pos = pos_list.pop(0)
                    profit = (last_price - pos["entry_price"]) * pos["qty"]
                    self.balance += pos["amount"] + profit
                    rec = {"timestamp": last_ts, "symbol": sym, "action": "SELL", "price": last_price, "amount": pos["amount"], "qty": pos["qty"], "profit": profit, "status": "CLOSED"}
                    self.trade_history.append(rec)
                self.positions.pop(sym, None)

        return {"final_balance": self.balance, "trade_history": self.trade_history, "initial_balance": self.initial_balance}
