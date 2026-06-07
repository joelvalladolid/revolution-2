import re

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Modificaremos la sección de backtest.
old_str = """elif page == "📈 Backtest Histórico":
    st.markdown('<p class="hero-title">📈 Backtest Histórico (Últimos 3 Meses)</p>', unsafe_allow_html=True)
    st.markdown("Simulación día a día del escáner y compra de señales Top 10", unsafe_allow_html=True)
    
    st.info("Este proceso descargará el historial de todo el S&P 500, simulará las condiciones de mercado (VIX) y evaluará las estrategias día a día durante 90 días.", icon="ℹ️")
    
    if st.button("🚀 Iniciar Backtest"):
        if "backtest_state" not in st.session_state or st.session_state.backtest_state.get('status') == 'DONE':
            st.session_state.backtest_state = {'status': 'RUNNING', 'progress': 0.0}
            from lab.backtest_engine import run_historical_backtest
            import threading
            threading.Thread(target=run_historical_backtest, args=(tickers, 90, 10000, 10, st.session_state.backtest_state), daemon=True).start()"""

new_str = """elif page == "📈 Backtest Histórico":
    st.markdown('<p class="hero-title">📈 Backtest Histórico</p>', unsafe_allow_html=True)
    st.markdown("Simulación día a día del escáner y compra de señales Top 10", unsafe_allow_html=True)
    
    days_back = st.number_input("Días atrás a simular", min_value=1, max_value=360, value=90, step=1)
    
    st.info(f"Este proceso descargará el historial de todo el S&P 500, simulará las condiciones de mercado (VIX) y evaluará las estrategias día a día durante {days_back} días.", icon="ℹ️")
    
    if st.button("🚀 Iniciar Backtest"):
        if "backtest_state" not in st.session_state or st.session_state.backtest_state.get('status') == 'DONE':
            st.session_state.backtest_state = {'status': 'RUNNING', 'progress': 0.0}
            from lab.backtest_engine import run_historical_backtest
            import threading
            threading.Thread(target=run_historical_backtest, args=(tickers, days_back, 10000, 10, st.session_state.backtest_state), daemon=True).start()"""

# Hacer el replace ignorando espacios exactos
def normalize(s):
    return re.sub(r'\s+', '', s)

# Buscaremos el target=run_historical_backtest
import sys
text = re.sub(r'st\.markdown\(\'<p class="hero-title">📈 Backtest Histórico \(Últimos 3 Meses\)</p>\', unsafe_allow_html=True\)', 
              r'st.markdown(\'<p class="hero-title">📈 Backtest Histórico</p>\', unsafe_allow_html=True)\n    days_back = st.number_input("Días atrás a simular", min_value=1, max_value=360, value=90, step=1)', text)

text = re.sub(r'st\.info\("Este proceso descargará el historial de todo el S&P 500, simulará las condiciones de mercado \(VIX\) y evaluará las estrategias día a día durante 90 días.", icon="ℹ️"\)', 
              r'st.info(f"Este proceso descargará el historial de todo el S&P 500, simulará las condiciones de mercado (VIX) y evaluará las estrategias día a día durante {days_back} días.", icon="ℹ️")', text)

text = re.sub(r'target=run_historical_backtest, args=\(tickers, 90, 10000, 10, st\.session_state\.backtest_state\)', 
              r'target=run_historical_backtest, args=(tickers, days_back, 10000, 10, st.session_state.backtest_state)', text)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Reemplazo realizado!")
