import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import logging
import datetime
import multiprocessing
import os

from lab.indicators import rsi, bollinger_pctB, stochastic_k, ema_discount
from lab.regime_detector import classify_regime

# Copia de reglas locales para desacoplar de lab.rule_engine y app.py
THRESHOLDS_BY_REGIME = {
    "CALM":       {"EMA200_disc": 5.0,  "BB_pctB": 0.30, "Stoch_K": 35},
    "SLOW_BEAR":  {"EMA200_disc": 8.0,  "BB_pctB": 0.30, "Stoch_K": 35},
    "FAST_CRASH": {"EMA200_disc": 12.0, "BB_pctB": 999,  "Stoch_K": 999},
}

RULE_SETS = {
    "CALM":       {"indicators": {"primary": [("EMA200_disc", 5.0)]}},
    "SLOW_BEAR":  {"indicators": {"primary": [("EMA200_disc", 8.0), ("BB_pctB", 0.30), ("Stoch_K", 35)]}},
    "FAST_CRASH": {"indicators": {"primary": [("EMA200_disc", 12.0)]}},
}

def ewma_var(rets, alpha=0.05):
    """Calcula EWMA variance puro en numpy para GARCH proxy"""
    if len(rets) == 0: return 0.0
    var = np.zeros_like(rets)
    var[0] = rets[0]**2
    for i in range(1, len(rets)):
        var[i] = alpha * (rets[i]**2) + (1 - alpha) * var[i-1]
    return var[-1]

def process_ticker_history(args):
    """
    Función Worker top-level para ProcessPoolExecutor.
    Recibe los datos históricos de un ticker y los eval_dates.
    Devuelve los trades candidatos por fecha.
    """
    t, precomp_dict, eval_dates_list, vix_history_dict = args
    res = []
    try:
        # Extraer numpy arrays
        dates_arr = precomp_dict['dates']
        close_vals = precomp_dict['Close']
        open_vals = precomp_dict['Open']
        high_vals = precomp_dict['High']
        low_vals = precomp_dict['Low']
        vol_vals = precomp_dict['Volume']
        
        ema_vals = precomp_dict['EMA200_disc']
        bb_vals = precomp_dict['BB_pctB']
        stoch_vals = precomp_dict['Stoch_K']
        rsi_vals = precomp_dict['RSI']
        vol_avg_vals = precomp_dict['Volume_Avg']
        
        # Retornos intraday precomputados
        intraday_rets = (close_vals / open_vals - 1)
        # Retornos C a C para MC
        cc_rets = np.zeros_like(close_vals)
        cc_rets[1:] = (close_vals[1:] / close_vals[:-1]) - 1

        # Crear diccionario lookup dates
        date_to_idx = {d: i for i, d in enumerate(dates_arr)}

        for date_str in eval_dates_list:
            if date_str not in date_to_idx:
                continue
            idx = date_to_idx[date_str]
            if idx < 252: 
                continue
            prev_date_str = dates_arr[idx - 1]
            regime = vix_history_dict.get(prev_date_str, "CALM")
            price = close_vals[idx - 1]
            if price <= 0: continue
            
            # 1. Filtros Técnicos y de Régimen (copiados de app.py)
            vol_avg = vol_avg_vals[idx - 1]
            if vol_avg < 5_000_000:
                continue
                
            # ATR 14 proxy 
            atr_lookback = max(0, idx - 14)
            tr = np.maximum(high_vals[atr_lookback:idx] - low_vals[atr_lookback:idx], 
                 np.maximum(np.abs(high_vals[atr_lookback:idx] - close_vals[max(0, atr_lookback-1):idx-1]), 
                            np.abs(low_vals[atr_lookback:idx] - close_vals[max(0, atr_lookback-1):idx-1])))
            atr_14 = np.mean(tr)
            atr_pct = (atr_14 / price) * 100
            if atr_pct < 1.0:
                continue

            ema_disc = ema_vals[idx - 1]
            ind_vals = {
                'EMA200_disc': ema_disc,
                'BB_pctB': bb_vals[idx - 1],
                'Stoch_K': stoch_vals[idx - 1],
                'RSI': rsi_vals[idx - 1]
            }
            
            rules = RULE_SETS.get(regime, RULE_SETS["CALM"])
            dyn_th = THRESHOLDS_BY_REGIME.get(regime, THRESHOLDS_BY_REGIME["CALM"])["EMA200_disc"]
            primary_met = False
            
            for ind_name, th in rules["indicators"]["primary"]:
                val = ind_vals.get(ind_name, np.nan)
                if np.isnan(val): continue
                direction = 'above' if ind_name == 'EMA200_disc' else 'below'
                if (direction == 'above' and val >= th) or (direction == 'below' and val <= th):
                    primary_met = True
                    break
                    
            is_close_or_met = primary_met or (not np.isnan(ema_disc) and ema_disc >= dyn_th * 0.5)
            
            rsi_val = ind_vals['RSI']
            passed_rsi = False
            if not np.isnan(rsi_val) and (35 <= rsi_val <= 65):
                passed_rsi = is_close_or_met
                
            if not passed_rsi:
                continue
                
            # Filtro fundamental mockeado (stars=10 neutral positivo en app.py min_stars=10 para CALM)
            stars = 10
            min_stars = 10
            fund_ok = stars >= min_stars
            if not primary_met or not fund_ok:
                continue

            # 2. Monte Carlo 5 Días (numpy puro con GARCH EWMA)
            hist_rets = cc_rets[max(0, idx-252):idx]
            hist_rets = hist_rets[~np.isnan(hist_rets)]
            if len(hist_rets) < 50:
                continue

            # GARCH Proxy
            hist_vol = np.std(hist_rets)
            var_ewma = ewma_var(hist_rets, alpha=0.05)
            garch_vol = np.sqrt(var_ewma) if var_ewma > 0 else hist_vol
            vol_scaling = garch_vol / hist_vol if hist_vol > 0 else 1.0

            scaled_returns = hist_rets * vol_scaling
            log_hist_returns = np.log1p(scaled_returns)
            
            # Horizon=5 days, N=10000
            sampled_log_returns = np.random.choice(log_hist_returns, size=(5, 5000), replace=True)
            cumulative_returns = np.sum(sampled_log_returns, axis=0)
            
            pnl = np.exp(cumulative_returns) - 1.0
            
            p_gt_2 = np.mean(pnl > 0.02)
            p10 = np.percentile(pnl, 10)
            
            # Filtro MC (app.py)
            if p_gt_2 < 0.35 or p10 < -0.10:
                continue
                
            pos_mask = pnl > 0
            prob_positive = np.mean(pos_mask) * 100
            expected_value = np.mean(pnl) * 100
            
            pos_returns = pnl[pnl > 0]
            neg_returns = pnl[pnl <= 0]
            mean_pos = np.mean(pos_returns) * 100 if len(pos_returns) > 0 else 0.0
            mean_neg = np.mean(neg_returns) * 100 if len(neg_returns) > 0 else 0.0
            
            open_p = open_vals[idx]
            if open_p > 0:
                max_fwd = min(len(close_vals), idx + 5)
                fwd_highs = high_vals[idx:max_fwd]
                fwd_lows = low_vals[idx:max_fwd]
                fwd_closes = close_vals[idx:max_fwd]
                res.append({
                    'date': date_str,
                    'ticker': t,
                    'buy_price': open_p,
                    'sell_price': fwd_closes[-1] if len(fwd_closes) > 0 else close_vals[-1],
                    'fwd_highs': fwd_highs,
                    'fwd_lows': fwd_lows,
                    'fwd_closes': fwd_closes,
                    'score': expected_value, # Usamos EV para rankear
                    'prob_positive': prob_positive,
                    'expected_value': expected_value,
                    'mean_pos': mean_pos,
                    'mean_neg': mean_neg,
                })
    except Exception as e:
        # Silencioso por worker
        pass
    return res

def run_historical_backtest(tickers, days_back=90, capital=10000, max_positions=10, state_dict=None):
    if state_dict is None:
        state_dict = {}

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days_back + 400)
    
    state_dict['status'] = 'Descargando datos históricos...'
    state_dict['progress'] = 0.0
    
    # 1. Bajar VIX
    try:
        tk = yf.Ticker("^VIX")
        vix_df = tk.history(start=start_date, end=end_date)
        if vix_df.empty:
            raise ValueError("Yahoo Finance no devolvió datos para el VIX.")
            
        vix_df = vix_df.dropna(subset=['Close'])
        vix_df.index = vix_df.index.tz_localize(None)
        regimes = classify_regime(vix_df['Close'])
        vix_history = pd.DataFrame({'Close': vix_df['Close'], 'Regime': regimes}, index=vix_df.index)
            
    except Exception as e:
        state_dict['status'] = f'Error en VIX: {e}'
        state_dict['error'] = True
        return None

    # 2. Leer Parquets o descargar de yfinance
    state_dict['status'] = 'Leyendo precios de S&P 500...'
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_5y")
        df_close_dict, df_open_dict, df_high_dict, df_low_dict, df_vol_dict = {}, {}, {}, {}, {}
        start_ts = pd.Timestamp(start_date).tz_localize(None)
        
        tickers_to_download = []
        for t in tickers:
            fpath = os.path.join(data_dir, f"{t}.parquet")
            if os.path.exists(fpath):
                df_t = pd.read_parquet(fpath)
                df_t.index = df_t.index.tz_localize(None)
                df_t = df_t[df_t.index >= start_ts]
                if not df_t.empty:
                    df_close_dict[t] = df_t['Close']
                    df_open_dict[t] = df_t['Open']
                    df_high_dict[t] = df_t['High']
                    df_low_dict[t] = df_t['Low']
                    df_vol_dict[t] = df_t['Volume']
            else:
                tickers_to_download.append(t)
                
        if tickers_to_download:
            state_dict['status'] = f'Descargando {len(tickers_to_download)} tickers vía API...'
            data = yf.download(tickers_to_download, start=start_date, end=end_date, progress=False, threads=True)
            for t in tickers_to_download:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        try: tdf = data.xs(t, level=1, axis=1).dropna(subset=['Close'])
                        except: tdf = data.xs(t, level=0, axis=1).dropna(subset=['Close'])
                    else:
                        tdf = data.dropna(subset=['Close'])
                    if not tdf.empty:
                        df_close_dict[t] = tdf['Close']
                        df_open_dict[t] = tdf['Open']
                        df_high_dict[t] = tdf['High']
                        df_low_dict[t] = tdf['Low']
                        df_vol_dict[t] = tdf['Volume']
                except Exception:
                    pass

        df_close = pd.DataFrame(df_close_dict).ffill()
        df_open = pd.DataFrame(df_open_dict).ffill()
        df_high = pd.DataFrame(df_high_dict).ffill()
        df_low = pd.DataFrame(df_low_dict).ffill()
        df_vol = pd.DataFrame(df_vol_dict).fillna(0)
    except Exception as e:
        state_dict['status'] = f'Error: {e}'
        state_dict['error'] = True
        return None

    eval_dates = vix_history.index[-days_back:]
    eval_dates_str = [d.strftime('%Y-%m-%d') for d in eval_dates]
    vix_regime_dict = {d.strftime('%Y-%m-%d'): r for d, r in zip(vix_history.index, vix_history['Regime'])}
    
    portfolio = capital
    equity_curve = []
    trades = []
    
    state_dict['status'] = 'Pre-calculando indicadores técnicos...'
    worker_args = []
    
    for c_idx, t in enumerate(df_close.columns):
        if c_idx % 50 == 0:
            state_dict['progress'] = c_idx / len(df_close.columns) * 0.2
            
        df_t = pd.DataFrame({
            'Open': df_open[t], 'High': df_high[t], 'Low': df_low[t],
            'Close': df_close[t], 'Volume': df_vol[t]
        }).dropna()
        if len(df_t) < 252: continue
            
        df_t['EMA200_disc'] = ema_discount(df_t)
        df_t['BB_pctB'] = bollinger_pctB(df_t)
        df_t['Stoch_K'] = stochastic_k(df_t)
        df_t['RSI'] = rsi(df_t)
        df_t['Volume_Avg'] = df_t['Volume'].rolling(20).mean()
        
        precomp_dict = {
            'dates': [d.strftime('%Y-%m-%d') for d in df_t.index],
            'Close': df_t['Close'].values, 'Open': df_t['Open'].values,
            'High': df_t['High'].values, 'Low': df_t['Low'].values,
            'Volume': df_t['Volume'].values, 'EMA200_disc': df_t['EMA200_disc'].values,
            'BB_pctB': df_t['BB_pctB'].values, 'Stoch_K': df_t['Stoch_K'].values,
            'RSI': df_t['RSI'].values, 'Volume_Avg': df_t['Volume_Avg'].values
        }
        worker_args.append((t, precomp_dict, eval_dates_str, vix_regime_dict))

    state_dict['status'] = 'Simulando día a día (ProcessPool Multiprocessing)...'
    all_candidates = []
    
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count() or 4) as executor:
        futures = [executor.submit(process_ticker_history, arg) for arg in worker_args]
        for idx, fut in enumerate(as_completed(futures)):
            all_candidates.extend(fut.result())
            if idx % 20 == 0:
                state_dict['progress'] = 0.2 + (idx / len(worker_args) * 0.6)

    candidates_by_date = {}
    for c in all_candidates:
        candidates_by_date.setdefault(c['date'], []).append(c)

    if state_dict.get('return_raw_candidates', False):
        return {
            'candidates_by_date': candidates_by_date,
            'eval_dates_str': eval_dates_str,
            'vix_history_dict': vix_regime_dict
        }

    state_dict['status'] = 'Ensamblando trades...'
    
    active_positions = []  # Lista de dicts: {'ticker', 'sell_date', 'shares', 'buy_price'}
    
    for i, date_str in enumerate(eval_dates_str):
        state_dict['progress'] = 0.8 + ((i + 1) / len(eval_dates_str) * 0.2)
        
        # 1. Vender posiciones que expiraron (horizonte=5 días)
        remaining_positions = []
        for pos in active_positions:
            if pos['sell_date'] <= date_str:
                # Sell
                profit_cash = pos['shares'] * pos['sell_price_real']
                portfolio += profit_cash
                pnl = (pos['sell_price_real'] - pos['buy_price']) / pos['buy_price']
                trades.append({
                    'ticker': pos['ticker'],
                    'buy_date': pos['buy_date'],
                    'sell_date': pos['sell_date'],
                    'buy_price': pos['buy_price'],
                    'sell_price': pos['sell_price_real'],
                    'pnl_pct': pnl * 100,
                    'profit_usd': profit_cash - (pos['shares'] * pos['buy_price']),
                    'expected_value': pos.get('expected_value', 0),
                    'prob_positive': pos.get('prob_positive', 0),
                    'mean_pos': pos.get('mean_pos', 0),
                    'mean_neg': pos.get('mean_neg', 0)
                })
            else:
                remaining_positions.append(pos)
        active_positions = remaining_positions
        
        # 2. Comprar nuevos candidatos
        # Calculamos el Max Positions del VIX (de ayer)
        if i == 0:
            prev_date_str = date_str
        else:
            prev_date_str = eval_dates_str[i-1]
            
        regime = vix_regime_dict.get(prev_date_str, "CALM")
        
        vix_slots = {"CALM": 10, "SLOW_BEAR": 1, "FAST_CRASH": 1}
        dyn_max_pos = vix_slots.get(regime, 10)
        
        candidates = candidates_by_date.get(date_str, [])
        candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)[:dyn_max_pos]
        
        # Asignar solo capital libre, y si quedan slots
        slots_available = dyn_max_pos - len(active_positions)
        if slots_available <= 0:
            candidates = []
        else:
            candidates = candidates[:slots_available]
        
        if candidates and portfolio > 0:
            alloc_per_ticker = portfolio / len(candidates)
            for c in candidates:
                shares = alloc_per_ticker / c['buy_price']
                portfolio -= alloc_per_ticker
                
                active_positions.append({
                    'ticker': c['ticker'],
                    'buy_date': date_str,
                    # Como sell_price_real fue simulado para el dia de salida
                    'sell_date': (datetime.datetime.strptime(date_str, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime('%Y-%m-%d'), # ~5 dias habiles
                    'shares': shares,
                    'buy_price': c['buy_price'],
                    'sell_price_real': c['sell_price'],
                    'expected_value': c.get('expected_value', 0),
                    'prob_positive': c.get('prob_positive', 0),
                    'mean_pos': c.get('mean_pos', 0),
                    'mean_neg': c.get('mean_neg', 0)
                })
        
        # Calcular equity no realizada
        unrealized = sum([pos['shares'] * pos['buy_price'] for pos in active_positions]) # aprox
        current_equity = portfolio + unrealized
        equity_curve.append({'date': date_str, 'equity': current_equity})

    # Forzar venta al final
    for pos in active_positions:
        profit_cash = pos['shares'] * pos['sell_price_real']
        portfolio += profit_cash
        pnl = (pos['sell_price_real'] - pos['buy_price']) / pos['buy_price']
        trades.append({
            'ticker': pos['ticker'], 'buy_date': pos['buy_date'], 'sell_date': pos['sell_date'],
            'buy_price': pos['buy_price'], 'sell_price': pos['sell_price_real'],
            'pnl_pct': pnl * 100, 'profit_usd': profit_cash - (pos['shares'] * pos['buy_price']),
            'expected_value': pos.get('expected_value', 0),
            'prob_positive': pos.get('prob_positive', 0),
            'mean_pos': pos.get('mean_pos', 0),
            'mean_neg': pos.get('mean_neg', 0)
        })
    
    current_equity = portfolio
    if equity_curve:
        equity_curve[-1]['equity'] = current_equity

    state_dict['status'] = 'Generando reporte...'
    df_equity = pd.DataFrame(equity_curve)
    df_trades = pd.DataFrame(trades)
    
    total_return = ((current_equity / capital) - 1) * 100
    win_rate = (len(df_trades[df_trades['pnl_pct'] > 0]) / len(df_trades) * 100) if len(df_trades) > 0 else 0
    
    res = {
        'equity_curve': df_equity,
        'trades': df_trades,
        'initial_capital': capital,
        'final_equity': current_equity,
        'total_return_pct': total_return,
        'win_rate': win_rate,
        'total_trades': len(df_trades)
    }
    state_dict['result'] = res
    state_dict['status'] = 'completed'
    return res
