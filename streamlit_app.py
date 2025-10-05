import streamlit as st
import pandas as pd
import numpy as np
import time
from bot import LorentzianTradingBot
from config import LORENTZIAN_CONFIG
import os

st.set_page_config(page_title="Lorentzian Bot Demo", layout="wide")
st.title("Lorentzian Trading Bot — Demo")

if 'bot' not in st.session_state:
    st.session_state.bot = LorentzianTradingBot(LORENTZIAN_CONFIG)

st.sidebar.header("Simulation controls")
symbol = st.sidebar.selectbox("Symbol", ["BTCUSDT","ETHUSDT","BNBUSDT","ADAUSDT","XRPUSDT"])
start_balance = st.sidebar.number_input("Start balance $", value=10.0, min_value=1.0)
st.sidebar.write("This demo uses generated historical-like data for simulation.")

if st.button("Run single simulated cycle"):
    # generate fake minute-level data (100 candles)
    import numpy as np
    now = pd.Timestamp.utcnow()
    periods = 100
    rng = pd.date_range(end=now, periods=periods, freq='T')
    price = 30000.0
    data = []
    for i in range(periods):
        o = price * (1 + np.random.normal(0,0.0005))
        h = o * (1 + abs(np.random.normal(0,0.001)))
        l = o * (1 - abs(np.random.normal(0,0.001)))
        c = o * (1 + np.random.normal(0,0.0008))
        v = np.random.randint(1,100)
        data.append([rng[i], o, h, l, c, v])
        price = c
    df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume'])
    df.set_index('timestamp', inplace=False)
    st.session_state.bot.balance = start_balance
    res = st.session_state.bot.run_bot_cycle_with_df(symbol, df, demo_mode=True)
    st.write(res)

st.subheader("Trade history (last 20)")
if st.session_state.bot.trade_history:
    st.dataframe(pd.DataFrame(st.session_state.bot.trade_history[-20:]))
else:
    st.info("No trades yet. Run cycles to generate simulated trades.")
