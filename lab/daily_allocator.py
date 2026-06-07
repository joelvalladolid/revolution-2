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
    elif vix_current > 20:
        regime = 'SLOW_BEAR'
    else:
        regime = 'CALM'
        
    # Parámetros de Riesgo Fijo Intraday
    max_risk_pct = 0.01 # 1% del portfolio en riesgo por trade
    risk_usd = total_capital * max_risk_pct
    max_position_pct = 0.20 # 20% cap por posición
    
    # Cap Temático (AI / Chips)
    ai_chips_tickers = {'NVDA', 'AMD', 'SMCI', 'TSM', 'AVGO', 'MU', 'INTC', 'QCOM', 'ASML', 'AMAT', 'LRCX', 'ARM'}
    theme_cap_pct = 0.30
    
    allocations = []
    
    # 1. Calcular tamaño de posición inicial por riesgo
    raw_allocs = {}
    methods_used = {}
    for s in active_signals:
        t = s['ticker']
        stop_pct = s.get('stop_pct', -0.01) # Default 1% if missing
        
        stop_dist = abs(stop_pct)
        if stop_dist < 0.005:
            stop_dist = 0.005 # Min 0.5% stop to prevent infinite sizing
            
        usd_amount = risk_usd / stop_dist
        methods_used[t] = 'Fixed Risk (1%)'
        
        # Limit by max position cap (20%)
        max_usd = total_capital * max_position_pct
        if usd_amount > max_usd:
            usd_amount = max_usd
            methods_used[t] = 'Hard Cap (20%)'
            
        raw_allocs[t] = usd_amount

    # 2. Apply Theme Cap (AI/Chips)
    ai_total = sum(v for k, v in raw_allocs.items() if k in ai_chips_tickers)
    max_theme_usd = total_capital * theme_cap_pct
    
    if ai_total > max_theme_usd:
        ratio = max_theme_usd / ai_total
        for k in raw_allocs:
            if k in ai_chips_tickers:
                raw_allocs[k] *= ratio
                methods_used[k] = 'Theme Cap (AI/Chips)'

    # 3. Check total capital
    current_total = sum(raw_allocs.values())
    if current_total > total_capital:
        ratio = total_capital / current_total
        for k in raw_allocs:
            raw_allocs[k] *= ratio
            if methods_used[k] not in ['Hard Cap (20%)', 'Theme Cap (AI/Chips)']:
                methods_used[k] = 'Global Scale Down'
            
    # 4. Build allocations list
    total_invested_usd = 0.0
    for t, usd in raw_allocs.items():
        if usd > 0:
            weight_pct = (usd / total_capital) * 100
            allocations.append({
                'ticker': t,
                'weight_pct': weight_pct,
                'usd_amount': usd,
                'method': methods_used[t]
            })
            total_invested_usd += usd
            
    # Añadir cash residual
    cash_usd = total_capital - total_invested_usd
    if cash_usd > 1:
        allocations.append({
            'ticker': 'CASH',
            'weight_pct': (cash_usd / total_capital) * 100,
            'usd_amount': cash_usd,
            'method': 'Cash Residual'
        })
        
    allocations.sort(key=lambda x: x['weight_pct'], reverse=True)
    return allocations, regime, (total_invested_usd / total_capital) * 100

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
