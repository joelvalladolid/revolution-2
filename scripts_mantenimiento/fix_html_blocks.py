import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix the FRANCOTIRADOR block
sidebar_bad = """<div style="padding:18px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#7C3AED,#3B82F6);
                 display:flex;align-items:center;justify-content:center;font-size:18px;">⚡</div>
      <div>
        <div style="font-size:15px;font-weight:800;background:linear-gradient(135deg,#A78BFA,#60A5FA);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">FRANCOTIRADOR</div>
        <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.8px;">Trading System</div>
      </div>
    </div>"""

sidebar_good = sidebar_bad.replace("\n", " ").replace("  ", " ")
text = text.replace(sidebar_bad, sidebar_good)
text = text.replace(sidebar_bad.replace("      ", ""), sidebar_good)

# Also fix the whole st.sidebar.markdown block by replacing newlines with spaces inside it
def fix_sidebar(m):
    return "st.sidebar.markdown(\"\"\"" + m.group(1).replace("\n", " ") + "\"\"\", unsafe_allow_html=True)"

text = re.sub(r'st\.sidebar\.markdown\(\"\"\"(.*?FRANCOTIRADOR.*?)\"\"\"\,\s*unsafe_allow_html=True\)', fix_sidebar, text, flags=re.DOTALL)

# Let's fix the regime banner. In `app.py`, there is a function `render_regime_banner`.
def fix_banner(m):
    return "st.markdown(f\"\"\"" + m.group(1).replace("\n", " ") + "\"\"\", unsafe_allow_html=True)"
text = re.sub(r'st\.markdown\(f?\"\"\"(.*?R\wGIMEN.*?)\"\"\"\,\s*unsafe_allow_html=True\)', fix_banner, text, flags=re.DOTALL)

def fix_banner2(m):
    return "st.markdown(\"\"\"" + m.group(1).replace("\n", " ") + "\"\"\", unsafe_allow_html=True)"
text = re.sub(r'st\.markdown\(\"\"\"(.*?R\wGIMEN.*?)\"\"\"\,\s*unsafe_allow_html=True\)', fix_banner2, text, flags=re.DOTALL)

# Let's just fix ALL st.markdown that contain HTML tags by removing newlines inside the tags
def remove_newlines_in_tags(match):
    return match.group(0).replace("\n", " ")

text = re.sub(r'<[^>]+>', remove_newlines_in_tags, text)

# For the specific regime strings shown by the user:
text = re.sub(r'(<div[^>]*>)\s+(<span[^>]*>.*?</span>)\s+(<span[^>]*>.*?</span>)\s+(</div>)', r'\1\2\3\4', text)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Done")
