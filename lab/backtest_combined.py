import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import pandas as pd
import numpy as np
import scipy.stats as stats
import yfinance as yf
from typing import Dict

from data.fetcher import fetch_history
from lab.indicators import ema_discount, bollinger_pctB, stochastic_k, rsi
from lab.regime_detector import classify_regime
from lab.rule_engine import evaluate_signal

"""
Backtest del sistema completo: régimen + técnico + fundamental.
Compara tres estrategias:
  A) Solo EMA200_disc (ganador individual)
  B) Motor de reglas dinámico sin filtro fundamental
  C) Motor de reglas dinámico con filtro fundamental (sistema completo)

Métricas: hit rate a 5 días, edge sobre baseline, distribución de señales por régimen.
También soporta la evaluación de indicadores individuales con métricas de riesgo (Kelly, CVaR, etc.)
"""

def compute_core_metrics_vectorized(pnl_vector: np.ndarray) -> Dict[str, float]:
    pnl = np.asarray(pnl_vector, dtype=np.float64).ravel()
    total_trades = pnl.size
    
    if total_trades == 0:
        return {'win_rate': 0.0, 'ev': 0.0, 'profit_factor': 0.0, 'n_signals': 0}
        
    winning_mask = pnl > 0
    losing_mask = pnl < 0
    
    winning_trades = pnl[winning_mask]
    losing_trades = pnl[losing_mask]
    
    n_wins = winning_trades.size
    n_losses = losing_trades.size
    effective_trades = n_wins + n_losses
    
    win_rate = (n_wins / effective_trades) if effective_trades > 0 else 0.0
    expected_value = float(np.mean(pnl))
    
    gross_profit = float(np.sum(winning_trades))
    gross_loss = float(np.abs(np.sum(losing_trades)))
    
    if gross_loss == 0.0:
        profit_factor = float('inf') if gross_profit > 0 else 0.0
    else:
        profit_factor = gross_profit / gross_loss
        
    return {
        'win_rate': float(win_rate),
        'ev': expected_value,
        'profit_factor': profit_factor,
        'n_signals': total_trades
    }

def compute_advanced_risk_metrics(
    strategy_returns: np.ndarray, 
    risk_free_rate: float = 0.0, 
    cvar_alpha: float = 0.05
) -> Dict[str, float]:
    rets = np.asarray(strategy_returns, dtype=np.float64).ravel()
    if rets.size < 2:
        return {'sharpe_90d': 0.0, 'sortino': 0.0, 'calmar': 0.0, 'cvar_5pct': 0.0, 'p_value': 1.0, 'max_dd': 0.0}
        
    mean_ret = float(np.mean(rets))
    std_ret = float(np.std(rets, ddof=1))
    
    sharpe = ((mean_ret - risk_free_rate) / std_ret) * np.sqrt(252) if std_ret > 1e-8 else 0.0
    
    downside_returns = rets[rets < risk_free_rate]
    downside_var = float(np.mean(downside_returns**2)) if downside_returns.size > 0 else 0.0
    downside_std = np.sqrt(downside_var)
    sortino = ((mean_ret - risk_free_rate) / downside_std) * np.sqrt(252) if downside_std > 1e-8 else float('inf')
    
    cum_returns = np.cumprod(1.0 + rets)
    running_max = np.maximum.accumulate(cum_returns)
    drawdowns = (cum_returns - running_max) / running_max
    max_drawdown = float(np.abs(np.min(drawdowns)))
    calmar = (mean_ret * 252) / max_drawdown if max_drawdown > 1e-8 else float('inf')
    
    var_threshold = np.percentile(rets, cvar_alpha * 100)
    tail_losses = rets[rets <= var_threshold]
    cvar = float(np.mean(tail_losses)) if tail_losses.size > 0 else 0.0
    
    t_stat, p_value = stats.ttest_1samp(rets, popmean=0.0, nan_policy='omit')
    if np.isnan(p_value):
        p_value = 1.0
        
    return {
        'sharpe_90d': float(sharpe),
        'sortino': float(sortino),
        'calmar': float(calmar),
        'cvar_5pct': float(cvar),
        'p_value': float(p_value),
        'max_dd': float(max_drawdown)
    }


STRATEGIES = {
    "A_EMA200_solo":         {"use_regime": False, "use_fundamental": False},
    "B_regime_no_fund":      {"use_regime": True,  "use_fundamental": False},
    "C_regime_plus_fund":    {"use_regime": True,  "use_fundamental": True},
}

PERIODS = {
    "full":       ("2015-01-01", "2024-12-31"),
    "bull_slow":  ("2015-01-01", "2019-12-31"),
    "covid":      ("2020-01-01", "2020-12-31"),
    "bear_2022":  ("2022-01-01", "2022-12-31"),
    "recovery":   ("2023-01-01", "2024-12-31"),
}

def kelly_criterion(hit_rate: float, avg_win: float, avg_loss: float) -> float:
    avg_win_abs = abs(avg_win)
    avg_loss_abs = abs(avg_loss)
    if avg_loss_abs == 0: return 0.0
    b = avg_win_abs / avg_loss_abs
    if b == 0: return 0.0
    return (hit_rate * b - (1.0 - hit_rate)) / b

def cvar_5pct(returns: list) -> float:
    if not returns: return 0.0
    sorted_r = sorted(returns)
    cutoff = int(len(sorted_r) * 0.05)
    return sum(sorted_r[:cutoff]) / max(cutoff, 1)

def calc_max_consec_losses(ticker_returns_dict) -> int:
    max_consec = 0
    for ticker, rets in ticker_returns_dict.items():
        consec = 0
        for r in rets:
            if r < 0:
                consec += 1
                if consec > max_consec:
                    max_consec = consec
            else:
                consec = 0
    return max_consec

def run_combined_backtest(tickers, start, end, indicator=None, risk_metrics=False, period_name=""):
    data_dict = fetch_history(tickers, start, end)
    
    if indicator:
        # Parse indicator (e.g., RSI_20)
        import re
        m = re.match(r'RSI_(\d+)', indicator)
        if m:
            rsi_th = float(m.group(1))
        else:
            rsi_th = 20.0
            
        sig_rets = []
        base_rets = []
        ticker_rets = {}
        
        for ticker, df in data_dict.items():
            if len(df) < 30: continue
            
            df['RSI'] = rsi(df)
            df['fwd_ret_1'] = (df['Close'].shift(-1) / df['Close']) - 1
            
            df_valid = df.dropna(subset=['fwd_ret_1', 'RSI'])
            ticker_rets[ticker] = []
            
            for idx, row in df_valid.iterrows():
                fwd = row['fwd_ret_1']
                val = row['RSI']
                
                base_rets.append(fwd)
                if val <= rsi_th:
                    sig_rets.append(fwd)
                    ticker_rets[ticker].append(fwd)
                    
        # Calculate metrics
        hit_rate = np.mean(np.array(sig_rets) > 0) if len(sig_rets) > 0 else 0.0
        base_hit = np.mean(np.array(base_rets) > 0) if len(base_rets) > 0 else 0.0
        edge = (hit_rate - base_hit) * 100
        
        sig_arr = np.array(sig_rets)
        wins = sig_arr[sig_arr > 0]
        losses = sig_arr[sig_arr < 0]
        
        avg_win = np.mean(wins) if len(wins) > 0 else 0.0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
        
        kelly = kelly_criterion(hit_rate, avg_win, avg_loss)
        cvar = cvar_5pct(sig_rets)
        max_consec = calc_max_consec_losses(ticker_rets)
        
        if risk_metrics:
            print(f"{'Período':<10} | {'Edge':<5} | {'Kelly %':<7} | {'CVaR 5%':<7} | {'Max consec. losses'}")
            print("-" * 65)
            print(f"{period_name:<10} | {edge:>4.2f}pp | {kelly*100:>6.1f}% | {cvar*100:>6.1f}% | {max_consec:>18}")
        else:
            print(f"RSI_{int(rsi_th)} | Edge: {edge:.2f}pp | Signals: {len(sig_rets)}")
        return

    # Si no hay indicator, correr backtest combinado estándar
    vix_df = yf.download("^VIX", start=start, end=end, progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.droplevel(1)
        
    vix_regime = classify_regime(vix_df['Close'])
    
    stats = {k: {'sig': [], 'base': [], 'regimes': [], 'ticker_rets': {}} for k in STRATEGIES.keys()}
    stats_by_period = {
        'BEAR': {k: {'sig': [], 'base': []} for k in STRATEGIES.keys()},
        'COVID': {k: {'sig': [], 'base': []} for k in STRATEGIES.keys()}
    }

    for ticker, df in data_dict.items():
        if len(df) < 260: continue
        
        df['fwd_ret_5'] = (df['Close'].shift(-5) / df['Close']) - 1
        df['1y_ret'] = df['Close'].pct_change(252)
        
        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB'] = bollinger_pctB(df)
        df['Stoch_K'] = stochastic_k(df)
        df['regime'] = vix_regime.reindex(df.index).ffill().fillna('CALM')
        
        fwd_rets = df['fwd_ret_5'].values
        ema_vals = df['EMA200_disc'].values
        bb_vals = df['BB_pctB'].values
        stoch_vals = df['Stoch_K'].values
        regimes = df['regime'].values
        ret_1y = df['1y_ret'].values
        dates = df.index
        
        for i in range(252, len(df)):
            if pd.isna(fwd_rets[i]): continue
            
            fwd = fwd_rets[i]
            reg = regimes[i]
            date = dates[i]
            
            is_bear = date.year == 2022
            is_covid = date.year == 2020
            
            ind_dict = {
                "EMA200_disc": ema_vals[i],
                "BB_pctB": bb_vals[i],
                "Stoch_K": stoch_vals[i]
            }
            stars = 15 if ret_1y[i] > 0 else 10
            
            for s in STRATEGIES.keys():
                stats[s]['base'].append(fwd)
                if is_bear: stats_by_period['BEAR'][s]['base'].append(fwd)
                if is_covid: stats_by_period['COVID'][s]['base'].append(fwd)
            
            # Eval A
            if ind_dict["EMA200_disc"] >= 15.0:
                stats['A_EMA200_solo']['sig'].append(fwd)
                stats['A_EMA200_solo']['regimes'].append(reg)
                if ticker not in stats['A_EMA200_solo']['ticker_rets']:
                    stats['A_EMA200_solo']['ticker_rets'][ticker] = []
                stats['A_EMA200_solo']['ticker_rets'][ticker].append(fwd)
                if is_bear: stats_by_period['BEAR']['A_EMA200_solo']['sig'].append(fwd)
                if is_covid: stats_by_period['COVID']['A_EMA200_solo']['sig'].append(fwd)
                
            # Eval B
            res_b = evaluate_signal(ind_dict, reg, 15)
            if res_b['signal']:
                stats['B_regime_no_fund']['sig'].append(fwd)
                stats['B_regime_no_fund']['regimes'].append(reg)
                if ticker not in stats['B_regime_no_fund']['ticker_rets']:
                    stats['B_regime_no_fund']['ticker_rets'][ticker] = []
                stats['B_regime_no_fund']['ticker_rets'][ticker].append(fwd)
                if is_bear: stats_by_period['BEAR']['B_regime_no_fund']['sig'].append(fwd)
                if is_covid: stats_by_period['COVID']['B_regime_no_fund']['sig'].append(fwd)
                
            # Eval C
            res_c = evaluate_signal(ind_dict, reg, stars)
            if res_c['signal']:
                stats['C_regime_plus_fund']['sig'].append(fwd)
                stats['C_regime_plus_fund']['regimes'].append(reg)
                if ticker not in stats['C_regime_plus_fund']['ticker_rets']:
                    stats['C_regime_plus_fund']['ticker_rets'][ticker] = []
                stats['C_regime_plus_fund']['ticker_rets'][ticker].append(fwd)
                if is_bear: stats_by_period['BEAR']['C_regime_plus_fund']['sig'].append(fwd)
                if is_covid: stats_by_period['COVID']['C_regime_plus_fund']['sig'].append(fwd)

    def calc_metrics(sig, base):
        if not sig: return 0, 0
        hit = np.mean(np.array(sig) > 0)
        base_hit = np.mean(np.array(base) > 0)
        edge = (hit - base_hit) * 100
        return hit * 100, edge
        
    if risk_metrics:
        print(f"{'Estrategia':<25} | {'Hit Rate':<8} | {'Edge':<5} | {'Kelly %':<7} | {'CVaR 5%':<7} | {'Max consec. losses'}")
        print("-" * 85)
        for s_name in STRATEGIES.keys():
            hit, edge = calc_metrics(stats[s_name]['sig'], stats[s_name]['base'])
            sig_arr = np.array(stats[s_name]['sig'])
            wins = sig_arr[sig_arr > 0]
            losses = sig_arr[sig_arr < 0]
            avg_win = np.mean(wins) if len(wins) > 0 else 0.0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
            kelly = kelly_criterion(hit/100.0, avg_win, avg_loss)
            cvar = cvar_5pct(stats[s_name]['sig'])
            max_consec = calc_max_consec_losses(stats[s_name]['ticker_rets'])
            print(f"{s_name:<25} | {hit:>7.2f}% | {edge:>3.1f}pp | {kelly*100:>6.1f}% | {cvar*100:>6.1f}% | {max_consec:>18}")
    else:
        print(f"{'Estrategia':<25} | {'Hit Rate':<8} | {'Edge':<5} | {'Señales':<7} | {'Edge BEAR':<9} | {'Edge COVID':<9}")
        print("-" * 75)
        for s_name in STRATEGIES.keys():
            hit, edge = calc_metrics(stats[s_name]['sig'], stats[s_name]['base'])
            n_sig = len(stats[s_name]['sig'])
            _, bear_edge = calc_metrics(stats_by_period['BEAR'][s_name]['sig'], stats_by_period['BEAR'][s_name]['base'])
            _, covid_edge = calc_metrics(stats_by_period['COVID'][s_name]['sig'], stats_by_period['COVID'][s_name]['base'])
            print(f"{s_name:<25} | {hit:>7.2f}% | {edge:>3.1f}pp | {n_sig:>7} | {bear_edge:>7.2f}pp | {covid_edge:>7.2f}pp")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sp500", action="store_true")
    parser.add_argument("--period", type=str)
    parser.add_argument("--indicator", type=str)
    parser.add_argument("--risk-metrics", action="store_true")
    args = parser.parse_args()
    
    if args.period and args.period in PERIODS:
        start, end = PERIODS[args.period]
        p_name = args.period
    else:
        start, end = PERIODS["full"]
        p_name = "full"
        
    try:
        from lab_tickers import _FALLBACK_SP500 as SP500_TICKERS
        tickers = SP500_TICKERS
    except ImportError:
        print("Error: No se encuentra lab_tickers.py en la raíz.")
        sys.exit(1)
            
    run_combined_backtest(tickers, start, end, indicator=args.indicator, risk_metrics=args.risk_metrics, period_name=p_name)
