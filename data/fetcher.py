import yfinance as yf
import pandas as pd
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

def fetch_history(tickers: list, start: str, end: str) -> dict:
    """
    Descarga historial de OHLCV para una lista de tickers.
    Soluciona el bug de yfinance que devuelve NaN en el día actual
    usando yahooquery para inyectar los precios en tiempo real.
    """
    if not tickers:
        return {}
    
    is_single = len(tickers) == 1
    
    if is_single:
        df = yf.download(tickers[0], start=start, progress=False)
        if df.empty: return {}
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        data_dict = {tickers[0]: df}
    else:
        data = yf.download(tickers, start=start, group_by="ticker", progress=False)
        data_dict = {}
        for t in tickers:
            try:
                df = data[t].dropna(how='all')
                if not df.empty:
                    data_dict[t] = df
            except KeyError:
                continue

    # PATCH: Arreglar filas con Close=NaN (día actual incompleto en yfinance)
    needs_patch = []
    for t, df in data_dict.items():
        if not df.empty and 'Close' in df.columns and pd.isna(df['Close'].iloc[-1]):
            needs_patch.append(t)
            
    if needs_patch:
        try:
            from yahooquery import Ticker
            yq_data = Ticker(needs_patch, asynchronous=True).price
            for t in needs_patch:
                if isinstance(yq_data, dict) and t in yq_data and isinstance(yq_data[t], dict):
                    pt = yq_data[t]
                    df = data_dict[t]
                    # Inyectar datos reales del día
                    idx = df.index[-1]
                    price = pt.get('regularMarketPrice')
                    if price:
                        df.at[idx, 'Close'] = price
                        df.at[idx, 'Open'] = pt.get('regularMarketOpen', price)
                        df.at[idx, 'High'] = pt.get('regularMarketDayHigh', price)
                        df.at[idx, 'Low'] = pt.get('regularMarketDayLow', price)
                        df.at[idx, 'Volume'] = pt.get('regularMarketVolume', 0)
        except Exception as e:
            pass # Si falla yahooquery, hacemos fallback a dropna abajo

    # Limpieza final: eliminar si sigue siendo NaN (si yahooquery falló o no tenía datos)
    final_result = {}
    for t, df in data_dict.items():
        if not df.empty and 'Close' in df.columns:
            df = df.dropna(subset=['Close'])
        if not df.empty:
            final_result[t] = df

    return final_result

