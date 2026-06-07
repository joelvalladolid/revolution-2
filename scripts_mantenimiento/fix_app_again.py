import re

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == "":
        continue
    new_lines.append(line)

# Let's fix specific lines by doing string replaces on the whole text
text = "".join(new_lines)

text = text.replace("if rt_price is not None and not pd.isna(rt_price):\n          vix.iloc[-1, vix.columns.get_loc('Close')] = rt_price", 
                    "if rt_price is not None and not pd.isna(rt_price):\n              vix.iloc[-1, vix.columns.get_loc('Close')] = rt_price")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed")
