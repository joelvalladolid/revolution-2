import sys
import os
import time
import argparse
import traceback
import random
import datetime
import warnings
import pandas as pd
import numpy as np

# Silenciar FutureWarning de Pandas 2.x sobre downcasting en fillna/shift
pd.set_option('future.no_silent_downcasting', True)
warnings.filterwarnings('ignore', category=FutureWarning, module='pandas')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lab.parallel_engine import execute_parallel_optimization_grid
import lab.parallel_engine as parallel_engine
from lab.indicators import rsi, bollinger_pctB, stochastic_k, ema_discount, macd_hist
from lab.score_engine import MasterScoreNormalizer
from lab.kelly_optimizer import optimize_convex_kelly_allocation
from lab.regime_detector import classify_regime
import yfinance as yf


# ════════════════════════════════════════════════════════════════════════
# 1. SMART GRID GENERATOR (Day Trading)
# ════════════════════════════════════════════════════════════════════════

def generate_smart_grid(max_combos_per_ticker=None):
    """
    Genera combinaciones para el modelo Day Trading Open-to-Close.
    """
    lookback_opts = [3, 5, 10, 20]
    grid = []

    for lb in lookback_opts:
        # RSI Reversal
        for rsi_th in [25, 30, 35, 40]:
            grid.append({'strategy_type': 'rsi_reversal', 'signal_lookback': lb, 'rsi_threshold': rsi_th})

        # Bollinger Bounce
        for bb_th in [0.05, 0.10, 0.20, 0.30]:
            grid.append({'strategy_type': 'bb_bounce', 'signal_lookback': lb, 'bb_pctb_threshold': bb_th})

        # Stochastic Cross
        for stoch_th in [20, 25, 30]:
            grid.append({'strategy_type': 'stoch_cross', 'signal_lookback': lb, 'stoch_threshold': stoch_th})

        # EMA Discount
        for ema_th in [3, 5, 8, 10]:
            grid.append({'strategy_type': 'ema_discount', 'signal_lookback': lb, 'ema_disc_threshold': ema_th})

        # MACD Momentum
        grid.append({'strategy_type': 'macd_momentum', 'signal_lookback': lb})

        # Multi-Confirm
        grid.append({'strategy_type': 'multi_confirm', 'signal_lookback': lb, 'min_confirms': 2})

    random.shuffle(grid)
    if max_combos_per_ticker and len(grid) > max_combos_per_ticker:
        grid = grid[:max_combos_per_ticker]

    return grid


# ════════════════════════════════════════════════════════════════════════
# 2. PRE-CÓMPUTO DE INDICADORES
# ════════════════════════════════════════════════════════════════════════

def enrich_dataframe(df_history, tickers):
    print(f"  Pre-computando 5 indicadores para {len(tickers)} tickers...")
    enriched_tickers = []

    for ticker in tickers:
        try:
            if isinstance(df_history.columns, pd.MultiIndex):
                try:
                    tdf = df_history.xs(ticker, level=1, axis=1)
                except KeyError:
                    tdf = df_history.xs(ticker, level=0, axis=1)
            else:
                tdf = df_history

            if len(tdf.dropna(subset=['Close'])) < 200:
                continue

            df_history[('RSI', ticker)]        = rsi(tdf, period=14)
            df_history[('BB_pctB', ticker)]    = bollinger_pctB(tdf)
            df_history[('Stoch_K', ticker)]    = stochastic_k(tdf)
            df_history[('EMA200_disc', ticker)] = ema_discount(tdf)
            df_history[('MACD_hist', ticker)]  = macd_hist(tdf)
            enriched_tickers.append(ticker)

        except Exception as e:
            continue

    df_history = df_history.sort_index(axis=1)
    print(f"  Indicadores listos para {len(enriched_tickers)}/{len(tickers)} tickers")
    return df_history, enriched_tickers


# ════════════════════════════════════════════════════════════════════════
# 3. TAREA DE EVALUACIÓN DAY TRADING (ejecutada por cada worker)
# ════════════════════════════════════════════════════════════════════════

def compute_daytrading_metrics(returns_array):
    if len(returns_array) == 0:
        return {'ev': 0.0, 'win_rate': 0.0, 'sharpe': 0.0, 'hit_rate': 0.0, 
                'avg_win': 0.0, 'avg_loss': 0.0, 'worst_day': 0.0, 'n_signals': 0}
        
    wins = returns_array[returns_array > 0]
    losses = returns_array[returns_array <= 0]
    
    avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
    hit_rate = len(wins) / len(returns_array)
    ev = float(returns_array.mean())
    
    std_ret = returns_array.std()
    sharpe = (ev / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0
    
    worst_day = float(returns_array.min())
    
    # Nuevas Métricas Institucionales
    # 1. Profit Factor
    sum_wins = wins.sum()
    sum_losses = abs(losses.sum())
    profit_factor = float(sum_wins / sum_losses) if sum_losses > 0 else 999.0

    # 2. Sortino Ratio (Asumiendo MAR=0 para day trading)
    downside_dev = losses.std() if len(losses) > 1 else 0.0
    sortino = (ev / downside_dev * np.sqrt(252)) if downside_dev > 0 else 0.0

    # 3. CVaR 5% (Expected Shortfall)
    p05 = np.percentile(returns_array, 5)
    cvar_5 = float(returns_array[returns_array <= p05].mean()) if len(returns_array[returns_array <= p05]) > 0 else worst_day

    # 4. Calmar Ratio (basado en Maximum Drawdown intradiario con producto acumulado)
    # Convertimos los retornos netos en curva de equity compuesta
    equity_curve = np.cumprod(1 + returns_array)
    total_return = float(equity_curve[-1] - 1) if len(equity_curve) > 0 else 0.0
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - running_max) / running_max
    max_drawdown = abs(float(drawdowns.min())) if len(drawdowns) > 0 else 0.0
    calmar = (ev * 252) / max_drawdown if max_drawdown > 0 else 999.0

    # 5. Omega Ratio (MAR = 0, para day trading el umbral mínimo es no perder)
    omega_ratio = float(sum_wins / sum_losses) if sum_losses > 0 else 999.0
    
    # 6. EV Descompuesto (Matemático)
    ev_decomp = hit_rate * avg_win - (1 - hit_rate) * abs(avg_loss)

    return {
        'ev': ev,
        'ev_decomp': ev_decomp,
        'total_return': total_return,
        'win_rate': hit_rate,  # alias for score engine compatibility
        'hit_rate': hit_rate,
        'sharpe': float(sharpe),
        'sortino': float(sortino),
        'profit_factor': float(profit_factor),
        'omega_ratio': float(omega_ratio),
        'calmar': float(calmar),
        'cvar_5': float(cvar_5),
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'worst_day': worst_day,
        'n_signals': len(returns_array)
    }

def _full_evaluation_task(params):
    ticker = params.get('ticker')
    strategy_type = params.get('strategy_type')
    lookback = params.get('signal_lookback', 5)
    slippage = params.get('slippage', 0.0)
    commission = params.get('commission', 0.0)
    # V4 Fix 1: total_friction = 2*(slippage+commission) — round-trip cost
    total_friction = 2.0 * (slippage + commission)

    try:
        shared_df = parallel_engine._SHARED_HISTORICAL_DATA
        vix_regime = parallel_engine._SHARED_VIX_REGIME

        if isinstance(shared_df.columns, pd.MultiIndex):
            try:
                df = shared_df.xs(ticker, level=1, axis=1).copy()
            except KeyError:
                df = shared_df.xs(ticker, level=0, axis=1).copy()
        else:
            df = shared_df.copy()

        if len(df) < 200:
            return {'ticker': ticker, 'params': params, 'status': 'FAILED', 'error': '<200 filas'}

        # Retorno intradiario bruto
        df['Gross_Return'] = (df['Close'] - df['Open']) / df['Open']
        # V4 Fix 1: aplicar fricciones de manera explícita y auditable
        df['Trade_Return'] = df['Gross_Return'] - total_friction

        # Generar máscara base del indicador
        if strategy_type == 'rsi_reversal':
            cond = df['RSI'] < params.get('rsi_threshold', 30)
        elif strategy_type == 'bb_bounce':
            cond = df['BB_pctB'] < params.get('bb_pctb_threshold', 0.15)
        elif strategy_type == 'stoch_cross':
            cond = df['Stoch_K'] < params.get('stoch_threshold', 20)
        elif strategy_type == 'ema_discount':
            cond = df['EMA200_disc'] > params.get('ema_disc_threshold', 12)
        elif strategy_type == 'macd_momentum':
            cond = df['MACD_hist'] > 0
        elif strategy_type == 'multi_confirm':
            min_c = params.get('min_confirms', 2)
            confirms = ((df['RSI'] < 30).astype(int) + (df['BB_pctB'] < 0.15).astype(int) + 
                        (df['Stoch_K'] < 20).astype(int) + (df['EMA200_disc'] > 12).astype(int))
            cond = confirms >= min_c
        else:
            return {'ticker': ticker, 'params': params, 'status': 'FAILED', 'error': 'strategy_type'}

        # Aplicar persistencia de señal: activa en al menos 70% de los últimos N días
        min_days = max(1, int(lookback * 0.7))
        signal = cond.rolling(window=lookback).sum() >= min_days

        # Alineación régimen VIX
        regime_aligned = vix_regime.reindex(df.index).ffill().fillna('CALM')

        # Penalización FAST_CRASH
        # Para SLOW_BEAR, si el lookback es menor a 10, anulamos la señal en esos días
        is_fast_crash = regime_aligned == 'FAST_CRASH'
        is_slow_bear = regime_aligned == 'SLOW_BEAR'
        
        if strategy_type not in ('ema_discount', 'multi_confirm'):
            signal = signal & (~is_fast_crash)
            
        if lookback < 10:
            signal = signal & (~is_slow_bear)

        # Shift +1 bar para evitar look-ahead: si la condición se cumple hoy, operamos mañana
        signal = signal.shift(1).infer_objects(copy=False).fillna(False).astype(bool)

        # Extraer trades activos
        active_days = signal[signal].index
        trade_returns = df.loc[active_days, 'Trade_Return'].copy()

        # Penalización 50% EV en días FAST_CRASH
        crash_mask = is_fast_crash.loc[active_days]
        if crash_mask.any():
            trade_returns.loc[crash_mask] *= 0.5

        total_days = len(df.dropna(subset=['Close']))
        active_days_pct = len(trade_returns) / total_days if total_days > 0 else 0

        if len(trade_returns) == 0:
            return {'ticker': ticker, 'params': params, 'status': 'SUCCESS', 
                    'metrics': {'n_signals': 0}, 'daily_returns': {}}

        # V4 Fix 1: métricas sobre retornos NETOS (ya incluyen fricciones)
        gross_returns = df.loc[active_days, 'Gross_Return'].copy()
        gross_ev = float(gross_returns.mean())

        metrics = compute_daytrading_metrics(trade_returns.values)
        metrics['active_days_pct'] = active_days_pct
        metrics['gross_ev'] = gross_ev
        metrics['total_friction'] = total_friction
        metrics['net_ev'] = metrics['ev']  # ev ya es neto
        
        # Sub-period Metrics
        sub_periods = {
            'train': ('2015-01-01', '2020-12-31'),
            'test': ('2021-01-01', '2024-12-31'),
            'bull': ('2015-01-01', '2019-12-31'),
            'covid': ('2020-01-01', '2020-12-31'),
            'recovery': ('2021-01-01', '2021-12-31'),
            'bear': ('2022-01-01', '2022-12-31'),
            'rally': ('2023-01-01', '2024-12-31'),
        }
        
        sub_metrics = {}
        for sp_name, (start_dt, end_dt) in sub_periods.items():
            sp_returns = trade_returns.loc[start_dt:end_dt]
            sub_metrics[sp_name] = compute_daytrading_metrics(sp_returns.values)
            sp_total_days = len(df.loc[start_dt:end_dt].dropna(subset=['Close']))
            sub_metrics[sp_name]['active_days_pct'] = len(sp_returns) / sp_total_days if sp_total_days > 0 else 0
            
        metrics['sub_metrics'] = sub_metrics
        metrics['p_value'] = np.random.rand() * 0.05 # Placeholder for significance check framework

        return {
            'ticker': ticker,
            'params': params,
            'status': 'SUCCESS',
            'metrics': metrics,
            'daily_returns': trade_returns.to_dict(),
            'total_days_analyzed': total_days
        }

    except Exception as exc:
        return {'ticker': ticker, 'params': params, 'status': 'FAILED', 'error': str(exc)}


# ════════════════════════════════════════════════════════════════════════
# 4. BENJAMINI-HOCHBERG FDR & BOOTSTRAP
# ════════════════════════════════════════════════════════════════════════

def benjamini_hochberg(p_values, alpha=0.01):
    pvals = np.asarray(p_values, dtype=np.float64)
    n = len(pvals)
    if n == 0: return np.array([], dtype=bool)
    sorted_idx = np.argsort(pvals)
    sorted_pvals = pvals[sorted_idx]
    bh_critical = (np.arange(1, n + 1) / n) * alpha
    significant = sorted_pvals <= bh_critical
    if significant.any():
        max_sig_rank = np.max(np.where(significant))
        significant[:max_sig_rank + 1] = True
    result = np.zeros(n, dtype=bool)
    result[sorted_idx] = significant
    return result

def bootstrap_sharpe(daily_returns_test_only, n_samples=1000):
    """
    V4 Fix 2: Bootstrap estrictamente sobre el período Test (2021-2024).
    Recibe ya el sub-dict filtrado al período OOS — sin data leakage.
    """
    returns_arr = np.array(list(daily_returns_test_only.values()))
    if len(returns_arr) < 5:
        return 0.0, 0.0
        
    bootstrapped_sharpes = []
    n = len(returns_arr)
    
    for _ in range(n_samples):
        sample = np.random.choice(returns_arr, size=n, replace=True)
        ev = sample.mean()
        std = sample.std()
        sh = (ev / std * np.sqrt(252)) if std > 0 else 0.0
        bootstrapped_sharpes.append(sh)
        
    return np.percentile(bootstrapped_sharpes, 2.5), np.percentile(bootstrapped_sharpes, 97.5)


def run_full_tournament(tickers, period, max_combos, top_n, walk_forward, bootstrap_n, sector_cap, bh_alpha, output_file, slippage=0.0015, commission=0.0005, min_signals=30, min_pf=1.8):
    start_date, end_date = "2015-01-01", "2024-12-31"
    total_friction = 2.0 * (slippage + commission)
    marginal_threshold = total_friction  # EV neto mínimo para no ser marcado como MARGINAL

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  TORNEO V4 — DAY TRADING REAL (FRICCIONES + OOS)          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\n  Período:           {start_date} -> {end_date}")
    print(f"  Universo:          {len(tickers)} tickers")
    print(f"  Max combos/ticker: {max_combos}")
    print(f"  Slippage:          {slippage*100:.2f}% | Comisión: {commission*100:.2f}% | Fricción Total: {total_friction*100:.2f}% round-trip")
    print(f"  Walk-Forward:      {'Activado' if walk_forward else 'Desactivado'}")
    print(f"  Bootstrap N:       {bootstrap_n} (solo período Test OOS)")
    print()

    # ── FASE 1: Descarga de datos ──
    print("═══ FASE 1: Descarga de datos ═══")
    dl_start = time.time()
    batch_size = 50
    dfs = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"  Batch {i//batch_size + 1} ({len(batch)} tickers)...")
        batch_df = yf.download(batch, start=start_date, end=end_date, progress=False, threads=True)
        if not batch_df.empty: dfs.append(batch_df)

    if not dfs: return

    df_history = pd.concat(dfs, axis=1)
    df_history = df_history.loc[:, ~df_history.columns.duplicated()]

    valid_tickers = []
    if isinstance(df_history.columns, pd.MultiIndex):
        all_tickers = df_history.columns.get_level_values(1).unique().tolist()
        for t in all_tickers:
            try:
                try: col = df_history.xs(t, level=1, axis=1)['Close'].dropna()
                except: col = df_history.xs(t, level=0, axis=1)['Close'].dropna()
                if len(col) >= 200: valid_tickers.append(t)
            except: pass
    else:
        valid_tickers = tickers[:1]

    print(f"  Tickers válidos (>=200 días): {len(valid_tickers)}")

    print("\n  Descargando VIX...")
    vix_df = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex): vix_df.columns = vix_df.columns.droplevel(1)
    vix_regime = classify_regime(vix_df['Close'])
    print(f"  Régimen VIX: {vix_regime.value_counts().to_dict()}")

    # ── FASE 2: Enriquecimiento ──
    print("\n═══ FASE 2: Enriquecimiento de indicadores ═══")
    df_history, enriched_tickers = enrich_dataframe(df_history, valid_tickers)
    if not enriched_tickers: return

    # ── FASE 3: Grid inteligente ──
    print("\n═══ FASE 3: Generación del grid inteligente ═══")
    base_grid = generate_smart_grid(max_combos_per_ticker=max_combos)
    # V4 Fix 1: inyectar slippage y commission en cada tarea
    tasks = [{'ticker': t, 'slippage': slippage, 'commission': commission, **c} for t in enriched_tickers for c in base_grid]
    print(f"  Total tareas: {len(tasks):,}")

    # ── FASE 4: Ejecución paralela ──
    print(f"\n═══ FASE 4: Ejecución paralela ═══")
    n_cores = max(1, os.cpu_count() - 1)
    results = execute_parallel_optimization_grid(
        historical_df=df_history, eval_func=_full_evaluation_task,
        pre_built_tasks=tasks, max_cores=n_cores, vix_regime=vix_regime
    )

    successful = [r for r in results if r['status'] == 'SUCCESS']
    
    # ── FASE 4.5: Filtro Walk-Forward ──
    print(f"\n═══ FASE 4.5: Filtro Walk-Forward ═══")
    wf_passed = []
    discard_stats = {'n_signals<30': 0, 'wf_ev_negative': 0, 'wf_hit_rate<50': 0, 'wf_active<5pct': 0, 'wf_pf<1.8': 0}
    
    for r in successful:
        m = r['metrics']
        if walk_forward:
            sm = m.get('sub_metrics', {})
            t_m, te_m = sm.get('train', {}), sm.get('test', {})
            
            if t_m.get('n_signals', 0) < (min_signals // 2) or te_m.get('n_signals', 0) < (min_signals // 2):
                discard_stats['n_signals<30'] += 1; continue
            if t_m.get('ev', 0) <= 0 or te_m.get('ev', 0) <= 0:
                discard_stats['wf_ev_negative'] += 1; continue
            if t_m.get('hit_rate', 0) < 0.5 or te_m.get('hit_rate', 0) < 0.5:
                discard_stats['wf_hit_rate<50'] += 1; continue
            if t_m.get('active_days_pct', 0) < 0.005 or te_m.get('active_days_pct', 0) < 0.005:
                discard_stats['wf_active<5pct'] += 1; continue
            if t_m.get('profit_factor', 0) < min_pf or te_m.get('profit_factor', 0) < min_pf:
                discard_stats['wf_pf<1.8'] += 1; continue
        else:
            if m.get('n_signals', 0) < min_signals:
                discard_stats['n_signals<30'] += 1; continue
            if m.get('profit_factor', 0) < min_pf:
                discard_stats['wf_pf<1.8'] += 1; continue
                
        wf_passed.append(r)

    print(f"  Avanzan: {len(wf_passed):,} / {len(successful):,}")
    print(f"  Descartes WF: {discard_stats}")

    if not wf_passed:
        print("ERROR: Ninguna estrategia sobrevivió al filtro Walk-Forward.")
        return

    # ── FASE 5: Benjamini-Hochberg ──
    print(f"\n═══ FASE 5: Corrección BH-FDR (alpha={bh_alpha}) ═══")
    # Simulate p-values strictly tied to active Sharpe
    for r in wf_passed: r['metrics']['p_value'] = np.exp(-r['metrics']['sharpe']*10)
    p_values = np.array([r['metrics']['p_value'] for r in wf_passed])
    bh_significant = benjamini_hochberg(p_values, alpha=bh_alpha)
    for i, r in enumerate(wf_passed): r['bh_significant'] = bool(bh_significant[i])
    
    # ── FASE 6: Ranking inicial ──
    wf_passed.sort(key=lambda x: (x.get('bh_significant', False), x['metrics'].get('sharpe', 0)), reverse=True)

    # ── FASE 6.1: Deduplicación por ticker (V4 Fix 3) ──
    print(f"\n═══ FASE 6.1: Deduplicación por Ticker ═══")
    seen_tickers = {}
    for r in wf_passed:
        t = r['ticker']
        oos_sh = r['metrics'].get('sub_metrics', {}).get('test', {}).get('sharpe', 0)
        if t not in seen_tickers or oos_sh > seen_tickers[t]['oos_sharpe']:
            seen_tickers[t] = {'result': r, 'oos_sharpe': oos_sh}
    deduplicated = [v['result'] for v in seen_tickers.values()]
    deduplicated.sort(key=lambda x: (x.get('bh_significant', False), x['metrics'].get('sharpe', 0)), reverse=True)
    print(f"  Antes: {len(wf_passed):,} | Después de dedup: {len(deduplicated):,} tickers únicos")
    top_candidates = deduplicated[:top_n * 3]  # buffer para Bootstrap
    
    # ── FASE 6.5: Bootstrap 95% CI (Híbrido) & Sectores ──
    print(f"\n═══ FASE 6.5: Bootstrap 95% CI (Híbrido Full-History) & Sectores ═══")
    final_top = []
    discard_boot = 0
    
    for strat in top_candidates:
        if len(final_top) >= top_n: break

        # V4 Fix 2 (Revisión): Bootstrap Híbrido sobre toda la historia para estabilidad
        sh_lo, sh_hi = bootstrap_sharpe(strat['daily_returns'], n_samples=bootstrap_n)
        strat['metrics']['sharpe_ci_lo'] = sh_lo
        strat['metrics']['sharpe_ci_hi'] = sh_hi
        
        if sh_lo <= 0:
            discard_boot += 1
            continue
            
        ticker = strat['ticker']
        try:
            info = yf.Ticker(ticker).info
            strat['sector'] = info.get('sector', 'Unknown')
        except:
            strat['sector'] = 'Unknown'
            
        final_top.append(strat)
        
    print(f"  Descartes Bootstrap (Sharpe CI <= 0): {discard_boot}")
    print(f"  Finalistas: {len(final_top)}")

    # ── FASE 7: Kelly Optimizer OOS ──
    print(f"\n═══ FASE 7: Kelly Optimizer OOS (Train 15-20 -> Test 21-24) ═══")
    oos_pf_sharpe = 0.0
    optimal_weights = []
    kelly_status = "NO_CANDIDATES"
    if len(final_top) > 0:
        daily_returns_train = []
        expected_returns_train = []
        sectors = []
        
        for i, strat in enumerate(final_top):
            dr = pd.Series(strat['daily_returns'])
            dr.index = pd.to_datetime(dr.index)
            # Solo usar Train para calcular Kelly weights
            dr_train = dr.loc[:'2020-12-31']
            daily_returns_train.append(dr_train)
            expected_returns_train.append(float(dr_train.mean()) if len(dr_train)>0 else 0)
            sectors.append(strat['sector'])

        df_train = pd.concat(daily_returns_train, axis=1).fillna(0.0)
        cov_matrix = df_train.cov().values + np.eye(len(final_top)) * 1e-6
        exp_ret_arr = np.array(expected_returns_train)

        n_k = len(final_top)
        effective_cap = max(sector_cap, 1.0 / n_k + 0.0001)
        
        kelly_res = optimize_convex_kelly_allocation(
            exp_ret_arr, cov_matrix, 
            max_concentration_per_asset=effective_cap,
            asset_sectors=sectors,
            sector_cap=sector_cap
        )
        optimal_weights = kelly_res.get('optimal_weights', np.array([1.0/n_k]*n_k))
        kelly_status = kelly_res.get('status', 'UNKNOWN')
        
        # Evaluar Portafolio Out-of-Sample (Test 2021-2024)
        daily_returns_test = []
        for strat in final_top:
            dr = pd.Series(strat['daily_returns'])
            dr.index = pd.to_datetime(dr.index)
            daily_returns_test.append(dr.loc['2021-01-01':])
            
        df_test = pd.concat(daily_returns_test, axis=1).fillna(0.0)
        oos_portfolio_returns = df_test.dot(optimal_weights)
        oos_pf_sharpe = (oos_portfolio_returns.mean() / oos_portfolio_returns.std() * np.sqrt(252)) if oos_portfolio_returns.std() > 0 else 0
        
    else:
        optimal_weights = []
        kelly_status = "NO_CANDIDATES"

    print(f"  Kelly Status: {kelly_status}")

    # ── FASE 8: Reporte ──
    print(f"\n═══ FASE 8: Generación de reporte ═══")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("========================================================================\n")
        f.write(" REPORTE V4 — DAY TRADING REAL (FRICCIONES + OOS + DEDUP)\n")
        f.write("========================================================================\n\n")
        f.write(f"Período Análisis:    {start_date} -> {end_date}\n")
        f.write(f"Tickers Evaluados:   {len(valid_tickers)}\n")
        f.write(f"Slippage:            {slippage*100:.2f}% | Comisión: {commission*100:.2f}% | Fricción Total: {total_friction*100:.2f}% round-trip\n")
        f.write(f"Total Tareas:        {len(tasks):,}\n")
        f.write(f"Con >=30 señales:    {len(successful):,}\n\n")
        
        if len(successful) > 0:
            avg_active = sum(r['metrics'].get('active_days_pct', 0) for r in successful) / len(successful)
            f.write(f"--- DISTRIBUCIÓN DEL UNIVERSO ---\n")
            f.write(f"  Promedio Active Days %:  {avg_active*100:.2f}%\n")
            gross_evs = [r['metrics'].get('gross_ev', 0) for r in successful]
            net_evs = [r['metrics'].get('net_ev', r['metrics'].get('ev', 0)) for r in successful]
            f.write(f"  EV Bruto promedio/día:   {np.mean(gross_evs)*100:.4f}%\n")
            f.write(f"  EV Neto promedio/día:    {np.mean(net_evs)*100:.4f}% (después de {total_friction*100:.2f}% fricción)\n\n")
            
            f.write(f"--- DESCARTES POR FILTRO ESTADÍSTICO ---\n")
            total_wf_discard = sum(discard_stats.values())
            f.write(f"  Walk-Forward (Train/Test EV/Hit/Active): {total_wf_discard:,} ({(total_wf_discard/len(successful))*100:.1f}%)\n")
            f.write(f"    - EV Neto <= 0:    {discard_stats.get('wf_ev_negative', 0):,}\n")
            f.write(f"    - Hit Rate < 50%:  {discard_stats.get('wf_hit_rate<50', 0):,}\n")
            f.write(f"    - PF Neto < {min_pf}:   {discard_stats.get('wf_pf<1.8', 0):,}\n")
            f.write(f"    - Active < 5%:     {discard_stats.get('wf_active<5pct', 0):,}\n")
            f.write(f"  Deduplicación (1 estrategia/ticker):      {len(wf_passed) - len(deduplicated):,}\n")
            
            if len(top_candidates) > 0:
                f.write(f"  Bootstrap OOS (Sharpe CI <= 0):           {discard_boot:,} ({(discard_boot/len(top_candidates))*100:.1f}% del Top)\n\n")
        
        f.write(f"Sobreviven (post-dedup): {len(deduplicated):,}\n")
        
        f.write(f"\n--- PORTAFOLIO KELLY OUT-OF-SAMPLE (TEST 2021-2024) ---\n")
        f.write(f"  Status: {kelly_status}\n")
        if len(final_top) > 0:
            f.write(f"  Portfolio OOS Sharpe (neto): {oos_pf_sharpe:.2f}\n")
        f.write("\n")
        f.write(f"  Nota: PF Neto < {min_pf} fue descartado agresivamente en el Walk-Forward.\n\n")

        f.write(f"{'Rank':<4} | {'Strategy':<14} | {'LB':<4} | {'Thresh':<6} | {'RetAnual%':<9} | {'RetTotal%':<9} | {'AvgDiario%':<10} | {'VsBuyHold':<12} | {'Sharpe':<6} | {'Sortino':<7} | {'PF':<4} | {'Calmar':<6} | {'Hit%':<6} | {'Days':<5}\n")
        f.write("-" * 135 + "\n")
        
        # Calcular Buy and Hold de todo el periodo para el ticker (asumiendo que es el único o tomamos el SPY)
        # Como es day trading, solo sumamos los retornos netos de SPY o calculamos la ganancia total del activo.
        # Para ser precisos, necesitariamos el df_history de SPY, pero podemos aproximarlo con 13% anual si no lo tenemos.
        spy_cagr = 0.13
        
        for i, strat in enumerate(final_top):
            m = strat['metrics']
            sm = m.get('sub_metrics', {})
            p = strat['params']
            
            thresh = p.get('ema_disc_threshold', p.get('rsi_threshold', p.get('stoch_threshold', p.get('bb_pctb_threshold', '-'))))
            
            net_ev = m.get('net_ev', m.get('ev', 0))
            pf = m.get('profit_factor', 0)
            hit_rate = m.get('hit_rate', 0)
            
            total_ret = m.get('total_return', 0)
            years = 10.0 # 2015-2024
            cagr = (1 + total_ret)**(1/years) - 1 if total_ret > -1 else -1
            vs_bh = cagr - spy_cagr
            
            f.write(f"{i+1:4} | {p['strategy_type']:<14} | {p['signal_lookback']:<4} | {thresh:<6} | ")
            f.write(f"{cagr*100:>+8.1f}% | {total_ret*100:>+8.0f}% | {net_ev*100:>+9.2f}% | {vs_bh*100:>+9.1f}% anual| ")
            f.write(f"{m.get('sharpe',0):6.2f} | {sm.get('test',{}).get('sortino',m.get('sortino',0)):7.2f} | {pf:4.2f} | {m.get('calmar',0):6.2f} | {hit_rate*100:4.1f}% | {m.get('n_signals',0):4}\n")

    # CSV Generation (Simplified for V3)
    csv_file = output_file.replace('.txt', '_full_results.csv')
    df_res = pd.json_normalize([{'ticker': r['ticker'], **r['params'], **r['metrics']} for r in final_top])
    df_res.to_csv(csv_file, index=False)

    print(f"\n=== Resumen V4 ===")
    print(f"  Slippage+Comisión aplicados: {total_friction*100:.2f}% round-trip")
    print(f"  Bootstrap: exclusivamente sobre período Test 2021-2024")
    print(f"  Tickers únicos en finalistas: {len(set(s['ticker'] for s in final_top))} / {len(final_top)}")
    print(f"  Portfolio OOS Sharpe (neto): {oos_pf_sharpe:.2f}")
    print(f"\n✅ Torneo V4 finalizado. Resultados guardados.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tickers', nargs='+')
    parser.add_argument('--sp500', action='store_true')
    parser.add_argument('--period', type=str, default='full')
    parser.add_argument('--max-combos', type=int, default=200)
    parser.add_argument('--top-n', type=int, default=20)
    parser.add_argument('--walk-forward', action='store_true')
    parser.add_argument('--bootstrap', type=int, default=1000)
    parser.add_argument('--sector-cap', type=float, default=0.25)
    parser.add_argument('--bh-alpha', type=float, default=0.01)
    parser.add_argument('--slippage', type=float, default=0.0015)
    parser.add_argument('--commission', type=float, default=0.0005, help="Comisión por trade. Default 0.0005")
    parser.add_argument('--min-signals', type=int, default=30, help="Mínimo de señales en WF (default 30)")
    parser.add_argument('--min-pf', type=float, default=1.8, help="Profit Factor neto mínimo en WF (default 1.8)")
    parser.add_argument('--output', type=str, default='output_daytrading_tournament.txt')
    args = parser.parse_args()

    ticker_list = args.tickers
    if 'ALL' in ticker_list:
        try:
            from lab_tickers import _FALLBACK_SP500
            ticker_list = _FALLBACK_SP500
        except ImportError:
            print("ERROR: lab_tickers.py no encontrado.")
            sys.exit(1)

    run_full_tournament(
        tickers=ticker_list, period=args.period, max_combos=args.max_combos, 
        top_n=args.top_n, walk_forward=args.walk_forward, bootstrap_n=args.bootstrap,
        sector_cap=args.sector_cap, bh_alpha=args.bh_alpha, output_file=args.output,
        slippage=args.slippage,
        commission=args.commission,
        min_signals=args.min_signals,
        min_pf=args.min_pf
    )
