# simulator_app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from bot_core import AdvancedLorentzianBot
from binance.client import Client
from config import BINANCE_CONFIG, LORENTZIAN_CONFIG
import threading, time, logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Lorentzian Bot Simulator (Advanced)", layout="wide")
st.title("Lorentzian Trading Bot — Advanced Simulator")

# Sidebar
st.sidebar.header("Settings")
symbol = st.sidebar.text_input("Symbol (e.g. BTCUSDT)", value="BTCUSDT")
timeframe = st.sidebar.selectbox("Timeframe", ["1m","5m","15m","1h"], index=0)
days = st.sidebar.slider("Days to simulate", 1, 90, 7)
start_balance = st.sidebar.number_input("Start balance $", value=LORENTZIAN_CONFIG.get("initial_balance",10.0), min_value=0.01)

# optimizer options
st.sidebar.markdown("### Optimizer")
run_opt = st.sidebar.button("Run optimizer (50 iter)")
n_iter = st.sidebar.number_input("Optimizer iterations", value=50, min_value=10, step=10)

# instantiate bot
cfg = LORENTZIAN_CONFIG.copy()
cfg["initial_balance"] = float(start_balance)
bot = AdvancedLorentzianBot(cfg)

@st.cache_data(ttl=600)
def fetch_klines(symbol, interval, days):
    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    try:
        klines = client.get_historical_klines(symbol, interval, start_str=str(start), end_str=str(end), limit=1000)
    except Exception as e:
        logger.error("fetch error: %s", e)
        return pd.DataFrame()
    if not klines:
        return pd.DataFrame()
    df = pd.DataFrame(klines, columns=['timestamp','open','high','low','close','volume','close_time','qav','num_trades','tbv','tqv','ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df[['timestamp','open','high','low','close','volume']]

# Run simulation
if st.button("Fetch & Run Simulation"):
    with st.spinner("Fetching..."):
        df = fetch_klines(symbol, timeframe, days)
        if df.empty:
            st.error("No data returned.")
        else:
            st.success(f"Fetched {len(df)} bars. Running simulation...")
            # default params (can later be replaced by optimizer results)
            params = {
                'score_th': cfg.get('score_threshold', 0.0005),
                'adx_th': cfg.get('adx_threshold', 8),
                'tp_pct': cfg.get('take_profit_pct', 0.03),
                'sl_pct': cfg.get('stop_loss_pct', 0.015),
                'risk_per_trade': cfg.get('risk_per_trade', 0.05),
                'commission': 0.0008,
                'slippage': 0.0005,
                'lookback': cfg.get('max_bars_back', 500),
                'min_amount': cfg.get('min_trade_amount', 0.01)
            }
            perf = bot.simulate(df, symbol, params)
            st.metric("Initial Balance $", bot.initial_balance)
            st.metric("Final Balance $", perf.get('final_balance', 0.0))
            st.metric("Total trades", perf.get('total_trades', 0))
            st.metric("Win rate", f"{perf.get('win_rate',0)*100:.1f}%")
            st.metric("Max drawdown", f"{perf.get('max_drawdown',0)*100:.1f}%")
            # trades table
            trades = pd.DataFrame(perf.get('trade_history', []))
            if not trades.empty:
                st.subheader("Closed trades")
                st.dataframe(trades.tail(200))
            # equity
            eq = perf.get('equity_curve', [])
            if eq:
                times = pd.date_range(end=datetime.utcnow(), periods=len(eq), freq='T')  # approximate times
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=times, y=eq, mode='lines', name='Equity'))
                fig_eq.update_layout(title='Equity Curve', yaxis_title='Balance ($)', height=300)
                st.plotly_chart(fig_eq, use_container_width=True)

# Run optimizer
if run_opt:
    with st.spinner("Running optimizer... this may take a while"):
        df = fetch_klines(symbol, timeframe, days)
        if df.empty:
            st.error("No data for optimization.")
        else:
            best = bot.optimize_params(df, symbol, n_iter=n_iter)
            st.success("Optimization finished.")
            st.subheader("Best params")
            st.json(best['params'])
            st.subheader("Performance")
            perf = best['perf']
            st.write({
                'final_balance': perf.get('final_balance'),
                'total_trades': perf.get('total_trades'),
                'win_rate': perf.get('win_rate'),
                'max_drawdown': perf.get('max_drawdown'),
                'sharpe': perf.get('sharpe')
            })
            # save params
            with open("best_params.json", "w") as f:
                json.dump(best, f, default=str, indent=2)
            st.info("Saved best_params.json")
