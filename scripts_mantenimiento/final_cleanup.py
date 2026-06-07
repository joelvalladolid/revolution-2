import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Forzar limpiar caracteres corruptos
corruptions = {
    "ðŸŸ¨": "🟨",
    "RÍ‰GIMEN": "RÉGIMEN",
    "Rgimen": "Régimen",
    "rgimen": "régimen",
    "seales": "señales",
    "Seales": "Señales",
    "Escner": "Escáner",
    "Navegacin": "Navegación",
    "Histrico": "Histórico",
    "da a da": "día a día",
    "Correlacin": "Correlación",
    "Configuracin": "Configuración",
    "Diagnstico": "Diagnóstico",
    "Anlisis": "Análisis",
    "Cunto": "Cuánto",
    "ltimos": "últimos",
    "dinmico": "dinámico",
    "Prximamente": "Próximamente"
}

for k, v in corruptions.items():
    text = text.replace(k, v)

# Para el HTML, si por alguna razón streamlit no lo está renderizando,
# a veces es porque hay un "st.markdown(" y luego otro "st.markdown(".
# Vamos a forzar que el HTML principal tenga unsafe_allow_html=True explícito
# y que se renderice bien.

# Reemplazaremos explícitamente el HTML literal que mandó el usuario por uno correcto.
# En lugar de depender del string gigante, usaremos sub strings.

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Text clean done")
