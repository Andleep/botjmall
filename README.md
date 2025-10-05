# Lorentzian Trading Bot — Demo Project

This repository contains a demo version of a Lorentzian-style trading bot and a Streamlit interface for simulation.

## Contents
- `bot.py` — simplified bot core (demo mode).
- `streamlit_app.py` — Streamlit demo UI to run simulated cycles.
- `config.py` — configurations (use environment variables for real API keys).
- `requirements.txt` — Python dependencies.

## Quick Start (local)
1. Create virtual env and activate:
```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.\\.venv\\Scripts\\activate  # Windows
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```
> Note: TA-Lib often requires system-level libraries. On Ubuntu: `sudo apt-get install -y build-essential libta-lib0 libta-lib-dev`

3. Run Streamlit demo:
```bash
streamlit run streamlit_app.py
```

## Important
- This is a **demo/simulation** project. Do **NOT** use real API keys until you fully test and understand the bot.
- Replace simulated data with real historical klines if you want to backtest seriously.
