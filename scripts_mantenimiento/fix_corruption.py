import re

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "if df is None or len(df) < 252:" in line and "return None" in line:
        # We need to split this line back into multiple lines
        # We can split on any sequence of 4 or more spaces that doesn't follow a comma or something?
        # Actually, if we just replace 8 or more spaces with newline + spaces
        
        def replacer(match):
            spaces = match.group(0)
            return "\n" + spaces
            
        fixed_line = re.sub(r' {8,}', replacer, line)
        
        # But wait, there might be spaces inside strings or dicts, like in the dict
        # `df, {              'EMA`
        # Let's see: `return df, {              'EMA`
        # If we replace that with `\n`, it's totally fine in Python inside a dict!
        lines[i] = fixed_line

with open("app.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Fixed line 955")
