import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Restaurar la codificación doble usando encode/decode con ignorar errores
try:
    fixed_text = text.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")
    # Para validar si mejoró, busquemos "RÉGIMEN"
    if "RÉGIMEN" in fixed_text or "Escáner" in fixed_text or "FRANCOTIRADOR" in fixed_text:
        text = fixed_text
        print("Restauración de encoding aplicada.")
except Exception as e:
    print(f"No se pudo aplicar restauración: {e}")

# Ahora arreglamos los posibles markdown sin unsafe_allow_html=True
# Si encontramos algo como st.sidebar.markdown(f"""...""") o st.markdown("""...""") 
# y la siguiente línea o esa no tiene unsafe_allow_html=True
# En streamlit, un markdown con tags HTML DEBE tenerlo. 
# Buscaremos todos los casos donde haya un string multi-línea con tags <div> y le forzaremos el flag.
# Pero el problema principal fue mi primer replace en powershell.
# Mi powershell: `-replace ', use_container_width=True', '' -replace ', use_container_width=False', ''`
# Puede que accidentalmente en ese "replace" haya borrado algo si el texto se cruzó, o si había algo como `use_container_width=True)` 
# y reemplacé y dejé el paréntesis suelto `)` y rompió el string.
# Revisemos el botón de borrar.
# "boton de borrar veo algo de letras raras" -> Ese es el botón "Limpiar Caché" o "Borrar".

text = text.replace("ðŸŸ¨", "🟨")
text = text.replace("RÍ‰GIMEN", "RÉGIMEN")
text = text.replace("seales", "señales")
text = text.replace("Seales", "Señales")
text = text.replace("Escner", "Escáner")
text = text.replace("Navegacin", "Navegación")
text = text.replace("Histrico", "Histórico")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("App.py re-escrito con fixes manuales.")
