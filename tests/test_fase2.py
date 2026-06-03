"""
╔══════════════════════════════════════════════════════════╗
║  TEST FASE 2 — Backtest Histórico Riguroso              ║
║  Fase 2 (V4) vs Equal Weight vs SPY Buy-and-Hold        ║
╚══════════════════════════════════════════════════════════╝

Uso:
  python test_fase2.py --tickers NVDA,AAPL,META,MSFT --period 2021-2024 --capital 10000

El test simula día a día:
  - Fase 2 (V4): composite_score × vol_parity × caps
  - Equal Weight: mismo capital dividido equitativamente
  - SPY Buy-and-Hold: referencia del mercado
"""
import sys
import os
import argparse
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf

# Importar el motor del allocator v3.0
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lab.daily_allocator import (
    compute_composite_score,
    calculate_allocations,
)

# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS DE PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────

def total_return(equity: pd.Series) -> float:
    return (equity.iloc[-1] / equity.iloc[0] - 1) * 100

def cagr(equity: pd.Series) -> float:
    n_years = len(equity) / 252
    return ((equity.iloc[-1] / equity.iloc[0]) ** (1 / n_years) - 1) * 100

def sharpe(daily_rets: pd.Series, rf: float = 0.04) -> float:
    excess = daily_rets - rf / 252
    return (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

def sortino(daily_rets: pd.Series, rf: float = 0.04) -> float:
    excess = daily_rets - rf / 252
    downside = excess[excess < 0].std()
    return (excess.mean() / downside * np.sqrt(252)) if downside > 0 else 0.0

def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return dd.min() * 100

def calmar(daily_rets: pd.Series, equity: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    return cagr(equity) / mdd if mdd > 0 else 0.0

def profit_factor(daily_rets: pd.Series) -> float:
    gains  = daily_rets[daily_rets > 0].sum()
    losses = abs(daily_rets[daily_rets < 0].sum())
    return gains / losses if losses > 0 else float('inf')

def cvar_5(daily_rets: pd.Series) -> float:
    threshold = daily_rets.quantile(0.05)
    return daily_rets[daily_rets <= threshold].mean() * 100

def worst_day(daily_rets: pd.Series) -> float:
    return daily_rets.min() * 100

# ─────────────────────────────────────────────────────────────────────────────
# OBTENER VIX HISTÓRICO
# ─────────────────────────────────────────────────────────────────────────────

def get_vix_series(start: str, end: str) -> pd.Series:
    print("  📡 Descargando VIX histórico...")
    try:
        vix = yf.download('^VIX', start=start, end=end, progress=False, auto_adjust=True)
        vix.index = pd.to_datetime(vix.index).tz_localize(None)
        return vix['Close']
    except:
        print("  ⚠ No se pudo descargar VIX, usando valor fijo 18.0")
        return pd.Series(dtype=float)

# ─────────────────────────────────────────────────────────────────────────────
# SIMULACIÓN DIARIA — FASE 2
# ─────────────────────────────────────────────────────────────────────────────

def _extract_ticker_df(price_data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extrae OHLCV de un ticker del DataFrame MultiIndex (ticker, metric)."""
    cols_needed = ['Close', 'High', 'Low', 'Volume']
    result = {}
    for c in cols_needed:
        if (ticker, c) in price_data.columns:
            result[c] = price_data[(ticker, c)]
    if 'Close' not in result:
        return pd.DataFrame()
    return pd.DataFrame(result).dropna(subset=['Close'])

def _get_close_series(price_data: pd.DataFrame, ticker: str) -> pd.Series:
    """Retorna la serie de Close para un ticker dado."""
    if (ticker, 'Close') in price_data.columns:
        return price_data[(ticker, 'Close')]
    elif 'Close' in price_data.columns:
        return price_data['Close']
    return pd.Series(dtype=float)

def simulate_fase2(price_data: pd.DataFrame, vix_series: pd.Series,
                   tickers: list, capital: float, lookback: int = 60) -> pd.Series:
    """
    Simula la estrategia Fase 2 v3.0 día a día.
    - TODOS los tickers de Fase 1 siempre entran (nunca se excluyen)
    - composite_score + sigmoid determinan CUÁNTO de cada uno
    - VIX controla el porcentaje global invertido
    """
    dates = price_data.index[lookback:]
    equity = pd.Series(index=dates, dtype=float)
    current_capital = capital

    print(f"  🔄 Simulando Fase 2 v3.0 ({len(dates)} días de trading)...")
    prev_pct = -1

    for i, date in enumerate(dates):
        pct = int(i / len(dates) * 100)
        if pct % 10 == 0 and pct != prev_pct:
            print(f"     Progreso: {pct}%...")
            prev_pct = pct

        hist_end = i + lookback
        hist_slice = price_data.iloc[:hist_end]

        try:
            vix_val = float(vix_series.loc[:date].iloc[-1]) if not vix_series.empty else 18.0
        except:
            vix_val = 18.0

        # Construir ticker_data_list — TODOS los tickers siempre entran
        ticker_data_list = []
        for t in tickers:
            try:
                tdf = _extract_ticker_df(hist_slice, t)
                if len(tdf) < 30:
                    ticker_data_list.append({
                        'ticker': t, 'composite_score': 0.0,
                        'sigmoid_multiplier': 0.5, 'vol_30d': 0.02,
                        'sector': 'Tech', 'close_series': pd.Series(dtype=float)
                    })
                    continue

                sd = compute_composite_score(tdf, vix_val)
                ticker_data_list.append({
                    'ticker':            t,
                    'composite_score':   sd['composite_score'],
                    'sigmoid_multiplier': sd['sigmoid_multiplier'],
                    'vol_30d':           max(sd['vol_30d'], 0.005),
                    'sector':            'Tech',
                    'close_series':      tdf['Close'],
                })
            except:
                ticker_data_list.append({
                    'ticker': t, 'composite_score': 0.0,
                    'sigmoid_multiplier': 0.5, 'vol_30d': 0.02,
                    'sector': 'Tech', 'close_series': pd.Series(dtype=float)
                })

        allocations, _, _ = calculate_allocations(ticker_data_list, vix_val, current_capital)

        # Calcular retorno del día con pesos asignados
        daily_ret = 0.0
        for a in allocations:
            if a['ticker'] == 'CASH':
                continue
            w = a['weight_pct'] / 100.0
            t = a['ticker']
            try:
                close_series = _get_close_series(price_data, t)
                idx_today = i + lookback
                if idx_today < len(close_series):
                    c_today = close_series.iloc[idx_today]
                    c_yest  = close_series.iloc[idx_today - 1]
                    if c_yest > 0 and np.isfinite(c_today) and np.isfinite(c_yest):
                        daily_ret += w * (c_today / c_yest - 1)
            except:
                continue

        current_capital *= (1 + daily_ret)
        equity.iloc[i] = current_capital

    print(f"     Progreso: 100% ✅")
    return equity

# ─────────────────────────────────────────────────────────────────────────────
# SIMULACIÓN DIARIA — EQUAL WEIGHT
# ─────────────────────────────────────────────────────────────────────────────

def simulate_equal_weight(price_data: pd.DataFrame, tickers: list,
                          capital: float, lookback: int = 60) -> pd.Series:
    dates = price_data.index[lookback:]
    equity = pd.Series(index=dates, dtype=float)
    current_capital = capital
    w = 1.0 / len(tickers)

    print(f"  🔄 Simulando Equal Weight ({len(dates)} días)...")
    for i, _ in enumerate(dates):
        daily_ret = 0.0
        for t in tickers:
            try:
                close_series = _get_close_series(price_data, t)
                idx_today = i + lookback
                if idx_today < len(close_series):
                    c_today = close_series.iloc[idx_today]
                    c_yest  = close_series.iloc[idx_today - 1]
                    if c_yest > 0 and not np.isnan(c_today) and not np.isnan(c_yest):
                        daily_ret += w * (c_today / c_yest - 1)
            except:
                continue
        current_capital *= (1 + daily_ret)
        equity.iloc[i] = current_capital

    print("     Equal Weight ✅")
    return equity

# ─────────────────────────────────────────────────────────────────────────────
# SIMULACIÓN — SPY BUY AND HOLD
# ─────────────────────────────────────────────────────────────────────────────

def simulate_spy_bh(price_data: pd.DataFrame, spy_data: pd.DataFrame,
                    capital: float, lookback: int = 60) -> pd.Series:
    dates = price_data.index[lookback:]

    if spy_data.empty:
        return pd.Series(capital, index=dates)

    spy_aligned = spy_data['Close'].reindex(dates, method='ffill').ffill().bfill()
    spy_ret     = spy_aligned.pct_change().fillna(0)
    equity      = capital * (1 + spy_ret).cumprod()

    first_valid = equity.first_valid_index()
    if first_valid:
        equity = equity / equity[first_valid] * capital

    print("     SPY Buy-and-Hold ✅")
    return equity

# ─────────────────────────────────────────────────────────────────────────────
# TABLA COMPARATIVA
# ─────────────────────────────────────────────────────────────────────────────

def print_comparison_table(equity_f2: pd.Series, equity_ew: pd.Series,
                            equity_spy: pd.Series, initial: float):
    systems = {
        'Fase 2 (V4)':   equity_f2,
        'Equal Weight':  equity_ew,
        'SPY B&H':       equity_spy,
    }

    metrics = {
        'Retorno Total (%)': lambda e: total_return(e),
        'CAGR (%)':          lambda e: cagr(e),
        'Sharpe':            lambda e: sharpe(e.pct_change().dropna()),
        'Sortino':           lambda e: sortino(e.pct_change().dropna()),
        'Max Drawdown (%)':  lambda e: max_drawdown(e),
        'Calmar':            lambda e: calmar(e.pct_change().dropna(), e),
        'Profit Factor':     lambda e: profit_factor(e.pct_change().dropna()),
        'CVaR 5% (%)':       lambda e: cvar_5(e.pct_change().dropna()),
        'Peor Día (%)':      lambda e: worst_day(e.pct_change().dropna()),
    }

    print("\n")
    print("═" * 75)
    print("  TABLA COMPARATIVA FINAL — Backtest Histórico")
    print("═" * 75)
    header = f"  {'Métrica':<22}"
    for name in systems:
        header += f"  {name:>14}"
    print(header)
    print("─" * 75)

    results_by_metric = {}
    for metric_name, fn in metrics.items():
        row = f"  {metric_name:<22}"
        vals = {}
        for sys_name, eq in systems.items():
            try:
                val = fn(eq.dropna())
                vals[sys_name] = val
            except:
                vals[sys_name] = float('nan')

        # Determinar el mejor (para métricas donde + es mejor)
        negative_metrics = {'Max Drawdown (%)', 'CVaR 5% (%)', 'Peor Día (%)'}
        for sys_name, val in vals.items():
            if pd.isna(val):
                row += f"  {'N/A':>14}"
            elif metric_name == 'Profit Factor' and val == float('inf'):
                row += f"  {'∞':>14}"
            else:
                row += f"  {val:>13.2f}"

        results_by_metric[metric_name] = vals
        print(row)

    print("─" * 75)

    # Veredicto
    f2_wins = 0
    total_metrics = 0
    for metric_name, vals in results_by_metric.items():
        negative_metrics = {'Max Drawdown (%)', 'CVaR 5% (%)', 'Peor Día (%)'}
        try:
            f2 = vals['Fase 2 (V4)']
            ew = vals['Equal Weight']
            spy = vals['SPY B&H']
            if pd.isna(f2) or pd.isna(ew) or pd.isna(spy):
                continue
            if metric_name in negative_metrics:
                # Menor es mejor (drawdown, CVaR son negativos o menores es mejor)
                if f2 > ew and f2 > spy:
                    f2_wins += 1
            else:
                if f2 > ew and f2 > spy:
                    f2_wins += 1
            total_metrics += 1
        except:
            continue

    print(f"\n  🏆 Fase 2 gana a AMBOS benchmarks en {f2_wins}/{total_metrics} métricas")
    if f2_wins >= total_metrics * 0.6:
        print("  ✅ VEREDICTO: La Fase 2 agrega valor real demostrable.")
    else:
        print("  ⚠ VEREDICTO: El position sizing necesita más ajuste en estas condiciones.")
    print("═" * 75)

    # Capital final
    print("\n  Capital final ($10,000 inicial):")
    for name, eq in systems.items():
        final = float(eq.dropna().iloc[-1])
        gain  = final - initial
        pct   = (final / initial - 1) * 100
        arrow = "📈" if pct > 0 else "📉"
        print(f"  {arrow} {name:<18} ${final:>10,.2f}  ({pct:+.1f}%)")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISIS 2022 — STRESS TEST DE CRISIS
# ─────────────────────────────────────────────────────────────────────────────

def print_2022_analysis(equity_f2: pd.Series, equity_ew: pd.Series, equity_spy: pd.Series):
    print("\n  📉 ANÁLISIS CRISIS 2022 (Stress Test):")
    print("─" * 75)
    for name, eq in [('Fase 2 (V4)', equity_f2), ('Equal Weight', equity_ew), ('SPY B&H', equity_spy)]:
        try:
            mask_2022 = (eq.index >= '2022-01-01') & (eq.index <= '2022-12-31')
            eq_2022 = eq[mask_2022].dropna()
            if len(eq_2022) < 10:
                print(f"  {name}: datos insuficientes para 2022")
                continue
            mdd_2022 = max_drawdown(eq_2022)
            ret_2022 = total_return(eq_2022)
            print(f"  {name:<20}  Retorno 2022: {ret_2022:>7.2f}%  |  Max Drawdown: {mdd_2022:>7.2f}%")
        except Exception as e:
            print(f"  {name}: Error — {e}")
    print("─" * 75)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Test Fase 2 — Backtest de 3 benchmarks')
    parser.add_argument('--tickers', type=str, default='NVDA,AAPL,META,MSFT',
                        help='Tickers de Fase 1 (coma separados)')
    parser.add_argument('--period',  type=str, default='2021-2024',
                        help='Período en formato YYYY-YYYY o start:end')
    parser.add_argument('--capital', type=float, default=10000.0,
                        help='Capital inicial en USD')
    parser.add_argument('--lookback', type=int, default=60,
                        help='Días de lookback para calcular indicadores (default: 60)')
    args = parser.parse_args()

    # Parsear período
    if ':' in args.period:
        start_year, end_year = args.period.split(':')
    elif '-' in args.period:
        parts = args.period.split('-')
        if len(parts) == 2:
            start_year = parts[0]
            end_year   = parts[1]
        else:
            start_year = '2021'
            end_year   = '2024'
    else:
        start_year = args.period
        end_year   = str(int(args.period) + 3)

    # Construir fechas completas
    if len(start_year) == 4:
        start_date = f"{start_year}-01-01"
    else:
        start_date = start_year
    if len(end_year) == 4:
        end_date = f"{end_year}-12-31"
    else:
        end_date = end_year

    tickers = [t.strip().upper() for t in args.tickers.split(',')]

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  TEST FASE 2 — Backtest Riguroso (3 Benchmarks)         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\n  📌 Tickers (Fase 1): {', '.join(tickers)}")
    print(f"  📅 Período: {start_date} → {end_date}")
    print(f"  💰 Capital: ${args.capital:,.0f}")
    print(f"  📊 Lookback: {args.lookback} días\n")

    # ── Descargar datos ────────────────────────────────────────────────────────
    all_tickers = tickers + ['SPY']
    print(f"  📡 Descargando datos históricos para {all_tickers}...")

    raw = yf.download(all_tickers, start=start_date, end=end_date,
                      progress=False, auto_adjust=True)
    raw.index = pd.to_datetime(raw.index).tz_localize(None)

    # Extraer datos de precio de los tickers y SPY
    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance retorna (metric, ticker), no (ticker, metric)
        # Detectar el orden real
        sample_cols = list(raw.columns[:4])
        # Si el primer nivel son métricas (Close, High...) el orden es (metric, ticker)
        first_levels = set(c[0] for c in raw.columns)
        if 'Close' in first_levels:
            # Formato (metric, ticker) → reordenar a (ticker, metric) para compatibilidad interna
            raw = raw.swaplevel(axis=1).sort_index(axis=1)

        # Ahora tenemos (ticker, metric)
        available = [t for t in tickers if (t, 'Close') in raw.columns]
        if not available:
            print("  ❌ ERROR: No se pudieron descargar datos para los tickers especificados.")
            print(f"  Columnas disponibles: {list(raw.columns[:10])}")
            return
        missing = [t for t in tickers if t not in available]
        if missing:
            print(f"  ⚠ Sin datos para: {', '.join(missing)}")
        tickers = available

        spy_data = pd.DataFrame({'Close': raw[('SPY', 'Close')]}).dropna() if ('SPY', 'Close') in raw.columns else pd.DataFrame()
        price_data = raw  # MultiIndex (ticker, metric)
    else:
        # Un solo ticker
        spy_data = pd.DataFrame({'Close': raw['Close']}).dropna()
        price_data = raw

    print(f"  ✅ Datos descargados. Período: {raw.index[0].date()} → {raw.index[-1].date()}")
    print(f"  ✅ Total de días de trading: {len(raw)}\n")

    # ── Descargar VIX ────────────────────────────────────────────────────────
    vix_series = get_vix_series(start_date, end_date)
    vix_series.index = pd.to_datetime(vix_series.index).tz_localize(None)

    lookback = min(args.lookback, len(raw) // 4)  # Safety check

    print()
    # ── Simulaciones ──────────────────────────────────────────────────────────
    print("━" * 60)
    print("  [1/3] Simulando Fase 2 (V4)...")
    equity_f2 = simulate_fase2(price_data, vix_series, tickers, args.capital, lookback)

    print()
    print("━" * 60)
    print("  [2/3] Simulando Equal Weight...")
    equity_ew = simulate_equal_weight(price_data, tickers, args.capital, lookback)

    print()
    print("━" * 60)
    print("  [3/3] Simulando SPY Buy-and-Hold...")
    equity_spy = simulate_spy_bh(price_data, spy_data, args.capital, lookback)

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    print_comparison_table(equity_f2, equity_ew, equity_spy, args.capital)
    print_2022_analysis(equity_f2, equity_ew, equity_spy)

    # ── Guardar resultados en CSV ─────────────────────────────────────────────
    output_file = f"test_fase2_results_{start_year}_{end_year}.csv"
    eq_df = pd.DataFrame({
        'Fase2_V4':     equity_f2,
        'EqualWeight':  equity_ew,
        'SPY_BnH':      equity_spy,
    })
    eq_df.to_csv(output_file)
    print(f"\n  💾 Curvas de equity guardadas en: {output_file}")
    print("\n  ✅ Test completado.\n")

if __name__ == '__main__':
    main()
