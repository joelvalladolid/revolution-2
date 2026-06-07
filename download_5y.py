import os
import yfinance as yf
import pandas as pd
from lab_tickers import fetch_sp500_tickers_wiki_v2

def main():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_5y")
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    tickers = fetch_sp500_tickers_wiki_v2()
    print(f"Tickers encontrados: {len(tickers)}")
    
    for t in tickers:
        file_path = os.path.join(folder, f"{t}.parquet")
        if os.path.exists(file_path):
            continue
        try:
            print(f"Descargando {t}...")
            df = yf.Ticker(t).history(period="5y")
            if not df.empty:
                df.to_parquet(file_path)
        except Exception as e:
            print(f"Error {t}: {e}")

if __name__ == '__main__':
    main()
