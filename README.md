# ⚡ Francotirador de Liquidez — Trading Radar

Motor cuantitativo de selección y asignación de acciones S&P 500.
**VIX + Técnico + Fundamental (yahooquery/yfinance) + Allocator de Capital**

## 🚀 Flujo de 2 Pasos

### Paso 1 — ¿Qué comprar? (`📡 Radar S&P 500`)
- Escanea los ~503 tickers del S&P 500
- Filtra por régimen VIX (CALM / SLOW_BEAR / FAST_CRASH)
- Aplica señales técnicas (EMA200, BB, Stoch, RSI)
- Evalúa calidad fundamental real (16 checks con yahooquery + yfinance)
- Rankea por Confidence Score

### Paso 2 — ¿Cuánto comprar? (`💰 Paso 2 — Cuánto Comprar`)
- Ingresa tu capital total (ej: $10,000)
- El sistema calcula pesos por **Volatilidad Inversa (Vol Parity)**
- Cap por ticker: 15% | Cap sectorial: 30%
- Ajuste por régimen VIX (FAST_CRASH reduce exposición al 50%)
- Resultado: tabla con `TICKER | % | $USD | N° acciones`

## 🖥️ Correr en Streamlit Cloud

1. Sube `REVOLUTION_ENTREGABLE/` como repositorio GitHub
2. En [share.streamlit.io](https://share.streamlit.io), apunta a `app.py`
3. ¡Listo!

## 💻 Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📁 Estructura

```
REVOLUTION_ENTREGABLE/
├── app.py                  # App principal Streamlit
├── estrategia.py           # Motor de 16 checks fundamentales
├── data_fetcher.py         # Datos financieros (yahooquery + yfinance)
├── lab_tickers.py          # Lista S&P 500 desde Wikipedia
├── requirements.txt
├── README.md
├── .gitignore
├── lab/
│   ├── regime_detector.py  # Clasificador VIX → régimen
│   ├── indicators.py       # Indicadores técnicos
│   ├── rule_engine.py      # Motor de reglas por régimen
│   ├── monte_carlo.py      # Simulación GBM 10k trayectorias
│   └── daily_allocator.py  # Asignación de capital (Paso 2)
└── data/
    └── fetcher.py          # Descarga OHLCV con yfinance
```

## 📊 Páginas de la App

| Página | Descripción |
|--------|-------------|
| 📡 Radar S&P 500 | Scanner completo con filtro técnico + fundamental |
| 💰 Paso 2 — Cuánto Comprar | Asignación de capital óptima |
| 🔍 Análisis Individual | Análisis ticker + Monte Carlo 5 días |
| 📊 Régimen de Mercado | VIX histórico 90 días |
| 🔗 Correlación | Matriz de covarianza Top 30 S&P 500 |

## ⚠️ Aviso Legal

Este sistema es educativo. No es asesoramiento financiero.
