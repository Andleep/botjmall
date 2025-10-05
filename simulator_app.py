import streamlit as st
import pandas as pd, numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from bot_core import LorentzianStrategyBot
from binance.client import Client
from config import BINANCE_CONFIG, LORENTZIAN_CONFIG
import time

st.set_page_config(page_title="Lorentzian Bot Simulator", layout="wide")
st.title("Lorentzian Trading Bot — Simulator (Historical Binance klines)")

# Sidebar controls
st.sidebar.header("Simulation Settings")
symbol = st.sidebar.selectbox("Symbol", ["BTCUSDT","ETHUSDT","BNBUSDT","ADAUSDT","XRPUSDT"])
timeframe = st.sidebar.selectbox("Timeframe", ["1m","5m","15m","1h"])
days = st.sidebar.slider("Days to simulate", 1, 90, 7)
start_balance = st.sidebar.number_input("Start balance $", value=10.0, min_value=1.0, step=1.0)
max_bars = st.sidebar.number_input("Max bars back (history sample size)", value=500, min_value=100, step=50)
st.sidebar.markdown("**Data Source:** Binance public klines (read-only for simulation).")

# instantiate bot
cfg = LORENTZIAN_CONFIG.copy()
cfg["initial_balance"] = float(start_balance)
cfg["max_bars_back"] = int(max_bars)
bot = LorentzianStrategyBot(cfg)

# fetch klines
@st.cache_data(ttl=600)
def fetch_klines(symbol, interval, days, limit_per_call=1000):
    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    klines = client.get_historical_klines(symbol, interval, start_str=str(start), end_str=str(end), limit=1000)
    if not klines:
        return pd.DataFrame()
    df = pd.DataFrame(klines, columns=['timestamp','open','high','low','close','volume','close_time','qav','num_trades','taker_base_vol','taker_quote_vol','ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df[['timestamp','open','high','low','close','volume']]

if st.button("Fetch & Run Simulation"):
    with st.spinner("Fetching klines from Binance..."):
        df = fetch_klines(symbol, timeframe, days)
        if df.empty:
            st.error("No klines returned. Check symbol/timeframe or Binance limits.")
        else:
            st.success(f"Fetched {len(df)} bars. Running backtest...")
            result = bot.run_backtest(df, symbol, timeframe, demo=True)
            st.success("Backtest completed!")
            st.metric("Initial Balance $", result.get("initial_balance", start_balance))
            st.metric("Final Balance $", result.get("final_balance", 0.0))
            trades = pd.DataFrame(result.get("trade_history", []))
            if not trades.empty:
                trades['timestamp'] = pd.to_datetime(trades['timestamp'])
                st.subheader("Trades")
                st.dataframe(trades)
                # plot candlesticks with entry/exit markers
                fig = go.Figure(data=[go.Candlestick(x=df['timestamp'],
                             open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
                buys = trades[trades['action']=="BUY"]
                sells = trades[trades['action']=="SELL"]
                if not buys.empty:
                    buy_y = []
                    for t in buys['timestamp']:
                        row = df[df['timestamp']==t]
                        buy_y.append(float(row['low'].values[0]) if len(row)>0 else None)
                    fig.add_trace(go.Scatter(x=buys['timestamp'], y=buy_y, mode='markers', marker=dict(symbol='triangle-up', size=10, color='green'), name='BUY'))
                if not sells.empty:
                    sell_y = []
                    for t in sells['timestamp']:
                        row = df[df['timestamp']==t]
                        sell_y.append(float(row['high'].values[0]) if len(row)>0 else None)
                    fig.add_trace(go.Scatter(x=sells['timestamp'], y=sell_y, mode='markers', marker=dict(symbol='triangle-down', size=10, color='red'), name='SELL'))
                fig.update_layout(height=600, title=f"{symbol} {timeframe} — Simulation", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No trades executed during the simulation period.")
