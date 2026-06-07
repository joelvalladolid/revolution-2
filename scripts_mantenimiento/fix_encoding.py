import os
import re

with open("app.py", "rb") as f:
    d = f.read()

# try decode ansi
try:
    text = d.decode("mbcs") # mbcs is ansi on windows
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Fixed ANSI to UTF-8")
except Exception as e:
    print("Error:", e)

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "run_historical_backtest" in line:
        print(f"Línea {i+1}: {line.strip()}")
    if "Backtest" in line:
        print(f"Línea {i+1}: {line.strip()}")
