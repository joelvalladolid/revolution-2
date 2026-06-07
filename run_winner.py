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
    
    vix_slots = config.get('vix_slots', {"CALM": 10, "SLOW_BEAR": 10, "FAST_CRASH": 10})
    
    for i, date_str in enumerate(eval_dates_str):
        # Para evitar look-ahead bias, miramos el regimen de AYER
        if i == 0:
            regime = "CALM"
        else:
            prev_date_str = eval_dates_str[i-1]
            regime = vix_history_dict.get(prev_date_str, "CALM")
            
        # Vender expirados (No hay SL)
        remaining_positions = []
        for pos in active_positions:
            if pos['sell_date'] <= date_str:
                profit_cash = pos['shares'] * pos['sell_price_real']
                portfolio += profit_cash
                pnl = (pos['sell_price_real'] - pos['buy_price']) / pos['buy_price']
                trades.append({
                    'ticker': pos['ticker'],
                    'pnl_pct': pnl * 100,
                    'profit_usd': profit_cash - (pos['shares'] * pos['buy_price'])
                })
            else:
                remaining_positions.append(pos)
                
        active_positions = remaining_positions
        
        # Comprar Nuevos
        max_pos = vix_slots.get(regime, 10)
        slots_available = max_pos - len(active_positions)
        
        if slots_available > 0 and portfolio > 0:
            candidates = candidates_by_date.get(date_str, [])
            # IMPORTANTE: el candidate fue emitido por worker usando el VIX de ayer tambien
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
                        
    # Forzar venta final
    for pos in active_positions:
        profit_cash = pos['shares'] * pos['sell_price_real']
        portfolio += profit_cash
        pnl = (pos['sell_price_real'] - pos['buy_price']) / pos['buy_price']
        trades.append({'ticker': pos['ticker'], 'pnl_pct': pnl * 100})
        
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
    print("Obteniendo señales del Worker Pesado (1 vez)...")
    tickers = fetch_sp500_tickers_wiki_v2()
    
    state = {'return_raw_candidates': True}
    res_raw = run_historical_backtest(tickers, days_back=1260, capital=10000, max_positions=10, state_dict=state)
    
    candidates_by_date = res_raw['candidates_by_date']
    eval_dates_str = res_raw['eval_dates_str']
    vix_history_dict = res_raw['vix_history_dict']

    config_winner = {
        'name': '3X_VIX_Safe_6_3 (NO LOOK-AHEAD BIAS)',
        'vix_slots': {"CALM": 10, "SLOW_BEAR": 6, "FAST_CRASH": 3}
    }
    config_father = {
        'name': 'PADRE (NO LOOK-AHEAD BIAS)',
        'vix_slots': {"CALM": 10, "SLOW_BEAR": 10, "FAST_CRASH": 10}
    }
    
    worker_args = [
        (config_winner, candidates_by_date, eval_dates_str, vix_history_dict, {}),
        (config_father, candidates_by_date, eval_dates_str, vix_history_dict, {})
    ]
    
    results = []
    with ProcessPoolExecutor() as executor:
        for res in executor.map(assemble_portfolio, worker_args):
            results.append(res)
            
    print("\n--- RESULTADOS ESTRICTAMENTE REALISTAS (CERO SESGO) ---")
    for r in results:
        print(f"{r['name']} | Retorno 5 años: {r['total_return']:.2f}% | Win Rate: {r['win_rate']:.1f}% | Trades: {r['trades']}")

if __name__ == '__main__':
    main()
