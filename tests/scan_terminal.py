# -*- coding: utf-8 -*-
"""
scan_terminal.py
Replica la logica del Radar S&P 500. Busca acciones con descuento bajo EMA200.
EMA200_disc POSITIVO = precio esta DEBAJO de EMA200 (oportunidad).
EMA200_disc NEGATIVO = precio esta ENCIMA de EMA200 (no aplica).
"""
import sys, os, datetime, warnings, time
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pandas as pd
import numpy as np
import yfinance as yf

from lab.regime_detector import classify_regime
from lab.indicators import ema_discount, bollinger_pctB, stochastic_k, rsi, mfi, macd_hist, williams_r, adx
from lab.rule_engine import evaluate_signal, RULE_SETS, calculate_confidence
from lab.monte_carlo import simulate_price_paths
from data.fetcher import fetch_history
from lab_tickers import fetch_sp500_tickers_wiki_v2

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

THRESHOLDS_BY_REGIME = {
    "CALM":       {"EMA200_disc": 8.0,  "BB_pctB": 0.15, "Stoch_K": 20},
    "SLOW_BEAR":  {"EMA200_disc": 12.0, "BB_pctB": 0.20, "Stoch_K": 20},
    "FAST_CRASH": {"EMA200_disc": 15.0, "BB_pctB": 999,  "Stoch_K": 999},
}

# ── 1. Regimen actual ─────────────────────────────────────────────────────────
print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
print(f"{BOLD}{CYAN}  FRANCOTIRADOR DE LIQUIDEZ -- SCAN TERMINAL{RESET}")
print(f"{BOLD}{CYAN}{'='*65}{RESET}")
print(f"  Fecha: {datetime.date.today().strftime('%d/%m/%Y %H:%M')}")

print(f"\n{BOLD}[1/4] Obteniendo regimen de mercado (VIX)...{RESET}")
try:
    vix_data = yf.Ticker("^VIX").history(period="3mo")
    vix_series = vix_data['Close']
    current_vix = float(vix_series.iloc[-1])
    regimes = classify_regime(vix_series)
    regime = str(regimes.iloc[-1])
    vix_10d_ago = float(vix_series.iloc[-10]) if len(vix_series) >= 10 else current_vix
    vix_change = ((current_vix - vix_10d_ago) / vix_10d_ago) * 100
    tnx = yf.Ticker("^TNX").history(period="5d")
    tnx_yield = float(tnx['Close'].iloc[-1]) if not tnx.empty else 4.2
except Exception as e:
    print(f"  Error VIX: {e}")
    regime, current_vix, vix_change, tnx_yield = "CALM", 15.0, 0.0, 4.2

regime_color = {"CALM": CYAN, "SLOW_BEAR": YELLOW, "FAST_CRASH": RED}.get(regime, CYAN)
regime_label = {"CALM": "[CALM - Mercado tranquilo]",
                "SLOW_BEAR": "[SLOW BEAR - Mercado bajando]",
                "FAST_CRASH": "[FAST CRASH - Crash rapido]"}.get(regime, regime)

print(f"  VIX actual : {BOLD}{current_vix:.2f}{RESET}  ({vix_change:+.1f}% vs 10d)")
print(f"  TNX Yield  : {tnx_yield:.2f}%")
print(f"  Regimen    : {regime_color}{BOLD}{regime_label}{RESET}")

rules = RULE_SETS.get(regime, RULE_SETS["CALM"])
dyn_th = THRESHOLDS_BY_REGIME.get(regime, THRESHOLDS_BY_REGIME["CALM"])["EMA200_disc"]

print(f"  Umbral EMA : {BOLD}{dyn_th}%{RESET} (precio debe estar {dyn_th}% por debajo de EMA200)")
print(f"  Fundamental: {'Requerido' if rules['requires_fundamental'] else 'Opcional'} (min {rules['min_stars']} stars)")

# ── 2. Lista S&P 500 ──────────────────────────────────────────────────────────
print(f"\n{BOLD}[2/4] Obteniendo lista S&P 500...{RESET}")
sp500 = fetch_sp500_tickers_wiki_v2()
print(f"  Tickers: {len(sp500)}")

# ── 3. Descarga bulk con yfinance (mucho mas rapido que uno a uno) ─────────────
print(f"\n{BOLD}[3/4] Descargando datos en bloque...{RESET}")
end_date   = datetime.date.today().strftime('%Y-%m-%d')
start_date = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

t0 = time.time()
# Descargar en chunks de 100 para no saturar
CHUNK = 100
all_data = {}

for i in range(0, len(sp500), CHUNK):
    chunk = sp500[i:i+CHUNK]
    pct = int(((i + len(chunk)) / len(sp500)) * 100)
    print(f"  Descargando chunk {i//CHUNK + 1}/{(len(sp500)-1)//CHUNK + 1} ({pct}%)...", end="\r")
    try:
        raw = yf.download(chunk, start=start_date, end=end_date,
                          group_by="ticker", progress=False, auto_adjust=True)
        for t in chunk:
            try:
                if len(chunk) == 1:
                    df = raw.copy()
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.droplevel(1)
                else:
                    df = raw[t].copy() if t in raw.columns.get_level_values(0) else pd.DataFrame()
                df = df.dropna(how='all')
                if not df.empty and len(df) >= 252:
                    all_data[t] = df
            except Exception:
                pass
    except Exception as e:
        print(f"\n  chunk error: {e}")

elapsed = time.time() - t0
print(f"\n  Datos validos: {GREEN}{BOLD}{len(all_data)}{RESET} tickers  ({elapsed:.1f}s)")

# ── 4. Calculo de indicadores y senales ───────────────────────────────────────
print(f"\n{BOLD}[4/4] Calculando indicadores y senales...{RESET}")

results_signal   = []
results_proximos = []

for idx, (ticker, df) in enumerate(all_data.items()):
    if (idx + 1) % 50 == 0 or (idx + 1) == len(all_data):
        pct = int(((idx + 1) / len(all_data)) * 100)
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  [{bar}] {pct:3d}% | Senales: {GREEN}{len(results_signal)}{RESET} | Proximos: {YELLOW}{len(results_proximos)}{RESET}    ", end="\r")

    try:
        df = df.copy()
        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB']     = bollinger_pctB(df)
        df['Stoch_K']     = stochastic_k(df)
        df['RSI']         = rsi(df)
        df['MFI']         = mfi(df)
        df['MACD_hist']   = macd_hist(df)
        df['Williams_R']  = williams_r(df)
        df['ADX']         = adx(df)

        last = df.iloc[-1]
        def safe(col):
            v = last.get(col, np.nan)
            return float(v) if pd.notna(v) else float('nan')

        ind_vals = {
            'EMA200_disc': safe('EMA200_disc'),
            'BB_pctB':     safe('BB_pctB'),
            'Stoch_K':     safe('Stoch_K'),
            'RSI':         safe('RSI'),
            'MFI':         safe('MFI'),
            'MACD_rising': bool(last.get('MACD_hist', 0) > 0) if pd.notna(last.get('MACD_hist', np.nan)) else False,
            'Williams_R':  safe('Williams_R'),
            'ADX':         safe('ADX'),
        }
        price    = float(last['Close'])
        ema_val  = ind_vals['EMA200_disc']

        # Check primary indicator
        primary_met = False
        for ind_name, th in rules["indicators"]["primary"]:
            val = ind_vals.get(ind_name, float('nan'))
            if pd.isna(val): continue
            direction = 'above' if ind_name == 'EMA200_disc' else 'below'
            if (direction == 'above' and val >= th) or (direction == 'below' and val <= th):
                primary_met = True
                break

        signal_res = evaluate_signal(ind_vals, regime, fundamental_stars=0)

        rec = {
            "ticker":      ticker,
            "price":       price,
            "ema_disc":    ema_val,
            "ind_vals":    ind_vals,
            "primary_met": primary_met,
            "signal":      signal_res,
            "df":          df,
        }

        if signal_res['signal']:
            results_signal.append(rec)
        elif primary_met or (not pd.isna(ema_val) and ema_val >= dyn_th * 0.5):
            results_proximos.append(rec)

    except Exception:
        pass

print(f"\n")

# ── RESULTADOS ────────────────────────────────────────────────────────────────
print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
print(f"{BOLD}  RESULTADOS DEL SCAN -- {datetime.date.today().strftime('%d/%m/%Y')}{RESET}")
print(f"{BOLD}  Regimen: {regime_color}{regime}{RESET}  |  VIX: {current_vix:.2f}  |  Umbral EMA: {dyn_th}%")
print(f"{BOLD}{CYAN}{'='*65}{RESET}")

# Senales activas
results_signal.sort(key=lambda x: x['signal']['confidence'], reverse=True)

if results_signal:
    print(f"\n{BOLD}{GREEN}>>> SENALES ACTIVAS HOY ({len(results_signal)} encontradas) <<<{RESET}")
    print(f"\n  {DIM}NOTA: EMA200% positivo = precio esta debajo de la media (descuento real){RESET}")
    print(f"\n  {'TICKER':<8} {'PRECIO':>8} {'EMA200%':>9} {'RSI':>6} {'STOCH':>6} {'BB%B':>5} {'CONF':>6}  RAZON")
    print(f"  {'--'*32}")
    for r in results_signal:
        iv = r['ind_vals']
        ema_s   = f"{r['ema_disc']:+.1f}%" if not pd.isna(r['ema_disc']) else "N/A"
        rsi_s   = f"{iv.get('RSI', float('nan')):.1f}"    if not pd.isna(iv.get('RSI', float('nan'))) else "N/A"
        stoch_s = f"{iv.get('Stoch_K', float('nan')):.1f}" if not pd.isna(iv.get('Stoch_K', float('nan'))) else "N/A"
        bb_s    = f"{iv.get('BB_pctB', float('nan')):.2f}" if not pd.isna(iv.get('BB_pctB', float('nan'))) else "N/A"
        conf    = r['signal']['confidence']
        triggered = ', '.join(r['signal'].get('indicators_triggered', []))
        conf_color = GREEN if conf >= 75 else YELLOW
        print(f"  {GREEN}{BOLD}{r['ticker']:<8}{RESET} ${r['price']:>7.2f} {GREEN}{ema_s:>9}{RESET} {rsi_s:>6} {stoch_s:>6} {bb_s:>5} {conf_color}{conf:>5.0f}%{RESET}  [{triggered}]")
else:
    print(f"\n  {YELLOW}>>> SIN SENALES ACTIVAS HOY <<<{RESET}")
    print(f"\n  Por que no hay senales:")
    print(f"  1. Regimen: {regime_color}{BOLD}{regime}{RESET}")
    print(f"  2. Requiere EMA200 discount >= {BOLD}{dyn_th}%{RESET} (precio debajo de EMA200)")
    if rules['requires_fundamental']:
        print(f"  3. Tambien requiere calidad fundamental >= {rules['min_stars']} stars")
    print(f"\n  {DIM}En mercado CALM la mayoria de acciones estan SOBRE su EMA200")
    print(f"  (precios subieron mucho). El sistema espera correcciones.{RESET}")

# Proximos
proximos = sorted(results_proximos,
                  key=lambda x: x['ema_disc'] if not pd.isna(x['ema_disc']) else -999,
                  reverse=True)[:20]

if proximos:
    print(f"\n{BOLD}{YELLOW}>>> PROXIMOS A SENAL -- Top {len(proximos)} con mayor descuento EMA200 <<<{RESET}")
    print(f"\n  {DIM}Estos tienen descuento parcial. Necesitan mas caida para activar senal.{RESET}")
    print(f"\n  {'TICKER':<8} {'PRECIO':>8} {'EMA200%':>9} {'RSI':>6} {'STOCH':>6} {'Le falta':>10}")
    print(f"  {'--'*30}")
    for r in proximos:
        iv = r['ind_vals']
        ema_val = r['ema_disc']
        ema_s   = f"{ema_val:+.1f}%" if not pd.isna(ema_val) else "N/A"
        rsi_s   = f"{iv.get('RSI', float('nan')):.1f}"     if not pd.isna(iv.get('RSI', float('nan'))) else "N/A"
        stoch_s = f"{iv.get('Stoch_K', float('nan')):.1f}" if not pd.isna(iv.get('Stoch_K', float('nan'))) else "N/A"
        falta   = dyn_th - ema_val if not pd.isna(ema_val) else float('nan')
        falta_s = f"falta {falta:.1f}%" if not pd.isna(falta) and falta > 0 else "LISTO"
        color = GREEN if falta_s == "LISTO" else (YELLOW if falta < 3 else RESET)
        print(f"  {YELLOW}{r['ticker']:<8}{RESET} ${r['price']:>7.2f} {YELLOW}{ema_s:>9}{RESET} {rsi_s:>6} {stoch_s:>6} {color}{falta_s:>10}{RESET}")

# Estadisticas de EMA
ema_vals_all = []
for ticker, df in all_data.items():
    try:
        disc = ema_discount(df)
        v = float(disc.iloc[-1])
        if not pd.isna(v):
            ema_vals_all.append((ticker, v))
    except:
        pass

ema_vals_all.sort(key=lambda x: x[1], reverse=True)

print(f"\n{BOLD}>>> DISTRIBUCION EMA200 DISCOUNT (mercado completo) <<<{RESET}")
above_ema   = sum(1 for _, v in ema_vals_all if v < 0)
below_5pct  = sum(1 for _, v in ema_vals_all if 0 <= v < 5)
below_8pct  = sum(1 for _, v in ema_vals_all if 5 <= v < dyn_th)
beyond_th   = sum(1 for _, v in ema_vals_all if v >= dyn_th)
total_ema   = len(ema_vals_all)

print(f"  Sobre EMA200 (precio alto)      : {above_ema:3d}  ({100*above_ema/max(total_ema,1):.0f}%) -- NO aplican")
print(f"  0% a 5% bajo EMA               : {below_5pct:3d}  ({100*below_5pct/max(total_ema,1):.0f}%)")
print(f"  5% a {dyn_th}% bajo EMA              : {below_8pct:3d}  ({100*below_8pct/max(total_ema,1):.0f}%)")
print(f"  {GREEN}>= {dyn_th}% bajo EMA (ZONA SENAL){RESET}   : {GREEN}{BOLD}{beyond_th:3d}{RESET}  ({GREEN}{100*beyond_th/max(total_ema,1):.0f}%{RESET})")

if ema_vals_all:
    print(f"\n  Top 10 con MAYOR descuento EMA200 hoy:")
    print(f"  {'TICKER':<8} {'EMA200%':>9}  {'PRECIO':>8}")
    for ticker, v in ema_vals_all[:10]:
        try:
            precio = float(all_data[ticker]['Close'].iloc[-1])
            color = GREEN if v >= dyn_th else YELLOW
            print(f"  {color}{ticker:<8}{RESET} {color}{v:+.1f}%{RESET}     ${precio:>7.2f}")
        except:
            pass

# Funnel final
print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
print(f"{BOLD}  FUNNEL RESUMEN{RESET}")
print(f"  S&P 500 total       : {len(sp500)}")
print(f"  Datos validos       : {len(all_data)}")
print(f"  Superan umbral EMA  : {beyond_th}")
print(f"  Senales activas     : {GREEN}{BOLD}{len(results_signal)}{RESET}")
print(f"  Proximos a senal    : {YELLOW}{len(proximos)}{RESET}")
print(f"{BOLD}{CYAN}{'='*65}{RESET}\n")
