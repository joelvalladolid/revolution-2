import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

def replacer(match):
    return match.group(1) + "\n" + match.group(2)

for _ in range(10): # run multiple times to catch overlapping
    text = re.sub(r'([^\n])( {10,})', replacer, text)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed globally")
