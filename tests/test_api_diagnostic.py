"""
Test diagnostico - verifica cada capa de API usada por la app.
Corre SIN Streamlit para aislar problemas.
"""
import sys, os, traceback, datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Suprimir warnings no relevantes
import warnings
warnings.filterwarnings("ignore")

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results = []

def test(name, fn):
    try:
        ok, detail = fn()
        status = PASS if ok else FAIL
        results.append((status, name, detail))
        print(f"  {status} {name}: {detail}")
    except Exception as e:
        results.append((FAIL, name, f"EXCEPTION: {e}\n{traceback.format_exc()}"))
        print(f"  {FAIL} {name}: EXCEPTION → {e}")

# ════════════════════════════════════════════════════════════════════
# 1. IMPORTS BÁSICOS
# ════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  DIAGNÓSTICO DE API — Trading App")
print("="*70)

print("\n[1/7] IMPORTS BÁSICOS")

def test_import_yfinance():
    import yfinance as yf
    return True, f"yfinance {yf.__version__}"
test("yfinance import", test_import_yfinance)

def test_import_yahooquery():
    from yahooquery import Ticker
    return True, "yahooquery OK"
test("yahooquery import", test_import_yahooquery)

def test_import_pandas():
    import pandas as pd
    return True, f"pandas {pd.__version__}"
test("pandas import", test_import_pandas)

def test_import_numpy():
    import numpy as np
    return True, f"numpy {np.__version__}"
test("numpy import", test_import_numpy)

def test_import_scipy():
    from scipy.signal import argrelextrema
    return True, "scipy OK"
test("scipy import", test_import_scipy)

# ════════════════════════════════════════════════════════════════════
# 2. IMPORTS DE MÓDULOS LOCALES
# ════════════════════════════════════════════════════════════════════
print("\n[2/7] MÓDULOS LOCALES")

def test_lab_imports():
    from lab.regime_detector import classify_regime
    from lab.indicators import ema_discount, bollinger_pctB, stochastic_k
    from lab.rule_engine import evaluate_signal, RULE_SETS, calculate_confidence
    from lab.monte_carlo import simulate_price_paths
    return True, "lab.* OK"
test("lab modules", test_lab_imports)

def test_data_fetcher_import():
    from data.fetcher import fetch_history
    return True, "data.fetcher OK"
test("data.fetcher", test_data_fetcher_import)

def test_data_fetcher_main():
    from data_fetcher import fetch_stock_data, search_ticker_by_name
    return True, "data_fetcher OK (fetch_stock_data + search_ticker_by_name)"
test("data_fetcher main", test_data_fetcher_main)

def test_estrategia():
    from estrategia import evaluar_protocolo_accion
    return True, "estrategia OK"
test("estrategia", test_estrategia)

def test_lab_tickers():
    from lab_tickers import fetch_sp500_tickers_wiki_v2
    return True, "lab_tickers OK"
test("lab_tickers", test_lab_tickers)

def test_daily_allocator():
    from lab.daily_allocator import calculate_allocations
    return True, "daily_allocator OK"
test("daily_allocator", test_daily_allocator)

# ════════════════════════════════════════════════════════════════════
# 3. yfinance API — PRECIOS
# ════════════════════════════════════════════════════════════════════
print("\n[3/7] yfinance — PRECIOS")

def test_yf_vix():
    import yfinance as yf
    tk = yf.Ticker("^VIX")
    hist = tk.history(period="5d")
    if hist.empty:
        return False, "VIX history VACÍO (posible bloqueo Yahoo)"
    val = float(hist['Close'].iloc[-1])
    return True, f"VIX actual: {val:.2f}"
test("yfinance ^VIX", test_yf_vix)

def test_yf_tnx():
    import yfinance as yf
    tk = yf.Ticker("^TNX")
    hist = tk.history(period="5d")
    if hist.empty:
        return False, "TNX history VACÍO"
    val = float(hist['Close'].iloc[-1])
    return True, f"TNX yield: {val:.2f}%"
test("yfinance ^TNX", test_yf_tnx)

def test_yf_aapl_history():
    import yfinance as yf
    df = yf.download("AAPL", period="1y", progress=False)
    if df.empty:
        return False, "AAPL 1y download VACÍO"
    rows = len(df)
    return rows >= 200, f"AAPL 1y: {rows} filas (necesita >=200)"
test("yfinance AAPL 1y", test_yf_aapl_history)

def test_yf_download_multi():
    import yfinance as yf
    df = yf.download(["AAPL", "MSFT"], period="5d", progress=False)
    if df.empty:
        return False, "Multi-ticker download VACÍO"
    return True, f"Multi download OK: {len(df)} filas, cols: {list(df.columns[:6])}"
test("yfinance multi-download", test_yf_download_multi)

def test_yf_fast_info():
    import yfinance as yf
    tk = yf.Ticker("AAPL")
    try:
        price = tk.fast_info.last_price
        if price is None:
            return False, "fast_info.last_price = None"
        return True, f"AAPL fast_info price: ${price:.2f}"
    except Exception as e:
        return False, f"fast_info falla: {e}"
test("yfinance fast_info", test_yf_fast_info)

# ════════════════════════════════════════════════════════════════════
# 4. yahooquery API — FUNDAMENTALES
# ════════════════════════════════════════════════════════════════════
print("\n[4/7] yahooquery — FUNDAMENTALES")

def test_yq_ticker():
    from yahooquery import Ticker
    yq = Ticker("AAPL", asynchronous=False, validate=True)
    fd = yq.financial_data
    if isinstance(fd, str):
        return False, f"financial_data es string: {fd[:100]}"
    aapl_fd = fd.get("AAPL", {})
    if isinstance(aapl_fd, str):
        return False, f"AAPL data es string: {aapl_fd[:100]}"
    price = aapl_fd.get("currentPrice")
    if price is None:
        return False, f"currentPrice es None. Keys: {list(aapl_fd.keys())[:10]}"
    return True, f"AAPL currentPrice: ${price}"
test("yahooquery AAPL financial_data", test_yq_ticker)

def test_yq_key_stats():
    from yahooquery import Ticker
    yq = Ticker("AAPL", asynchronous=False, validate=True)
    ks = yq.key_stats
    aapl_ks = ks.get("AAPL", {}) if isinstance(ks, dict) else {}
    if isinstance(aapl_ks, str):
        return False, f"key_stats es string: {aapl_ks[:100]}"
    pe = aapl_ks.get("forwardPE")
    return pe is not None, f"forwardPE: {pe}"
test("yahooquery key_stats", test_yq_key_stats)

def test_yq_income_stmt():
    from yahooquery import Ticker
    yq = Ticker("AAPL", asynchronous=False, validate=True)
    inc = yq.income_statement(frequency="quarterly", trailing=False)
    if inc is None or (hasattr(inc, 'empty') and inc.empty):
        return False, "income_statement vacío"
    rows = len(inc)
    return rows >= 4, f"income_statement quarterly: {rows} filas"
test("yahooquery income_statement", test_yq_income_stmt)

def test_yq_balance_sheet():
    from yahooquery import Ticker
    yq = Ticker("AAPL", asynchronous=False, validate=True)
    bs = yq.balance_sheet(frequency="annual")
    if bs is None or (hasattr(bs, 'empty') and bs.empty):
        return False, "balance_sheet vacío"
    return True, f"balance_sheet annual: {len(bs)} filas"
test("yahooquery balance_sheet", test_yq_balance_sheet)

# ════════════════════════════════════════════════════════════════════
# 5. data.fetcher — fetch_history
# ════════════════════════════════════════════════════════════════════
print("\n[5/7] data.fetcher — fetch_history")

def test_fetch_history():
    from data.fetcher import fetch_history
    end = datetime.date.today().strftime('%Y-%m-%d')
    start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')
    result = fetch_history(["AAPL"], start=start, end=end)
    df = result.get("AAPL")
    if df is None or df.empty:
        return False, "fetch_history('AAPL') devolvió vacío"
    rows = len(df)
    return rows >= 252, f"AAPL 2y: {rows} filas (mín 252 para técnicos)"
test("fetch_history AAPL 2y", test_fetch_history)

# ════════════════════════════════════════════════════════════════════
# 6. data_fetcher — fetch_stock_data (pipeline completo)
# ════════════════════════════════════════════════════════════════════
print("\n[6/7] data_fetcher — fetch_stock_data (PIPELINE COMPLETO)")

def test_fetch_stock_data():
    # Importar sin streamlit cache (mock st.cache_data)
    import importlib
    # Limpiar cache de streamlit si existe
    try:
        from data_fetcher import fetch_stock_data
        # La función puede depender de st.cache_data decorator
        # Si estamos fuera de streamlit, puede fallar
        data = fetch_stock_data("AAPL")
        if not data or not isinstance(data, dict):
            return False, "fetch_stock_data devolvió vacío o no-dict"
        price = data.get("price")
        sector = data.get("sector", "N/A")
        rev_g = data.get("revenue_growth_ttm")
        keys_count = len(data)
        return price is not None, f"price=${price}, sector={sector}, rev_growth_ttm={rev_g}, {keys_count} keys"
    except Exception as e:
        return False, f"Exception: {e}"
test("fetch_stock_data AAPL", test_fetch_stock_data)

# ════════════════════════════════════════════════════════════════════
# 7. PIPELINE COMPLETO — analyze_ticker_for_today
# ════════════════════════════════════════════════════════════════════
print("\n[7/7] PIPELINE COMPLETO — analyze_ticker_for_today")

def test_analyze_pipeline():
    try:
        # Este import puede fallar si hay dependencia de streamlit
        from lab.regime_detector import classify_regime
        from lab.indicators import ema_discount, bollinger_pctB, stochastic_k
        from lab.rule_engine import evaluate_signal, RULE_SETS
        from data.fetcher import fetch_history
        from estrategia import evaluar_protocolo_accion
        from data_fetcher import fetch_stock_data
        import pandas as pd
        
        end = datetime.date.today().strftime('%Y-%m-%d')
        start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')
        
        # Paso 1: fetch_history
        result = fetch_history(["AAPL"], start=start, end=end)
        df = result.get("AAPL")
        if df is None or len(df) < 252:
            return False, f"fetch_history insuficiente: {len(df) if df is not None else 0} filas"
        
        # Paso 2: Indicadores técnicos
        from lab.indicators import rsi, mfi, macd_hist, williams_r, adx
        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB'] = bollinger_pctB(df)
        df['Stoch_K'] = stochastic_k(df)
        df['RSI'] = rsi(df)
        
        last = df.iloc[-1]
        ema_val = float(last['EMA200_disc'])
        
        # Paso 3: Fundamental
        data = fetch_stock_data("AAPL")
        price = data.get("price", float(last['Close']))
        
        tech_real = {
            'rsi': float(last['RSI']),
            'sma_200': df['Close'].rolling(window=200).mean().iloc[-1],
            'fifty_two_position': 50,
        }
        
        res = evaluar_protocolo_accion(data, tech_real, 4.2, price, soportes=[], profile='B')
        stars = res.get('passed', 0)
        total = res.get('total', 0)
        
        return True, f"Pipeline OK! EMA_disc={ema_val:.1f}%, stars={stars}/{total}, price=${price:.2f}"
    except Exception as e:
        return False, f"Pipeline falló: {e}\n{traceback.format_exc()}"
test("Pipeline completo AAPL", test_analyze_pipeline)

# ════════════════════════════════════════════════════════════════════
# 8. SP500 TICKERS
# ════════════════════════════════════════════════════════════════════
print("\n[8/8] SP500 TICKERS")

def test_sp500_tickers():
    from lab_tickers import fetch_sp500_tickers_wiki_v2
    tickers = fetch_sp500_tickers_wiki_v2()
    if not tickers:
        return False, "Lista vacía"
    return len(tickers) > 400, f"{len(tickers)} tickers obtenidos"
test("SP500 tickers wiki", test_sp500_tickers)

# ════════════════════════════════════════════════════════════════════
# RESUMEN
# ════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  RESUMEN")
print("="*70)

passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)

print(f"\n  {PASS} Pasaron: {passed}/{len(results)}")
print(f"  {FAIL} Fallaron: {failed}/{len(results)}")

if failed > 0:
    print(f"\n  FALLOS DETALLADOS:")
    for status, name, detail in results:
        if status == FAIL:
            print(f"    {FAIL} {name}")
            print(f"       {detail}")

print("\n" + "="*70)
