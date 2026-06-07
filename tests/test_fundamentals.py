import sys
import os

# Ensure the paths are set up correctly
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from data_fetcher import fetch_stock_data
from estrategia import evaluar_protocolo_accion

def test_ticker(ticker):
    print(f"--- Testing {ticker} ---")
    data = fetch_stock_data(ticker)
    
    if not data:
        print("fetch_stock_data returned empty data!")
        return

    # Mock tech_real
    tech_real = {
        'rsi': 50,
        'sma_200': 150,
        'fifty_two_position': 80
    }
    
    tnx_yield = 4.5
    current_price = data.get('price', 150)
    
    res = evaluar_protocolo_accion(data, tech_real, tnx_yield, current_price, soportes=[], profile='B', scan_mode='MOMENTUM')
    
    passed = int(res.get('passed', 0))
    total  = int(res.get('total', 1))
    
    print(f"Passed: {passed} / Total: {total}")
    for k, v in data.items():
        if k not in ['history', 'vwap', 'volume_profile', 'technicals']:
            print(f"Data {k}: {v}")
    
    print("Verdicts:")
    for verdict in res.get('verdicts', []):
        print(f"  {verdict[0]}: {'PASS' if verdict[1] else 'FAIL' if verdict[1] is False else 'SKIP'}")

if __name__ == "__main__":
    test_ticker("AAPL")
    test_ticker("NVDA")
