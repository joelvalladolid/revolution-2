import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import datetime
import yfinance as yf
from lab.backtest_engine import run_historical_backtest

tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK-B', 'LLY', 'AVGO']
print("Iniciando test de robustez de backtest con múltiples duraciones...")

for d in [1, 5, 15]:
    print(f"\nProbando con {d} días...")
    try:
        res = run_historical_backtest(tickers, days_back=d)
        if res:
            print(f"Test de {d} días completado sin crashear. Trades: {res['total_trades']}")
        else:
            print(f"Fallo o devolvió vacío el de {d} días.")
    except Exception as e:
        print(f"Error crasheo en {d} días: {e}")
