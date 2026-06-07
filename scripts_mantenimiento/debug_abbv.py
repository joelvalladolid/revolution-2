# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from unittest.mock import MagicMock
st_mock = MagicMock()
st_mock.cache_data = lambda **kw: (lambda f: f)
st_mock.cache_resource = lambda **kw: (lambda f: f)
st_mock.set_page_config = lambda **kw: None
st_mock.error = lambda *a, **kw: None
st_mock.warning = lambda *a, **kw: None
sys.modules['streamlit'] = st_mock

import yfinance as yf
from yahooquery import Ticker as YQTicker

print("="*60)
print("DIAGNOSTICO ABBV - Precio Real vs APIs")
print("="*60)

# --- 1. yfinance: fast_info ---
print("\n[1] yfinance fast_info:")
tk = yf.Ticker("ABBV")
try:
    fi = tk.fast_info
    print(f"    last_price     = {fi.last_price}")
    print(f"    previous_close = {fi.previous_close}")
    print(f"    market_cap     = {fi.market_cap}")
except Exception as e:
    print(f"    ERROR: {e}")

# --- 2. yfinance: .info ---
print("\n[2] yfinance .info:")
try:
    info = tk.info
    print(f"    currentPrice       = {info.get('currentPrice')}")
    print(f"    regularMarketPrice = {info.get('regularMarketPrice')}")
    print(f"    previousClose      = {info.get('previousClose')}")
    print(f"    open               = {info.get('open')}")
except Exception as e:
    print(f"    ERROR: {e}")

# --- 3. yfinance: history ultimo dia ---
print("\n[3] yfinance history(period='5d'):")
try:
    hist = tk.history(period="5d")
    if not hist.empty:
        print(f"    Ultimas filas:")
        print(hist.tail())
        print(f"    Ultimo Close = {hist['Close'].iloc[-1]}")
    else:
        print("    VACIO")
except Exception as e:
    print(f"    ERROR: {e}")

# --- 4. yahooquery ---
print("\n[4] yahooquery financial_data:")
try:
    yq = YQTicker("ABBV", asynchronous=False, validate=True)
    fd = yq.financial_data
    if isinstance(fd, dict) and 'ABBV' in fd:
        d = fd['ABBV']
        if isinstance(d, dict):
            print(f"    currentPrice = {d.get('currentPrice')}")
            print(f"    targetMean   = {d.get('targetMeanPrice')}")
        else:
            print(f"    Respuesta tipo: {type(d)}: {d}")
    else:
        print(f"    Respuesta: {fd}")
except Exception as e:
    print(f"    ERROR: {e}")

# --- 5. yahooquery summary_detail ---
print("\n[5] yahooquery summary_detail:")
try:
    sd = yq.summary_detail
    if isinstance(sd, dict) and 'ABBV' in sd:
        d = sd['ABBV']
        if isinstance(d, dict):
            print(f"    previousClose      = {d.get('previousClose')}")
            print(f"    regularMarketPrice = {d.get('regularMarketPrice')}")
            print(f"    open               = {d.get('open')}")
        else:
            print(f"    Respuesta tipo: {type(d)}: {d}")
except Exception as e:
    print(f"    ERROR: {e}")

# --- 6. data_fetcher.py fetch_stock_data ---
print("\n[6] data_fetcher.fetch_stock_data('ABBV'):")
try:
    import data_fetcher
    import importlib
    importlib.reload(data_fetcher)
    data = data_fetcher.fetch_stock_data("ABBV")
    print(f"    price           = {data.get('price')}")
    print(f"    market_cap      = {data.get('market_cap')}")
    print(f"    name            = {data.get('name')}")
    print(f"    sector          = {data.get('sector')}")
    print(f"    fifty_two_high  = {data.get('fifty_two_high')}")
    print(f"    fifty_two_low   = {data.get('fifty_two_low')}")
    print(f"    trailing_pe     = {data.get('trailing_pe')}")
except Exception as e:
    print(f"    ERROR: {e}")
    import traceback
    traceback.print_exc()

# --- 7. Precio con download bulk (como hace el scanner) ---
print("\n[7] yf.download(['ABBV'], period='5d'):")
try:
    bulk = yf.download(["ABBV"], period="5d", progress=False)
    if not bulk.empty:
        print(bulk.tail())
        # Check column structure
        if isinstance(bulk.columns, __import__('pandas').MultiIndex):
            print(f"    MultiIndex columns: {bulk.columns.tolist()}")
            close = bulk[('Close', 'ABBV')].iloc[-1]
        else:
            close = bulk['Close'].iloc[-1]
        print(f"    Ultimo Close via download = {close}")
    else:
        print("    VACIO")
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "="*60)
print("FIN DIAGNOSTICO")
print("="*60)
