import yfinance as yf
import pandas as pd
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

def fetch_history(tickers: list, start: str, end: str) -> dict:
    """
    Descarga historial de OHLCV para una lista de tickers.
    Retorna un diccionario {ticker: DataFrame}.
    """
    if not tickers:
        return {}
    
    if len(tickers) == 1:
        # Se omite 'end' para forzar la descarga de datos intradiarios de hoy
        df = yf.download(tickers[0], start=start, progress=False)
        if df.empty:
            return {}
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        # Fix: eliminar filas con Close=NaN (datos parciales del día actual)
        df = df.dropna(subset=['Close'])
        if df.empty:
            return {}
        return {tickers[0]: df}
    
    # Se omite 'end' para forzar la descarga de datos intradiarios de hoy
    data = yf.download(tickers, start=start, group_by="ticker", progress=False)
    
    result = {}
    for ticker in tickers:
        try:
            df = data[ticker].dropna(how='all')
            # Fix: eliminar filas con Close=NaN (datos parciales del día actual)
            if not df.empty and 'Close' in df.columns:
                df = df.dropna(subset=['Close'])
            if not df.empty:
                result[ticker] = df
        except KeyError:
            continue
            
    return result

