import ast
import re

def fix_file():
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    while True:
        try:
            ast.parse("".join(lines))
            break # Fixed!
        except SyntaxError as e:
            line_idx = e.lineno - 1
            line = lines[line_idx]
            
            # Find the longest sequence of spaces first
            # Actually, split on all sequences of 4 or more spaces that follow a word or colon
            # To be safe, let's just replace `(.) {4,}` with `\1\n    ...`
            def replacer(match):
                char = match.group(1)
                spaces = match.group(2)
                return char + "\n" + spaces
                
            new_line = re.sub(r'([^\s])( {4,})', replacer, line)
            
            if new_line == line:
                print(f"Could not fix line {e.lineno}: {line[:50]}")
                # Try 2 spaces?
                new_line = re.sub(r'([^\s])( {2,})', replacer, line)
                if new_line == line:
                    break
            
            # Since a single line becomes multiple lines, we replace the element in the list
            # and flatmap it
            new_lines = [l + "\n" if not l.endswith("\n") else l for l in new_line.split('\n')]
            
            # Clean empty ones
            new_lines = [l for l in new_lines if l]
            
            lines = lines[:line_idx] + new_lines + lines[line_idx+1:]
            
            print(f"Fixed line {e.lineno}")

    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    # Check again
    try:
        ast.parse("".join(lines))
        print("Syntax is OK!")
    except SyntaxError as e:
        print(f"Still SyntaxError at line {e.lineno}")

fix_file()
