# Lorentzian Trading Bot v2 — Simulator (Binance historical klines)

This version uses real historical klines fetched from Binance for simulation (read-only).
It runs a Lorentzian-style classifier with EMA/ADX/ATR/VWAP filters on chosen symbol/timeframe.

## How to run locally
1. Create virtual environment and activate it.
2. Install requirements: `pip install -r requirements.txt`
3. Set optional environment variables for Binance API (not required for public klines):
   - BINANCE_API_KEY, BINANCE_API_SECRET
4. Run Streamlit app:
   `streamlit run simulator_app.py`

## Notes
- This is a simulator/backtester. It uses Binance historical data and does NOT place real orders.
- Check Binance rate limits. Fetching many days at high resolution may hit limits.
