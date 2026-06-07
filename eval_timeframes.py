import os
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
from lab.backtest_engine import run_historical_backtest
from lab_tickers import fetch_sp500_tickers_wiki_v2

def run_horizon(config, candidates_by_date, eval_dates_str, vix_history_dict, spy_dict):
    capital = 10000.0
    portfolio = capital
    active_positions = []
    trades = []
    
    macro_ema = config.get('macro_ema', None)
    vix_slots = config.get('vix_slots', {"CALM": 10, "SLOW_BEAR": 10, "FAST_CRASH": 10})
    
    for i, date_str in enumerate(eval_dates_str):
        if i == 0:
            prev_date_str = date_str
            regime = "CALM"
        else:
            prev_date_str = eval_dates_str[i-1]
            regime = vix_history_dict.get(prev_date_str, "CALM")
            
        macro_ok = True
        if macro_ema and prev_date_str in spy_dict:
            if spy_dict[prev_date_str]['Close'] < spy_dict[prev_date_str][f'EMA_{macro_ema}']:
                macro_ok = False
        
        remaining_positions = []
        for pos in active_positions:
            if pos['sell_date'] <= date_str:
                profit_cash = pos['shares'] * pos['sell_price_real']
                portfolio += profit_cash
                pnl = (pos['sell_price_real'] - pos['buy_price']) / pos['buy_price']
                trades.append({
                    'pnl_pct': pnl * 100,
                    'profit_usd': profit_cash - (pos['shares'] * pos['buy_price'])
                })
            else:
                remaining_positions.append(pos)
                
        active_positions = remaining_positions
        
        if macro_ok:
            max_pos = vix_slots.get(regime, 10)
            slots_available = max_pos - len(active_positions)
            
            if slots_available > 0 and portfolio > 0:
                candidates = candidates_by_date.get(date_str, [])
                candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)[:slots_available]
                
                if candidates:
                    alloc_per_ticker = portfolio / len(candidates)
                    for c in candidates:
                        shares = alloc_per_ticker / c['buy_price']
                        portfolio -= alloc_per_ticker
                        active_positions.append({
                            'ticker': c['ticker'],
                            'buy_date': date_str,
                            'sell_date': (datetime.datetime.strptime(date_str, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime('%Y-%m-%d'),
                            'shares': shares,
                            'buy_price': c['buy_price'],
                            'sell_price_real': c['sell_price']
                        })
                        
    for pos in active_positions:
        profit_cash = pos['shares'] * pos['sell_price_real']
        portfolio += profit_cash
        pnl = (pos['sell_price_real'] - pos['buy_price']) / pos['buy_price']
        trades.append({'pnl_pct': pnl * 100})
        
    total_return = ((portfolio / capital) - 1) * 100
    win_rate = (len([t for t in trades if t['pnl_pct'] > 0]) / len(trades) * 100) if trades else 0
    
    return total_return, win_rate, len(trades)

def main():
    print("Obteniendo datos globales (esto toma 20s)...")
    tickers = fetch_sp500_tickers_wiki_v2()
    state = {'return_raw_candidates': True}
    res_raw = run_historical_backtest(tickers, days_back=1260, capital=10000, max_positions=10, state_dict=state)
    
    candidates_by_date = res_raw['candidates_by_date']
    all_eval_dates = res_raw['eval_dates_str']
    vix_history_dict = res_raw['vix_history_dict']
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=1260 + 400)
    spy = yf.Ticker("SPY").history(start=start_date, end=end_date)
    spy.index = spy.index.tz_localize(None)
    spy_dict = {}
    for d, row in spy.iterrows():
        spy_dict[d.strftime('%Y-%m-%d')] = row.to_dict()

    config_dios = {'vix_slots': {"CALM": 10, "SLOW_BEAR": 3, "FAST_CRASH": 0}}
    config_padre = {'vix_slots': {"CALM": 10, "SLOW_BEAR": 10, "FAST_CRASH": 10}}
    
    horizons = [
        ("10 dias", 10),
        ("30 dias", 30),
        ("90 dias", 90),
        ("180 dias", 180),
        ("1 ano", 252),
        ("2 anos", 504),
        ("3 anos", 756),
        ("4 anos", 1008),
        ("5 anos", 1260)
    ]
    
    print("\n" + "="*70)
    print("PANORAMA DE TIEMPO: DIOS 'COBARDE DE HIELO' vs PADRE vs S&P500")
    print("="*70)
    
    for label, days in horizons:
        # Extraer los ultimos N dias
        if days > len(all_eval_dates):
            sub_dates = all_eval_dates
        else:
            sub_dates = all_eval_dates[-days:]
            
        first_d = sub_dates[0]
        last_d = sub_dates[-1]
        
        # Benchmark SPY
        if first_d in spy_dict and last_d in spy_dict:
            spy_ret = (spy_dict[last_d]['Close'] / spy_dict[first_d]['Close'] - 1) * 100
        else:
            spy_ret = 0.0
            
        ret_d, wr_d, t_d = run_horizon(config_dios, candidates_by_date, sub_dates, vix_history_dict, spy_dict)
        ret_p, wr_p, t_p = run_horizon(config_padre, candidates_by_date, sub_dates, vix_history_dict, spy_dict)
        
        print(f"\n[ Horizonte: {label} ]")
        print(f"S&P 500   : {spy_ret:7.2f}%")
        print(f"PADRE     : {ret_p:7.2f}% | WinR: {wr_p:5.1f}% | Trades: {t_p}")
        print(f"DIOS      : {ret_d:7.2f}% | WinR: {wr_d:5.1f}% | Trades: {t_d}")

if __name__ == '__main__':
    main()
