# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
test_verify_all.py — Verificación automática de todos los módulos.
Sin lanzar Streamlit. Mockea st.cache_data / st.cache_resource.
"""
import sys
import os
from unittest.mock import MagicMock

# ─── Mock Streamlit ANTES de cualquier import ────────────────────────────────
st_mock = MagicMock()
st_mock.cache_data = lambda **kw: (lambda f: f)
st_mock.cache_resource = lambda **kw: (lambda f: f)
st_mock.set_page_config = lambda **kw: None
st_mock.error = lambda *a, **kw: None
st_mock.warning = lambda *a, **kw: None
sys.modules['streamlit'] = st_mock

# Agregar raíz del proyecto al path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import traceback
import numpy as np
import pandas as pd

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def run_test(name, fn):
    try:
        fn()
        print(f"{PASS} — {name}")
        results.append((name, True, ""))
    except Exception as e:
        tb = traceback.format_exc()
        print(f"{FAIL} — {name}")
        print(f"   Error: {e}")
        print(f"   Trace:\n{tb}")
        results.append((name, False, str(e)))

def make_ohlcv(n=350):
    """Crea DataFrame OHLCV falso con n filas."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high  = close + np.abs(np.random.randn(n) * 0.3)
    low   = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.2
    vol   = np.random.randint(500_000, 5_000_000, n).astype(float)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low,
                        "Close": close, "Volume": vol}, index=dates)
    return df

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: regime_detector
# ─────────────────────────────────────────────────────────────────────────────
def test_regime_detector():
    from lab.regime_detector import classify_regime
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    # CALM: VIX=15
    vix_calm = pd.Series([15.0]*30, index=idx)
    r = classify_regime(vix_calm)
    assert r.iloc[-1] == "CALM", f"Expected CALM, got {r.iloc[-1]}"

    # SLOW_BEAR: VIX=25
    vix_bear = pd.Series([25.0]*30, index=idx)
    r = classify_regime(vix_bear)
    assert r.iloc[-1] == "SLOW_BEAR", f"Expected SLOW_BEAR, got {r.iloc[-1]}"

    # FAST_CRASH: VIX=45
    vix_crash = pd.Series([45.0]*30, index=idx)
    r = classify_regime(vix_crash)
    assert r.iloc[-1] == "FAST_CRASH", f"Expected FAST_CRASH, got {r.iloc[-1]}"

run_test("regime_detector — classify_regime CALM/BEAR/CRASH", test_regime_detector)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: indicators
# ─────────────────────────────────────────────────────────────────────────────
def test_indicators():
    from lab.indicators import (
        ema_discount, bollinger_pctB, stochastic_k,
        rsi, mfi, macd_hist, williams_r, adx
    )
    df = make_ohlcv(350)

    for name, fn in [
        ("ema_discount",   lambda: ema_discount(df)),
        ("bollinger_pctB", lambda: bollinger_pctB(df)),
        ("stochastic_k",   lambda: stochastic_k(df)),
        ("rsi",            lambda: rsi(df)),
        ("mfi",            lambda: mfi(df)),
        ("macd_hist",      lambda: macd_hist(df)),
        ("williams_r",     lambda: williams_r(df)),
        ("adx",            lambda: adx(df)),
    ]:
        series = fn()
        assert isinstance(series, pd.Series), f"{name} debe retornar Series"
        assert len(series) == len(df), f"{name} longitud incorrecta"
        last50 = series.iloc[-50:]
        nan_count = last50.isna().sum()
        assert nan_count < 45, f"{name} tiene demasiados NaN en últimas 50 rows: {nan_count}"

run_test("indicators — 8 indicadores técnicos (Series, longitud, NaN)", test_indicators)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: rule_engine
# ─────────────────────────────────────────────────────────────────────────────
def test_rule_engine():
    from lab.rule_engine import evaluate_signal, RULE_SETS, calculate_confidence

    # Señal activa en CALM (EMA200_disc >= 5, stars >= 10)
    ind_ok = {"EMA200_disc": 6.0, "BB_pctB": 0.2, "Stoch_K": 20.0,
               "RSI": 45.0, "MFI": 40.0, "MACD_hist": 0.1, "Williams_R": -85.0, "ADX": 28.0}
    res = evaluate_signal(ind_ok, "CALM", 10)
    assert res["signal"] == True, f"CALM debe dar signal=True, got {res}"
    assert res["confidence"] > 0, "Confidence debe ser >0"

    # Señal inactiva (EMA disco bajo, pocas estrellas)
    ind_bad = {"EMA200_disc": 1.0, "BB_pctB": 0.9}
    res = evaluate_signal(ind_bad, "CALM", 3)
    assert res["signal"] == False, f"CALM con stars=3 debe dar signal=False, got {res}"

    # SLOW_BEAR necesita 2 señales
    ind_bear = {"EMA200_disc": 9.0, "BB_pctB": 0.25, "Stoch_K": 30.0}
    res = evaluate_signal(ind_bear, "SLOW_BEAR", 9)
    assert res["signal"] == True, f"SLOW_BEAR con suficientes indicators debe dar True"

    # Verificar RULE_SETS contiene los 3 regímenes
    assert "CALM" in RULE_SETS
    assert "SLOW_BEAR" in RULE_SETS
    assert "FAST_CRASH" in RULE_SETS

run_test("rule_engine — evaluate_signal True/False, RULE_SETS completos", test_rule_engine)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: monte_carlo
# ─────────────────────────────────────────────────────────────────────────────
def test_monte_carlo():
    from lab.monte_carlo import simulate_price_paths
    np.random.seed(123)
    rets = pd.Series(np.random.randn(252) * 0.01)  # retornos diarios fake
    mc = simulate_price_paths(current_price=150.0, historical_returns=rets,
                               horizon_days=5, n_simulations=10_000)

    required_keys = ["prob_positive", "prob_gt_1pct", "prob_gt_2pct",
                     "prob_gt_5pct", "p10", "p50", "p90", "sigma_anual"]
    for k in required_keys:
        assert k in mc, f"Falta clave: {k}"

    assert 0 <= mc["prob_positive"] <= 1, f"prob_positive fuera de rango: {mc['prob_positive']}"
    assert 0 <= mc["prob_gt_2pct"] <= 1
    assert mc["p10"] <= mc["p50"] <= mc["p90"], "p10 ≤ p50 ≤ p90 debe cumplirse"
    assert mc["sigma_anual"] > 0, "Volatilidad debe ser positiva"

run_test("monte_carlo — 10K simulaciones, claves correctas, probabilidades válidas", test_monte_carlo)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: daily_allocator
# ─────────────────────────────────────────────────────────────────────────────
def test_daily_allocator():
    from lab.daily_allocator import calculate_allocations

    signals = [
        {"ticker": "AAPL", "strategy": "scanner", "hit_rate": 0, "avg_win": 0,
         "avg_loss": 0, "sector": "Technology", "n_signals": 0, "vol_30d": 0.015, "confidence": 80},
        {"ticker": "MSFT", "strategy": "scanner", "hit_rate": 0, "avg_win": 0,
         "avg_loss": 0, "sector": "Technology", "n_signals": 0, "vol_30d": 0.012, "confidence": 70},
        {"ticker": "JPM", "strategy": "scanner", "hit_rate": 0, "avg_win": 0,
         "avg_loss": 0, "sector": "Financial Services", "n_signals": 0, "vol_30d": 0.018, "confidence": 60},
    ]

    allocs, regime, inv_pct = calculate_allocations(signals, vix_current=18, total_capital=10_000)
    assert len(allocs) >= 3, "Debe haber al menos 3 entradas (posiblemente + CASH)"
    assert regime == "CALM", f"VIX=18 → CALM, got {regime}"

    total_pct = sum(a["weight_pct"] for a in allocs)
    assert abs(total_pct - 100) < 1.0, f"Pesos deben sumar ~100%, got {total_pct}"

    # Cap por ticker: ≤20% en CALM
    for a in allocs:
        if a["ticker"] != "CASH":
            assert a["weight_pct"] <= 20.01, f"{a['ticker']} supera cap 20%: {a['weight_pct']}"

run_test("daily_allocator — Vol Parity, caps 20%, suma 100%, régimen CALM", test_daily_allocator)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: data/fetcher (fetch_history con AAPL real)
# ─────────────────────────────────────────────────────────────────────────────
def test_fetch_history():
    from data.fetcher import fetch_history
    import datetime
    end   = datetime.date.today().strftime('%Y-%m-%d')
    start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

    result = fetch_history(["AAPL"], start=start, end=end)
    assert "AAPL" in result, "fetch_history debe retornar dict con 'AAPL'"
    df = result["AAPL"]
    assert len(df) >= 200, f"Debe tener >= 200 filas, tiene {len(df)}"
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        assert col in df.columns, f"Falta columna {col}"
    assert df["Close"].isna().sum() == 0, "No debe haber NaN en Close"

run_test("data/fetcher — fetch_history AAPL 2 años, OHLCV sin NaN", test_fetch_history)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: lab_tickers (sin cache real de streamlit)
# ─────────────────────────────────────────────────────────────────────────────
def test_lab_tickers():
    import importlib, types

    # Recargar módulo con st ya mockeado
    import lab_tickers
    importlib.reload(lab_tickers)
    tickers = lab_tickers.fetch_sp500_tickers_wiki_v2()
    assert isinstance(tickers, list), "Debe retornar lista"
    assert len(tickers) >= 400, f"Debe tener >= 400 tickers, tiene {len(tickers)}"
    assert "AAPL" in tickers, "AAPL debe estar en la lista"
    assert "MSFT" in tickers, "MSFT debe estar en la lista"

run_test("lab_tickers — fetch_sp500_tickers_wiki_v2 >=400 tickers, AAPL/MSFT presentes", test_lab_tickers)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 8: data_fetcher fetch_stock_data (AAPL real — Plan A yahooquery)
# ─────────────────────────────────────────────────────────────────────────────
def test_fetch_stock_data():
    import data_fetcher
    import importlib
    importlib.reload(data_fetcher)
    data = data_fetcher.fetch_stock_data("AAPL")

    assert data, "fetch_stock_data debe retornar dict no vacío"
    assert data.get("price") is not None, "Debe tener 'price'"
    price = data.get("price")
    assert 50 < price < 10000, f"Precio AAPL sospechoso: {price}"

    # Verificar campos fundamentales clave
    important_keys = ["sector", "revenue_growth", "gross_margins", "profit_margins"]
    missing = [k for k in important_keys if k not in data]
    assert len(missing) == 0, f"Faltan claves: {missing}"

    sector = data.get("sector")
    assert sector not in (None, "N/A", ""), f"Sector vacío para AAPL: {sector}"

run_test("data_fetcher — fetch_stock_data AAPL: precio real, fundamentales, sector", test_fetch_stock_data)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 9: estrategia evaluar_protocolo_accion
# ─────────────────────────────────────────────────────────────────────────────
def test_estrategia():
    from estrategia import evaluar_protocolo_accion

    # Datos fake tipo empresa saludable
    data = {
        "description": "Apple Inc. designs, manufactures, and markets smartphones...",
        "sector": "Technology",
        "total_cash": 50_000_000_000,
        "total_debt": 30_000_000_000,
        "gross_margins": 0.44,
        "operating_margins": 0.30,
        "profit_margins": 0.25,
        "peg_ratio": 1.8,
        "revenue_growth": 0.05,
        "earnings_growth": 0.08,
        "forward_eps": 7.5,
        "trailing_eps": 6.8,
        "fcf_yield": 0.04,
        "fcf_growth": 0.10,
        "free_cf": 80_000_000_000,
        "ebitda": 120_000_000_000,
        "interest_expense": 3_000_000_000,
        "debt_to_equity": 150.0,
        "total_assets": 350_000_000_000,
        "goodwill": 5_000_000_000,
        "intangible_assets": 2_000_000_000,
        "short_term_debt": 8_000_000_000,
        "net_income": 96_000_000_000,
        "operating_cf": 110_000_000_000,
        "revenue_growth_ttm": 0.05,
        "fcf_growth_ttm": 0.10,
        "shares_growth": 0.01,
        "roic": 0.45,
        "roe": 0.80,
        "current_ratio": 1.5,
    }
    tech = {
        "rsi": 45.0,
        "sma_200": 165.0,
        "fifty_two_position": 70.0,
    }

    res = evaluar_protocolo_accion(data, tech, tnx_yield=4.2, price=180.0,
                                   soportes=[], profile='B', scan_mode='DIP')

    assert "passed" in res, "Debe tener 'passed'"
    assert "total" in res, "Debe tener 'total'"
    assert "verdicts" in res, "Debe tener 'verdicts'"
    passed = res["passed"]
    total  = res["total"]
    verdicts = res["verdicts"]
    assert total >= 5, f"Total checks debe ser >= 5, got {total}"
    assert len(verdicts) >= 10, f"Debe haber >= 10 verdicts, got {len(verdicts)}"
    print(f"   → {passed}/{total} checks pasados, {len(verdicts)} verdicts")

run_test("estrategia — evaluar_protocolo_accion: passed/total/verdicts correctos", test_estrategia)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 10: indicators sobre datos reales AAPL
# ─────────────────────────────────────────────────────────────────────────────
def test_indicators_real():
    from data.fetcher import fetch_history
    from lab.indicators import ema_discount, bollinger_pctB, stochastic_k, rsi
    import datetime
    end   = datetime.date.today().strftime('%Y-%m-%d')
    start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

    result = fetch_history(["AAPL"], start=start, end=end)
    df = result["AAPL"]

    ema_disc = ema_discount(df)
    bb = bollinger_pctB(df)
    stoch = stochastic_k(df)
    rsi_s = rsi(df)

    last = df.iloc[-1]
    ema_val = float(ema_disc.iloc[-1])
    rsi_val = float(rsi_s.iloc[-1])

    print(f"   → AAPL EMA200_disc={ema_val:.2f}%, RSI={rsi_val:.2f}, BB%B={float(bb.iloc[-1]):.2f}, Stoch_K={float(stoch.iloc[-1]):.2f}")
    assert not pd.isna(ema_val), "EMA200_disc no debe ser NaN"
    assert 0 <= rsi_val <= 100, f"RSI fuera de rango: {rsi_val}"

run_test("indicators sobre datos reales AAPL — valores válidos", test_indicators_real)

# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN FINAL
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("RESUMEN DE TESTS")
print("="*60)
passed_count = sum(1 for _, ok, _ in results if ok)
total_count  = len(results)
print(f"Resultado: {passed_count}/{total_count} tests pasaron\n")

for name, ok, err in results:
    status = "✅" if ok else "❌"
    print(f"  {status} {name}")
    if not ok and err:
        print(f"     → {err[:120]}")

if passed_count == total_count:
    print("\n🎯 TODOS LOS TESTS PASARON")
else:
    print(f"\n⚠️  {total_count - passed_count} tests fallaron")
    sys.exit(1)
