import datetime
from lab.backtest_engine import run_historical_backtest
from lab_tickers import fetch_sp500_tickers_wiki_v2

def run_eval():
    tickers = fetch_sp500_tickers_wiki_v2()
    print(f"Descargados {len(tickers)} tickers.")
    state = {}
    print("Iniciando simulacion backtest (5 años = 1260 dias)...")
    res = run_historical_backtest(tickers, days_back=1260, capital=10000, max_positions=10, state_dict=state)
    
    print("\n" + "="*50)
    print("RESULTADOS DEL BACKTEST (1260 Dias)")
    print("="*50)
    print(f"Retorno Total:   {res['total_return_pct']:.2f}%")
    print(f"Win Rate:        {res['win_rate']:.1f}%")
    print(f"Capital Final:   ${res['final_equity']:.2f}")
    print(f"Total Trades:    {res['total_trades']}")
    print("="*50)

if __name__ == "__main__":
    run_eval()
