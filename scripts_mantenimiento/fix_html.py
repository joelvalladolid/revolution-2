import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Algunos bloques markdown pueden tener problemas si se borró o escapó la comilla
# Vamos a arreglar cualquier markdown de streamlit que no tenga unsafe_allow_html pero tenga divs
def add_unsafe(match):
    content = match.group(0)
    if 'unsafe_allow_html=True' not in content:
        # Añadir al final
        content = content.replace(')', ', unsafe_allow_html=True)')
    return content

# Es muy arriesgado usar regex simple, así que arreglaré solo la barra lateral de francotirador si es que está mal.
# Pero noté antes que SÍ tenía unsafe_allow_html=True al final: """, unsafe_allow_html=True)
# ¿Quizás el problema es que la función original era `st.sidebar.markdown` y yo al hacer el decode rompí el sidebar y se quedó en st.markdown?
# O quizás el error es que Streamlit necesita unsafe_allow_html en cada uno de los sub-bloques o algo similar.
# Reemplazaré el bloque del sidebar por una llamada muy clara y segura.
# Pero como no veo el archivo completo, usaré un replace más directo.

# Busquemos los strings que empiezan con st.markdown y le pasamos el replace
text = text.replace('st.markdown("""\n      <div style="width:36px', 'st.sidebar.markdown("""\n      <div style="width:36px')

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)
