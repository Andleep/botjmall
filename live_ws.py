# live_ws.py
import pandas as pd
from binance import ThreadedWebsocketManager
from collections import deque
import logging
from config import BINANCE_CONFIG

logger = logging.getLogger(__name__)
twm = None
klines_cache = {}  # symbol -> deque of dicts

def start_kline_ws(symbol: str, interval: str='1m', maxlen: int = 2000):
    """
    Start a kline websocket for `symbol` with given interval.
    Keeps last `maxlen` candles in memory at klines_cache[symbol].
    """
    global twm, klines_cache
    if symbol in klines_cache:
        # already started for this symbol
        return

    klines_cache[symbol] = deque(maxlen=maxlen)

    def _handle(msg):
        try:
            k = msg['k']
            ts = pd.to_datetime(k['t'], unit='ms', utc=True)
            o = float(k['o'])
            h = float(k['h'])
            l = float(k['l'])
            c = float(k['c'])
            v = float(k['v'])
            klines_cache[symbol].append({'timestamp': ts, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})
        except Exception as e:
            logger.error("WS parse error: %s", e)

    twm = ThreadedWebsocketManager(api_key=BINANCE_CONFIG.get("api_key",""), api_secret=BINANCE_CONFIG.get("api_secret",""))
    twm.start()
    # thread-safe start of kline socket
    twm.start_kline_socket(callback=_handle, symbol=symbol, interval=interval)

def stop_all():
    global twm
    if twm:
        try:
            twm.stop()
        except Exception:
            pass
        twm = None

def get_klines_from_ws(symbol: str):
    """
    Return a pandas DataFrame of current cached klines for symbol (may be empty).
    """
    from collections import deque
    data = list(klines_cache.get(symbol, deque()))
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df.rename(columns={'timestamp':'timestamp','open':'open','high':'high','low':'low','close':'close','volume':'volume'}, inplace=True)
    return df
