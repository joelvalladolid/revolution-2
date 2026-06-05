# ⚡ Francotirador de Liquidez — Trading Radar

Motor cuantitativo de selección y asignación de acciones S&P 500.
**VIX + Técnico + Fundamental (yahooquery/yfinance) + Monte Carlo + Allocator de Capital**

> Última actualización: 5 de junio de 2026

---

## 📋 Índice

1. [Resumen del Sistema](#resumen-del-sistema)
2. [Flujo Detallado de Ejecución](#-flujo-detallado-de-ejecución-paso-a-paso)
3. [Modos de Escaneo](#-modos-de-escaneo-momentum-vs-dip)
4. [Las 16 Estrellas Fundamentales](#-las-16-estrellas-fundamentales-sistema-de-calidad-corporativa)
5. [Fórmulas Matemáticas](#-fórmulas-matemáticas-de-cada-indicador)
6. [Simulación Monte Carlo](#-simulación-monte-carlo-gbm-bootstrap)
7. [Motor de Reglas por Régimen](#-motor-de-reglas-por-régimen-rule_enginepy)
8. [Asignación de Capital (Paso 2)](#-asignación-de-capital-paso-2)
9. [APIs y Comandos de Datos](#-apis-y-comandos-de-datos)
10. [Estructura del Proyecto](#-estructura-del-proyecto)
11. [Correr Localmente](#-correr-localmente)
12. [Páginas de la App](#-páginas-de-la-app)
13. [Aviso Legal](#️-aviso-legal)

---

## Resumen del Sistema

El sistema analiza las ~500 acciones del S&P 500 en tiempo real, pasándolas por un embudo de 5 filtros progresivos:

```
500 tickers S&P 500
  └→ Filtro 1: Datos suficientes (≥252 días de historia)
      └→ Filtro 2: Indicador primario (EMA200 discount por régimen)
          └→ Filtro 3: RSI saludable + Volumen >300K
              └→ Filtro 4: Calidad fundamental (≥N estrellas de 16 checks)
                  └→ Filtro 5: Monte Carlo (probabilidad estadística de ganancia)
                      └→ 🎯 SEÑAL ACTIVA (BUY / STRONG BUY)
```

---

## 🚀 Flujo Detallado de Ejecución (Paso a Paso)

### 1. Inicialización y Régimen de Mercado

#### 1.1 Petición VIX
```python
# API: yfinance
tk = yf.Ticker("^VIX")
vix = tk.history(period="3mo")  # 3 meses de datos del VIX
rt_price = tk.fast_info.last_price  # precio en tiempo real
```
Se descarga el histórico de 3 meses del índice de volatilidad VIX. Se limpia de valores NaN y se actualiza el último punto con el precio en tiempo real.

#### 1.2 Clasificación de Régimen (`lab/regime_detector.py`)
El VIX determina el "estado del mercado" usando estas reglas:

| Condición | Régimen | Significado |
|-----------|---------|-------------|
| VIX ≤ 20 | `CALM` | Mercado tranquilo, tendencia alcista |
| VIX > 20 | `SLOW_BEAR` | Mercado bajista lento, corrección |
| VIX > 40 **o** VIX subió >50% en 10 días | `FAST_CRASH` | Crash o pánico de mercado |

**Fórmula del cambio VIX a 10 días:**
```
vix_10d_change = ((VIX_hoy - VIX_hace10días) / VIX_hace10días) × 100
```

Cada régimen activa diferentes umbrales de filtrado técnico y fundamental.

#### 1.3 Petición Bonos del Tesoro (TNX)
```python
# API: yfinance
tnx = yf.Ticker("^TNX").history(period="5d")
tnx_yield = tnx['Close'].iloc[-1]  # Rendimiento actual del bono a 10 años
```
El yield del bono a 10 años (^TNX) se usa como tasa libre de riesgo en evaluaciones de PEG ratio y valuación.

#### 1.4 Impacto del TNX en los Filtros
Cuando `tnx_yield > 4.5%`:
- El límite de PEG ratio se endurece: Tech pasa de 2.5 → 1.5, otros de 1.5 → 1.0
- Esto refleja que en entornos de tasas altas, las valuaciones deben ser más conservadoras

---

### 2. Preparación del Escáner (S&P 500)

#### 2.1 Descarga de Tickers
```python
# API: requests + pandas (scraping Wikipedia)
url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
tables = pd.read_html(html, attrs={"id": "constituents"})
tickers = [str(t).replace(".", "-") for t in df["Symbol"].tolist()]
```
Se extraen los símbolos actuales del S&P 500 desde la tabla de Wikipedia. Si falla, se usa un fallback de ~500 tickers hardcodeados.

#### 2.2 Descarga Masiva de Precios
```python
# API: yfinance (bulk download)
bulk_data = fetch_history(tickers, start=start, end=end)
# Internamente: yf.download(tickers, start=start, group_by="ticker", progress=False)
```
Se descargan 2 años de datos OHLCV (Open, High, Low, Close, Volume) de los 500 tickers en un solo request batch. Esto evita hacer 500 peticiones individuales.

---

### 3. Fase de Procesamiento Multihilo

Se abre un pool de **5 hilos** (`ThreadPoolExecutor(max_workers=5)`) donde cada ticker pasa por el filtro `analyze_ticker_for_today`. Todo el pipeline se ejecuta por cada combinación de (ticker × modo de escaneo).

#### A. Primera Fase: Análisis Técnico (`get_ticker_technicals`)

- Si el ticker tiene **menos de 252 días** de historia → **SE DESCARTA** automáticamente
- Se calculan 8 indicadores técnicos (ver sección Fórmulas más abajo):

| Indicador | Variable | Descripción |
|-----------|----------|-------------|
| EMA 200 Discount | `EMA200_disc` | % de descuento respecto a la EMA de 200 periodos |
| Bollinger %B | `BB_pctB` | Posición relativa dentro de las bandas de Bollinger |
| Stochastic K | `Stoch_K` | Oscilador estocástico (momento de precio) |
| RSI | `RSI` | Índice de fuerza relativa |
| MFI | `MFI` | Money Flow Index (volumen + precio) |
| MACD Histogram | `MACD_hist` | Momento del MACD |
| Williams %R | `Williams_R` | Sobrecompra/sobreventa |
| ADX | `ADX` | Fuerza de la tendencia |

#### B. Segunda Fase: Filtros Primarios y de Volumen

**Modo MOMENTUM:**
- EMA200_disc entre -50% y 0% (precio **encima** de EMA200)
- RSI entre 40 y 75

**Modo DIP:**
- EMA200_disc ≥ umbral del régimen (precio **debajo** de EMA200)
  - CALM: ≥ 5%
  - SLOW_BEAR: ≥ 8%
  - FAST_CRASH: ≥ 12%
- RSI entre 35 y 65

**Volumen:** Promedio de 20 días > 300,000 acciones → si no, **SE DESCARTA**

*Nota:* Si no cumple estas condiciones primarias, el ticker se guarda solo como "Candidato a Vigilar" con un score de proximidad.

#### C. Tercera Fase: Análisis Fundamental (`get_fundamental_stars`)

Si superó el filtro técnico, se descargan los datos fundamentales de Yahoo Finance y se evalúan con `evaluar_protocolo_accion()`.

**Proceso de normalización de estrellas:**
```python
EXPECTED_CHECKS = 10
if total >= EXPECTED_CHECKS:
    normalized = passed           # datos suficientes — usar raw
elif total >= 3:
    normalized = round((passed / total) * EXPECTED_CHECKS)  # escalar proporcionalmente
else:
    normalized = 0                # datos insuficientes — no evaluar
```

**Estrellas mínimas requeridas por modo y régimen:**

| Modo | Régimen | Mínimo Estrellas |
|------|---------|-----------------|
| MOMENTUM | Cualquiera | 5 / 10 |
| DIP | CALM | 10 / 10 |
| DIP | SLOW_BEAR | 8 / 10 |
| DIP | FAST_CRASH | 10 / 10 |

Si no cumple el mínimo → **SE DESCARTA**

#### D. Cuarta Fase: Simulación Monte Carlo

Si pasó técnico y fundamental → se simula el futuro probabilístico (ver sección Monte Carlo más abajo).

**Requisitos Monte Carlo por modo y régimen:**

| Modo | Régimen | Prob. Mínima | P10 Mínimo | Target |
|------|---------|-------------|-----------|--------|
| MOMENTUM | CALM | 35% de P(>1%) | -8% | P(>1%) |
| MOMENTUM | NORMAL | 40% de P(>2%) | -7% | P(>2%) |
| MOMENTUM | SLOW_BEAR | 45% de P(>2%) | -5% | P(>2%) |
| DIP | Todos | 40% de P(>2%) | -6% | P(>2%) |

Si no cumple → **SE DESCARTA**

---

### 4. Impresión de Resultados

1. **Señales Activas:** Empresas que sobrevivieron TODOS los filtros → etiqueta **BUY** o **STRONG BUY**
2. **Próximamente (Vigilar):** Las que pasaron filtros parciales → etiqueta **VIGILAR** con score de proximidad
3. **Funnel:** Embudo visual mostrando cuántas pasaron cada fase

---

## 🎯 Modos de Escaneo: MOMENTUM vs DIP

El sistema selecciona automáticamente el modo de escaneo según el régimen de mercado:

| Régimen | Modos Activos | Lógica |
|---------|--------------|--------|
| CALM | MOMENTUM | En mercado tranquilo, busca acciones en tendencia alcista |
| SLOW_BEAR | MOMENTUM + DIP | En corrección, busca ambos: rebotes y tendencia |
| FAST_CRASH | DIP | En pánico, solo busca gangas profundas |

### Modo MOMENTUM
Busca acciones **por encima** de su EMA200 (en tendencia alcista saludable):
- Precio entre 0% y 50% por encima de EMA200
- RSI entre 40-75 (ni sobrevendido ni sobrecomprado)
- Omite 3 checks fundamentales (PEG, FCF, Euforia)
- Requiere solo 5 estrellas mínimas

### Modo DIP
Busca acciones con **descuento significativo** respecto a su EMA200 (rebote de calidad):
- Precio X% por debajo de EMA200 (X depende del régimen)
- RSI entre 35-65
- Evaluación fundamental completa (16 checks)
- Requiere 8-10 estrellas según régimen

---

## ⭐ Las 16 Estrellas Fundamentales (Sistema de Calidad Corporativa)

Cada estrella corresponde a un check de `estrategia.py → evaluar_protocolo_accion()`. Una acción puede obtener hasta **16 estrellas** en modo DIP (hasta **13 en modo MOMENTUM**, donde se omiten 3 checks).

Cada check retorna: `True` (pasa ✅), `False` (falla ❌), o `None` (dato no disponible, no cuenta ➖).

### Listado Completo de los 16 Checks

| # | Check | Fórmula / Criterio | Aplica en |
|---|-------|-------------------|-----------|
| 1 | **Negocio Comprensible** | `description != ""` (Yahoo devuelve descripción) | DIP + MOM |
| 2 | **Cash > Deuda** | `total_cash > total_debt` (o strategic si interest_coverage > 8 y D/E < 2) | DIP + MOM |
| 3 | **Rentabilidad** | `gross_margins > 0` **y** `profit_margins > 0` | DIP + MOM |
| 4 | **PEG Ratio Saludable** | `0 < PEG < 1.5` (2.5 para Tech) **y** `earnings_growth > 0`. Si TNX > 4.5%: Tech 1.5, otros 1.0. **Perfil B anula PEG.** | Solo DIP |
| 5 | **Revenue Creciendo** | `revenue_growth > 0` | DIP + MOM |
| 6 | **EPS Positivo y Mejorando** | `forward_eps > trailing_eps` **y** `forward_eps > 0`. REITs: siempre True. | DIP + MOM |
| 7 | **FCF Fuerte** | `fcf_yield > 3%` **o** (`fcf_growth > 0` y `free_cf > 0`) | Solo DIP |
| 8 | **No en Euforia Extrema** | **No** (`posición_52_semanas > 90%` **y** `RSI > 75`) | Solo DIP |
| 9 | **Apalancamiento Operativo Positivo** | `fcf_growth > revenue_growth` (flujo de caja crece más rápido que ingresos) | DIP + MOM |
| 10 | **Crecimiento de Earnings Positivo** | `earnings_growth > 0` | DIP + MOM |
| 11 | **Márgenes Saludables** | `profit_margins ≥ 40% × operating_margins` (si op > 0) | DIP + MOM |
| 12 | **No Dilución** | `shares_growth ≤ 2%` (crecimiento anual de acciones en circulación) | DIP + MOM |
| 13 | **Eficiencia de Capital** | `ROIC > 10%` (o ROE/ROA si no hay ROIC). ROIC = EBIT × (1 - tax_rate) / invested_capital | DIP + MOM |
| 14 | **Goodwill + Intangibles** | `(goodwill + intangibles) / total_assets < 40%` (60% para Tech, 65% para Financial) | DIP + MOM |
| 15 | **Accruals Ratio** | `(net_income - operating_cashflow) / total_assets < 0.07` | DIP + MOM |
| 16 | **Deuda Corto Plazo** | `short_term_debt / total_debt < 35%` | DIP + MOM |

### Exenciones Sectoriales
Algunos sectores tienen exenciones automáticas (check no penaliza ni bonifica):

| Sector | Checks Exentos |
|--------|---------------|
| Financial Services | Deuda/Equity |
| Real Estate | Deuda/Equity, FCF |
| Utilities | Deuda/Equity |

### Normalización
Los checks se evalúan y luego se normalizan a una escala de **/10 estrellas**:
- Si el total de checks con datos ≥ 10: se usa el conteo raw de `passed`
- Si el total ≥ 3 pero < 10: se escala proporcionalmente a /10 (`round(passed/total × 10)`)
- Si el total < 3: se marca como 0 (datos insuficientes)

**Ejemplo:** Si Yahoo devuelve datos para solo 8 de los 16 checks, y 5 pasan:
```
normalized = round(5/8 × 10) = round(6.25) = 6 estrellas
```

---

## 📐 Fórmulas Matemáticas de Cada Indicador

### EMA 200 Discount (`ema_discount`)
Mide cuánto está el precio por debajo (positivo) o por encima (negativo) de la EMA de 200 períodos:

```
EMA_200 = EMA exponencial de Close con span=200
EMA200_disc = ((EMA_200 - Close) / EMA_200) × 100
```
- Valor positivo → precio DEBAJO de EMA (potencial compra DIP)
- Valor negativo → precio ENCIMA de EMA (potencial MOMENTUM)

### Bollinger %B (`bollinger_pctB`)
Posición del precio dentro de las bandas de Bollinger (20 períodos, 2 desviaciones estándar):

```
SMA_20 = Media móvil simple de Close (20 periodos)
σ = Desviación estándar de Close (20 periodos)
Upper = SMA_20 + (2 × σ)
Lower = SMA_20 - (2 × σ)
%B = (Close - Lower) / (Upper - Lower)
```
- %B < 0.3 → precio cerca de banda inferior (sobreventa)
- %B > 0.7 → precio cerca de banda superior (sobrecompra)

### RSI - Relative Strength Index (`rsi`)
```
Δ = Close[t] - Close[t-1]
Gain_avg = Media móvil de ganancias (14 periodos)
Loss_avg = Media móvil de pérdidas (14 periodos)
RS = Gain_avg / Loss_avg
RSI = 100 - (100 / (1 + RS))
```
- RSI < 30 → sobrevendido
- RSI > 70 → sobrecomprado

### Stochastic K (`stochastic_k`)
```
Lowest_Low = Mínimo de Low en 14 periodos
Highest_High = Máximo de High en 14 periodos
Raw_K = 100 × ((Close - Lowest_Low) / (Highest_High - Lowest_Low))
Stoch_K = Media móvil de Raw_K (3 periodos, suavizado)
```
- Stoch_K < 20 → sobrevendido extremo
- Stoch_K < 35 → zona de interés para DIP

### MFI - Money Flow Index (`mfi`)
```
Typical_Price = (High + Low + Close) / 3
Raw_Money_Flow = Typical_Price × Volume
Positive_MF = Suma de Raw_MF cuando TP sube (14 periodos)
Negative_MF = Suma de Raw_MF cuando TP baja (14 periodos)
MFI = 100 - (100 / (1 + Positive_MF / Negative_MF))
```

### MACD Histogram (`macd_hist`)
```
EMA_fast = EMA de Close (span=12)
EMA_slow = EMA de Close (span=26)
MACD_line = EMA_fast - EMA_slow
Signal_line = EMA de MACD_line (span=9)
MACD_hist = MACD_line - Signal_line
```
- MACD_hist > 0 → momentum alcista

### Williams %R (`williams_r`)
```
Highest_High = Máximo de High en 14 periodos
Lowest_Low = Mínimo de Low en 14 periodos
Williams_%R = -100 × ((Highest_High - Close) / (Highest_High - Lowest_Low))
```
- %R ≤ -80 → sobrevendido

### ADX - Average Directional Index (`adx`)
```
+DM = High[t] - High[t-1] (si > 0, sino 0)
-DM = Low[t-1] - Low[t] (si > 0, sino 0)
TR = max(High-Low, |High-Close[t-1]|, |Low-Close[t-1]|)
ATR = EMA de TR (alpha=1/14)
+DI = 100 × (EMA de +DM / ATR)
-DI = 100 × |EMA de -DM / ATR|
DX = (|+DI - -DI| / |+DI + -DI|) × 100
ADX = EMA de DX (alpha=1/14)
```
- ADX > 25 → tendencia fuerte (alcista o bajista)

---

## 📊 Simulación Monte Carlo (GBM Bootstrap)

### Modelo
Se usa **Bootstrap Monte Carlo** (no GBM paramétrico clásico) para capturar fat tails reales:

```python
# 1. Calcular retornos logarítmicos históricos (últimos 252 días)
log_returns = np.log1p(historical_returns)

# 2. Muestrear con reemplazo: 5 días × 10,000 simulaciones
sampled = np.random.choice(log_returns, size=(5, 10_000), replace=True)

# 3. Acumular retornos por camino
cumulative = np.sum(sampled, axis=0)

# 4. Calcular precios finales
final_prices = current_price × exp(cumulative)

# 5. Extraer distribución
returns = (final_prices - current_price) / current_price
```

### Métricas de Salida

| Métrica | Descripción |
|---------|-------------|
| `prob_positive` | P(retorno > 0%) — probabilidad de no perder |
| `prob_gt_1pct` | P(retorno > 1%) — probabilidad de ganar >1% |
| `prob_gt_2pct` | P(retorno > 2%) — probabilidad de ganar >2% |
| `prob_gt_5pct` | P(retorno > 5%) — probabilidad de ganar >5% |
| `p10` | Percentil 10 del retorno (escenario pesimista) |
| `p50` | Percentil 50 del retorno (escenario base, mediana) |
| `p90` | Percentil 90 del retorno (escenario optimista) |
| `sigma_anual` | Volatilidad anualizada = σ_diaria × √252 |

### Ventajas del Bootstrap vs GBM Clásico
- Captura colas gruesas (fat tails) y asimetrías reales del mercado
- No asume retornos normales
- Preserva autocorrelaciones del régimen actual

---

## 🔧 Motor de Reglas por Régimen (`rule_engine.py`)

### Tabla de Reglas

| Régimen | Indicador Primario | Umbral | Secundarios | Señales Mín. | Stars Mín. | Fundamental |
|---------|-------------------|--------|-------------|-------------|-----------|-------------|
| CALM | EMA200_disc | ≥ 5% | Ninguno | 1 | 10 | Requerido |
| SLOW_BEAR | EMA200_disc | ≥ 8% | BB_%B ≤ 0.3, Stoch_K ≤ 35 | 2 | 8 | Requerido |
| FAST_CRASH | EMA200_disc | ≥ 12% | Ninguno | 1 | 10 | Requerido |

### Cálculo de Confidence Score
```
score = 0
if indicador_primario_disparado: score += 50
if 1+ secundarios disparados: score += 25
if 2+ secundarios disparados: score += 15
if 3+ secundarios disparados: score += 10
if fundamental_ok: score += 20
if régimen == SLOW_BEAR: score += 10  (bonus: edge histórico +6.85pp)

confidence = min(100, (score / 130) × 100)
```

### Clasificación de Señal

| Confidence | Etiqueta | Color |
|-----------|----------|-------|
| ≥ 75 | STRONG BUY | Verde |
| ≥ 50 | BUY | Amarillo |
| < 50 | VIGILAR | Azul |

---

## 💰 Asignación de Capital (Paso 2)

Después de que el Radar detecta señales activas, el usuario ingresa su capital total y el sistema calcula cuánto invertir en cada empresa.

### Metodología: Volatility Parity (Paridad de Volatilidad Inversa)

```python
# Para cada señal activa:
vol_30d = df['Close'].pct_change().tail(30).std()  # volatilidad 30 días
raw_weight = 1.0 / vol_30d  # peso inverso a volatilidad

# Normalizar a 100%
weights = {ticker: raw / sum(all_raw) for ticker, raw in raw_weights.items()}
```

**Cascada de métodos (fallback):**
1. **Kelly Fraccional (25%):** Si hay ≥30 trades históricos con avg_win > 0
2. **Vol Parity:** Si hay datos de volatilidad (caso normal del scanner)
3. **Equal Weight:** Si no hay datos de volatilidad

### Caps y Restricciones

| Restricción | CALM | SLOW_BEAR | FAST_CRASH |
|------------|------|-----------|------------|
| Cap por ticker | 15% | 10% | 15% |
| Cap sectorial | 30% | 30% | 30% |
| Multiplicador régimen | 100% | 100% | 50% (mitad al cash) |

El exceso por cap se redistribuye proporcionalmente entre los activos no limitados.

---

## 🌐 APIs y Comandos de Datos

### Fuentes de Datos

| Fuente | Librería | Datos | Uso |
|--------|---------|-------|-----|
| **Yahoo Finance** (fundamentales) | `yahooquery` (Plan A) | Balance, Income, CashFlow, KeyStats | 16 checks fundamentales, ROIC, TTM |
| **Yahoo Finance** (fallback) | `yfinance` (Plan B) | `.info`, `.financials`, `.balance_sheet`, `.cashflow` | Mismos datos si yahooquery falla |
| **Yahoo Finance** (precios) | `yfinance` | `.history()`, `yf.download()` | OHLCV histórico, VIX, TNX |
| **Wikipedia** | `requests` + `pandas` | Tabla HTML del S&P 500 | Lista de 500 tickers |

### Comandos API Clave (yahooquery — Plan A)

```python
from yahooquery import Ticker
yq = Ticker("AAPL", asynchronous=False, validate=True, session=resilient_session)

# Módulos principales usados:
yq.financial_data      # currentPrice, margins, cashflow, debtToEquity, ROE, ROA...
yq.key_stats           # PE, PEG, forwardPE, priceToBook, enterpriseValue, beta...
yq.summary_detail      # marketCap, trailingPE, dividendRate, 52-week range...
yq.asset_profile       # sector, industry, description (longBusinessSummary)...
yq.quote_type          # quoteType (EQUITY, ETF, INDEX...)

# Statements (DataFrames):
yq.balance_sheet(frequency="annual")    # TotalAssets, Goodwill, StockholdersEquity...
yq.income_statement(frequency="annual") # OperatingIncome, InterestExpense, TaxProvision...
yq.income_statement(frequency="quarterly") # Para cálculos TTM (Trailing 12 Months)
yq.cash_flow(frequency="quarterly")     # OperatingCashFlow, CapitalExpenditure (TTM)
```

### Comandos API Clave (yfinance — Plan B / Precios)

```python
import yfinance as yf

# Precio individual con tiempo real:
tk = yf.Ticker("AAPL")
tk.history(period="2y")     # DataFrame OHLCV
tk.fast_info.last_price     # precio en tiempo real
tk.info                     # dict con fundamentales (fallback)

# Descarga masiva (scanner):
yf.download(tickers_list, start="2024-01-01", group_by="ticker", progress=False)
# Retorna DataFrame multi-ticker con columnas agrupadas por ticker

# Índices:
yf.Ticker("^VIX").history(period="3mo")    # Volatilidad VIX
yf.Ticker("^TNX").history(period="5d")     # Yield bonos 10 años
```

### Cálculos TTM (Trailing Twelve Months)

Los crecimientos de Revenue y FCF se calculan con datos trimestrales para mayor precisión:

```python
# Revenue Growth TTM:
rev_ttm_now = sum(revenue de últimos 4 trimestres)
rev_ttm_prev = sum(revenue de trimestres 5-8)  # o último anual
rev_growth_ttm = (rev_ttm_now / rev_ttm_prev) - 1

# FCF TTM:
ocf_ttm = sum(Operating Cash Flow de últimos 4 trimestres)
capex_ttm = sum(|CapEx| de últimos 4 trimestres)  # abs() siempre
fcf_ttm = ocf_ttm - capex_ttm

# ROIC (Return on Invested Capital):
real_tax = TaxProvision / PretaxIncome  # clamped 0-50%
invested_capital = StockholdersEquity + (TotalDebt - TotalCash)
ROIC = (OperatingIncome × (1 - real_tax)) / invested_capital
```

### Sesión HTTP Resiliente

Todas las peticiones a Yahoo usan una sesión con reintentos automáticos:

```python
retries = Retry(
    total=3,                                    # 3 reintentos
    backoff_factor=1.5,                         # espera 1.5s, 3s, 4.5s
    status_forcelist=[401, 429, 500, 502, 503, 504],  # errores HTTP
)
session.headers['User-Agent'] = 'Mozilla/5.0 ...'  # evitar bloqueos
```

---

## 📁 Estructura del Proyecto

```
revolution-2-main/
├── app.py                          # App principal Streamlit (1855 líneas)
│                                   # - UI completa con CSS cuántico
│                                   # - Scanner S&P 500 con threading
│                                   # - Análisis individual
│                                   # - Correlación, VIX, Allocator
│
├── estrategia.py                   # Motor de 16 checks fundamentales
│                                   # - evaluar_protocolo_accion()
│                                   # - Exenciones sectoriales
│                                   # - Checks anti-trampa de valor
│
├── data_fetcher.py                 # Datos financieros (yahooquery + yfinance)
│                                   # - fetch_stock_data() (individual)
│                                   # - _yq_fundamentals() (yahooquery)
│                                   # - _calcular_metricas_ttm_yq() (TTM)
│                                   # - search_ticker_by_name()
│                                   # - calculate_technicals()
│
├── lab_tickers.py                  # Lista S&P 500 desde Wikipedia
│                                   # - fetch_sp500_tickers_wiki_v2()
│                                   # - Fallback hardcodeado de ~500 tickers
│
├── requirements.txt                # Dependencias del proyecto
├── README.md                       # Este archivo
├── INSTRUCCIONES.md                # Notas internas
│
├── lab/
│   ├── regime_detector.py          # VIX → régimen (CALM/SLOW_BEAR/FAST_CRASH)
│   ├── indicators.py               # 8 indicadores técnicos (RSI, EMA, BB, etc.)
│   ├── rule_engine.py              # Motor de reglas por régimen + confidence
│   ├── monte_carlo.py              # Bootstrap Monte Carlo (10K trayectorias)
│   ├── daily_allocator.py          # Vol Parity + Kelly + caps sectoriales
│   ├── score_engine.py             # Normalizador de scores
│   ├── sltp_engine.py              # Motor Stop-Loss / Take-Profit
│   ├── backtest_combined.py        # Backtesting combinado
│   ├── kelly_optimizer.py          # Optimizador Kelly
│   ├── parallel_engine.py          # Motor de ejecución paralela
│   ├── strategy_tournament.py      # Torneo de estrategias
│   ├── tournament_short.py         # Torneo corto
│   └── debug_funnel.py             # Debug del embudo
│
├── data/
│   └── fetcher.py                  # Descarga OHLCV con yf.download()
│                                   # - fetch_history() bulk + individual
│
├── tests/
│   ├── test_scan.py                # Test del scanner
│   ├── test_score.py               # Test de scoring
│   ├── test_fase2.py               # Test fase 2
│   ├── test_api_diagnostic.py      # Diagnóstico de API
│   ├── test_cat.py                 # Test categórico
│   ├── debug_fails.py              # Debug de fallos
│   ├── quick_backtest.py           # Backtest rápido
│   ├── scan_terminal.py            # Scanner en terminal
│   ├── sim_daytrading.py           # Simulación daytrading
│   ├── sim_daytrading_1y.py        # Simulación daytrading 1 año
│   └── sim_hold5d_1y.py            # Simulación hold 5 días 1 año
│
├── test_verify_all.py              # Test automático de todos los módulos
├── test_fundamental_pipeline.py    # Test del pipeline fundamental
│
└── logs/                           # Logs y resultados de ejecución
```

---

## 💻 Correr Localmente

### Requisitos
- Python 3.10+
- Conexión a internet (para APIs de Yahoo Finance y Wikipedia)

### Instalación
```bash
pip install -r requirements.txt
```

### Dependencias
| Paquete | Versión | Uso |
|---------|---------|-----|
| `streamlit` | ≥1.32.0 | Framework web UI |
| `pandas` | ≥2.0.0 | DataFrames y análisis |
| `numpy` | ≥1.26.0 | Cálculos numéricos y Monte Carlo |
| `yfinance` | ≥0.2.40 | Precios y datos de mercado |
| `yahooquery` | ≥2.3.7 | Fundamentales contables (Plan A) |
| `plotly` | ≥5.20.0 | Gráficos interactivos (VIX, Correlación) |
| `requests` | ≥2.31.0 | HTTP requests (Wikipedia, sesión resiliente) |
| `lxml` | ≥5.0.0 | Parser HTML para Wikipedia |
| `pandas-ta` | ≥0.3.14b | Indicadores técnicos (solo backtesting) |
| `scipy` | ≥1.12.0 | Detección de soportes/resistencias |

### Ejecución
```bash
streamlit run app.py
```
La app se abrirá en `http://localhost:8501`.

---

## 📊 Páginas de la App

| Página | Descripción |
|--------|-------------|
| 📡 **Radar S&P 500** | Scanner completo: descarga 500 tickers, aplica los 5 filtros en 5 hilos paralelos, muestra funnel y tabla de resultados |
| 💰 **Paso 2 — Cuánto Comprar** | Ingresa capital → calcula asignación por Vol Parity con caps por ticker y sector |
| 🔍 **Análisis Individual** | Evalúa un ticker específico: técnico + fundamental + Monte Carlo con desglose completo |
| 📊 **Régimen de Mercado** | VIX histórico 90 días con gráfico color-coded por régimen y tabla de últimos 30 días |
| 🔗 **Correlación** | Matriz de covarianza triangular inferior de 30 blue-chips (heatmap Plotly) |
| ⚙️ **Configuración** | Ajustes del sistema (API keys, umbrales VIX) — placeholder |
| 🏥 **Diagnóstico de Datos** | Inspección forense de todas las capas: API, técnicos, fundamentales, Monte Carlo, señal |

---

## ⚠️ Aviso Legal

Este sistema es **exclusivamente educativo y de investigación**. No constituye asesoramiento financiero de ningún tipo. Las decisiones de inversión son responsabilidad exclusiva del usuario.

- Los datos provienen de Yahoo Finance y pueden tener retrasos o errores
- Las simulaciones Monte Carlo no predicen el futuro — modelan probabilidades basadas en datos históricos
- El rendimiento pasado no garantiza resultados futuros
- Siempre verifica la información con fuentes independientes antes de operar
