import os
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ProcessPoolExecutor, as_completed
from lab.backtest_engine import run_historical_backtest
from lab_tickers import fetch_sp500_tickers_wiki_v2

def assemble_portfolio(args):
    config, candidates_by_date, eval_dates_str, vix_history_dict, spy_dict = args
    
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
    
    return {
        'name': config['name'],
        'total_return': total_return,
        'win_rate': win_rate,
        'trades': len(trades),
        'final_equity': portfolio
    }

def main():
    print("Iniciando Torneo Gran Final de 100 Clones...")
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=1260 + 400)
    spy = yf.Ticker("SPY").history(start=start_date, end=end_date)
    spy.index = spy.index.tz_localize(None)
    for period in range(10, 201, 10):
        spy[f'EMA_{period}'] = spy['Close'].ewm(span=period, adjust=False).mean()
    for period in [15, 25]:
        spy[f'EMA_{period}'] = spy['Close'].ewm(span=period, adjust=False).mean()
        
    spy_dict = {}
    for d, row in spy.iterrows():
        spy_dict[d.strftime('%Y-%m-%d')] = row.to_dict()

    tickers = fetch_sp500_tickers_wiki_v2()
    state = {'return_raw_candidates': True}
    res_raw = run_historical_backtest(tickers, days_back=1260, capital=10000, max_positions=10, state_dict=state)
    
    candidates_by_date = res_raw['candidates_by_date']
    eval_dates_str = res_raw['eval_dates_str']
    vix_history_dict = res_raw['vix_history_dict']

    configs = []
    
    print("Iniciando Torneo GEN 4 (Los Bisnietos de Dios)...")
    
    # Bases del Top 10 de Gen 3:
    # 3_0 y 4_0 fueron los reyes. 1_1 y 1_2 sobrevivieron. 
    top_10_bases = [
        ("GEN3_3_0", 3, 0, None), 
        ("GEN3_4_0", 4, 0, None), 
        ("GEN3_1_1", 1, 1, None),
        ("GEN3_1_2", 1, 2, None), 
        ("GEN3_1_4", 1, 4, None), 
        ("GEN3_3_0_E40", 3, 0, 40),
        ("GEN3_4_0_E40", 4, 0, 40), 
        ("GEN3_3_0_E20", 3, 0, 20), 
        ("GEN3_4_0_E20", 4, 0, 20),
        ("GEN3_3_0_E10", 3, 0, 10) # Inventado para forzar EMA rapida
    ]

    c_id = 1
    for base in top_10_bases:
        base_name = base[0]
        sb = base[1]
        fc = base[2]
        base_ema = base[3]
        
        # 1. Base
        configs.append({'name': f"{c_id}_BASE_{base_name}", 'macro_ema': base_ema, 'vix_slots': {"CALM": 10, "SLOW_BEAR": sb, "FAST_CRASH": fc}})
        c_id += 1
        
        # 2-5. Micro mutaciones (+1/-1 en CALM) para buscar el sweet spot de agresividad
        for d_calm in [-2, -1, 1, 2]:
            new_calm = max(1, 10 + d_calm)
            configs.append({'name': f"{c_id}_MUT_{base_name}_C_{new_calm}", 'macro_ema': base_ema, 'vix_slots': {"CALM": new_calm, "SLOW_BEAR": sb, "FAST_CRASH": fc}})
            c_id += 1
                
        # 6-10. Mutaciones de EMA ultra rápidas
        emas_to_try = [10, 15, 20, 25, 30]
        for ema in emas_to_try:
            configs.append({'name': f"{c_id}_EMA{ema}_{base_name}", 'macro_ema': ema, 'vix_slots': {"CALM": 10, "SLOW_BEAR": sb, "FAST_CRASH": fc}})
            c_id += 1

    worker_args = [(c, candidates_by_date, eval_dates_str, vix_history_dict, spy_dict) for c in configs]
    
    results = []
    with ProcessPoolExecutor() as executor:
        for res in executor.map(assemble_portfolio, worker_args):
            results.append(res)
            
    results = sorted(results, key=lambda x: x['total_return'], reverse=True)
    
    print("\n--- EL GRAN TORNEO DE 100 CLONES (TOP 15) ---")
    for i, r in enumerate(results[:15]):
        print(f"{i+1}. {r['name']} | Ret: {r['total_return']:.2f}% | WR: {r['win_rate']:.1f}%")

if __name__ == '__main__':
    main()
