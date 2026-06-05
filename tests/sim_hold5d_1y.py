# -*- coding: utf-8 -*-
"""
sim_hold5d_1y.py
Simulación de la estrategia en el ÚLTIMO AÑO, pero con Hold de 5 días.
Compra al cierre del día de la señal, y vende al cierre 5 días después.
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

today = datetime.date.today()
start_date = (today - datetime.timedelta(days=730)).strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
sim_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')

vix_df = yf.download("^VIX", start=start_date, end=end_date, progress=False)
if isinstance(vix_df.columns, pd.MultiIndex):
    vix_df.columns = vix_df.columns.droplevel(1)
vix_series = vix_df['Close'].dropna()
regimes = classify_regime(vix_series)

sp500 = fetch_sp500_tickers_wiki_v2()
raw_data = yf.download(sp500, start=start_date, end=end_date, group_by="ticker", progress=False, auto_adjust=True)

trading_days = vix_series[vix_series.index >= sim_start_date].index.tolist()

tickers_data = {}
for t in sp500:
    try:
        df = raw_data[t].copy() if t in raw_data.columns.get_level_values(0) else pd.DataFrame()
        df = df.dropna(subset=['Close'])
        if len(df) < 200: continue
            
        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB'] = bollinger_pctB(df)
        df['Stoch_K'] = stochastic_k(df)
        df['RSI'] = rsi(df)
        
        # El retorno a 5 días
        df['Ret_5d'] = (df['Close'].shift(-5) / df['Close']) - 1
        tickers_data[t] = df
    except:
        pass

capital_inicial = 10000.0
capital = capital_inicial
portfolio_log = []

for i in range(1, len(trading_days) - 5): # Evitar los últimos 5 días donde no hay retorno 5d
    current_day = trading_days[i]
    prev_day = trading_days[i-1]
    
    regime = regimes.reindex([prev_day]).ffill().fillna('CALM').iloc[0]
    signals = []
    
    for t, df in tickers_data.items():
        if prev_day not in df.index or current_day not in df.index:
            continue
            
        last_row = df.loc[prev_day]
        ind = {
            'EMA200_disc': last_row['EMA200_disc'],
            'BB_pctB': last_row['BB_pctB'],
            'Stoch_K': last_row['Stoch_K'],
            'RSI': last_row['RSI']
        }
        res = evaluate_signal(ind, str(regime), fundamental_stars=15)
        
        if res['signal']:
            ret_5d = df.loc[current_day, 'Ret_5d']
            if not pd.isna(ret_5d):
                signals.append(ret_5d)
    
    if len(signals) > 0:
        avg_ret = np.mean(signals)
        
        # En una simulación real de hold 5d, el capital se traslapa.
        # Para hacer la comparativa simple del edge, asumimos que cada día se invierte 
        # una fracción del capital o medimos el promedio de trades.
        # Aquí sumamos el retorno de los trades al log.
        portfolio_log.append({'Date': current_day, 'Signals': len(signals), 'Ret': avg_ret})

if len(portfolio_log) > 0:
    all_rets = [x['Ret'] for x in portfolio_log]
    # Retorno acumulado asumiendo reinversión continua (aproximación)
    cum_ret = np.prod([1 + r for r in all_rets]) - 1
    
    print(f"HOLD 5 DÍAS")
    print(f"Total Días con Señal: {len(all_rets)}")
    print(f"Win Rate Días: {np.mean(np.array(all_rets) > 0) * 100:.1f}%")
    print(f"Promedio por operación de 5 días: {np.mean(all_rets) * 100:.2f}%")
    
    # Capital de 10k iterado (modelo simple asumiendo que metes todo cada 5 días, que no es exacto, pero da idea)
    # Mejor mostramos la ganancia promedio de cada trade
else:
    print("Sin señales")
