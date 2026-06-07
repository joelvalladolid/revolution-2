import sys
import os
import yfinance as yf
from yahooquery import Ticker

print('YFINANCE:')
tk = yf.Ticker('ABBV')
info = tk.info
print(f"Price: {info.get('currentPrice')}")
print(f"Market Cap: {info.get('marketCap')}")
print(f"Trailing PE: {info.get('trailingPE')}")
print(f"Forward PE: {info.get('forwardPE')}")

print('\nYAHOOQUERY:')
yq = Ticker('ABBV')
fd = yq.financial_data.get('ABBV', {})
sd = yq.summary_detail.get('ABBV', {})
ks = yq.key_stats.get('ABBV', {})

print(f"Price: {fd.get('currentPrice')}")
print(f"Market Cap: {sd.get('marketCap')}")
print(f"Trailing PE: {sd.get('trailingPE')}")
print(f"Forward PE: {ks.get('forwardPE')}")
