import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from app import analyze_ticker_for_today, get_current_regime, get_tnx_yield
import datetime

regime, cvix, _ = get_current_regime()
tnx = get_tnx_yield()
end_date = datetime.date.today().strftime('%Y-%m-%d')
start_date = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

tickers_to_test = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']
print(f'Testing {tickers_to_test} in regime {regime}')

for t in tickers_to_test:
    for m in ['MOMENTUM', 'DIP']:
        res = analyze_ticker_for_today(t, regime, tnx, start_date, end_date, False, m, None, cvix)
        if res:
            fund_ok = res.get('signal', {}).get('fundamental_ok', False)
            signal_ok = res.get('signal', {}).get('signal', False)
            rationale = res.get('signal', {}).get('rationale', '')
            print(f'{t} [{m}]: Fund_OK: {fund_ok}, Signal_OK: {signal_ok}, Rationale: {rationale}')
