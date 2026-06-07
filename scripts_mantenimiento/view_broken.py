with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "FRANCOTIRADOR" in l or "SLOW_BEAR" in l or "unsafe_allow_html" in l or "sidebar.markdown" in l:
        print(f"{i+1}: {l.encode('ascii', 'ignore').decode().strip()}")
