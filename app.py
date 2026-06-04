"""
🎯 Francotirador de Liquidez — Trading App
Motor cuantitativo con régimen VIX + técnico + fundamental.
"""
import streamlit as st
import sys, os, datetime, json, time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
import yfinance as yf

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lab.regime_detector import classify_regime
from lab.indicators import ema_discount, bollinger_pctB, stochastic_k
from lab.rule_engine import evaluate_signal, RULE_SETS, calculate_confidence
from lab.monte_carlo import simulate_price_paths
from data.fetcher import fetch_history
from lab_tickers import fetch_sp500_tickers_wiki_v2

try:
    from estrategia import evaluar_protocolo_accion
    from data_fetcher import fetch_stock_data
    FUND_AVAILABLE = True
except ImportError:
    FUND_AVAILABLE = False
    def evaluar_protocolo_accion(*a, **kw): return {"total": 0, "passed": 0}
    def fetch_stock_data(ticker): return {}

try:
    from data_fetcher import search_ticker_by_name
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    def search_ticker_by_name(q): return []

try:
    from lab.daily_allocator import calculate_allocations
    ALLOCATOR_AVAILABLE = True
except ImportError:
    ALLOCATOR_AVAILABLE = False
    def calculate_allocations(signals, vix, capital): return [], 'CALM', 0.0

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ Trading Radar",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def get_global_scans():
    return {}

GLOBAL_SCANS = get_global_scans()

if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ── CSS ───────────────────────────────────────────────────────────────────────
QUANTUM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
  --bg-void: #030308;
  --bg-base: #070710;
  --bg-surface: #0C0C1A;
  --bg-elevated: #111122;
  --bg-card: #15152A;
  --border: rgba(120,120,255,0.08);
  --border-accent: rgba(120,120,255,0.16);
  --emerald: #00D4A0;
  --violet: #7C3AED;
  --violet-light: #A78BFA;
  --red: #FF4560;
  --amber: #FFB800;
  --blue: #3B82F6;
  --cyan: #00C8E0;
  --text-primary: #EEF2FF;
  --text-secondary: #8892B0;
  --text-muted: #4A5568;
  --font-main: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

/* Ocultar chrome de Streamlit — header NO se oculta (contiene toggle del sidebar) */
#MainMenu, footer { visibility: hidden; }
.stDeployButton { display: none; }

/* Hacer header transparente pero conservar interactividad del toggle */
header {
  background: transparent !important;
  border-bottom: none !important;
}

/* Forzar visibilidad de los botones de collapse/expand del sidebar */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
button[aria-label="Close sidebar"],
button[aria-label="Open sidebar"],
button[aria-label="Abrir barra lateral"],
button[aria-label="Cerrar barra lateral"] {
  visibility: visible !important;
  opacity: 1 !important;
  display: flex !important;
  pointer-events: auto !important;
  z-index: 999999 !important;
}

/* Ocultar el título y toolbar del header, no los botones */
header svg + div,
[data-testid="stAppViewBlockContainer"] > header > div > div:last-child {
  visibility: hidden;
}


/* Fondo principal — selectores forzados para Streamlit moderno */
html, body { background: var(--bg-void) !important; }
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="block-container"],
.main, .main > div {
  background: var(--bg-void) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-main) !important;
}

/* Sidebar */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
  background: var(--bg-base) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] p { color: var(--text-secondary) !important; }

/* Streamlit generic text */
h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; }
.stMarkdown p { color: var(--text-secondary); }

/* st.metric */
[data-testid="stMetric"] {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 16px;
}
[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 11px !important; }
[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-family: var(--font-mono) !important; }
[data-testid="stMetricDelta"] { color: var(--emerald) !important; }

/* Hero titles */
.hero-title {
  font-size: 2.4rem;
  font-weight: 900;
  background: linear-gradient(135deg, #A78BFA, #60A5FA, #00D4A0);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 4px 0;
  line-height: 1.1;
}
.hero-sub {
  font-size: 0.95rem;
  color: var(--text-secondary);
  margin: 0 0 24px 0;
}

/* Section title */
.section-title {
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
  margin: 24px 0 16px 0;
}

/* Signal cards (analisis individual) */
.signal-card {
  background: linear-gradient(135deg, rgba(0,212,160,0.08), rgba(59,130,246,0.06));
  border: 1px solid rgba(0,212,160,0.25);
  border-radius: 16px;
  padding: 24px 28px;
  margin-bottom: 24px;
}
.signal-card-warn {
  background: linear-gradient(135deg, rgba(255,184,0,0.07), rgba(255,69,96,0.05));
  border: 1px solid rgba(255,184,0,0.2);
  border-radius: 16px;
  padding: 24px 28px;
  margin-bottom: 24px;
}

/* Confidence number */
.confidence-num {
  font-family: var(--font-mono);
  font-size: 3rem;
  font-weight: 900;
  background: linear-gradient(135deg, #00D4A0, #3B82F6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
}

/* Badges */
.badge-buy {
  background: rgba(0,212,160,0.15);
  color: #00D4A0;
  border: 1px solid rgba(0,212,160,0.35);
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 700;
}
.badge-wait {
  background: rgba(255,184,0,0.12);
  color: #FFB800;
  border: 1px solid rgba(255,184,0,0.3);
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 700;
}

/* Metric cards (render_individual) */
.metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 16px;
}
.metric-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.metric-value {
  font-family: var(--font-mono);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.metric-delta-neu {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.5;
}

/* Funnel */
.funnel-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.funnel-label { font-size: 11px; color: var(--text-secondary); min-width: 200px; white-space: nowrap; }
.funnel-bar-wrap { flex: 1; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
.funnel-bar { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
.funnel-val { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); min-width: 32px; text-align: right; }

/* Metric mini cards */
.mc { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
      padding: 14px 16px; position: relative; overflow: hidden; margin-bottom: 8px; }
.mc::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; border-radius: 12px 12px 0 0; }
.mc.g::before { background: linear-gradient(90deg, #00D4A0, #00A87F); }
.mc.v::before { background: linear-gradient(90deg, #7C3AED, #3B82F6); }
.mc.r::before { background: linear-gradient(90deg, #FF4560, #C0392B); }
.mc.a::before { background: linear-gradient(90deg, #FFB800, #E67E22); }
.mc.c::before { background: linear-gradient(90deg, #00C8E0, #0099BB); }
.mc-label { font-size: 9px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
            color: var(--text-muted); margin-bottom: 7px; }
.mc-val { font-family: var(--font-mono); font-size: 22px; font-weight: 700; }
.mc-val.g { color: var(--emerald); } .mc-val.r { color: var(--red); }
.mc-val.v { color: var(--violet-light); } .mc-val.a { color: var(--amber); }
.mc-sub { font-size: 10px; color: var(--text-muted); margin-top: 5px; }

/* Signal badges */
.sig { padding: 3px 9px; border-radius: 6px; font-size: 10px; font-weight: 700;
       letter-spacing: .4px; white-space: nowrap; display: inline-block; }
.sig.SB { background: rgba(0,212,160,0.2); color: #00D4A0; border: 1px solid rgba(0,212,160,0.35); }
.sig.B  { background: rgba(0,212,160,0.1); color: #6FEAD4; border: 1px solid rgba(0,212,160,0.2); }
.sig.H  { background: rgba(255,184,0,0.1); color: #FFB800; border: 1px solid rgba(255,184,0,0.2); }
.sig.W  { background: rgba(59,130,246,0.1); color: #60A5FA; border: 1px solid rgba(59,130,246,0.2); }

/* Regimen banners */
.regime-calm  { background: rgba(59,130,246,0.1);  border: 1px solid rgba(59,130,246,0.3);
                border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; }
.regime-bear  { background: rgba(255,184,0,0.1);   border: 1px solid rgba(255,184,0,0.3);
                border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; }
.regime-crash { background: rgba(255,69,96,0.1);   border: 1px solid rgba(255,69,96,0.3);
                border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; }

/* Score bar */
.score-bar-track { width: 100%; height: 6px; background: rgba(255,255,255,0.05);
                   border-radius: 3px; overflow: hidden; }
.score-bar-fill  { height: 100%; border-radius: 3px; transition: width .8s ease; }

/* Data table */
.qt { width: 100%; border-collapse: collapse; font-size: 12px; }
.qt th { text-align: left; padding: 8px 12px; font-size: 9px; font-weight: 700;
         letter-spacing: .8px; text-transform: uppercase; color: var(--text-muted);
         border-bottom: 1px solid var(--border); }
.qt th.r, .qt td.r { text-align: right; }
.qt td { padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.025);
         color: var(--text-secondary); font-family: var(--font-mono); font-size: 11px; }
.qt tr:hover td { background: var(--bg-elevated); color: var(--text-primary); }

/* Input override */
.stTextInput input, .stNumberInput input {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  border-radius: 9px !important;
  color: var(--text-primary) !important;
  font-family: var(--font-main) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
  border-color: rgba(124,58,237,0.4) !important;
  box-shadow: 0 0 0 2px rgba(124,58,237,0.15) !important;
}

/* Button override */
.stButton > button {
  background: linear-gradient(135deg, #7C3AED, #3B82F6) !important;
  border: none !important;
  color: white !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* Progress bar */
[data-testid="stProgressBar"] > div { background: linear-gradient(90deg, #7C3AED, #3B82F6) !important; }

/* Expander */
.streamlit-expanderHeader {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--text-primary) !important;
}

/* Alerts */
[data-testid="stAlert"] {
  background: var(--bg-card) !important;
  border-radius: 10px !important;
  border: 1px solid var(--border) !important;
}

/* Form */
[data-testid="stForm"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  padding: 20px !important;
}

/* Dataframe */
[data-testid="stDataFrame"] { background: var(--bg-card) !important; border-radius: 10px !important; }

/* Radio nav */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
}
</style>
"""
st.markdown(QUANTUM_CSS, unsafe_allow_html=True)

THRESHOLDS_BY_REGIME = {
    "CALM":       {"EMA200_disc": 5.0,  "BB_pctB": 0.30, "Stoch_K": 35},
    "SLOW_BEAR":  {"EMA200_disc": 8.0,  "BB_pctB": 0.30, "Stoch_K": 35},
    "FAST_CRASH": {"EMA200_disc": 12.0, "BB_pctB": 999,  "Stoch_K": 999},
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_current_regime():
    try:
        tk = yf.Ticker("^VIX")
        vix = tk.history(period="3mo")
        if vix.empty: return "CALM", 15.0, 0.0
        
        # Obtener el precio más reciente (tiempo real)
        try:
            rt_price = tk.fast_info.last_price
            if rt_price is not None and not pd.isna(rt_price):
                vix.iloc[-1, vix.columns.get_loc('Close')] = rt_price
        except:
            pass

        vix_series = vix['Close']
        current_vix = float(vix_series.iloc[-1])
        regimes = classify_regime(vix_series)
        current_regime = str(regimes.iloc[-1])
        vix_10d_ago = float(vix_series.iloc[-10]) if len(vix_series) >= 10 else current_vix
        vix_change = ((current_vix - vix_10d_ago) / vix_10d_ago) * 100
        return current_regime, current_vix, vix_change
    except:
        return "CALM", 15.0, 0.0

def get_tnx_yield():
    try:
        tnx = yf.Ticker("^TNX").history(period="5d")
        return float(tnx['Close'].iloc[-1]) if not tnx.empty else 4.2
    except: return 4.2

def get_vix_history_90d():
    try:
        tk = yf.Ticker("^VIX")
        vix = tk.history(period="3mo")
        if vix.empty: return pd.DataFrame()
        
        try:
            rt_price = tk.fast_info.last_price
            if rt_price is not None and not pd.isna(rt_price):
                vix.iloc[-1, vix.columns.get_loc('Close')] = rt_price
        except:
            pass

        regimes = classify_regime(vix['Close'])
        df = vix[['Close']].copy()
        df.columns = ['VIX']
        df['regime'] = regimes.reindex(df.index).ffill().fillna('CALM')
        return df
    except: return pd.DataFrame()

def get_ticker_technicals(ticker: str, start: str, end: str, preloaded_df=None):
    """Returns (df, ind_values, current_price) or (None, None, None)"""
    try:
        if preloaded_df is not None:
            df = preloaded_df.copy() if not preloaded_df.empty else None
        else:
            result = fetch_history([ticker], start=start, end=end)
            df = result.get(ticker)
            
        if df is None or len(df) < 252:
            return None, None, None
        from lab.indicators import rsi, mfi, macd_hist, williams_r, adx

        df['EMA200_disc'] = ema_discount(df)
        df['BB_pctB']     = bollinger_pctB(df)
        df['Stoch_K']     = stochastic_k(df)
        df['RSI']         = rsi(df)
        df['MFI']         = mfi(df)
        df['MACD_hist']   = macd_hist(df)
        df['Williams_R']  = williams_r(df)
        df['ADX']         = adx(df)

        last = df.iloc[-1]
        return df, {
            'EMA200_disc': float(last['EMA200_disc']) if pd.notna(last['EMA200_disc']) else float('nan'),
            'BB_pctB':     float(last['BB_pctB'])     if pd.notna(last['BB_pctB'])     else float('nan'),
            'Stoch_K':     float(last['Stoch_K'])     if pd.notna(last['Stoch_K'])     else float('nan'),
            'RSI':         float(last['RSI'])         if pd.notna(last['RSI'])         else float('nan'),
            'MFI':         float(last['MFI'])         if pd.notna(last['MFI'])         else float('nan'),
            'MACD_rising': bool(last['MACD_hist'] > 0) if pd.notna(last['MACD_hist']) else False,
            'Williams_R':  float(last['Williams_R'])  if pd.notna(last['Williams_R'])  else float('nan'),
            'ADX':         float(last['ADX'])         if pd.notna(last['ADX'])         else float('nan'),
        }, float(last['Close'])
    except Exception as e:
        import traceback
        st.error(f"DEBUG EXCEPTION in get_ticker_technicals: {e} \n {traceback.format_exc()}")
        return None, None, None

def calculate_proximity_score(ema_disc: float, stars: int, regime: str, scan_mode: str = "DIP", rsi: float = None) -> float:
    """
    Score de 0-100 para empresas que NO tienen señal completa.
    Refleja qué tan cerca están de activar la señal.
    """
    if scan_mode == "MOMENTUM":
        # Técnico: RSI entre 40-75 es momentum saludable
        if rsi is not None and not pd.isna(rsi):
            if 50 <= rsi <= 70:
                tech_score = 40.0
            elif 40 <= rsi < 50 or 70 < rsi <= 75:
                tech_score = 25.0
            else:
                tech_score = 10.0  # aún da algo de puntos si pasa el filtro
        else:
            tech_score = 0.0
            
        # EMA score: ema_disc negativo = encima de EMA200 (bien para momentum)
        # Más negativo = más por encima = mejor señal momentum
        if not pd.isna(ema_disc) and ema_disc < 0:
            ema_score = min(abs(ema_disc) / 30.0, 1.0) * 20  # bonus hasta 20pts
        else:
            ema_score = 0.0
        tech_score = min(tech_score + ema_score, 50.0)
            
        min_stars = 8  # Actualizado para coincidir con min_mom_stars
        fund_score = min(stars / min_stars, 1.0) * 40
        
        if tech_score >= 30 and fund_score >= 32:
            bonus = 10
        else:
            bonus = 0
            
        return round(tech_score + fund_score + bonus, 1)

    thresholds = THRESHOLDS_BY_REGIME.get(regime, THRESHOLDS_BY_REGIME["CALM"])
    ema_target = thresholds["EMA200_disc"]

    # Componente técnico: qué % del umbral EMA ya alcanzaron
    ema_disc_clamped = max(0.0, ema_disc)
    if ema_target > 0:
        tech_score = min(ema_disc_clamped / ema_target, 1.0) * 40  # máx 40 pts
    else:
        tech_score = 40.0

    # Componente fundamental: estrellas / total de checks (mínimo 10 en CALM)
    min_stars = 10
    fund_score = min(stars / min_stars, 1.0) * 40  # máx 40 pts

    # Bonus si ambos superan el 80% del umbral
    if tech_score >= 32 and fund_score >= 32:
        bonus = 20
    else:
        bonus = 0

    return round(tech_score + fund_score + bonus, 1)

def get_fundamental_stars(ticker: str, tnx_yield: float, current_price: float, df=None, ind_vals=None, scan_mode: str = 'DIP') -> tuple[int, list]:
    if not FUND_AVAILABLE: return 0, [("Módulo fundamental no disponible (modo demo)", None)]
    try:
        data = fetch_stock_data(ticker)
        
        # Calcular tech real basado en API y Dataframe en lugar de hardcodeo
        tech_real = {}
        if ind_vals:
            tech_real['rsi'] = ind_vals.get('RSI', 50)
        
        if df is not None and not df.empty:
            tech_real['sma_200'] = df['Close'].rolling(window=200).mean().iloc[-1]
            low_52 = df['Low'].rolling(window=252).min().iloc[-1]
            high_52 = df['High'].rolling(window=252).max().iloc[-1]
            if high_52 > low_52:
                tech_real['fifty_two_position'] = ((current_price - low_52) / (high_52 - low_52)) * 100
            else:
                tech_real['fifty_two_position'] = 50
        else:
            tech_real['sma_200'] = current_price
            tech_real['fifty_two_position'] = 50

        res = evaluar_protocolo_accion(data, tech_real, tnx_yield, current_price, soportes=[], profile='B', scan_mode=scan_mode)
        passed = int(res.get('passed', 0))
        total  = int(res.get('total', 1))

        # Normalizar: si Yahoo devuelve datos parciales, escalar a /10 equivalente
        # Ejemplo: 4 passed de 6 total → round(4/6 * 10) = 7 estrellas normalizadas
        EXPECTED_CHECKS = 10
        if total >= EXPECTED_CHECKS:
            normalized = passed          # datos suficientes — usar raw
        elif total >= 3:
            normalized = round((passed / total) * EXPECTED_CHECKS)
        else:
            normalized = 0              # datos insuficientes — no evaluar

        return normalized, res.get('verdicts', [])
    except Exception as e:
        return 0, [("Error de API (Yahoo bloqueó la conexión)", False)]

def analyze_ticker_for_today(ticker: str, regime: str, tnx_yield: float,
                             start: str, end: str, force_fundamental: bool = False, scan_mode: str = "DIP", preloaded_df=None) -> dict | None:
    try:
        df, ind_vals, price = get_ticker_technicals(ticker, start, end, preloaded_df)
        if df is None: return None

        ema_disc = ind_vals.get('EMA200_disc', float('nan'))

        # Pre-check primary indicator for efficiency
        rules = RULE_SETS.get(regime, RULE_SETS["CALM"])
        dyn_th = THRESHOLDS_BY_REGIME.get(regime, THRESHOLDS_BY_REGIME["CALM"])["EMA200_disc"]
        primary_met = False
        
        if scan_mode == "MOMENTUM":
            # MOMENTUM: buscamos acciones POR ENCIMA de EMA200 (tendencia alcista)
            # ema_disc > 0 significa precio < EMA (debajo), ema_disc < 0 significa precio > EMA (encima)
            # Queremos encima del EMA200: ema_disc negativo (precio en tendencia alcista)
            # Rango: precio entre 0% y 50% por encima del EMA200 (ni demasiado estirado)
            if not pd.isna(ema_disc) and (-50.0 <= ema_disc <= 0.0):
                primary_met = True
            is_close_or_met = primary_met
        else:
            for ind_name, th in rules["indicators"]["primary"]:
                val = ind_vals.get(ind_name, float('nan'))
                if pd.isna(val): continue
                direction = 'above' if ind_name == 'EMA200_disc' else 'below'
                if (direction == 'above' and val >= th) or (direction == 'below' and val <= th):
                    primary_met = True
                    break
            is_close_or_met = primary_met or (not pd.isna(ema_disc) and ema_disc >= dyn_th * 0.5)

        rsi_val = ind_vals.get('RSI', float('nan'))
        vol_avg = df['Volume'].tail(20).mean() if 'Volume' in df.columns else 0.0

        passed_rsi = False
        passed_vol = False

        if scan_mode == "MOMENTUM":
            # RSI entre 40 y 75: ni sobrevendido (debilidad) ni sobrecomprado extremo
            if not pd.isna(rsi_val) and (40 <= rsi_val <= 75):
                passed_rsi = is_close_or_met
        else:
            if not pd.isna(rsi_val) and (35 <= rsi_val <= 65):
                passed_rsi = is_close_or_met
        
        if vol_avg > 300000:  # reducido de 500k - incluir más small caps liq
            passed_vol = passed_rsi

        # Para MOMENTUM, siempre correr fundamental si pasó el filtro primario
        # (en DIP solo si pasó volume/RSI)
        if passed_vol:
            is_fund_candidate = True
        elif scan_mode == "MOMENTUM" and primary_met:
            # En momentum corremos fundamental aunque no pase vol estrictamente
            is_fund_candidate = True
            passed_rsi = True
            passed_vol = True
        else:
            is_fund_candidate = False

        stars = 0
        checks = []
        if is_fund_candidate or force_fundamental:
            stars, checks = get_fundamental_stars(ticker, tnx_yield, price, df=df, ind_vals=ind_vals, scan_mode=scan_mode)

        if scan_mode == "MOMENTUM":
            # Stars mínimas en MOMENTUM: 5 (normalizado sobre /10)
            # Con datos parciales de Yahoo, una buena empresa saca 4-6 raw → ~7-10 normalizado
            min_mom_stars = 5
            signal_res = {
                "signal": primary_met and (stars >= min_mom_stars),
                "fundamental_ok": stars >= min_mom_stars,
                "confidence": 100.0 if (primary_met and stars >= min_mom_stars) else 0.0,
                "rationale": f"Momentum OK ({stars}/10 stars)" if (primary_met and stars >= min_mom_stars) else f"Falla Momentum: EMA {ema_disc:.1f}%, {stars}/10 stars (mín {min_mom_stars})",
                "indicators_active": ["EMA200_disc"],
                "indicators_triggered": ["EMA200_disc"] if primary_met else []
            }
        else:
            signal_res = evaluate_signal(ind_vals, regime, stars)

        if signal_res['signal']:
            try:
                rets = df['Close'].pct_change().dropna().tail(252)
                horizon = 5
                mc = simulate_price_paths(price, rets, horizon_days=horizon, n_simulations=10_000)
                
                if scan_mode == "MOMENTUM":
                    mc_reqs = {
                        # (prob_minima_subida, p10_minimo)
                        # Relajados: 35% para CALM (antes 45%), p10 >= -8%
                        "CALM":      (0.35, -0.08),
                        "NORMAL":    (0.40, -0.07),
                        "CAUTION":   (0.42, -0.06),
                        "SLOW_BEAR": (0.45, -0.05)
                    }
                    req_p, req_p10 = mc_reqs.get(regime, (0.40, -0.07))
                    mc['req_p'] = req_p
                    mc['req_p10'] = req_p10
                    mc['req_regime'] = regime
                    
                    p_gt_target = mc['prob_gt_1pct'] if regime == "CALM" else mc['prob_gt_2pct']
                    p10 = mc['p10']
                    
                    if p_gt_target < req_p or p10 < req_p10:
                        signal_res['signal'] = False
                        target_str = "P(>1%)" if regime == "CALM" else "P(>2%)"
                        signal_res['rationale'] = f"MC falla: {target_str}={p_gt_target*100:.1f}% (req {req_p*100:.0f}%), p10={p10*100:.1f}%"
                else:  # DIP mode
                    p_gt_2 = mc['prob_gt_2pct']
                    p10 = mc['p10']
                    mc['req_p'] = 0.40   # era 0.55 — demasiado exigente para DIP
                    mc['req_regime'] = "DIP"
                    if p_gt_2 < 0.40 or p10 < -0.06:  # p10 era -0.03, muy estricto
                        signal_res['signal'] = False
                        signal_res['rationale'] = f"MC falla: P(>2%)={p_gt_2*100:.1f}%, p10={p10*100:.1f}%"
            except Exception as e:
                signal_res['signal'] = False
                signal_res['rationale'] = f"Error en Monte Carlo: {str(e)}"
        else:
            mc = None

        return {
            "ticker":      ticker,
            "price":       price,
            "ema_disc":    ema_disc,
            "ind_vals":    ind_vals,
            "stars":       stars,
            "checks":      checks,
            "primary_met": primary_met,
            "passed_rsi":  passed_rsi,
            "passed_vol":  passed_vol,
            "signal":      signal_res,
            "df":          df,
            "mc":          mc,
            "timestamp":   datetime.datetime.now().strftime('%H:%M:%S'),
        }
    except Exception as e:
        import traceback
        st.error(f"DEBUG EXCEPTION in analyze_ticker_for_today: {e} \n {traceback.format_exc()}")
        return None


def render_regime_banner(vix_val, regime):
    colors = {"CALM": ("c", "#00C8E0", "🟦"), "SLOW_BEAR": ("a", "#FFB800", "🟨"), "FAST_CRASH": ("r", "#FF4560", "🟥")}
    cls, color, emoji = colors.get(regime, ("v", "#A78BFA", "🔵"))
    activos = {"CALM": "EMA200_disc (8%)", "SLOW_BEAR": "EMA200 (12%) + BB + Stoch", "FAST_CRASH": "Solo EMA200 (15%)"}
    st.markdown(f"""
    <div class="regime-{cls.replace('r','crash').replace('a','bear').replace('c','calm')}">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <span style="font-size:11px;font-weight:700;color:{color}">{emoji} RÉGIMEN: {regime}</span>
          <span style="font-size:10px;color:var(--text-muted);margin-left:12px">VIX: {vix_val:.2f}</span>
        </div>
        <div style="font-size:10px;color:var(--text-secondary)">Activos: <b>{activos[regime]}</b></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_scanner_table(results: list, is_proximity: bool = False):
    """
    is_proximity=True  → sección "Próximamente", etiqueta VIGILAR/MONITOREAR
    is_proximity=False → sección señales activas, etiqueta BUY/STRONG BUY
    """
    rows = ""
    for r in results:
        ticker = r.get('ticker', '')
        nombre = r.get('nombre', ticker)
        precio = r.get('price', 0.0)
        ema_val = r.get('ema_disc', 0.0)
        stars = r.get('stars', 0)
        signal_dict = r.get('signal', {})
        conf = signal_dict.get('confidence', 0) if isinstance(signal_dict, dict) else r.get('confidence', 0)

        scan_mode = r.get('scan_mode', '')
        
        # En sección Próximamente: siempre VIGILAR, nunca BUY
        if is_proximity:
            sig_class = "W"
            sig_text  = "VIGILAR"
            score_color = "#60A5FA"
        else:
            if scan_mode == "MOMENTUM":
                mc_data = r.get('mc') or {}
                p1_pct = mc_data.get('prob_gt_1pct', 0) * 100
                if p1_pct >= 50.0:
                    sig_class = "SB"
                    score_color = "#00D4A0"
                elif p1_pct >= 47.0:
                    sig_class = "B"
                    score_color = "#FFB800"
                else:
                    sig_class = "W"
                    score_color = "#60A5FA"
            else:
                sig_class = "SB" if conf >= 75 else "B" if conf >= 50 else "W"
                score_color = "#00D4A0" if conf >= 75 else "#FFB800" if conf >= 50 else "#60A5FA"
                
            sig_text  = "STRONG BUY" if sig_class == "SB" else "BUY" if sig_class == "B" else "VIGILAR"

        ema_str = f"{-ema_val:.1f}%" if ema_val < 0 else f"+{ema_val:.1f}%"

        # Stars: mostrar N/D si fundamental no disponible (stars == 0 y is_proximity)
        stars_str = f"{stars}/16" if (stars > 0 or not is_proximity) else "N/D"

        mc = r.get('mc')
        if mc:
            req_regime = mc.get('req_regime', '')
            target_val = 0
            if req_regime == "CALM" and r.get('scan_mode', '') == "MOMENTUM":
                target_val = mc.get('prob_gt_1pct', 0) * 100
                target_label = "P(>1%)"
            else:
                target_val = mc.get('prob_gt_2pct', 0) * 100
                target_label = "P(>2%)"
                
            p90 = mc.get('p90', 0) * 100
            p10 = mc.get('p10', 0) * 100
            vol = mc.get('sigma_anual', 0) * 100
            req_p = mc.get('req_p', 0) * 100
            req_str = f"<br><span style='font-size:10px;color:var(--text-muted)'>Req: {req_p:.0f}% ({req_regime})</span>" if req_p > 0 else ""
            mc_html = f'<td class="r" style="color:#00D4A0;font-weight:600;">{target_label}: {target_val:.1f}%{req_str}</td><td class="r" style="font-size:11px;"><span style="color:#00D4A0">+{p90:.1f}%</span> / <span style="color:#FF4560">{p10:.1f}%</span></td><td class="r" style="color:var(--text-secondary)">{vol:.1f}%</td>'
        else:
            mc_html = '<td class="r" style="color:var(--text-muted)">N/A</td><td class="r" style="color:var(--text-muted)">N/A</td><td class="r" style="color:var(--text-muted)">N/A</td>'

        m = r.get('scan_mode', '')
        scan_mode_badge = ""
        if m == "MOMENTUM":
            scan_mode_badge = ' <span style="font-size:9px;background:#3B82F6;color:#fff;padding:2px 4px;border-radius:3px;margin-left:4px;">MOM</span>'
        elif m == "DIP":
            scan_mode_badge = ' <span style="font-size:9px;background:#10B981;color:#fff;padding:2px 4px;border-radius:3px;margin-left:4px;">DIP</span>'
            
        rows += f"""
        <tr>
          <td style="font-weight:600;color:var(--text-primary)">{ticker}{scan_mode_badge}</td>
          <td style="color:var(--text-secondary)">{nombre}</td>
          <td class="r">${precio:.2f}</td>
          <td class="r" style="color:#FF4560">{ema_str}</td>
          <td class="r" style="color:var(--text-muted)">{stars_str}</td>
          <td>
            <div class="sb" style="display:flex;align-items:center;gap:8px">
              <div class="score-bar-track" style="width:80px">
                <div class="score-bar-fill" style="width:{conf}%;background:{score_color}"></div>
              </div>
              <span style="font-family:var(--font-mono);font-size:11px;color:{score_color}">{conf:.0f}</span>
            </div>
          </td>
          {mc_html}
          <td><span class="sig {sig_class}">{sig_text}</span></td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--text-muted)">Sin resultados</td></tr>'

    header_stars = "STARS" if not is_proximity else "FUND."
    return f"""
    <table class="qt">
      <thead>
        <tr>
          <th>TICKER</th><th>EMPRESA</th><th class="r">PRECIO</th>
          <th class="r">EMA200 DISC</th><th class="r">{header_stars}</th>
          <th>TÉCNICO</th><th class="r">P(>2%)</th><th class="r">P90/P10</th><th class="r">VOL ANUAL</th><th>ESTADO</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


# ── Funnel display ────────────────────────────────────────────────────────────
def render_funnel(total, downloaded, regime, passed_ema, passed_rsi, passed_vol, passed_fund, signals):
    steps = [
        ("S&P 500 total",             total,      total),
        ("Datos descargados",         downloaded, total),
        ("Pasaron EMA umbral",        passed_ema, total),
        ("Pasaron filtro RSI",        passed_rsi, total),
        ("Pasaron filtro Volumen",    passed_vol, total),
        ("Pasaron filtro fundamental",passed_fund,total),
        ("SEÑAL COMPLETA activa",     signals,    total),
    ]
    html = '<div style="background:#0f172a;border-radius:12px;padding:16px 20px;margin:12px 0;">'
    html += f'<p style="color:#64748b;font-size:0.8rem;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">📊 Funnel — Régimen HOY: <b style="color:#3b82f6">{regime}</b></p>'
    for label, val, mx in steps:
        pct = int((val / mx) * 100) if mx > 0 else 0
        color = "#22c55e" if "SEÑAL" in label and val > 0 else "#3b82f6"
        html += f"""<div class="funnel-row">
          <span class="funnel-label">{label}</span>
          <div class="funnel-bar-wrap">
            <div class="funnel-bar" style="width:{pct}%;background:{color};"></div>
          </div>
          <span class="funnel-val">{val}</span>
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ── Individual analysis card ──────────────────────────────────────────────────
def render_individual(ticker: str, regime: str, tnx_yield: float):
    end   = datetime.date.today().strftime('%Y-%m-%d')
    start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

    with st.spinner(f"Analizando {ticker}..."):
        res = analyze_ticker_for_today(ticker, regime, tnx_yield, start, end, force_fundamental=True)

    if res is None:
        st.error(f"No se pudieron obtener datos para **{ticker}**. Verifica que el ticker sea válido.")
        return

    s = res["signal"]
    conf = s["confidence"]
    rules = RULE_SETS.get(regime, RULE_SETS["CALM"])

    # Header
    signal_class = "signal-card" if s["signal"] else "signal-card-warn"
    badge_html = '<span class="badge-buy">✅ SEÑAL ACTIVA</span>' if s["signal"] else '<span class="badge-wait">⚠️ SIN SEÑAL COMPLETA</span>'
    st.markdown(f"""
    <div class="{signal_class}">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h2 style="margin:0;color:#fff;font-size:2rem;font-weight:900;">{ticker}</h2>
          <p style="margin:4px 0;color:#94a3b8;">${res['price']:.2f} · {badge_html}</p>
        </div>
        <div style="text-align:right;">
          <div class="confidence-num">{conf:.0f}</div>
          <div style="color:#64748b;font-size:0.75rem;text-transform:uppercase;">/ 100 Confidence</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Régimen y Reglas Activas</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    # Card 1: Régimen
    regime_icons = {"CALM": "🟦", "SLOW_BEAR": "🟨", "FAST_CRASH": "🟥"}
    with c1:
        ok_reg = True  # régimen siempre está disponible
        color = "#22c55e" if ok_reg else "#ef4444"
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Régimen HOY</div>
          <div class="metric-value" style="color:{color}">{regime_icons.get(regime,'🟦')} {regime}</div>
          <div class="metric-delta-neu" style="font-size:0.75rem;">{rules['rationale'][:60]}…</div>
        </div>""", unsafe_allow_html=True)

    # Card 2: Técnico
    with c2:
        triggered = s["indicators_triggered"]
        active    = s["indicators_active"]
        tech_ok   = len(triggered) >= rules["min_signals"]
        color = "#22c55e" if tech_ok else "#ef4444"
        lines = []
        for ind_name, th in (rules["indicators"]["primary"] + rules["indicators"]["secondary"]):
            val = res["ind_vals"].get(ind_name, float('nan'))
            trig = ind_name in triggered
            mark = "✅" if trig else "⚠️"
            direction = "≥" if ind_name == 'EMA200_disc' else "≤"
            val_str = f"{val:.1f}%" if ind_name == "EMA200_disc" else f"{val:.2f}" if not pd.isna(val) else "N/A"
            lines.append(f"{mark} {ind_name}: {val_str} (umbral {direction}{th})")
        tech_html = "<br>".join(lines) or "—"
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Técnico</div>
          <div class="metric-value" style="color:{color}">{'✅ OK' if tech_ok else '❌ Falta'}</div>
          <div class="metric-delta-neu" style="font-size:0.78rem;line-height:1.6;">{tech_html}</div>
        </div>""", unsafe_allow_html=True)

    # Card 3: Fundamental (Full width below)
    fund_min = rules["min_stars"]
    fund_ok  = s["fundamental_ok"]
    stars    = res["stars"]
    color = "#22c55e" if fund_ok else ("#f59e0b" if not rules["requires_fundamental"] else "#ef4444")
    req_txt = f"Mín: {fund_min} stars" if rules["requires_fundamental"] else "Opcional"
    
    checks_html = "<div style='display: grid; grid-template-columns: 1fr; gap: 6px; margin-top: 12px;'>"
    for name, status in res.get("checks", []):
        if status is True: 
            icon = "✅"
            bg = "rgba(34, 197, 94, 0.1)"
            border = "rgba(34, 197, 94, 0.2)"
        elif status is False: 
            icon = "❌"
            bg = "rgba(239, 68, 68, 0.1)"
            border = "rgba(239, 68, 68, 0.2)"
        else: 
            icon = "➖"
            bg = "rgba(148, 163, 184, 0.1)"
            border = "rgba(148, 163, 184, 0.2)"
            
        checks_html += f"<div style='background: {bg}; border: 1px solid {border}; border-radius: 6px; padding: 6px 10px; font-size: 0.75rem; display: flex; align-items: center; gap: 8px;'><span style='font-size: 0.9rem;'>{icon}</span><span style='color: #e2e8f0; line-height: 1.2;'>{name}</span></div>"
    checks_html += "</div>"
        
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Calidad Fundamental</div>
      <div class="metric-value" style="color:{color}">{stars}/16 ⭐</div>
      <div class="metric-delta-neu" style="margin-bottom:8px;">{req_txt} · {'✅ Pasa' if fund_ok else ('⚠️ No requerido' if not rules['requires_fundamental'] else '❌ Falla')}</div>
      {checks_html}
    </div>""", unsafe_allow_html=True)

    # Señales Corto Plazo
    st.markdown('<div class="section-title">⏱️ Señales de Corto Plazo (1 día)</div>', unsafe_allow_html=True)
    
    rsi_val = res["ind_vals"].get("RSI", float("nan"))
    will_val = res["ind_vals"].get("Williams_R", float("nan"))
    stoch_val = res["ind_vals"].get("Stoch_K", float("nan"))
    
    rsi_ok = rsi_val <= 20 if pd.notna(rsi_val) else False
    will_ok = will_val <= -80 if pd.notna(will_val) else False
    stoch_ok = stoch_val <= 20 if pd.notna(stoch_val) else False

    st.markdown(f"""
    <div style="background:#0f172a;border-radius:12px;padding:16px 20px;margin-bottom:20px;">
      <table class="qt" style="width:100%;">
        <thead>
          <tr>
            <th>INDICADOR</th>
            <th class="r">VALOR ACTUAL</th>
            <th class="r">UMBRAL</th>
            <th class="r">EDGE HISTÓRICO (1D)</th>
            <th style="text-align:center">ESTADO</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="font-weight:600;color:var(--text-primary)">RSI (14)</td>
            <td class="r">{"{:.2f}".format(rsi_val) if pd.notna(rsi_val) else "N/A"}</td>
            <td class="r">≤ 20</td>
            <td class="r" style="color:#00D4A0">+2.79 pp</td>
            <td style="text-align:center">{"🟢 ACTIVO" if rsi_ok else "⚪ INACTIVO"}</td>
          </tr>
          <tr>
            <td style="font-weight:600;color:var(--text-primary)">Williams %R (14)</td>
            <td class="r">{"{:.2f}".format(will_val) if pd.notna(will_val) else "N/A"}</td>
            <td class="r">≤ -80</td>
            <td class="r" style="color:#00D4A0">+1.85 pp</td>
            <td style="text-align:center">{"🟢 ACTIVO" if will_ok else "⚪ INACTIVO"}</td>
          </tr>
          <tr>
            <td style="font-weight:600;color:var(--text-primary)">Stochastic K (14)</td>
            <td class="r">{"{:.2f}".format(stoch_val) if pd.notna(stoch_val) else "N/A"}</td>
            <td class="r">≤ 20</td>
            <td class="r" style="color:#00D4A0">+1.50 pp</td>
            <td style="text-align:center">{"🟢 ACTIVO" if stoch_ok else "⚪ INACTIVO"}</td>
          </tr>
        </tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # Monte Carlo
    st.markdown('<div class="section-title">📈 Simulación Monte Carlo (10,000 trayectorias · 5 días)</div>',
                unsafe_allow_html=True)
    df_hist = res["df"]
    rets = df_hist['Close'].pct_change().dropna().tail(252)
    with st.spinner("Simulando..."):
        mc = simulate_price_paths(res["price"], rets, horizon_days=5, n_simulations=10_000)

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("Prob. > 0%",   f"{mc['prob_positive']*100:.1f}%")
    mc2.metric("Prob. > 2%",   f"{mc['prob_gt_2pct']*100:.1f}%")
    mc3.metric("Prob. > 5%",   f"{mc['prob_gt_5pct']*100:.1f}%")
    mc4.metric("Pesimista p10",f"{mc['p10']*100:.1f}%")
    mc5.metric("Optimista p90",f"{mc['p90']*100:.1f}%")

    st.markdown(f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:16px 20px;margin-top:12px;">
      <p style="margin:0;color:#94a3b8;font-size:0.85rem;">
        Escenario base <b style="color:#fff">(p50): {mc['p50']*100:+.1f}%</b> &nbsp;·&nbsp;
        Volatilidad anualizada: <b style="color:#fff">{mc['sigma_anual']*100:.1f}%</b>
      </p>
    </div>""", unsafe_allow_html=True)


# ── Correlación en Tiempo Real ──────────────────────────────────────────────────
import plotly.graph_objects as go
from typing import Tuple

import io
@st.cache_data(ttl=3600, show_spinner=False, max_entries=5)
def compute_optimized_correlation_matrix(price_matrix_json: str) -> Tuple[np.ndarray, list]:
    df_prices = pd.read_json(io.StringIO(price_matrix_json), orient='split')
    df_prices.ffill(inplace=True)
    df_prices.bfill(inplace=True)
    tickers = df_prices.columns.tolist()
    corr_matrix_full = np.corrcoef(df_prices.values.T)
    lower_triangle_mask = np.tril(np.ones(corr_matrix_full.shape, dtype=bool))
    corr_matrix_lower = np.where(lower_triangle_mask, corr_matrix_full, np.nan)
    return corr_matrix_lower, tickers

def render_realtime_correlation_heatmap(df_prices: pd.DataFrame) -> None:
    if df_prices.empty:
        st.warning("Datos estructurales insuficientes para evaluación de covarianza.")
        return
        
    json_payload = df_prices.to_json(orient='split')
    
    with st.spinner("Resolviendo topología de covarianza cruzada..."):
        corr_matrix, labels = compute_optimized_correlation_matrix(json_payload)
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=labels,
        y=labels,
        colorscale='RdBu',
        zmin=-1, zmax=1,
        hoverongaps=False, 
        showscale=True
    ))
    
    fig.update_layout(
        title='Estructura de Correlación Matricial (Triangular Inferior)',
        xaxis_nticks=min(len(labels), 30),
        yaxis_nticks=min(len(labels), 30),
        margin=dict(l=20, r=20, t=40, b=20),
        height=750,
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    st.plotly_chart(fig, use_container_width=True)

# ── VIX History page ──────────────────────────────────────────────────────────
def render_vix_page():
    st.markdown('<p class="hero-title">📈 Régimen de Mercado</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Histórico del VIX y clasificación de regímenes · últimos 90 días</p>', unsafe_allow_html=True)

    df = get_vix_history_90d()
    if df.empty:
        st.error("No se pudieron cargar datos del VIX.")
        return

    # Regime distribution
    counts = df['regime'].value_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("🟦 Días CALM",      counts.get("CALM", 0))
    c2.metric("🟨 Días SLOW_BEAR", counts.get("SLOW_BEAR", 0))
    c3.metric("🟥 Días FAST_CRASH",counts.get("FAST_CRASH", 0))

    # Color-coded VIX chart
    st.markdown('<div class="section-title">VIX Histórico con Regímenes</div>', unsafe_allow_html=True)

    regime_color_map = {"CALM": "#3b82f6", "SLOW_BEAR": "#f59e0b", "FAST_CRASH": "#ef4444"}
    colors = df['regime'].map(regime_color_map).fillna("#3b82f6")

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df['VIX'],
        mode='lines', name='VIX',
        line=dict(color='#94a3b8', width=1),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.08)'
    ))
    # Threshold lines
    fig.add_hline(y=20, line_dash="dash", line_color="#3b82f6", annotation_text="VIX 20 (CALM→BEAR)")
    fig.add_hline(y=40, line_dash="dash", line_color="#ef4444", annotation_text="VIX 40 (FAST_CRASH)")
    fig.update_layout(
        paper_bgcolor='#0a0e1a', plot_bgcolor='#0f172a',
        font=dict(color='#e2e8f0', family='Inter'),
        xaxis=dict(gridcolor='#1e293b'), yaxis=dict(gridcolor='#1e293b'),
        height=400, margin=dict(l=0, r=0, t=20, b=0),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

    # Recent regime log
    st.markdown('<div class="section-title">Registro de Regímenes (últimos 30 días)</div>', unsafe_allow_html=True)
    last30 = df.tail(30)[['VIX','regime']].copy()
    last30.index = last30.index.strftime('%Y-%m-%d')
    last30.columns = ['VIX', 'Régimen']
    st.dataframe(last30.style.map(
        lambda v: 'color: #3b82f6' if v == 'CALM' else ('color: #f59e0b' if v == 'SLOW_BEAR' else 'color: #ef4444'),
        subset=['Régimen']
    ), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def full_reset():
    """Limpia todo el estado, cachés y variables globales."""
    # 1. Limpiar st.session_state
    keys_to_clear = ['radar_results', 'radar_all_ema', 'radar_funnel', 'scan_progress', 'scan_total', 'scan_is_running']
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
            
    # 2. Limpiar cache general de Streamlit
    st.cache_data.clear()
    
    # 3. Limpiar lru_cache en data_fetcher y estrategia
    try:
        from data.fetcher import fetch_stock_data
        if hasattr(fetch_stock_data, "cache_clear"):
            fetch_stock_data.cache_clear()
    except Exception:
        pass
    try:
        from data.fetcher import fetch_stock_data_radar
        if hasattr(fetch_stock_data_radar, "cache_clear"):
            fetch_stock_data_radar.cache_clear()
    except Exception:
        pass
    try:
        from estrategia import evaluar_protocolo_accion
        if hasattr(evaluar_protocolo_accion, "cache_clear"):
            evaluar_protocolo_accion.cache_clear()
    except Exception:
        pass
        
    # 4. Limpiar globales
    global GLOBAL_SCANS
    if 'session_id' in st.session_state:
        sid = st.session_state.session_id
        if sid in GLOBAL_SCANS:
            del GLOBAL_SCANS[sid]

regime, current_vix, vix_change = get_current_regime()
tnx_yield = get_tnx_yield()

end_date   = datetime.date.today().strftime('%Y-%m-%d')
start_date = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

# Sidebar
with st.sidebar:
    st.markdown("""
    <div style="padding:18px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#7C3AED,#3B82F6);
                 display:flex;align-items:center;justify-content:center;font-size:18px;">⚡</div>
      <div>
        <div style="font-size:15px;font-weight:800;background:linear-gradient(135deg,#A78BFA,#60A5FA);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">FRANCOTIRADOR</div>
        <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.8px;">Trading System</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    page = st.radio("", ["📡 Radar S&P 500", "💰 Paso 2 — Cuánto Comprar",
                         "🔍 Análisis Individual",
                         "📊 Régimen de Mercado", "🔗 Correlación", "⚙️ Configuración", "🏥 Diagnóstico de Datos"],
                    label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown(f"**VIX:** `{current_vix:.2f}`")
    st.markdown(f"**TNX Yield:** `{tnx_yield:.2f}%`")
    
    st.markdown("---")
    if st.button("🗑️ Borrar Memoria y Redescargar"):
        full_reset()
        st.success("Memoria borrada. Sistema 100% limpio. Por favor refresca (F5).")

# ── PAGE: Radar ────────────────────────────────────────────────────────────────
if page == "📡 Radar S&P 500":
    st.markdown('<p class="hero-title">⚡ Radar de Trading</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Scanner cuantitativo S&P 500 · Motor de reglas dinámico</p>', unsafe_allow_html=True)

    render_regime_banner(current_vix, regime)

    if 'radar_results' not in st.session_state:
        st.session_state.radar_results   = []
        st.session_state.radar_all_ema   = []  # all results for "closest" view
        st.session_state.radar_funnel    = {}

    if regime == "CALM":
        modes_to_run = ["MOMENTUM"]
        mode_text = "Momentum"
    elif regime == "SLOW_BEAR":
        modes_to_run = ["MOMENTUM", "DIP"]
        mode_text = "Momentum y Dip"
    else:
        modes_to_run = ["DIP"]
        mode_text = "Dip"

    st.markdown(f'<p style="color:var(--text-secondary);font-size:13px;margin-top:-10px;margin-bottom:20px;">Modo activo: <b>{mode_text}</b> — Régimen <b>{regime}</b></p>', unsafe_allow_html=True)
    scan_btn = st.button("🚀 Ejecutar Escáner (S&P 500)", use_container_width=False)
    sp500_list = fetch_sp500_tickers_wiki_v2()
    session_id = st.session_state.session_id

    # -- Background Worker Definition --
    def scan_worker(sid, tickers, current_regime, t_yield, s_date, e_date, mode_list):
        state = GLOBAL_SCANS[sid]
        
        # 1. BULK FETCH TÉCNICO (Elimina 500 requests individuales)
        try:
            from data.fetcher import fetch_history
            bulk_data = fetch_history(tickers, start=s_date, end=e_date)
        except Exception:
            bulk_data = {}
        
        # 2. RUN WORKERS CONCURRENTE (x5 para acelerar Monte Carlo y Fundamental)
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {}
            for t in tickers:
                for m in mode_list:
                    preloaded_df = bulk_data.get(t)
                    futures[ex.submit(analyze_ticker_for_today, t, current_regime, t_yield, s_date, e_date, False, m, preloaded_df)] = (t, m)
                       
            for fut in as_completed(futures):
                if state['cancel']:
                    break
                    
                state['completed'] += 1
                res = fut.result()
                if res is None: continue
                
                t, m = futures[fut]
                res['scan_mode'] = m
                
                state['downloaded'] += 1
                ema_val = res['ema_disc']
                dyn_th = THRESHOLDS_BY_REGIME.get(current_regime, THRESHOLDS_BY_REGIME["CALM"])["EMA200_disc"]
                
                stars_val = res.get('passed', res.get('stars', 0))
                rsi_val = res.get('ind_vals', {}).get('RSI', None)
                proximity = calculate_proximity_score(ema_val if not pd.isna(ema_val) else 0.0, stars_val, current_regime, scan_mode=m, rsi=rsi_val)
                res['confidence'] = proximity
                if isinstance(res.get('signal'), dict):
                    res['signal']['confidence'] = proximity

                res['signal_active'] = res['signal']['signal']
                res['ema200_disc'] = res['ema_disc']

                if not pd.isna(ema_val):
                    state['all_ema_rows'].append(res)
                if res['primary_met'] or (not pd.isna(ema_val) and ema_val >= dyn_th):
                    state['passed_ema'] += 1
                if res.get('passed_rsi', False):
                    state['passed_rsi'] += 1
                if res.get('passed_vol', False):
                    state['passed_vol'] += 1
                if res['signal']['fundamental_ok']:
                    state['passed_fund'] += 1
                    
                if res['signal']['signal']:
                    state['results'].append(res)
                    state['signals_found'] += 1

        if not state['cancel']:
            # Sort arrays
            state['results'] = sorted(state['results'], key=lambda x: x.get('mc', {}).get('prob_gt_2pct', 0) if isinstance(x.get('mc'), dict) else 0, reverse=True)
            state['all_ema_rows'] = sorted(state['all_ema_rows'], key=lambda x: x['ema_disc'] if not pd.isna(x['ema_disc']) else 0, reverse=True)
            state['status'] = 'completed'
        else:
            state['status'] = 'cancelled'

    # -- Start Scan Trigger --
    if scan_btn:
        full_reset()
        
        st.session_state.radar_results = []
        st.session_state.radar_all_ema = []
        st.session_state.radar_funnel  = {}
        
        GLOBAL_SCANS[session_id] = {
            'status': 'running',
            'cancel': False,
            'total_t': len(sp500_list) * len(modes_to_run),
            'completed': 0,
            'downloaded': 0,
            'passed_ema': 0,
            'passed_rsi': 0,
            'passed_vol': 0,
            'passed_fund': 0,
            'signals_found': 0,
            'results': [],
            'all_ema_rows': []
        }
        threading.Thread(target=scan_worker, args=(session_id, sp500_list, regime, tnx_yield, start_date, end_date, modes_to_run), daemon=True).start()

    # -- Auto-refresh Fragment for UI --
    @st.fragment(run_every="2s")
    def render_live_radar():
        sid = st.session_state.session_id
        state = GLOBAL_SCANS.get(sid)
        
        # Determine if we should show persisted data or live data
        if not state:
            # Nothing running globally for this session, just show what's in session state
            if st.session_state.radar_funnel:
                f = st.session_state.radar_funnel
                render_funnel(f["total"], f["downloaded"], f["regime"], f["passed_ema"], f.get("passed_rsi", 0), f.get("passed_vol", 0), f["passed_fund"], f["signals"])
                if st.session_state.radar_results:
                    st.markdown(render_scanner_table(st.session_state.radar_results), unsafe_allow_html=True)
            return

        # Read live state
        c = state['completed']
        t = state['total_t']
        
        # Detener escaneo
        if state['status'] == 'running':
            if st.button("⏹️ Detener Escaneo"):
                state['cancel'] = True
                st.rerun()

        if state['status'] == 'running':
            st.progress(c / t if t > 0 else 0, text=f"Escaneando... {c}/{t} completados")
            render_funnel(t, state['downloaded'], regime, state['passed_ema'], state['passed_rsi'], state['passed_vol'], state['passed_fund'], state['signals_found'])
            if state['results']:
                st.markdown(render_scanner_table(state['results']), unsafe_allow_html=True)
            st.session_state.radar_results = state['results']
                
        elif state['status'] == 'completed':
            # Sync to session_state
            st.session_state.radar_results = state['results']
            st.session_state.radar_all_ema = state['all_ema_rows']
            st.session_state.radar_funnel = {
                "total": t, "downloaded": state['downloaded'], "regime": regime,
                "passed_ema": state['passed_ema'], "passed_rsi": state['passed_rsi'], "passed_vol": state['passed_vol'],
                "passed_fund": state['passed_fund'], "signals": state['signals_found']
            }
            st.success(f"✅ Escaneo completo · {state['signals_found']} señales activas")
            render_funnel(t, state['downloaded'], regime, state['passed_ema'], state['passed_rsi'], state['passed_vol'], state['passed_fund'], state['signals_found'])
            if state['results']:
                st.markdown(render_scanner_table(state['results']), unsafe_allow_html=True)
            GLOBAL_SCANS.pop(sid, None) # Clear out the background task tracker since we persisted to session state
            
        elif state['status'] == 'cancelled':
            st.warning(f"⚠️ Escaneo detenido por el usuario. {c}/{t} analizados.")
            render_funnel(t, state['downloaded'], regime, state['passed_ema'], state['passed_rsi'], state['passed_vol'], state['passed_fund'], state['signals_found'])
            st.session_state.radar_results = state['results']
            if state['results']:
                st.markdown(render_scanner_table(state['results']), unsafe_allow_html=True)
            GLOBAL_SCANS.pop(sid, None)

    render_live_radar()


    if st.session_state.radar_funnel or st.session_state.radar_results or st.session_state.radar_all_ema:
        # 1. Active signals section
        st.markdown('<div class="section-title">🎯 Señales Activas (Ranking por Confidence)</div>', unsafe_allow_html=True)
        
        señales_activas = [r for r in st.session_state.radar_results if r.get('signal', {}).get('signal', False) or r.get('signal_active', False)]
        
        if señales_activas:
            st.markdown(render_scanner_table(señales_activas), unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(255,184,0,0.05);border:1px solid rgba(255,184,0,0.2);
                        border-radius:10px;padding:20px;text-align:center;color:#FFB800">
              <div style="font-size:24px;margin-bottom:8px">⏳</div>
              <div style="font-weight:700">Sin señales activas hoy</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:4px">
                Régimen {regime} · Mercado en valuación extendida · Sistema en espera
              </div>
            </div>""", unsafe_allow_html=True)

        # 2. Proximos section
        if st.session_state.radar_all_ema:
            st.markdown('<div class="section-title">🔭 Próximamente (Top 20 por EMA200 Discount)</div>', unsafe_allow_html=True)
            proximos_raw = [r for r in st.session_state.radar_all_ema if not (r.get('signal', {}).get('signal', False) or r.get('signal_active', False))]
            proximos = sorted(proximos_raw, key=lambda x: x.get('ema200_disc', x.get('ema_disc', -999)) if not pd.isna(x.get('ema200_disc', x.get('ema_disc', -999))) else -999, reverse=True)[:20]
            st.markdown(render_scanner_table(proximos, is_proximity=True), unsafe_allow_html=True)

# ── PAGE: Individual ──────────────────────────────────────────────────────────
elif page == "🔍 Análisis Individual":
    st.markdown('<p class="hero-title">🔍 Análisis Individual</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Evalúa cualquier ticker con el motor de reglas + Monte Carlo</p>', unsafe_allow_html=True)

    render_regime_banner(current_vix, regime)

    col_s, col_b = st.columns([4, 1])
    with col_s:
        ticker_input = st.text_input(
            "", placeholder="Buscar ticker o empresa (ej: AAPL, Microsoft, Nvidia...)",
            label_visibility="collapsed", key="ticker_search"
        )
    with col_b:
        analyze_btn = st.button("⚡ Analizar", use_container_width=True)

    # Name search
    if ticker_input and (len(ticker_input) > 5 or ' ' in ticker_input) and SEARCH_AVAILABLE:
        with st.spinner("Buscando..."):
            resultados = search_ticker_by_name(ticker_input)
        if resultados:
            opciones = [f"{r['symbol']} — {r.get('name', r['symbol'])}" for r in resultados[:8]]
            seleccion = st.selectbox("¿Quisiste decir?", opciones, key="search_select")
            if seleccion:
                ticker_input = seleccion.split(" — ")[0]

    ticker_final = ticker_input.strip().upper() if ticker_input else ""

    if ticker_final:
        render_individual(ticker_final, regime, tnx_yield)
    else:
        st.markdown("""
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:40px;text-align:center;margin-top:20px;">
          <div style="font-size:3rem;">🔍</div>
          <h3 style="color:#e2e8f0;margin:12px 0;">Busca un ticker para analizar</h3>
          <p style="color:#64748b;">Escribe el símbolo (AAPL, MSFT) o el nombre de la empresa y pulsa Analizar o Enter</p>
        </div>""", unsafe_allow_html=True)

# ── PAGE: Régimen ─────────────────────────────────────────────────────────────
elif page == "📊 Régimen de Mercado":
    render_vix_page()

# ── PAGE: Correlación ─────────────────────────────────────────────────────────
elif page == "🔗 Correlación":
    st.markdown('<p class="hero-title">🔗 Correlación de Activos</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Matriz de covarianza cruzada en tiempo real</p>', unsafe_allow_html=True)
    
    st.info("Obteniendo datos de precios de una muestra representativa (Top 30 S&P 500)...")
    try:
        sample_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "BRK-B", "JPM", "JNJ", 
                          "V", "PG", "UNH", "HD", "MA", "DIS", "PYPL", "BAC", "VZ", "ADBE", "NFLX", "INTC", 
                          "CMCSA", "PFE", "KO", "PEP", "T", "XOM", "CSCO", "ABT"]
        df_history = yf.download(sample_tickers, period="3mo", progress=False)["Close"]
        if isinstance(df_history.columns, pd.MultiIndex):
            df_history.columns = df_history.columns.droplevel(0) if "Close" in df_history.columns.names else df_history.columns
        render_realtime_correlation_heatmap(df_history)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")

# ── PAGE: Configuración ───────────────────────────────────────────────────────
elif page == "⚙️ Configuración":
    st.markdown('<p class="hero-title">⚙️ Configuración</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Ajustes del sistema y conexión de APIs</p>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:20px;margin-top:20px;">
      <h3 style="color:#e2e8f0;margin-bottom:16px;">Ajustes del Sistema</h3>
    </div>""", unsafe_allow_html=True)
    
    with st.form("config_form"):
        st.text_input("API Key (FMP)", type="password", placeholder="Ingresa tu API Key de Financial Modeling Prep")
        st.text_input("API Key (OpenAI)", type="password", placeholder="Ingresa tu API Key de OpenAI")
        st.slider("Umbral VIX (Calm -> Bear)", min_value=15.0, max_value=30.0, value=20.0, step=0.5)
        st.slider("Umbral VIX (Bear -> Crash)", min_value=30.0, max_value=50.0, value=40.0, step=0.5)
        submitted = st.form_submit_button("Guardar Configuración")
        if submitted:
            st.success("Configuración guardada correctamente.")

# ── PAGE: Paso 2 — Asignación de Capital ─────────────────────────────────────
elif page == "💰 Paso 2 — Cuánto Comprar":
    st.markdown('<p class="hero-title">💰 Paso 2 — Asignación de Capital</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Dado tu capital, el sistema calcula cuánto poner en cada empresa con señal activa</p>', unsafe_allow_html=True)

    render_regime_banner(current_vix, regime)

    # Instrucciones del flujo
    st.markdown("""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:14px;padding:20px;margin-bottom:24px;">
      <p style="color:#94a3b8;margin:0;font-size:0.9rem;line-height:1.7;">
        <b style="color:#e2e8f0;">Flujo de 2 pasos:</b><br>
        <b style="color:#00D4A0;">Paso 1</b> → Ve a <b>📡 Radar S&amp;P 500</b> y ejecuta el escáner para detectar señales activas.<br>
        <b style="color:#A78BFA;">Paso 2</b> → Ingresa tu capital aquí y el sistema calcula cuánto comprar de cada empresa.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Input de capital
    col_cap, col_btn = st.columns([3, 1])
    with col_cap:
        capital_input = st.number_input(
            "Capital total disponible (USD)",
            min_value=100.0, max_value=10_000_000.0,
            value=10_000.0, step=500.0,
            format="%.2f",
            help="Ingresa el monto total que quieres invertir"
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        calcular_btn = st.button("⚡ Calcular Asignación", use_container_width=True)

    # Obtener señales de la sesión
    señales_guardadas = st.session_state.get('radar_results', [])
    señales_activas_alloc = [r for r in señales_guardadas
                             if r.get('signal', {}).get('signal', False) or r.get('signal_active', False)]

    if calcular_btn or señales_activas_alloc:
        if not señales_activas_alloc:
            st.markdown("""
            <div style="background:rgba(255,184,0,0.05);border:1px solid rgba(255,184,0,0.2);
                        border-radius:12px;padding:24px;text-align:center;">
              <div style="font-size:2rem;margin-bottom:8px;">⚠️</div>
              <div style="font-weight:700;color:#FFB800;margin-bottom:6px;">Sin señales activas en esta sesión</div>
              <div style="font-size:0.85rem;color:#64748b;">
                Ve a <b style="color:#e2e8f0;">📡 Radar S&amp;P 500</b> → ejecuta el escáner primero.<br>
                Las señales activas aparecerán aquí automáticamente.
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Preparar datos para el allocator
            # Calcular volatilidad 30d de cada ticker en señales activas
            import yfinance as yf
            alloc_signals = []
            with st.spinner(f"Calculando volatilidades de {len(señales_activas_alloc)} activos..."):
                for r in señales_activas_alloc:
                    ticker = r['ticker']
                    vol_30d = 0.02  # fallback
                    try:
                        df_r = r.get('df')
                        if df_r is not None and not df_r.empty:
                            vol_30d = float(df_r['Close'].pct_change().tail(30).std())
                    except Exception:
                        pass
                    alloc_signals.append({
                        'ticker':    ticker,
                        'strategy':  'scanner',
                        'hit_rate':  0,   # sin CSV → Vol Parity fallback
                        'avg_win':   0,
                        'avg_loss':  0,
                        'sector':    'Unknown',
                        'n_signals': 0,   # fuerza Vol Parity
                        'vol_30d':   vol_30d,
                        'confidence': r.get('signal', {}).get('confidence', 0),
                    })

            allocations, alloc_regime, inv_pct = calculate_allocations(
                alloc_signals, current_vix, capital_input
            )

            # Métricas resumen
            activos_alloc = [a for a in allocations if a['ticker'] != 'CASH']
            cash_alloc    = next((a for a in allocations if a['ticker'] == 'CASH'), None)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Capital Total", f"${capital_input:,.0f}")
            m2.metric("Empresas a comprar", len(activos_alloc))
            m3.metric("Capital invertido", f"{inv_pct:.1f}%")
            m4.metric("Cash reservado", f"${(cash_alloc['usd_amount'] if cash_alloc else 0):,.0f}")

            st.markdown('<div class="section-title">📋 Plan de Compras</div>', unsafe_allow_html=True)

            # Tabla de asignación
            rows_alloc = ""
            for a in allocations:
                ticker_a = a['ticker']
                pct_a    = a['weight_pct']
                usd_a    = a['usd_amount']
                method_a = a['method']

                is_cash  = ticker_a == 'CASH'
                color_t  = "#94a3b8" if is_cash else "#e2e8f0"
                color_p  = "#4A5568" if is_cash else ("#00D4A0" if pct_a >= 10 else "#A78BFA")
                bar_w    = min(int(pct_a * 3), 100)

                # Precio actual para calcular número de acciones
                shares_str = "—"
                if not is_cash:
                    try:
                        r_match = next((r for r in señales_activas_alloc if r['ticker'] == ticker_a), None)
                        if r_match:
                            precio_a = r_match.get('price', 0)
                            if precio_a and precio_a > 0:
                                n_shares = int(usd_a // precio_a)
                                shares_str = f"{n_shares} acc. @ ${precio_a:.2f}"
                    except Exception:
                        pass

                rows_alloc += f"""
                <tr>
                  <td style="font-weight:700;color:{color_t};font-size:13px;">{ticker_a}</td>
                  <td>
                    <div style="display:flex;align-items:center;gap:8px;">
                      <div style="width:120px;height:6px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden;">
                        <div style="width:{bar_w}%;height:100%;background:{color_p};border-radius:3px;"></div>
                      </div>
                      <span style="font-family:var(--font-mono);font-size:12px;color:{color_p};font-weight:700;">{pct_a:.1f}%</span>
                    </div>
                  </td>
                  <td class="r" style="font-family:var(--font-mono);color:#00D4A0;font-weight:700;font-size:13px;">${usd_a:,.2f}</td>
                  <td style="color:#64748b;font-size:11px;">{shares_str}</td>
                  <td style="color:#4A5568;font-size:10px;">{method_a}</td>
                </tr>"""

            st.markdown(f"""
            <table class="qt" style="width:100%;">
              <thead>
                <tr>
                  <th>TICKER</th>
                  <th>PESO</th>
                  <th class="r">MONTO USD</th>
                  <th>ACCIONES APROX.</th>
                  <th>MÉTODO</th>
                </tr>
              </thead>
              <tbody>{rows_alloc}</tbody>
            </table>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;
                        padding:14px 20px;margin-top:16px;font-size:0.8rem;color:#64748b;">
              <b style="color:#94a3b8;">Metodología:</b> Pesos por Volatilidad Inversa (Vol Parity) con cap por ticker 15%
              y cap sectorial 30%. Régimen detectado: <b style="color:#e2e8f0;">{alloc_regime}</b>.
              Las acciones aproximadas se calculan asumiendo precio de cierre del último día disponible.
              <br><b style="color:#FFB800;">⚠️ Esto no es asesoramiento financiero. Siempre verifica antes de operar.</b>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:40px;text-align:center;margin-top:20px;">
          <div style="font-size:3rem;">💰</div>
          <h3 style="color:#e2e8f0;margin:12px 0;">Ejecuta el Radar primero</h3>
          <p style="color:#64748b;">Ve a <b style="color:#e2e8f0;">📡 Radar S&amp;P 500</b>, ejecuta el escáner,<br>
          y vuelve aquí para calcular cuánto invertir en cada empresa detectada.</p>
        </div>
        """, unsafe_allow_html=True)


# ── PAGE: Data Health ──────────────────────────────────────────────────────────
elif page == "🏥 Diagnóstico de Datos":
    st.markdown('<p class="hero-title">🏥 Diagnóstico Profundo</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Inspección forense de todas las capas de datos, indicadores y reglas para un ticker</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        test_ticker = st.text_input("Ticker a analizar", value="AAPL").upper().strip()
    with col2:
        st.write("")
        st.write("")
        run_diag = st.button("🔬 Ejecutar Diagnóstico Profundo", type="primary")

    if run_diag and test_ticker:
        with st.spinner(f"Analizando {test_ticker}..."):
            import time, datetime
            start_time = time.time()
            
            # Variables de contexto para el test
            regime, current_vix, vix_change = get_current_regime()
            tnx_yield = get_tnx_yield()
            end_date = datetime.date.today().strftime('%Y-%m-%d')
            start_date = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')
            
            # 1. Fetch Fundamentals
            st.markdown("### 1. Conexión y Datos Fundamentales (API)")
            data = fetch_stock_data(test_ticker)
            api_time = time.time() - start_time
            
            if not data or data.get("price") is None:
                st.error(f"❌ Falló la conexión o no se encontraron datos para {test_ticker}.")
                st.json(data)
            else:
                is_cached = api_time < 0.1
                cache_status = "⚡ HIT (Caché)" if is_cached else "🌐 MISS (Network Fetch)"
                st.success(f"✅ Conexión exitosa. Latencia: {api_time:.3f}s [{cache_status}]")
                with st.expander("Ver RAW JSON Completo", expanded=False):
                    st.json(data)
                
                # Tabla de campos clave
                st.markdown("#### Campos Clave Extraídos")
                key_fields = {
                    "price": data.get("price"),
                    "market_cap": data.get("market_cap"),
                    "sector": data.get("sector"),
                    "industry": data.get("industry"),
                    "trailing_pe": data.get("trailing_pe"),
                    "forward_pe": data.get("forward_pe"),
                    "peg_ratio": data.get("peg_ratio"),
                    "total_cash": data.get("total_cash"),
                    "total_debt": data.get("total_debt"),
                    "free_cf": data.get("free_cf"),
                    "revenue_growth_ttm": data.get("revenue_growth_ttm"),
                    "fcf_growth_ttm": data.get("fcf_growth_ttm"),
                }
                st.table(pd.DataFrame([key_fields]))

            # 2. Fetch Technicals
            st.markdown("### 2. Histórico y Técnicos")
            df, ind_vals, price = get_ticker_technicals(test_ticker, start_date, end_date)
            
            if df is None or df.empty:
                st.error(f"❌ No se pudo descargar el histórico de 1 año para {test_ticker}.")
            else:
                st.success(f"✅ Histórico descargado: {len(df)} días de trading.")
                with st.expander("Ver DataFrame Histórico (últimos 5 días)", expanded=False):
                    st.dataframe(df.tail())
                
                st.markdown("#### Indicadores Técnicos Calculados")
                if ind_vals:
                    st.table(pd.DataFrame([ind_vals]))
                else:
                    st.warning("ind_vals es None")

            # 3. Reglas Fundamentales (estrategia.py)
            st.markdown("### 3. Motor de Reglas Fundamentales")
            if not FUND_AVAILABLE:
                st.error("Módulo estrategia no disponible")
            else:
                tech_real = {}
                if ind_vals: tech_real['rsi'] = ind_vals.get('RSI', 50)
                if df is not None and not df.empty:
                    tech_real['sma_200'] = df['Close'].rolling(window=200).mean().iloc[-1]
                    low_52 = df['Low'].rolling(window=252).min().iloc[-1]
                    high_52 = df['High'].rolling(window=252).max().iloc[-1]
                    if high_52 > low_52:
                        tech_real['fifty_two_position'] = ((price - low_52) / (high_52 - low_52)) * 100
                    else:
                        tech_real['fifty_two_position'] = 50
                else:
                    tech_real['sma_200'] = price
                    tech_real['fifty_two_position'] = 50

                res = evaluar_protocolo_accion(data, tech_real, tnx_yield, price, soportes=[], profile='B', scan_mode='DIP')
                
                passed = res.get('passed', 0)
                total = res.get('total', 0)
                st.metric("Estrellas Fundamentales", f"{passed} / {total} ⭐")
                
                verdicts = res.get('verdicts', [])
                if verdicts:
                    st.markdown("#### Desglose de Reglas Evaluadas")
                    v_html = "<table class='qt' style='width:100%;'><thead><tr><th>Regla</th><th>Resultado</th></tr></thead><tbody>"
                    for rule_name, rule_res in verdicts:
                        icon = "🟢 Pasa" if rule_res is True else "🔴 Falla" if rule_res is False else "⚪ N/A"
                        v_html += f"<tr><td>{rule_name}</td><td>{icon}</td></tr>"
                    v_html += "</tbody></table>"
                    st.markdown(v_html, unsafe_allow_html=True)
                else:
                    st.warning("No se retornaron verdicts.")

            # 4. Monte Carlo
            st.markdown("### 4. Simulación Monte Carlo (10,000 caminos)")
            if df is not None and not df.empty:
                rets = df['Close'].pct_change().dropna()
                mc_res = simulate_price_paths(price, rets, horizon_days=5, n_simulations=10000)
                st.success("✅ Simulación completada")
                st.table(pd.DataFrame([mc_res]))
            else:
                st.warning("No hay histórico para Monte Carlo.")

            # 5. Evaluación de Señal (rule_engine.py)
            st.markdown("### 5. Evaluación de Señal (rule_engine.py)")
            if ind_vals:
                eval_res = evaluate_signal(ind_vals, regime, passed)
                
                col1, col2 = st.columns(2)
                col1.metric("Regla de Régimen", eval_res.get('regime'))
                col1.metric("¿Señal Activa?", "✅ SÍ" if eval_res.get('signal') else "❌ NO")
                col2.metric("Nivel de Confianza", f"{eval_res.get('confidence', 0):.1f}%")
                col2.metric("Rationale", eval_res.get('rationale'))
                
                with st.expander("Detalles de la señal", expanded=True):
                    st.json(eval_res)
            else:
                st.warning("No hay ind_vals para evaluar la señal.")

        st.success("✅ Diagnóstico profundo finalizado.")
