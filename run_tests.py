from lab.backtest_engine import run_historical_backtest
from lab_tickers import fetch_sp500_tickers_wiki_v2

def main():
    tickers = fetch_sp500_tickers_wiki_v2()
    print("Iniciando Backtests...")
    for days in [1260]:
        print(f"\n--- BACKTEST {days} DÍAS (5 AÑOS) ---")
        state = {}
        res = run_historical_backtest(tickers, days_back=days, capital=10000, max_positions=10, state_dict=state)
        if res:
            print(f"Retorno Total: {res['total_return_pct']:.2f}%")
            print(f"Win Rate: {res['win_rate']:.2f}%")
            print(f"Trades Totales: {res['total_trades']}")
            print(f"Equidad Final: ${res['final_equity']:.2f}")
        else:
            print("Error en backtest")

if __name__ == '__main__':
    main()
