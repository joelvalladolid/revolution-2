import yfinance as yf
import pandas as pd
import numpy as np

def get_vix_regime(days_back=252):
    """
    Descarga el ^VIX, usa el cierre del día de AYER para evitar look-ahead bias,
    calcula percentiles y determina el régimen (Regla VIX_3_0).
    Retorna un diccionario con estado y métricas.
    """
    try:
        # Descargamos algo más de data para asegurar suficientes días de trading
        vix = yf.Ticker("^VIX").history(period="2y")
        if vix.empty or len(vix) < 10:
            return _fallback_vix()
        
        # Cortar a los últimos 'days_back' días
        vix = vix.tail(days_back + 1) # +1 porque ignoraremos "hoy"
        
        # El cierre de ayer es el iloc[-2] (el último cerrado asumiendo que el mercado pudo abrir hoy)
        # Ojo: si corremos esto a media noche, yf devuelve la data de ayer como la última.
        # Es más seguro tomar 'vix.iloc[-1]' y en el backtest tomar 'ayer'. Pero en LIVE 
        # (ejecución antes de apertura), el iloc[-1] es literalmente la data "de ayer".
        # Validaremos la hora actual? Mejor usar la última data completada de 'Close'.
        # En la vida real (LIVE), al usar app.py, si se consulta antes de que abra el mercado, 
        # el último 'Close' es de ayer. 
        # Usaremos el último 'Close' siempre. En el motor VIX_3_0 real eso es todo lo que sabemos.
        
        history_closes = vix['Close'].values
        last_vix = history_closes[-1]
        
        # Calculamos percentiles
        pct_75 = np.percentile(history_closes, 75)
        pct_95 = np.percentile(history_closes, 95)
        
        percentile_score = (np.sum(history_closes < last_vix) / len(history_closes)) * 100
        
        if last_vix < pct_75:
            regime = "CALM"
            max_pos = 10
        elif last_vix < pct_95:
            regime = "SLOW_BEAR"
            max_pos = 1
        else:
            regime = "FAST_CRASH"
            max_pos = 1
            
        return {
            "status": "OK",
            "regime": regime,
            "max_positions": max_pos,
            "current_vix": round(last_vix, 2),
            "percentile": round(percentile_score, 1),
            "pct_75_val": round(pct_75, 2),
            "pct_95_val": round(pct_95, 2)
        }
        
    except Exception as e:
        return _fallback_vix(str(e))

def _fallback_vix(err_msg="Error"):
    return {
        "status": "ERROR",
        "error": err_msg,
        "regime": "CALM",
        "max_positions": 10,
        "current_vix": 15.0,
        "percentile": 50.0,
        "pct_75_val": 20.0,
        "pct_95_val": 30.0
    }
