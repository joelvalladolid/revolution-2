import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove blank lines globally if the whole file is double spaced
# But to be safe, just remove blank lines inside st.markdown(""" ... """)
def fix_markdown(match):
    block = match.group(1)
    # Remove all blank lines inside the block
    block = re.sub(r'\n\s*\n', '\n', block)
    # Also remove newlines inside HTML tags (e.g., between <div and >)
    # A simple way is to replace newlines followed by spaces with a single space
    # but only if it's inside an attribute or we can just remove all newlines in the block
    # and replace with space, since HTML doesn't care about newlines.
    # However, Python formatting might care.
    # Let's just remove all newlines inside the markdown block and replace with a space.
    # Because it's raw HTML, spaces are fine.
    # Wait, some markdown blocks might have actual markdown like "**VIX:**".
    # So removing all newlines is bad for markdown.
    
    # Just fix the newlines that break HTML.
    # 1) Remove blank lines
    lines = [line for line in block.split('\n') if line.strip() != '']
    # 2) Join lines that start with an HTML attribute or just don't start with a tag
    # Actually, Markdown breaks if an HTML tag is split across lines or has blank lines.
    return 'st.markdown("""' + '\n'.join(lines) + '"""'

content = re.sub(r'st\.markdown\("""(.*?)"""', fix_markdown, content, flags=re.DOTALL)

# Let's also do it for single quotes '''
content = re.sub(r"st\.markdown\('''(.*?)'''", fix_markdown, content, flags=re.DOTALL)

# Let's also do it for st.sidebar.markdown
def fix_sidebar_markdown(match):
    block = match.group(1)
    lines = [line for line in block.split('\n') if line.strip() != '']
    return 'st.sidebar.markdown("""' + '\n'.join(lines) + '"""'

content = re.sub(r'st\.sidebar\.markdown\("""(.*?)"""', fix_sidebar_markdown, content, flags=re.DOTALL)

# Same for st.write
def fix_write(match):
    block = match.group(1)
    lines = [line for line in block.split('\n') if line.strip() != '']
    return 'st.write("""' + '\n'.join(lines) + '"""'

content = re.sub(r'st\.write\("""(.*?)"""', fix_write, content, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed HTML newlines inside st.markdown.")
