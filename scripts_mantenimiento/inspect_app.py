with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "button" in l.lower() and "borrar" in l.lower():
        print(f"Boton borrar {i+1}: {l.strip()}")
    if "button" in l.lower() and "limpiar" in l.lower():
        print(f"Boton limpiar {i+1}: {l.strip()}")
    if "FRANCOTIRADOR" in l:
        # imprimir unas lineas antes y despues para ver el html
        for j in range(max(0, i-5), min(len(lines), i+15)):
            print(f"SIDEBAR {j+1}: {lines[j].strip()}")
