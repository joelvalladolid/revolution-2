# -*- coding: utf-8 -*-
"""
quick_backtest.py
Test rapido de las 3 estrategias en un ticker (default MSFT).
Estrategia C = la que usa la web (regimen + fundamental).

Resultados: Hit Rate, Edge sobre buy-and-hold, Sharpe, Max Drawdown, Kelly.
"""
import sys, os, warnings
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.abspath(os.path.join(_HERE, '..'))
for p in [_HERE, ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

from data.fetcher import fetch_history
from lab.indicators import ema_discount, bollinger_pctB, stochastic_k, rsi as rsi_fn
from lab.regime_detector import classify_regime
from lab.rule_engine import evaluate_signal

TICKER = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
START  = "2015-01-01"
END    = "2024-12-31"
HOLD_DAYS = 5   # retorno a 5 dias

print(f"\n{'='*62}")
print(f"  BACKTEST RAPIDO — {TICKER}  |  {START} → {END}")
print(f"  Comparando 3 estrategias (hold {HOLD_DAYS}d tras señal)")
print(f"{'='*62}")

# ── Descargar datos ──────────────────────────────────────────────
print(f"\n[1/3] Descargando {TICKER} + VIX ({START}-{END})...")
data_dict = fetch_history([TICKER], start=START, end=END)
df = data_dict.get(TICKER)
if df is None or len(df) < 300:
    print(f"  ERROR: No hay suficientes datos para {TICKER}")
    sys.exit(1)
print(f"  Barras: {len(df)} dias")

vix_raw = yf.download("^VIX", start=START, end=END, progress=False)
if isinstance(vix_raw.columns, pd.MultiIndex):
    vix_raw.columns = vix_raw.columns.droplevel(1)
vix_series = vix_raw['Close']
regimes = classify_regime(vix_series)

# ── Calcular indicadores ─────────────────────────────────────────
print(f"[2/3] Calculando indicadores...")
df = df.copy()
df['EMA200_disc'] = ema_discount(df)
df['BB_pctB']     = bollinger_pctB(df)
df['Stoch_K']     = stochastic_k(df)
df['RSI']         = rsi_fn(df)
df['regime']      = regimes.reindex(df.index).ffill().fillna('CALM')
df['fwd_ret']     = (df['Close'].shift(-HOLD_DAYS) / df['Close']) - 1
df['1y_ret']      = df['Close'].pct_change(252)
df = df.dropna(subset=['EMA200_disc', 'BB_pctB', 'Stoch_K', 'RSI', 'fwd_ret'])

print(f"  Barras validas: {len(df)}")

# ── Backtest ──────────────────────────────────────────────────────
print(f"[3/3] Evaluando señales...")

sig_A, sig_B, sig_C = [], [], []  # retornos cuando hay señal
base_rets = df['fwd_ret'].tolist()

# Por año para análisis temporal
by_year_A = {}
by_year_C = {}

for idx, row in df.iterrows():
    fwd   = row['fwd_ret']
    reg   = row['regime']
    year  = idx.year

    ind   = {
        'EMA200_disc': row['EMA200_disc'],
        'BB_pctB':     row['BB_pctB'],
        'Stoch_K':     row['Stoch_K'],
        'RSI':         row['RSI'],
    }
    stars_proxy = 15 if row['1y_ret'] > 0 else 10

    # Estrategia A: EMA200 >= 15% (filtro simple)
    if row['EMA200_disc'] >= 15.0:
        sig_A.append(fwd)
        by_year_A.setdefault(year, []).append(fwd)

    # Estrategia B: Motor reglas sin fundamental
    res_b = evaluate_signal(ind, reg, fundamental_stars=15)
    if res_b['signal']:
        sig_B.append(fwd)

    # Estrategia C: Motor reglas + fundamental (proxy 1y return)
    res_c = evaluate_signal(ind, reg, fundamental_stars=stars_proxy)
    if res_c['signal']:
        sig_C.append(fwd)
        by_year_C.setdefault(year, []).append(fwd)

# ── Métricas ──────────────────────────────────────────────────────
def metrics(rets, base):
    rets = np.array(rets)
    base = np.array(base)
    if len(rets) == 0:
        return dict(n=0, hit=0, edge=0, avg_ret=0, sharpe=0, max_dd=0, kelly=0, pf=0)

    n      = len(rets)
    hit    = float(np.mean(rets > 0)) * 100
    base_h = float(np.mean(base > 0)) * 100
    edge   = hit - base_h
    avg_r  = float(np.mean(rets)) * 100

    # Sharpe anualizado (señales ~252/n por año)
    std    = float(np.std(rets, ddof=1))
    sharpe = (float(np.mean(rets)) / std * np.sqrt(252)) if std > 1e-8 else 0

    # Max Drawdown sobre equity curve de señales
    cum = np.cumprod(1 + rets)
    running_max = np.maximum.accumulate(cum)
    dd = (cum - running_max) / running_max
    max_dd = float(abs(np.min(dd))) * 100

    # Kelly 25% (fraccional)
    wins   = rets[rets > 0]
    losses = rets[rets < 0]
    avg_w  = float(np.mean(wins))  if len(wins)   > 0 else 0
    avg_l  = float(np.mean(losses)) if len(losses) > 0 else 0
    b      = abs(avg_w / avg_l) if abs(avg_l) > 1e-8 else 0
    kelly_raw = (hit/100 * b - (1 - hit/100)) / b if b > 0 else 0
    kelly  = max(0, kelly_raw) * 25  # Kelly 25%

    # Profit Factor
    gross_p = float(np.sum(wins))
    gross_l = float(abs(np.sum(losses)))
    pf = gross_p / gross_l if gross_l > 0 else float('inf')

    return dict(n=n, hit=hit, edge=edge, avg_ret=avg_r,
                sharpe=sharpe, max_dd=max_dd, kelly=kelly, pf=pf)

m_A = metrics(sig_A, base_rets)
m_B = metrics(sig_B, base_rets)
m_C = metrics(sig_C, base_rets)
m_base = dict(
    n=len(base_rets),
    hit=float(np.mean(np.array(base_rets)>0))*100,
    edge=0, avg_ret=float(np.mean(base_rets))*100,
    sharpe=float(np.mean(base_rets)/np.std(base_rets)*np.sqrt(252)) if np.std(base_rets)>0 else 0,
    max_dd=0, kelly=0, pf=0
)

# ── OUTPUT ────────────────────────────────────────────────────────
print(f"\n{'='*62}")
print(f"  RESULTADOS — {TICKER}  ({START[:4]}–{END[:4]})")
print(f"{'='*62}")

STRATS = [
    ("BUY & HOLD (baseline)", m_base),
    ("A  EMA200 solo (>=15%)", m_A),
    ("B  Regimen + Tecnico",   m_B),
    ("C  Regimen + Funda [WEB]", m_C),
]

# Tabla
COLS = ["Estrategia", "N señales", "Hit Rate", "Edge", "Avg Ret 5d", "Sharpe", "Max DD", "Kelly 25%", "Profit F."]
print(f"\n  {'Estrategia':<26} {'N':>5}  {'Hit%':>6}  {'Edge':>6}  {'Avg5d':>6}  {'Sharpe':>6}  {'MaxDD':>6}  {'Kelly':>6}  {'PF':>5}")
print(f"  {'─'*90}")

labels_short = ["BASELINE", "A EMA200", "B Régimen", "C SISTEMA WEB"]
for (name, m), label in zip(STRATS, labels_short):
    hit_s   = f"{m['hit']:.1f}%"
    edge_s  = f"{m['edge']:+.1f}pp" if m['edge'] != 0 else "  —"
    avg_s   = f"{m['avg_ret']:+.2f}%"
    sh_s    = f"{m['sharpe']:.2f}"
    dd_s    = f"{m['max_dd']:.1f}%" if m['max_dd'] > 0 else "  —"
    k_s     = f"{m['kelly']:.1f}%"  if m['kelly'] > 0 else "  —"
    pf_s    = f"{m['pf']:.2f}"      if m['pf'] not in (0, float('inf')) else ("INF" if m['pf']==float('inf') else "—")
    star    = " <-- ESTRATEGIA WEB" if "WEB" in name else ""
    print(f"  {name:<26} {m['n']:>5}  {hit_s:>6}  {edge_s:>6}  {avg_s:>6}  {sh_s:>6}  {dd_s:>6}  {k_s:>6}  {pf_s:>5}{star}")

# Análisis por régimen de Estrategia C
print(f"\n{'='*62}")
print(f"  ANALISIS POR REGIMEN — Estrategia C (la web) en {TICKER}")
print(f"{'='*62}")
regs = ['CALM', 'SLOW_BEAR', 'FAST_CRASH']
print(f"\n  {'Regimen':<14} {'N':>5}  {'Hit%':>6}  {'Avg5d':>7}")
print(f"  {'─'*38}")
for r in regs:
    rets_r = []
    for idx, row in df.iterrows():
        ind = {
            'EMA200_disc': row['EMA200_disc'], 'BB_pctB': row['BB_pctB'],
            'Stoch_K': row['Stoch_K'], 'RSI': row['RSI'],
        }
        stars_proxy = 15 if row['1y_ret'] > 0 else 10
        if row['regime'] == r:
            res = evaluate_signal(ind, r, stars_proxy)
            if res['signal']:
                rets_r.append(row['fwd_ret'])
    if rets_r:
        hit_r = np.mean(np.array(rets_r) > 0) * 100
        avg_r = np.mean(rets_r) * 100
        print(f"  {r:<14} {len(rets_r):>5}  {hit_r:>5.1f}%  {avg_r:>+6.2f}%")
    else:
        print(f"  {r:<14}     0    N/A      N/A")

# Análisis por año (Estrategia C vs Baseline)
print(f"\n{'='*62}")
print(f"  AÑO A AÑO — Estrategia C vs Baseline en {TICKER}")
print(f"{'='*62}")
print(f"\n  {'Año':>4}  {'Señ C':>6}  {'Hit C':>6}  {'Hit base':>8}  {'Edge':>6}")
print(f"  {'─'*42}")
for yr in sorted(set(list(by_year_C.keys()) + list(by_year_A.keys()))):
    c_r = by_year_C.get(yr, [])
    # baseline ese año
    base_yr = df[df.index.year == yr]['fwd_ret'].tolist()
    hit_c    = np.mean(np.array(c_r) > 0) * 100 if c_r else 0
    hit_base = np.mean(np.array(base_yr) > 0) * 100 if base_yr else 0
    edge_yr  = hit_c - hit_base
    edge_s   = f"{edge_yr:+.1f}pp"
    hit_c_s  = f"{hit_c:.1f}%"   if c_r else "   —"
    print(f"  {yr:>4}  {len(c_r):>6}  {hit_c_s:>6}  {hit_base:>7.1f}%  {edge_s:>6}")

print(f"\n{'='*62}")
print(f"  CONCLUSION")
print(f"{'='*62}")

if m_C['n'] > 0:
    # Compare C vs A
    delta_edge = m_C['edge'] - m_A['edge']
    delta_sharpe = m_C['sharpe'] - m_A['sharpe']
    print(f"\n  Estrategia C vs A EMA200 puro:")
    print(f"    Edge:   {m_C['edge']:+.1f}pp vs {m_A['edge']:+.1f}pp  (delta: {delta_edge:+.1f}pp)")
    print(f"    Sharpe: {m_C['sharpe']:.2f} vs {m_A['sharpe']:.2f}  (delta: {delta_sharpe:+.2f})")
    print(f"    Kelly:  {m_C['kelly']:.1f}% vs {m_A['kelly']:.1f}%")
    print(f"\n  La estrategia del sistema web (C) genera {m_C['n']} senales en {TICKER}")
    print(f"  con Hit Rate de {m_C['hit']:.1f}% vs {m_base['hit']:.1f}% del baseline.")
    if m_C['edge'] > 0:
        print(f"  Edge POSITIVO de {m_C['edge']:+.1f}pp sobre buy-and-hold.")
    else:
        print(f"  Edge negativo: la estrategia es mas selectiva, espera mejores condiciones.")
else:
    print(f"\n  Estrategia C no genero senales en {TICKER} en este periodo.")
    print(f"  Razon: {TICKER} es una empresa de calidad que pocas veces cae bajo EMA200.")
    print(f"  Estrategia A (EMA solo): {m_A['n']} senales, {m_A['hit']:.1f}% hit rate.")

print(f"\n  Nota: 'fundamental_stars' es un proxy (1y return > 0 = buena empresa).")
print(f"  En la web usa yahooquery con 16 checks reales para mayor precision.")
print(f"{'='*62}\n")
