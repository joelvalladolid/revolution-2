# -*- coding: utf-8 -*-
"""
sim_daytrading.py
Simulación de Day Trading en el último mes (Open-to-Close).
Compra en la apertura las acciones que dieron señal el día anterior,
vende al cierre del mismo día.
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
print(f"  SIMULACIÓN DAY TRADING (ÚLTIMO MES) — OPEN TO CLOSE")
print(f"============================================================")

# Fechas
today = datetime.date.today()
start_date = (today - datetime.timedelta(days=400)).strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
sim_start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')

print("[1/3] Descargando VIX y lista S&P 500...")
try:
    vix_df = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.droplevel(1)
    vix_series = vix_df['Close'].dropna()
    regimes = classify_regime(vix_series)
except Exception as e:
    print("Error descargando VIX:", e)
    sys.exit(1)

sp500 = fetch_sp500_tickers_wiki_v2()

print(f"[2/3] Descargando datos de {len(sp500)} empresas (1 año histórico)...")
# Descargar datos
raw_data = yf.download(sp500, start=start_date, end=end_date, group_by="ticker", progress=False, auto_adjust=True)

# Obtener los días de trading del último mes a simular
trading_days = vix_series[vix_series.index >= sim_start_date].index.tolist()
if len(trading_days) == 0:
    print("No hay días de trading en el periodo seleccionado.")
    sys.exit(0)

print(f"Días de simulación: {len(trading_days)} días de trading")

portfolio_log = []
capital_inicial = 10000.0
capital = capital_inicial
historico_capital = [capital]

print(f"[3/3] Ejecutando simulación día a día...")

# Precalcular indicadores por ticker para hacer la simulación rápida
tickers_data = {}
for t in sp500:
    try:
        if len(sp500) == 1:
            df = raw_data.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
        else:
            df = raw_data[t].copy() if t in raw_data.columns.get_level_values(0) else pd.DataFrame()
            
        df = df.dropna(subset=['Close', 'Open'])
        if len(df) < 200:
            continue
            
        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB'] = bollinger_pctB(df)
        df['Stoch_K'] = stochastic_k(df)
        df['RSI'] = rsi(df)
        df['Open_to_Close'] = (df['Close'] - df['Open']) / df['Open'] # Retorno day trading
        
        tickers_data[t] = df
    except:
        pass

for i in range(1, len(trading_days)):
    current_day = trading_days[i]
    prev_day = trading_days[i-1]
    
    # Régimen del día anterior
    regime = regimes.reindex([prev_day]).ffill().fillna('CALM').iloc[0]
    
    signals = []
    
    for t, df in tickers_data.items():
        # Obtener datos hasta prev_day
        df_prev = df[df.index <= prev_day]
        if len(df_prev) < 200: continue
        
        last_row = df_prev.iloc[-1]
        
        ind = {
            'EMA200_disc': last_row['EMA200_disc'],
            'BB_pctB': last_row['BB_pctB'],
            'Stoch_K': last_row['Stoch_K'],
            'RSI': last_row['RSI']
        }
        
        # Filtro fundamental relajado para la simulación rápida (proxy)
        # Asumimos que empresas S&P500 tienen calidad aceptable
        res = evaluate_signal(ind, str(regime), fundamental_stars=15)
        
        if res['signal']:
            # Verificar si hay datos para el current_day (para operar)
            if current_day in df.index:
                day_ret = df.loc[current_day, 'Open_to_Close']
                if not pd.isna(day_ret):
                    signals.append({'ticker': t, 'return': day_ret})
    
    # Calcular PnL del día
    if len(signals) > 0:
        avg_ret = np.mean([s['return'] for s in signals])
        pnl = capital * avg_ret
        capital += pnl
        
        win_trades = sum(1 for s in signals if s['return'] > 0)
        
        log_entry = {
            'Date': current_day.strftime('%Y-%m-%d'),
            'Regime': regime,
            'Signals': len(signals),
            'WinRate': (win_trades/len(signals))*100,
            'AvgRet': avg_ret*100,
            'Capital': capital
        }
        portfolio_log.append(log_entry)
        print(f"  {log_entry['Date']} | Reg: {regime:<10} | Acciones: {len(signals):>2} | WinRate: {log_entry['WinRate']:>5.1f}% | Retorno: {log_entry['AvgRet']:>+5.2f}% | Cap: ${capital:,.2f}")
    else:
        # No hay señales
        log_entry = {
            'Date': current_day.strftime('%Y-%m-%d'),
            'Regime': regime,
            'Signals': 0,
            'WinRate': 0.0,
            'AvgRet': 0.0,
            'Capital': capital
        }
        portfolio_log.append(log_entry)
        print(f"  {log_entry['Date']} | Reg: {regime:<10} | Acciones:  0 | Sin operaciones. Esperando.")
        
    historico_capital.append(capital)

print(f"\n============================================================")
print(f"  RESULTADOS DE LA SIMULACIÓN (Últimos 30 días)")
print(f"============================================================")
dias_operados = sum(1 for x in portfolio_log if x['Signals'] > 0)
total_trades = sum(x['Signals'] for x in portfolio_log)

if dias_operados > 0:
    retorno_total = ((capital / capital_inicial) - 1) * 100
    retornos_diarios = [x['AvgRet']/100 for x in portfolio_log if x['Signals'] > 0]
    win_rate_dias = sum(1 for x in retornos_diarios if x > 0) / dias_operados * 100
    
    print(f"  Capital Inicial:    ${capital_inicial:,.2f}")
    print(f"  Capital Final:      ${capital:,.2f}")
    print(f"  Retorno Total:      {retorno_total:+.2f}%")
    print(f"  Días Analizados:    {len(portfolio_log)}")
    print(f"  Días con Señal:     {dias_operados}")
    print(f"  Total Operaciones:  {total_trades}")
    print(f"  Win Rate de Días:   {win_rate_dias:.1f}%")
    print(f"  Promedio x Día Op:  {np.mean(retornos_diarios)*100:+.2f}%")
else:
    print(f"  No hubo señales en el último mes.")
    print(f"  Razón: El mercado estuvo mayormente en régimen CALM con índices en máximos,")
    print(f"  lo cual significa que muy pocas acciones cumplen el requisito de fuerte descuento técnico.")
print(f"============================================================\n")
