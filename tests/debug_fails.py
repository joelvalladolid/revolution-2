import sys, os
from collections import Counter
sys.path.insert(0, r"c:\Users\Alumno\Desktop\SMF\revolution-main\REVOLUTION_ENTREGABLE")
from data_fetcher import fetch_stock_data
from estrategia import evaluar_protocolo_accion
from lab_tickers import fetch_sp500_tickers_wiki_v2

tickers = fetch_sp500_tickers_wiki_v2()[:100]
fail_counter = Counter()

for t in tickers:
    try:
        data = fetch_stock_data(t)
        if not data or not isinstance(data, dict): continue
        price = data.get('currentPrice', 100)
        tech_real = {'sma_200': price, 'fifty_two_position': 50, 'rsi': 50}
        res = evaluar_protocolo_accion(data, tech_real, 4.2, price, soportes=[], profile='B')
        for rule, passed in res.get('verdicts', []):
            if not passed:
                fail_counter[rule] += 1
    except Exception as e:
        pass

print("=== TOP FAILURES ===")
for r, c in fail_counter.most_common(5):
    print(f"{c} veces: {r}")
