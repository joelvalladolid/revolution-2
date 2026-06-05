import sys, os
sys.path.insert(0, os.path.abspath('.'))
from data.fetcher import fetch_history
from lab.indicators import ema_discount, bollinger_pctB, stochastic_k
from lab.regime_detector import classify_regime
import yfinance as yf
import pandas as pd

# 1. Régimen actual
vix_df = yf.download('^VIX', period='60d', progress=False)
if isinstance(vix_df.columns, pd.MultiIndex):
    vix = vix_df['Close'].iloc[:, 0]
else:
    vix = vix_df['Close']
regime_series = classify_regime(vix)
today_regime = regime_series.iloc[-1]
print(f"RÉGIMEN HOY: {today_regime}")
print(f"VIX actual: {vix.iloc[-1]:.1f}")

# 2. Muestra de 20 tickers — cuántos tienen EMA200 discount significativo
sample = ['AAPL','MSFT','NVDA','META','GOOGL','AMZN','TSLA','JPM','V','MA',
          'UNH','HD','COST','AVGO','LLY','ABBV','MRK','PFE','XOM','CVX']

results = []
for ticker in sample:
    try:
        df = yf.download(ticker, period='300d', progress=False)
        if df.empty:
            continue
            
        # Para versiones recientes de yfinance donde las columnas pueden ser MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df['EMA200'] = df['Close'].ewm(span=200).mean()
        df['disc'] = (df['EMA200'] - df['Close']) / df['EMA200'] * 100
        last_disc = df['disc'].iloc[-1]
        last_bb = bollinger_pctB(df).iloc[-1]
        last_stoch = stochastic_k(df).iloc[-1]
        results.append({
            'ticker': ticker,
            'ema200_disc': round(last_disc, 2),
            'bb_pctB': round(last_bb, 3),
            'stoch_k': round(last_stoch, 1),
            'pass_15': last_disc >= 15,
            'pass_12': last_disc >= 12,
            'pass_8':  last_disc >= 8,
        })
    except Exception as e:
        print(f"Error {ticker}: {e}")

if results:
    df_r = pd.DataFrame(results).sort_values('ema200_disc', ascending=False)
    print(df_r.to_string())
    print(f"\nPasan disc>=15: {df_r['pass_15'].sum()}/{len(results)}")
    print(f"Pasan disc>=12: {df_r['pass_12'].sum()}/{len(results)}")
    print(f"Pasan disc>=8:  {df_r['pass_8'].sum()}/{len(results)}")
else:
    print("No se obtuvieron resultados de los tickers.")
