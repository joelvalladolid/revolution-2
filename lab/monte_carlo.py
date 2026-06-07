import numpy as np
import pandas as pd
from scipy.stats import genpareto

def calculate_garch_volatility(returns: pd.Series, alpha: float = 0.05) -> float:
    """
    Calcula una proxy de volatilidad GARCH(1,1) usando EWMA
    para capturar el régimen de volatilidad más reciente.
    """
    # Usamos EWMA (Exponential Weighted Moving Average) como proxy rápido para GARCH variance
    # Lambda = 1 - alpha. alpha = 0.05 -> lambda = 0.95, similar al GARCH param de JP Morgan RiskMetrics
    var_ewma = returns.ewm(alpha=alpha, adjust=False).var().iloc[-1]
    # Si var es NaN o 0, usamos std hist
    if pd.isna(var_ewma) or var_ewma == 0:
        return returns.std()
    return np.sqrt(var_ewma)

def calculate_evt_stop(returns: pd.Series, current_price: float, tail_fraction: float = 0.10, risk_quantile: float = 0.01) -> dict:
    """
    Aplica Extreme Value Theory (EVT) en la cola izquierda de retornos
    para estimar la máxima caída esperada y calibrar el stop loss.
    """
    # Filtramos la cola izquierda (los peores días)
    left_tail = returns[returns < 0]
    if len(left_tail) < 20:
        # Si no hay suficientes datos, fallback a un percentil empírico simple
        p_stop = returns.quantile(risk_quantile)
        stop_price = current_price * (1 + p_stop)
        return {"stop_pct": float(p_stop), "stop_price": float(stop_price), "method": "empirical_percentile"}

    # Umbral es el percentil 10 de todos los retornos (peores 10%)
    threshold = returns.quantile(tail_fraction)
    exceedances = threshold - left_tail[left_tail <= threshold]
    
    if len(exceedances) < 5:
        p_stop = returns.quantile(risk_quantile)
        stop_price = current_price * (1 + p_stop)
        return {"stop_pct": float(p_stop), "stop_price": float(stop_price), "method": "empirical_percentile"}

    # Ajustar Generalized Pareto Distribution
    # genpareto.fit devuelve shape (c), loc, scale
    try:
        c, loc, scale = genpareto.fit(exceedances)
        # Calcular el cuantil bajo EVT para el risk_quantile (ej: 1% risk total)
        # P(X > x) = (N_tail / N_total) * (1 + c*(x - loc)/scale)^(-1/c)
        prob_tail = len(exceedances) / len(returns)
        # Queremos x tal que prob_tail * (1 + c*x/scale)^(-1/c) = risk_quantile
        # Despejamos x:
        if risk_quantile >= prob_tail:
            # El cuantil pedido está fuera de la cola de EVT, usar umbral
            x = 0
        elif abs(c) > 1e-6:
            x = (scale / c) * (((prob_tail / risk_quantile) ** c) - 1)
        else:
            x = scale * np.log(prob_tail / risk_quantile)
            
        evt_return = threshold - x
        stop_price = current_price * (1 + evt_return)
        return {"stop_pct": float(evt_return), "stop_price": float(stop_price), "method": "evt_gpd"}
    except Exception:
        p_stop = returns.quantile(risk_quantile)
        stop_price = current_price * (1 + p_stop)
        return {"stop_pct": float(p_stop), "stop_price": float(stop_price), "method": "empirical_fallback"}


def simulate_price_paths(
    current_price: float,
    historical_returns: pd.Series,
    horizon_days: int = 1, # FORZADO A 1 PARA INTRADAY
    n_simulations: int = 10_000,
    fast_mode: bool = False
) -> dict:
    """
    Modelo Bootstrap Monte Carlo escalado con GARCH y EVT.
    Optimizado para simulaciones Intraday (horizon=1).
    Con fast_mode=True se ignora EVT para backtesting veloz.
    """
    historical_returns = historical_returns.dropna()
    
    if len(historical_returns) < 50:
        return {
            "prob_positive": 0.0, "prob_gt_1pct": 0.0, "prob_gt_2pct": 0.0, "prob_gt_5pct": 0.0,
            "p10": 0.0, "p50": 0.0, "p90": 0.0, "sigma_anual": 0.0,
            "stop_pct": 0.0, "stop_price": current_price, "ratio_rr": 0.0
        }

    # Volatilidad histórica vs GARCH actual
    hist_vol = historical_returns.std()
    garch_vol = calculate_garch_volatility(historical_returns)
    vol_scaling = garch_vol / hist_vol if hist_vol > 0 else 1.0

    # Escalar retornos para el bootstrap según la volatilidad actual
    scaled_returns = historical_returns * vol_scaling
    
    log_hist_returns = np.log1p(scaled_returns.values)
    sampled_log_returns = np.random.choice(
        log_hist_returns, 
        size=(horizon_days, n_simulations), 
        replace=True
    )
    cumulative_returns = np.sum(sampled_log_returns, axis=0)
    final_prices = current_price * np.exp(cumulative_returns)

    returns = (final_prices - current_price) / current_price

    # Calcular subida esperada optimista (P90) para el ratio R/R
    p90_return = float(np.percentile(returns, 90))

    # EVT para calibrar Stop Óptimo (riesgo 1% o peor escenario esperado)
    if fast_mode:
        stop_pct = 0.0
        stop_price = current_price
        ratio_rr = 0.0
    else:
        evt_stop_data = calculate_evt_stop(scaled_returns, current_price, risk_quantile=0.01)
        stop_pct = evt_stop_data["stop_pct"]
        stop_price = evt_stop_data["stop_price"]

        if stop_pct < 0:
            ratio_rr = abs(p90_return / stop_pct)
        else:
            ratio_rr = 0.0

    # Separar caminos ganadores y perdedores
    pos_returns = returns[returns > 0]
    neg_returns = returns[returns <= 0]
    
    prob_positive = float((returns > 0).mean())
    
    mean_pos = float(pos_returns.mean()) if len(pos_returns) > 0 else 0.0
    mean_neg = float(neg_returns.mean()) if len(neg_returns) > 0 else 0.0
    
    # Esperanza Matemática explícita
    expected_value = (prob_positive * mean_pos) + ((1 - prob_positive) * mean_neg)
    mean_return = float(returns.mean())
    ev_sanity_delta = abs(expected_value - mean_return)

    return {
        "prob_positive":  prob_positive,
        "prob_gt_1pct":   float((returns > 0.01).mean()),
        "prob_gt_2pct":   float((returns > 0.02).mean()),
        "prob_gt_5pct":   float((returns > 0.05).mean()),
        "p10": float(np.percentile(returns, 10)),
        "p50": float(np.percentile(returns, 50)),
        "p90": p90_return,
        "sigma_anual": float(garch_vol * np.sqrt(252)),
        "stop_pct": float(stop_pct),
        "stop_price": float(stop_price),
        "ratio_rr": float(ratio_rr),
        "mean_pos": mean_pos,
        "mean_neg": mean_neg,
        "expected_value": expected_value,
        "mean_return": mean_return,
        "ev_sanity_delta": ev_sanity_delta
    }
