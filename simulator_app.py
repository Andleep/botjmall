import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from bot_core import LorentzianStrategyBot
from binance.client import Client
from config import BINANCE_CONFIG, LORENTZIAN_CONFIG
import threading, time, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Lorentzian Bot Simulator", layout="wide")
st.title("Lorentzian Trading Bot — Simulator (Historical Binance klines & Live Demo)")

# ---------------------------
# Sidebar - Controls
# ---------------------------
st.sidebar.header("Simulation / Live Settings")

# Symbol input: either free text or load list from Binance
use_load_symbols = st.sidebar.checkbox("Load symbols from Binance (may be slow)", value=False)
symbol = "BTCUSDT"
if use_load_symbols:
    try:
        client_tmp = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
        infos = client_tmp.get_exchange_info()
        symbols = [s['symbol'] for s in infos['symbols'] if s['status']=='TRADING']
        symbol = st.sidebar.selectbox("Symbol", symbols, index=symbols.index("BTCUSDT") if "BTCUSDT" in symbols else 0)
    except Exception as e:
        st.sidebar.warning("Could not load symbols from Binance. Using manual input. " + str(e))
        symbol = st.sidebar.text_input("Symbol (e.g. BTCUSDT)", value="BTCUSDT")
else:
    symbol = st.sidebar.text_input("Symbol (e.g. BTCUSDT)", value="BTCUSDT")

timeframe = st.sidebar.selectbox("Timeframe", ["1m","5m","15m","1h"], index=0)
days = st.sidebar.slider("Days to simulate (historical)", 1, 90, 7)
start_balance = st.sidebar.number_input("Start balance $", value=10.0, min_value=0.01, step=1.0)

# Strategy / filter params (overrides config)
st.sidebar.markdown("### Strategy Params (override)")
risk_per_trade = st.sidebar.number_input("Risk per trade (%)", value=LORENTZIAN_CONFIG.get("risk_per_trade",0.02)*100, min_value=0.1, max_value=50.0)/100.0
min_trade_amount = st.sidebar.number_input("Min trade amount $", value=LORENTZIAN_CONFIG.get("min_trade_amount",0.1), min_value=0.0001, step=0.1)
adx_threshold = st.sidebar.number_input("ADX threshold", value=LORENTZIAN_CONFIG.get("adx_threshold", 12), min_value=0, max_value=100, step=1)
min_atr_ratio = st.sidebar.number_input("Min ATR ratio (ATR/price)", value=LORENTZIAN_CONFIG.get("min_atr_ratio",1e-4), format="%.6f")
use_time_filter = st.sidebar.checkbox("Use time filter (avoid edges of hour)", value=LORENTZIAN_CONFIG.get("use_time_filter", False))
allow_multi = st.sidebar.checkbox("Allow multiple positions per symbol", value=LORENTZIAN_CONFIG.get("allow_multiple_positions", True))
reentry_bars = st.sidebar.number_input("Re-entry bars after entry", value=LORENTZIAN_CONFIG.get("reentry_bars", 5), min_value=0, step=1)
max_bars_back = st.sidebar.number_input("Max bars back (history sample size)", value=LORENTZIAN_CONFIG.get("max_bars_back", 500), min_value=50, step=50)

# Pack config and instantiate bot
cfg = LORENTZIAN_CONFIG.copy()
cfg.update({
    "initial_balance": float(start_balance),
    "risk_per_trade": float(risk_per_trade),
    "min_trade_amount": float(min_trade_amount),
    "adx_threshold": int(adx_threshold),
    "min_atr_ratio": float(min_atr_ratio),
    "use_time_filter": bool(use_time_filter),
    "allow_multiple_positions": bool(allow_multi),
    "reentry_bars": int(reentry_bars),
    "max_bars_back": int(max_bars_back)
})
bot = LorentzianStrategyBot(cfg)

# ---------------------------
# Helpers: fetch klines
# ---------------------------
@st.cache_data(ttl=600)
def fetch_klines(symbol, interval, days, limit_per_call=1000):
    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    try:
        klines = client.get_historical_klines(symbol, interval, start_str=str(start), end_str=str(end), limit=1000)
    except Exception as e:
        logger.error("Error fetching klines: %s", e)
        return pd.DataFrame()
    if not klines:
        return pd.DataFrame()
    df = pd.DataFrame(klines, columns=['timestamp','open','high','low','close','volume','close_time','qav','num_trades','taker_base_vol','taker_quote_vol','ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df[['timestamp','open','high','low','close','volume']]

# ---------------------------
# Run historical simulation
# ---------------------------
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
                    fig.add_trace(go.Scatter(x=buys['timestamp'], y=buy_y, mode='markers', marker=dict(symbol='triangle-up', size=12, color='green'), name='BUY'))
                if not sells.empty:
                    sell_y = []
                    for t in sells['timestamp']:
                        row = df[df['timestamp']==t]
                        sell_y.append(float(row['high'].values[0]) if len(row)>0 else None)
                    fig.add_trace(go.Scatter(x=sells['timestamp'], y=sell_y, mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='SELL'))

                # improved layout with zoom/pan and rangeslider
                fig.update_layout(
                    height=650,
                    title=f"{symbol} {timeframe} — Simulation",
                    xaxis_rangeslider_visible=True,
                    xaxis=dict(rangeselector=dict(
                        buttons=list([
                            dict(count=1, label='1d', step='day', stepmode='backward'),
                            dict(count=7, label='7d', step='day', stepmode='backward'),
                            dict(count=1, label='1m', step='month', stepmode='backward'),
                            dict(step='all')
                        ])
                    ), rangeslider=dict(visible=True)),
                    dragmode='pan'
                )
                plotly_config = {"displayModeBar": True, "scrollZoom": True, "modeBarButtonsToAdd": ["zoom2d","pan2d","autoScale2d","resetScale2d"]}
                st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            else:
                st.info("No trades executed during the simulation period.")

# ---------------------------
# Live Demo (read-only) - polling
# ---------------------------
st.sidebar.markdown("---")
st.sidebar.header("Live Demo (Read-only)")

live_interval = st.sidebar.number_input("Live poll interval (seconds)", value=60, min_value=5, step=5)

if 'live_running' not in st.session_state:
    st.session_state['live_running'] = False
    st.session_state['last_live_result'] = None

def live_loop(symbol, timeframe, bot, interval):
    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    while st.session_state.get("live_running", False):
        try:
            klines = client.get_klines(symbol=symbol, interval=timeframe, limit=1000)
            if not klines:
                logger.warning("No klines in live poll.")
                time.sleep(interval)
                continue
            df = pd.DataFrame(klines, columns=['timestamp','open','high','low','close','volume','ct','q','n','tbv','tqv','i'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df_res = df[['timestamp','open','high','low','close','volume']]
            res = bot.run_backtest(df_res, symbol, timeframe, demo=True)
            st.session_state['last_live_result'] = res
            logger.info("Live demo tick: final_balance=%s trades=%d", res.get("final_balance"), len(res.get("trade_history", [])))
        except Exception as e:
            logger.error("Live loop error: %s", e)
        time.sleep(interval)

col1, col2 = st.columns(2)
with col1:
    if st.button("Start Live Demo"):
        if not st.session_state['live_running']:
            st.session_state['live_running'] = True
            t = threading.Thread(target=live_loop, args=(symbol, timeframe, bot, int(live_interval)), daemon=True)
            t.start()
            st.success("Live demo started (read-only).")
with col2:
    if st.button("Stop Live Demo"):
        st.session_state['live_running'] = False
        st.success("Live demo stopped.")

if st.session_state.get('last_live_result'):
    lr = st.session_state['last_live_result']
    st.metric("Live Demo - Initial Balance $", lr.get("initial_balance", start_balance))
    st.metric("Live Demo - Current/Final Balance $", lr.get("final_balance", 0.0))
    trades = pd.DataFrame(lr.get("trade_history", []))
    if not trades.empty:
        trades['timestamp'] = pd.to_datetime(trades['timestamp'])
        st.subheader("Live Demo - Recent Trades")
        st.dataframe(trades.tail(50))
