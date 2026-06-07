import yfinance as yf
print("yfinance version:", yf.__version__)
tk = yf.Ticker("AAPL")
print("Fast Info Last Price:", tk.fast_info.get("lastPrice", "N/A"))
print("Income Statement columns:", tk.income_statement.columns.tolist() if tk.income_statement is not None and not tk.income_statement.empty else "Empty")
print("Financials empty?:", tk.financials.empty)

from yahooquery import Ticker
yq = Ticker("AAPL")
print("yq.financial_data:", list(yq.financial_data.keys()))
