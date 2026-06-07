import datetime
import yfinance as yf
import pandas as pd

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=10)

v = yf.Ticker("^VIX").history(start=start_date, end=end_date)
v.index = v.index.tz_localize(None)

d = yf.download(['AAPL'], start=start_date, end=end_date, ignore_tz=True)

print("VIX Index:")
print(v.index)
print("\nAAPL Index:")
print(d.index)
print(f"Intersection len: {len(v.index.intersection(d.index))}")
