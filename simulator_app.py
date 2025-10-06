# simulator_app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from bot_core import AdvancedLorentzianBot
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import BINANCE_CONFIG, LORENTZIAN_CONFIG
from live_ws import start_kline_ws, get_klines_from_ws, stop_all
import os, pickle, time, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Lorentzian Bot Simulator (Safe)", layout="wide")
st.title("Lorentzian Trading Bot — Safe Simulator + Live (WebSocket)")

# Sidebar
st.sidebar.header("Settings")
symbol = st.sidebar.text_input("Symbol (e.g. BTCUSDT)", value="BTCUSDT")
timeframe = st.sidebar.selectbox("Timeframe", ["1m","5m","15m","1h"], index=0)
days = st.sidebar.slider("Days to simulate", 1, 90, 7)
start_balance = st.sidebar.number_input("Start balance $", value=LORENTZIAN_CONFIG.get("initial_balance",10.0), min_value=0.01)

# instantiate bot
cfg = LORENTZIAN_CONFIG.copy()
cfg["initial_balance"] = float(start_balance)
bot = AdvancedLorentzianBot(cfg)

# caching folder
CACHE_DIR = cfg.get("klines_cache_dir", ".klines_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = cfg.get("klines_cache_ttl_secs", 3600)

def cache_path_for(symbol, interval, days):
    key = f"{symbol}_{interval}_{days}.pkl"
    return os.path.join(CACHE_DIR, key)

def safe_fetch_klines(symbol, interval, days, max_attempts=6):
    """
    Fetch klines with local cache + exponential backoff + basic weight-limit protection.
    """
    path = cache_path_for(symbol, interval, days)
    # return cache if not too old
    if os.path.exists(path):
        try:
            mtime = os.path.getmtime(path)
            age = time.time() - mtime
            if age < CACHE_TTL:
                with open(path, "rb") as f:
                    df = pickle.load(f)
                    logger.info("Loaded klines from cache: %s", path)
                    return df
        except Exception:
            pass

    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    attempt = 0
    wait = 1.0
    while attempt < max_attempts:
        try:
            end = datetime.utcnow()
            start = end - timedelta(days=days)
            klines = client.get_historical_klines(symbol, interval, start_str=str(start), end_str=str(end), limit=1000)
            if not klines:
                return pd.DataFrame()
            df = pd.DataFrame(klines, columns=['timestamp','open','high','low','close','volume','close_time','qav','num_trades','tbv','tqv','ignore'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            for c in ['open','high','low','close','volume']:
                df[c] = pd.to_numeric(df[c], errors='coerce')
            df = df[['timestamp','open','high','low','close','volume']]
            # save cache
            try:
                with open(path, "wb") as f:
                    pickle.dump(df, f)
                logger.info("Cached klines to %s", path)
            except Exception:
                pass
            return df
        except BinanceAPIException as e:
            msg = str(e)
            logger.error("BinanceAPIException: %s", msg)
            if "weight" in msg.lower() or getattr(e, "code", None) == -1003:
                logger.warning("Rate limit hit. Backing off for %s seconds...", wait)
                time.sleep(wait)
                wait = min(wait * 2, 60)
            else:
                time.sleep(wait)
                wait = min(wait * 2, 60)
        except Exception as e:
            logger.error("Error fetching klines: %s", e)
            time.sleep(wait)
            wait = min(wait * 2, 60)
        attempt += 1
    logger.error("Failed fetching klines after %d attempts", max_attempts)
    return pd.DataFrame()

# Main: Simulation button
if st.button("Fetch & Run Simulation"):
    with st.spinner("Fetching klines (safe) and running simulation..."):
        df = safe_fetch_klines(symbol, timeframe, days)
        if df.empty:
            st.error("لا توجد بيانات (تحقّق من الزوج أو انتظر رفع الحظر).")
        else:
            st.success(f"Fetched {len(df)} bars. Running simulation...")
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
            trades = pd.DataFrame(perf.get('trade_history', []))
            if not trades.empty:
                trades['timestamp'] = pd.to_datetime(trades['timestamp'])
                st.subheader("Closed trades (latest)")
                st.dataframe(trades.tail(200))
            eq = perf.get('equity_curve', [])
            if eq:
                times = pd.date_range(end=datetime.utcnow(), periods=len(eq), freq='T')
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=times, y=eq, mode='lines', name='Equity'))
                fig_eq.update_layout(title='Equity Curve', yaxis_title='Balance ($)', height=300)
                st.plotly_chart(fig_eq, use_container_width=True)

# Live demo using WebSocket (safe)
st.sidebar.markdown("---")
st.sidebar.header("Live Demo (WebSocket)")

if 'ws_running' not in st.session_state:
    st.session_state['ws_running'] = False

col1, col2 = st.columns(2)
with col1:
    if st.button("Start Live (WebSocket)"):
        try:
            start_kline_ws(symbol, interval=timeframe, maxlen=2000)
            st.session_state['ws_running'] = True
            st.success("WebSocket started — receiving live klines.")
        except Exception as e:
            st.error(f"Failed to start WebSocket: {e}")
with col2:
    if st.button("Stop Live (WebSocket)"):
        try:
            stop_all()
            st.session_state['ws_running'] = False
            st.success("Stopped WebSocket.")
        except Exception as e:
            st.error(f"Failed to stop WebSocket: {e}")

if st.session_state.get('ws_running'):
    # display last cached klines
    df_live = get_klines_from_ws(symbol)
    if not df_live.empty:
        st.subheader("Last cached live klines (from WebSocket)")
        st.dataframe(df_live.tail(50))
        # small visualization
        fig = go.Figure(data=[go.Candlestick(x=df_live['timestamp'], open=df_live['open'], high=df_live['high'], low=df_live['low'], close=df_live['close'])])
        fig.update_layout(height=450, xaxis_rangeslider_visible=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No live klines yet — انتظر قليلًا بعد بدء WebSocket.")

# cleanup on stop (optional)
st.sidebar.markdown("---")
st.sidebar.caption("ملاحظة: لا تطلب قائمة رموز كبيرة من Binance لتفادي استهلاك الوزن (weight).")
