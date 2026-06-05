import pandas as pd

def classify_regime(vix_series: pd.Series) -> pd.Series:
    """
    Para cada día, retorna el régimen del mercado basado en el VIX.
    """
    vix_10d_change = vix_series.pct_change(10) * 100

    # Inicializar con CALM
    regime = pd.Series("CALM", index=vix_series.index)
    
    # SLOW_BEAR
    regime[vix_series > 20] = "SLOW_BEAR"
    
    # FAST_CRASH overrides SLOW_BEAR
    regime[(vix_series > 40) | (vix_10d_change > 50)] = "FAST_CRASH"

    return regime
