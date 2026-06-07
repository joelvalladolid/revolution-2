# -*- coding: utf-8 -*-
"""
sim_daytrading_1y.py
Simulación de Day Trading en el ÚLTIMO AÑO (Open-to-Close).
Compra en la apertura las acciones S&P500 que dieron señal, vende al cierre.
Compara contra Buy & Hold del S&P500 (SPY).
"""
import sys, os, warnings, datetime
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
from lab.indicators import ema_discount, bollinger_pctB, stochastic_k, rsi
from lab.rule_engine import evaluate_signal
from lab_tickers import fetch_sp500_tickers_wiki_v2

print(f"============================================================")
print(f"  SIMULACIÓN DAY TRADING S&P500 (ÚLTIMO AÑO) — OPEN TO CLOSE")
print(f"============================================================")

today = datetime.date.today()
start_date = (today - datetime.timedelta(days=730)).strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
sim_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')

print("[1/3] Descargando VIX, SPY (Benchmark) y lista S&P 500...")
try:
    vix_df = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    spy_df = yf.download("SPY", start=start_date, end=end_date, progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.droplevel(1)
        spy_df.columns = spy_df.columns.droplevel(1)
    vix_series = vix_df['Close'].dropna()
    regimes = classify_regime(vix_series)
except Exception as e:
    print("Error descargando VIX/SPY:", e)
    sys.exit(1)

sp500 = fetch_sp500_tickers_wiki_v2()

print(f"[2/3] Descargando datos de {len(sp500)} empresas (2 años históricos)...")
raw_data = yf.download(sp500, start=start_date, end=end_date, group_by="ticker", progress=False, auto_adjust=True)

trading_days = vix_series[vix_series.index >= sim_start_date].index.tolist()
if len(trading_days) == 0:
    print("No hay días de trading en el periodo seleccionado.")
    sys.exit(0)

print(f"Días de simulación: {len(trading_days)} días de trading")

portfolio_log = []
capital_inicial = 10000.0
capital = capital_inicial

print(f"[3/3] Ejecutando simulación día a día...")

tickers_data = {}
for t in sp500:
    try:
        df = raw_data[t].copy() if t in raw_data.columns.get_level_values(0) else pd.DataFrame()
        df = df.dropna(subset=['Close', 'Open'])
        if len(df) < 200: continue
            
        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB'] = bollinger_pctB(df)
        df['Stoch_K'] = stochastic_k(df)
        df['RSI'] = rsi(df)
        df['Open_to_Close'] = (df['Close'] - df['Open']) / df['Open']
        tickers_data[t] = df
    except:
        pass

for i in range(1, len(trading_days)):
    current_day = trading_days[i]
    prev_day = trading_days[i-1]
    
    regime = regimes.reindex([prev_day]).ffill().fillna('CALM').iloc[0]
    signals = []
    
    for t, df in tickers_data.items():
        df_prev = df[df.index <= prev_day]
        if len(df_prev) < 200: continue
        
        last_row = df_prev.iloc[-1]
        ind = {
            'EMA200_disc': last_row['EMA200_disc'],
            'BB_pctB': last_row['BB_pctB'],
            'Stoch_K': last_row['Stoch_K'],
            'RSI': last_row['RSI']
        }
        res = evaluate_signal(ind, str(regime), fundamental_stars=15)
        
        if res['signal'] and current_day in df.index:
            day_ret = df.loc[current_day, 'Open_to_Close']
            if not pd.isna(day_ret):
                signals.append(day_ret)
    
    if len(signals) > 0:
        avg_ret = np.mean(signals)
        capital += capital * avg_ret
        win_trades = sum(1 for s in signals if s > 0)
        portfolio_log.append({
            'Date': current_day, 'Regime': regime, 'Signals': len(signals),
            'AvgRet': avg_ret, 'Capital': capital
        })
    else:
        portfolio_log.append({
            'Date': current_day, 'Regime': regime, 'Signals': 0,
            'AvgRet': 0.0, 'Capital': capital
        })

print(f"\n============================================================")
print(f"  RESULTADOS DE LA SIMULACIÓN (Último Año)")
print(f"============================================================")

dias_operados = sum(1 for x in portfolio_log if x['Signals'] > 0)
total_trades = sum(x['Signals'] for x in portfolio_log)

spy_start_price = spy_df[spy_df.index >= sim_start_date]['Close'].iloc[0]
spy_end_price = spy_df[spy_df.index <= trading_days[-1]]['Close'].iloc[-1]
spy_return = ((spy_end_price / spy_start_price) - 1) * 100

retorno_total = ((capital / capital_inicial) - 1) * 100
retornos_diarios = [x['AvgRet'] for x in portfolio_log if x['Signals'] > 0]
win_rate_dias = (sum(1 for x in retornos_diarios if x > 0) / dias_operados * 100) if dias_operados > 0 else 0

print(f"  Capital Inicial:    ${capital_inicial:,.2f}")
print(f"  Capital Final:      ${capital:,.2f}")
print(f"  Retorno Estrategia: {retorno_total:+.2f}%")
print(f"  Retorno S&P 500:    {spy_return:+.2f}% (Buy & Hold)")
print(f"  --------------------------------------------------------")
print(f"  Días Analizados:    {len(portfolio_log)}")
print(f"  Días con Señal:     {dias_operados}")
print(f"  Total Operaciones:  {total_trades}")
print(f"  Win Rate de Días:   {win_rate_dias:.1f}%")
print(f"  Promedio x Día Op:  {np.mean(retornos_diarios)*100:+.2f}%" if dias_operados > 0 else "N/A")
print(f"============================================================\n")
