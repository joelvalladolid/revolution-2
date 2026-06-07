with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
indent_level = 0
for line in lines:
    stripped = line.strip()
    if not stripped:
        new_lines.append(line)
        continue
    
    # Check if we need to dedent
    if stripped.startswith(("elif", "else:", "except", "finally:")):
        indent_level = max(0, indent_level - 1)
        new_line = ("    " * indent_level) + stripped + "\n"
        indent_level += 1
    elif stripped == "return True" and "if" in new_lines[-1]: # rudimentary heuristic
        # we don't know the real indent
        pass
    
    # It's too complex to write a full parser. 
