with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(2995, 3010):
    if i < len(lines):
        print(f"{i+1}: {lines[i].strip()}")
