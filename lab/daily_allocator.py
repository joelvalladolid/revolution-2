import sys
import os
import argparse
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Importar indicadores del motor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lab.indicators import rsi, bollinger_pctB, stochastic_k, ema_discount, macd_hist

def get_signal_active_today(ticker, strat_type, lookback, thresh, df):
    """
    Descarga data reciente, calcula el indicador y verifica si la señal
    estaba activa ayer (t-1) para operar hoy.
    """
    if len(df) < lookback + 50:
        return False
        
    df = df.copy()
    if strat_type == 'rsi_reversal':
        df['RSI'] = rsi(df, 14)
        cond = df['RSI'] < float(thresh) if thresh else False
    elif strat_type == 'bb_bounce':
        df['BB'] = bollinger_pctB(df)
        cond = df['BB'] < float(thresh) if thresh else False
    elif strat_type == 'stoch_cross':
        df['Stoch'] = stochastic_k(df)
        cond = df['Stoch'] < float(thresh) if thresh else False
    elif strat_type == 'ema_discount':
        df['EMA_Disc'] = ema_discount(df)
        cond = df['EMA_Disc'] > float(thresh) if thresh else False
    elif strat_type == 'macd_momentum':
        df['MACD'] = macd_hist(df)
        cond = df['MACD'] > 0
    elif strat_type == 'multi_confirm':
        c1 = (rsi(df, 14) < 30).astype(int)
        c2 = (bollinger_pctB(df) < 0.15).astype(int)
        c3 = (stochastic_k(df) < 20).astype(int)
        c4 = (ema_discount(df) > 12).astype(int)
        cond = (c1 + c2 + c3 + c4) >= 2
    else:
        return False
        
    if isinstance(cond, bool):
        return False
        
    min_days = max(1, int(lookback * 0.7))
    signal = cond.rolling(window=lookback).sum() >= min_days
    
    # La señal para HOY depende del cierre de AYER (t-1)
    if len(signal) > 1:
        return bool(signal.iloc[-2]) # -1 is today (might be mid-day), -2 is yesterday's close.
                                     # Wait, if we download yf today before market open, -1 is yesterday.
                                     # Let's check the date of the last row.
        # Actually, to be robust, we take the last fully closed daily bar.
        # If run before open, iloc[-1] is yesterday.
    
    return bool(signal.iloc[-1])

def apply_cap_and_redistribute(weights_dict, cap, group_map=None):
    """
    Aplica cap (individual o grupal) y redistribuye el exceso proporcionalmente.
    group_map: dict {ticker: group_name}. Si es None, es cap individual.
    """
    weights = weights_dict.copy()
    
    for _ in range(100):
        excess = 0.0
        capped_items = set()
        
        # Check caps
        if group_map:
            # Sector Cap
            group_sums = {}
            for t, w in weights.items():
                g = group_map.get(t, 'Unknown')
                group_sums[g] = group_sums.get(g, 0.0) + w
                
            for g, g_sum in group_sums.items():
                if g_sum > cap + 1e-5:
                    ratio = cap / g_sum
                    for t, w in weights.items():
                        if group_map.get(t, 'Unknown') == g:
                            excess += w - (w * ratio)
                            weights[t] = w * ratio
                            capped_items.add(t)
        else:
            # Individual Cap
            for t, w in weights.items():
                if w > cap + 1e-5:
                    excess += w - cap
                    weights[t] = cap
                    capped_items.add(t)
                    
        if excess <= 1e-5:
            break
            
        # Redistribute excess proportionally among non-capped
        uncapped = {t: w for t, w in weights.items() if t not in capped_items}
        sum_uncapped = sum(uncapped.values())
        
        if sum_uncapped < 1e-5:
            break # All are capped or 0, cannot redistribute
            
        for t in uncapped:
            weights[t] += excess * (uncapped[t] / sum_uncapped)
            
    return weights

def calculate_allocations(active_signals, vix_current, total_capital):
    if not active_signals:
        return [], 'CALM', 0.0
        
    # Determinar Régimen VIX
    if vix_current > 35:
        regime = 'FAST_CRASH'
        ticker_cap = 0.15
        regime_multiplier = 0.5
    elif vix_current > 20:
        regime = 'SLOW_BEAR'
        ticker_cap = 0.10
        regime_multiplier = 1.0
    else:
        regime = 'CALM'
        ticker_cap = 0.15
        regime_multiplier = 1.0
        
    sector_cap = 0.30
    
    # 1. Calcular pesos crudos en cascada
    raw_weights = {}
    methods_used = {}
    
    for s in active_signals:
        t = s['ticker']
        hr = s.get('hit_rate', 0)
        aw = s.get('avg_win', 0)
        al = s.get('avg_loss', 0)
        n_trades = s.get('n_signals', 0)
        vol = s.get('vol_30d', 0.02)
        
        if n_trades >= 30 and aw > 0:
            # Method 1: Fractional Kelly (25%)
            kelly = (hr * aw - (1 - hr) * abs(al)) / aw
            if kelly > 0:
                raw_weights[t] = kelly * 0.25
                methods_used[t] = 'Kelly (25%)'
                continue
                
        if vol > 0:
            # Method 2: Volatility Parity (Raw Inverse Vol)
            raw_weights[t] = 1.0 / vol
            methods_used[t] = 'Vol Parity'
        else:
            # Method 3: Equal Weight
            raw_weights[t] = 1.0
            methods_used[t] = 'Equal Weight'
            
    # 2. Normalizar a 1.0
    total_raw = sum(raw_weights.values())
    if total_raw > 0:
        norm_weights = {t: w / total_raw for t, w in raw_weights.items()}
    else:
        norm_weights = {t: 1.0 / len(raw_weights) for t in raw_weights}
        
    # 3. Aplicar Cap Ticker (15% o 10%) con redistribución
    capped_w = apply_cap_and_redistribute(norm_weights, ticker_cap, group_map=None)
    
    # 5. Aplicar Cap Sectorial (30%) con redistribución
    sector_map = {s['ticker']: s.get('sector', 'Unknown') for s in active_signals}
    final_w = apply_cap_and_redistribute(capped_w, sector_cap, group_map=sector_map)
    
    # 6. Ajuste VIX FAST_CRASH
    if regime_multiplier < 1.0:
        final_w = {t: w * regime_multiplier for t, w in final_w.items()}
        
    total_invested_pct = sum(final_w.values())
    
    allocations = []
    for t, w in final_w.items():
        if w > 0:
            allocations.append({
                'ticker': t,
                'weight_pct': w * 100,
                'usd_amount': w * total_capital,
                'method': methods_used[t]
            })
            
    # Añadir cash residual
    cash_pct = 1.0 - total_invested_pct
    if cash_pct > 1e-4:
        allocations.append({
            'ticker': 'CASH',
            'weight_pct': cash_pct * 100,
            'usd_amount': cash_pct * total_capital,
            'method': 'Regime/Cap Cash'
        })
        
    allocations.sort(key=lambda x: x['weight_pct'], reverse=True)
    return allocations, regime, total_invested_pct * 100

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=str, required=True, help="CSV del torneo (ej: output_daytrading_tournament_full_results.csv)")
    parser.add_argument('--capital', type=float, required=True, help="Capital total en USD")
    parser.add_argument('--vix', type=float, required=True, help="Nivel del VIX actual")
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    if not os.path.exists(args.results):
        print(f"Error: {args.results} no encontrado.")
        return

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  DAILY ALLOCATOR — Day Trading Institucional             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    df_res = pd.read_csv(args.results)
    if df_res.empty:
        print("El CSV de resultados está vacío. No hay estrategias aprobadas.")
        return
        
    tickers = df_res['ticker'].unique().tolist()
    print(f"Descargando data reciente para {len(tickers)} tickers aprobados...")
    
    data = yf.download(tickers, period="1y", progress=False, threads=True)
    
    active_signals = []
    for idx, row in df_res.iterrows():
        t = row['ticker']
        try:
            if isinstance(data.columns, pd.MultiIndex):
                try: tdf = data.xs(t, level=1, axis=1).dropna(subset=['Close'])
                except: tdf = data.xs(t, level=0, axis=1).dropna(subset=['Close'])
            else:
                tdf = data.dropna(subset=['Close'])
                
            strat = row['strategy_type']
            lb = row['signal_lookback']
            
            thresh = None
            for col in ['ema_disc_threshold', 'rsi_threshold', 'stoch_threshold', 'bb_pctb_threshold']:
                if col in row and pd.notna(row[col]):
                    thresh = row[col]
                    break
                    
            is_active = get_signal_active_today(t, strat, lb, thresh, tdf)
            if is_active:
                vol_30d = tdf['Close'].pct_change().tail(30).std()
                active_signals.append({
                    'ticker': t,
                    'strategy': strat,
                    'hit_rate': row.get('hit_rate', 0),
                    'avg_win': row.get('avg_win', 0),
                    'avg_loss': row.get('avg_loss', 0),
                    'sector': row.get('sector', 'Unknown'),
                    'n_signals': row.get('n_signals', 0),
                    'vol_30d': vol_30d
                })
        except Exception as e:
            print(f"Error procesando {t}: {e}")
            
    print(f"\nSeñales activas HOY: {len(active_signals)}")
    for s in active_signals:
        print(f"  - {s['ticker']} ({s['strategy']})")
        
    allocations, regime, inv_pct = calculate_allocations(active_signals, args.vix, args.capital)
    
    print(f"\nRégimen Detectado: {regime} (VIX={args.vix:.1f})")
    print(f"Capital Invertido: {inv_pct:.1f}%\n")
    
    print(f"{'Ticker':<8} | {'Weight %':<10} | {'USD Amount':<12} | {'Method'}")
    print("-" * 60)
    for a in allocations:
        print(f"{a['ticker']:<8} | {a['weight_pct']:<9.2f}% | ${a['usd_amount']:<11.2f} | {a['method']}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w') as f:
            f.write(f"DATE: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"VIX: {args.vix}\n")
            f.write(f"REGIME: {regime}\n")
            f.write(f"CAPITAL: ${args.capital:.2f}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'Ticker':<8} | {'Weight %':<10} | {'USD Amount':<12} | {'Method'}\n")
            f.write("-" * 60 + "\n")
            for a in allocations:
                f.write(f"{a['ticker']:<8} | {a['weight_pct']:<9.2f}% | ${a['usd_amount']:<11.2f} | {a['method']}\n")
        print(f"\nAllocations guardadas en {args.output}")

if __name__ == '__main__':
    main()
