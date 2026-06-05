import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import pandas as pd
import numpy as np
import itertools
import yfinance as yf
from scipy.stats import ttest_ind

from lab.indicators import (
    rsi, mfi, williams_r, cci, bollinger_pctB, 
    ema_discount, volume_ratio, macd_hist, stochastic_k, obv_slope,
    hurst_exponent, adx, roc, vwap_deviation, atr_normalized, cmf
)
from data.fetcher import fetch_history
from lab.regime_detector import classify_regime

HORIZONS = [1, 3, 5, 10]

PERIODS = {
    "full":       ("2015-01-01", "2024-12-31"),
    "bull_slow":  ("2015-01-01", "2019-12-31"),
    "covid":      ("2020-01-01", "2020-12-31"),
    "bear_2022":  ("2022-01-01", "2022-12-31"),
    "recovery":   ("2023-01-01", "2024-12-31"),
}

INDICATOR_CONFIGS = {
    "RSI_14":        (rsi,           [20, 25, 30, 35, 40], 'below'),
    "MFI_14":        (mfi,           [20, 25, 30, 35],     'below'),
    "Williams_R":    (williams_r,    [-80, -85, -90],      'below'),
    "CCI_20":        (cci,           [-100, -150, -200],   'below'),
    "BB_pctB":       (bollinger_pctB,[0.05, 0.1, 0.2],     'below'),
    "EMA200_disc":   (ema_discount,  [5, 8, 10, 12, 15],   'above'),
    "Volume_ratio":  (volume_ratio,  [1.5, 2.0, 2.5],      'above'),
    "MACD_hist_pos": (macd_hist,     [0],                  'above'),
    "Stoch_K":       (stochastic_k,  [20, 25, 30],         'below'),
    "OBV_slope_pos": (obv_slope,     [0],                  'above'),
    "ADX_14":        (adx,            [20, 25, 30],        'above'),
    "Hurst_rev":     (hurst_exponent, [0.4, 0.45],         'below'),
    "CMF_20":        (cmf,            [0],                  'above'),
    "ROC_10":        (roc,            [-5, -8, -10],        'below'),
}

ALL_WEATHER = [
    ("EMA200_disc", 15.0),
    ("EMA200_disc", 12.0),
    ("EMA200_disc", 10.0),
    ("BB_pctB", 0.2),
    ("Stoch_K", 20.0)
]

def format_ind_name(name, threshold, direction):
    # Ensure float formatting for consistency
    th = float(threshold)
    if direction == 'below':
        return f"{name} <={th}"
    else:
        return f"{name} >={th}"

def run_indicator_tournament(tickers: list, start: str, end: str, combos=False) -> pd.DataFrame:
    print(f"Descargando datos para {len(tickers)} tickers...")
    data_dict = fetch_history(tickers, start, end)
    print(f"Datos descargados para {len(data_dict)} tickers válidos.")
    
    print("Descargando VIX...")
    vix_df = yf.download("^VIX", start=start, end=end, progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.droplevel(1)
    
    if vix_df.empty:
        print("Error: No se pudo descargar el VIX.")
        return pd.DataFrame()
        
    vix_regime = classify_regime(vix_df['Close'])

    for ticker, df in data_dict.items():
        # Alinear régimen
        df['regime'] = vix_regime.reindex(df.index).ffill().fillna('CALM')
        for h in HORIZONS:
            df[f'fwd_ret_{h}'] = (df['Close'].shift(-h) / df['Close']) - 1

    results = []

    # Pre-calcular todas las señales individuales
    print("Calculando señales individuales...")
    signals_dict = {} # key: ticker -> dict: indicator_name -> series(bool)
    
    for ticker, df in data_dict.items():
        signals_dict[ticker] = {}
        for ind_name, (func, thresholds, direction) in INDICATOR_CONFIGS.items():
            try:
                ind_series = func(df)
                for th in thresholds:
                    name_th = format_ind_name(ind_name, th, direction)
                    if direction == 'below':
                        signals_dict[ticker][name_th] = (ind_series <= th)
                    else:
                        signals_dict[ticker][name_th] = (ind_series >= th)
            except Exception:
                pass

    eval_items = []

    if combos:
        print("Preparando combos...")
        # Generar nombres ALL_WEATHER
        aw_names = []
        for ind_name, th in ALL_WEATHER:
            direction = INDICATOR_CONFIGS[ind_name][2]
            aw_names.append(format_ind_name(ind_name, th, direction))
            
        combos_2 = list(itertools.combinations(aw_names, 2))
        combos_3 = list(itertools.combinations(aw_names, 3))
        
        # Test specific: RSI_14 <= 20
        rsi_20 = format_ind_name("RSI_14", 20.0, "below")
        
        # We will create pseudo-signals for combinations
        eval_items = []
        for combo in combos_2:
            name = " + ".join(combo)
            eval_items.append((name, list(combo)))
            
        for combo in combos_3:
            name = " + ".join(combo)
            eval_items.append((name, list(combo)))
            
        eval_items.append((rsi_20, [rsi_20]))
        
        # Include individual ALL_WEATHER for comparison
        for name in aw_names:
            eval_items.append((name, [name]))

    else:
        for ind_name, (func, thresholds, direction) in INDICATOR_CONFIGS.items():
            for th in thresholds:
                name = format_ind_name(ind_name, th, direction)
                eval_items.append((name, [name]))

    print(f"Evaluando {len(eval_items)} configuraciones...")
    
    # Evaluar
    for eval_name, components in eval_items:
        for h in HORIZONS:
            stats = {'ALL': {'sig': [], 'base': []}, 'CALM': {'sig': [], 'base': []}, 
                     'SLOW_BEAR': {'sig': [], 'base': []}, 'FAST_CRASH': {'sig': [], 'base': []}}
            
            for ticker, df in data_dict.items():
                if f'fwd_ret_{h}' not in df.columns:
                    continue
                    
                # Combinar señales
                ticker_signals = signals_dict.get(ticker, {})
                valid = True
                for comp in components:
                    if comp not in ticker_signals:
                        valid = False
                        break
                if not valid: continue
                
                signal = ticker_signals[components[0]]
                for comp in components[1:]:
                    signal = signal & ticker_signals[comp]
                
                valid_mask = df[f'fwd_ret_{h}'].notna()
                sig_mask = signal & valid_mask
                base_mask = (~signal) & valid_mask
                
                if sig_mask.sum() > 0 or base_mask.sum() > 0:
                    fwd_rets = df[f'fwd_ret_{h}'].values
                    regimes = df['regime'].values
                    
                    sig_idx = np.where(sig_mask)[0]
                    base_idx = np.where(base_mask)[0]
                    
                    for r_name in ['CALM', 'SLOW_BEAR', 'FAST_CRASH']:
                        r_mask = (regimes == r_name)
                        r_sig_mask = sig_mask & r_mask
                        r_base_mask = base_mask & r_mask
                        
                        r_sig_idx = np.where(r_sig_mask)[0]
                        r_base_idx = np.where(r_base_mask)[0]
                        
                        if len(r_sig_idx) > 0:
                            stats[r_name]['sig'].extend(fwd_rets[r_sig_idx])
                        if len(r_base_idx) > 0:
                            stats[r_name]['base'].extend(fwd_rets[r_base_idx])
                            
                    if len(sig_idx) > 0:
                        stats['ALL']['sig'].extend(fwd_rets[sig_idx])
                    if len(base_idx) > 0:
                        stats['ALL']['base'].extend(fwd_rets[base_idx])

            # Calcular métricas
            n_signals = len(stats['ALL']['sig'])
            if n_signals < 5:
                continue
                
            def calc_edge(sig_list, base_list):
                if len(sig_list) == 0 or len(base_list) == 0:
                    return float('nan')
                sig_arr = np.array(sig_list)
                base_arr = np.array(base_list)
                return np.mean(sig_arr > 0) - np.mean(base_arr > 0)

            edge_all = calc_edge(stats['ALL']['sig'], stats['ALL']['base'])
            edge_calm = calc_edge(stats['CALM']['sig'], stats['CALM']['base'])
            edge_slow = calc_edge(stats['SLOW_BEAR']['sig'], stats['SLOW_BEAR']['base'])
            edge_crash = calc_edge(stats['FAST_CRASH']['sig'], stats['FAST_CRASH']['base'])
            
            sig_array = np.array(stats['ALL']['sig'])
            base_array = np.array(stats['ALL']['base'])
            try:
                t_stat, p_value = ttest_ind(sig_array, base_array, equal_var=False)
            except Exception:
                p_value = 1.0

            results.append({
                'indicator': eval_name,
                'horizon_days': h,
                'n_signals': n_signals,
                'edge_all': edge_all,
                'edge_calm': edge_calm,
                'edge_slow_bear': edge_slow,
                'edge_fast_crash': edge_crash,
                'p_value': p_value
            })

    return pd.DataFrame(results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs='+', help="Lista de tickers a testear")
    parser.add_argument("--sp500", action="store_true", help="Cargar los ~500 tickers del SP500")
    parser.add_argument("--period", type=str, choices=list(PERIODS.keys()), help="Período predefinido")
    parser.add_argument("--start", type=str, help="Fecha inicio")
    parser.add_argument("--end", type=str, help="Fecha fin")
    parser.add_argument("--combos", action="store_true", help="Probar combinaciones")
    parser.add_argument("--horizon", type=int, default=5, help="Horizonte a mostrar (1, 3, 5, 10)")
    args = parser.parse_args()
    
    if args.period:
        start_date, end_date = PERIODS[args.period]
    elif args.start and args.end:
        start_date, end_date = args.start, args.end
    else:
        print("Debes especificar --period o bien --start y --end")
        sys.exit(1)
        
    if args.sp500:
        try:
            from lab_tickers import _FALLBACK_SP500 as SP500_TICKERS
            tickers_list = SP500_TICKERS
        except ImportError:
            print("Error: No se encuentra lab_tickers.py en la raíz.")
            sys.exit(1)
    elif args.tickers:
        tickers_list = args.tickers
    else:
        print("Debes especificar --sp500 o pasar --tickers")
        sys.exit(1)
    
    df_results = run_indicator_tournament(tickers_list, start_date, end_date, args.combos)
    
    if not df_results.empty:
        top_h = df_results[df_results['horizon_days'] == args.horizon].sort_values(by='edge_all', ascending=False)
        print(f"\n=== TOP 25 INDICADORES A {args.horizon} DÍAS (Por Edge) ===")
        print(top_h.head(25).to_string(index=False))
        
        mode = "combos" if args.combos else "single"
        period_str = args.period if args.period else "custom"
        csv_name = f"tournament_results_{period_str}_{mode}.csv"
        df_results.to_csv(csv_name, index=False)
        print(f"\nResultados completos guardados en {csv_name}")
    else:
        print("No se generaron resultados.")
