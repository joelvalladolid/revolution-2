"""Módulo para obtener datos financieros desde Yahoo Finance.

Arquitectura híbrida:
  Capa A — yahooquery : fundamentales contables (Income, Balance, CF, KeyStats)
  Capa B — yfinance   : histórico de precios → técnicos (VWAP, SMA, RSI, gráfico)

Compatibilidad garantizada: el dict de salida tiene las MISMAS CLAVES de siempre,
por lo que estrategia.py no requiere ningún cambio.
"""
import yfinance as yf
import numpy as np
import pandas as pd
import math
import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Cambiar a True para diagnóstico de cálculos TTM
TTM_DEBUG = False

# ── Constante de tamaño de mini-lote para fetch_batch_fundamentals ────────────
RADAR_MINI_BATCH_SIZE = 50

def _create_resilient_session() -> requests.Session:
    """Crea una sesión HTTP con reintentos y backoff para yahooquery."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[401, 429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return session

# Sesión global reutilizable
_RESILIENT_SESSION = None

def _get_session() -> requests.Session:
    """Retorna la sesión resiliente global (lazy init)."""
    global _RESILIENT_SESSION
    if _RESILIENT_SESSION is None:
        _RESILIENT_SESSION = _create_resilient_session()
    return _RESILIENT_SESSION


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_get(mapping, key, default=None):
    """Extrae un valor de un dict/objeto sin lanzar excepciones."""
    try:
        val = mapping.get(key, default)
        # yahooquery devuelve el string "No fundamental data found for ..."
        # cuando un ticker es inválido → tratarlo como default
        if isinstance(val, str) and val.lower().startswith("no "):
            return default
        return val
    except Exception:
        return default


def _normalize_for_yq(ticker: str) -> str:
    """
    yahooquery usa BRK-B donde yfinance usa BRK.B.
    Convierte el punto a guión para tickers de clase (no índices ni cripto).
    """
    if "." in ticker and not ticker.startswith("^"):
        return ticker.replace(".", "-")
    return ticker


def _find_row(df, keyword_groups):
    """
    Busca en el index de un DataFrame la primera fila cuyo nombre
    contenga las palabras clave indicadas (case-insensitive).
    keyword_groups: lista de listas, cada sublista = conjunto de palabras que deben
    aparecer TODAS en el nombre. Retorna la Serie dropna() o None.
    """
    if df is None or df.empty:
        return None
    idx_lower = [str(i).lower() for i in df.index]
    for kws in keyword_groups:
        if isinstance(kws, str):
            kws = [kws]
        for i, name in enumerate(idx_lower):
            if all(k.lower() in name for k in kws):
                return df.iloc[i].dropna()
    return None


def _clean_val(val):
    """Limpia np.nan / pd.NA a None para evitar fallos lógicos en Python."""
    if val is None:
        return None
    import pandas as pd
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CAPA A — FUNDAMENTALES VÍA yahooquery
# ─────────────────────────────────────────────────────────────────────────────

def _yq_fundamentals(ticker_symbol: str, yq_obj=None) -> dict:
    """
    Descarga fundamentales contables de un ticker usando yahooquery.
    Si se pasa un objeto yahooquery ya construido (yq_obj), lo reutiliza.
    Retorna dict con todas las claves de fundamentales, o {} si falla.
    """
    try:
        from yahooquery import Ticker
        yq = yq_obj if yq_obj is not None else Ticker(
            _normalize_for_yq(ticker_symbol), asynchronous=False, validate=True,
            session=_get_session()
        )
        yq_ticker = _normalize_for_yq(ticker_symbol)

        # ── Módulos de alta densidad (dicts planos) ───────────────────────
        fd = _safe_get(yq.financial_data,  yq_ticker, {}) or {}
        ks = _safe_get(yq.key_stats,       yq_ticker, {}) or {}
        sd = _safe_get(yq.summary_detail,  yq_ticker, {}) or {}
        ap = _safe_get(yq.asset_profile,   yq_ticker, {}) or {}
        qt = _safe_get(yq.quote_type,      yq_ticker, {}) or {}

        # Si yahooquery devuelve error string para este ticker → abortar
        if isinstance(fd, str) or isinstance(ks, str):
            return {}

        # ── Dict base de fundamentales ────────────────────────────────────
        data = {
            "name":             fd.get("shortName") or ap.get("longName", ticker_symbol),
            "long_name":        ap.get("longName", ""),
            "sector":           ap.get("sector", "N/A"),
            "industry":         ap.get("industry", "N/A"),
            "description":      ap.get("longBusinessSummary", ""),
            "price":            fd.get("currentPrice") or sd.get("regularMarketPrice"),
            "market_cap":       sd.get("marketCap"),
            "enterprise_value": ks.get("enterpriseValue"),
            "shares_out":       ks.get("sharesOutstanding"),
            "fifty_two_high":   sd.get("fiftyTwoWeekHigh"),
            "fifty_two_low":    sd.get("fiftyTwoWeekLow"),
            "avg_volume":       sd.get("averageVolume"),
            "beta":             ks.get("beta"),
            "dividend_rate":    sd.get("dividendRate"),
            "payout_ratio":     sd.get("payoutRatio"),
            "trailing_pe":      sd.get("trailingPE"),
            "forward_pe":       ks.get("forwardPE"),
            "peg_ratio":        ks.get("pegRatio"),
            "price_to_book":    ks.get("priceToBook"),
            "price_to_sales":   sd.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda":     ks.get("enterpriseToEbitda"),
            "ev_to_revenue":    ks.get("enterpriseToRevenue"),
            "revenue":          fd.get("totalRevenue"),
            "revenue_growth":   fd.get("revenueGrowth"),
            "gross_margins":    fd.get("grossMargins"),
            "operating_margins":fd.get("operatingMargins"),
            "profit_margins":   fd.get("profitMargins"),
            "roe":              fd.get("returnOnEquity"),
            "roa":              fd.get("returnOnAssets"),
            "roic":             None,  # calculado abajo (BUG B1 fix)
            "trailing_eps":     ks.get("trailingEps"),
            "forward_eps":      ks.get("forwardEps"),
            "earnings_growth":  fd.get("earningsGrowth"),
            "net_income":       fd.get("netIncomeToCommon"),
            "total_cash":       fd.get("totalCash"),
            "total_debt":       fd.get("totalDebt"),
            "debt_to_equity":   fd.get("debtToEquity"),
            "current_ratio":    fd.get("currentRatio"),
            "quick_ratio":      fd.get("quickRatio"),
            "operating_cf":     fd.get("operatingCashflow"),
            "free_cf":          fd.get("freeCashflow"),
            "ebitda":           fd.get("ebitda"),
            "target_high":      fd.get("targetHighPrice"),
            "target_low":       fd.get("targetLowPrice"),
            "target_mean":      fd.get("targetMeanPrice"),
            "target_median":    fd.get("targetMedianPrice"),
            "recommendation":   fd.get("recommendationKey"),
            "num_analysts":     fd.get("numberOfAnalystOpinions"),
            "quote_type":       qt.get("quoteType", "").upper(),
            # campos que se rellenan después
            "total_assets":     None,
            "goodwill":         None,
            "intangible_assets":None,
            "short_term_debt":  None,
            "interest_expense": None,  # BUG B4 fix: siempre extraído
            "shares_growth":    None,
        }

        # ── Balance Sheet (anual) ─────────────────────────────────────────
        try:
            bs_df = yq.balance_sheet(frequency="annual")
            if bs_df is not None and not (isinstance(bs_df, dict) and not bs_df):
                import pandas as pd
                if isinstance(bs_df, pd.DataFrame) and not bs_df.empty:
                    if bs_df.index.names and "symbol" in bs_df.index.names:
                        bs_df = bs_df.reset_index()
                    # multi-ticker: filtrar por symbol
                    if "symbol" in bs_df.columns:
                        bs_df = bs_df[bs_df["symbol"] == yq_ticker]
                    if not bs_df.empty:
                        bs_latest = bs_df.sort_values("asOfDate").iloc[-1]
                    data["total_assets"] = _clean_val(bs_latest.get("TotalAssets"))

                    # A2 FIX: goodwill — fallback para empresas sin desglose separado
                    goodwill = _clean_val(bs_latest.get("Goodwill"))
                    if goodwill is None:
                        goodwill = _clean_val(bs_latest.get("GoodwillAndOtherIntangibleAssets"))
                    data["goodwill"] = goodwill if goodwill is not None else 0

                    # A2 FIX: intangibles — alias alternativo
                    intangibles = _clean_val(bs_latest.get("OtherIntangibleAssets"))
                    if intangibles is None:
                        intangibles = _clean_val(bs_latest.get("OtherIntangibles"))
                    if intangibles is None:
                        intangibles = _clean_val(bs_latest.get("DefinedPensionBenefit"))
                    data["intangible_assets"] = intangibles if intangibles is not None else 0

                    # A2 FIX: short_term_debt — fallback en cadena para bancos/REITs/extranjeras
                    st_debt = _clean_val(bs_latest.get("CurrentDebt"))
                    if st_debt is None:
                        st_debt = _clean_val(bs_latest.get("CurrentBorrowings"))
                    if st_debt is None:
                        st_debt = _clean_val(bs_latest.get("ShortTermBorrowings"))
                    if st_debt is None:
                        st_debt = _clean_val(bs_latest.get("CurrentDebtAndCapitalLeaseObligation"))
                    if st_debt is None:
                        st_debt = _clean_val(bs_latest.get("CurrentDeferredLiabilities"))

                    data["short_term_debt"] = st_debt if st_debt is not None else 0

                    # A2 FIX: equity — fallback para REITs/MLPs que usan TotalEquityGrossMinorityInterest
                    _equity = _clean_val(bs_latest.get("StockholdersEquity"))
                    if _equity is None:
                        _equity = _clean_val(bs_latest.get("TotalEquityGrossMinorityInterest"))
                    if _equity is None:
                        _equity = _clean_val(bs_latest.get("CommonStockEquity"))
                    _net_debt = (
                        (data.get("total_debt") or 0)
                        - (data.get("total_cash") or 0)
                    )
                    _invested_capital = (_equity or 0) + _net_debt
                    data["_equity"]           = _equity
                    data["_invested_capital"] = _invested_capital
        except Exception:
            pass

        # ── Income Statement anual (interest_expense, shares_growth, ROIC) ─
        # BUG B4 FIX: interest_expense se extrae SIEMPRE, no solo cuando cash<debt
        # BUG B1 FIX: ROIC usando OperatingIncome real + tasa de impuesto real
        try:
            inc_df = yq.income_statement(frequency="annual", trailing=False)
            if inc_df is not None and not (isinstance(inc_df, dict) and not inc_df):
                import pandas as pd
                if isinstance(inc_df, pd.DataFrame) and not inc_df.empty:
                    if inc_df.index.names and "symbol" in inc_df.index.names:
                        inc_df = inc_df.reset_index()
                    if "symbol" in inc_df.columns:
                        inc_df = inc_df[inc_df["symbol"] == yq_ticker]
                    if not inc_df.empty:
                        inc_sorted = inc_df.sort_values("asOfDate")
                        latest_inc = inc_sorted.iloc[-1]

                    # Interest expense (BUG B4 fix)
                    ie = _clean_val(latest_inc.get("InterestExpense"))
                    if ie is not None:
                        try:
                            data["interest_expense"] = abs(float(ie))
                        except (TypeError, ValueError):
                            pass

                    # Shares growth (dilución)
                    if len(inc_sorted) >= 2:
                        recent_s = _clean_val(latest_inc.get("DilutedAverageShares"))
                        prev_s   = _clean_val(inc_sorted.iloc[-2].get("DilutedAverageShares"))
                        if recent_s and prev_s and prev_s > 0:
                            try:
                                data["shares_growth"] = (
                                    float(recent_s) / float(prev_s)
                                ) - 1
                            except (TypeError, ValueError):
                                pass

                    # Net Income (para Accruals Ratio)
                    ni = _clean_val(latest_inc.get("NetIncomeCommonStockholders")) or _clean_val(latest_inc.get("NetIncome"))
                    if ni is not None:
                        data["net_income"] = float(ni)

                    # ROIC real (BUG B1 fix — sin proxies, C4)
                    ebit = _clean_val(latest_inc.get("OperatingIncome"))
                    tax_provision = _clean_val(latest_inc.get("TaxProvision"))
                    pretax_income = _clean_val(latest_inc.get("PretaxIncome"))
                    invested_cap  = data.get("_invested_capital")

                    if (
                        ebit is not None
                        and tax_provision is not None
                        and pretax_income is not None
                        and pretax_income != 0
                        and invested_cap is not None
                        and invested_cap > 0
                    ):
                        try:
                            real_tax = float(tax_provision) / float(pretax_income)
                            real_tax = max(0.0, min(real_tax, 0.50))  # clamp 0-50%
                            data["roic"] = (
                                float(ebit) * (1 - real_tax)
                            ) / float(invested_cap)
                        except (TypeError, ValueError, ZeroDivisionError):
                            data["roic"] = None
                    # else: roic queda None (preferible a número inventado — C4)
        except Exception:
            pass

        # Limpiar campos temporales de cálculo
        data.pop("_equity", None)
        data.pop("_invested_capital", None)

        return data

    except Exception as e:
        if TTM_DEBUG:
            print(f"[YQ FUND] {ticker_symbol}: excepción → {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# CAPA A — TTM VÍA yahooquery (BUG B3 fix: signo CapEx consistente)
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_metricas_ttm_yq(yq_obj, ticker_symbol="?", yq_ticker=None):
    """
    Calcula Revenue Growth y FCF usando Trailing Twelve Months con yahooquery.

    BUG B3 FIX: usa abs(CapEx) consistentemente en todas las ramas, igual
    que la función original _calcular_metricas_ttm para yfinance.

    Retorna (rev_growth_ttm, fcf_growth_ttm, fcf_actual_ttm).
    """
    if yq_ticker is None:
        yq_ticker = _normalize_for_yq(ticker_symbol)
    try:
        fin_q = yq_obj.income_statement(frequency="quarterly", trailing=False)
        cf_q  = yq_obj.cash_flow(frequency="quarterly", trailing=False)
        fin_a = yq_obj.income_statement(frequency="annual",    trailing=False)
        cf_a  = yq_obj.cash_flow(frequency="annual",           trailing=False)

        # Filtrar por ticker si es multi-ticker
        for df_name, df in [("fin_q", fin_q), ("cf_q", cf_q),
                             ("fin_a", fin_a), ("cf_a", cf_a)]:
            pass  # usamos los dataframes directamente, filtrado abajo

        def _filter(df):
            if df is None or df.empty:
                return df
            if "symbol" in df.columns:
                df = df[df["symbol"] == yq_ticker]
            return df

        fin_q = _filter(fin_q)
        cf_q  = _filter(cf_q)
        fin_a = _filter(fin_a)
        cf_a  = _filter(cf_a)

        if fin_q is None or fin_q.empty or len(fin_q) < 4:
            if TTM_DEBUG:
                print(f"[TTM YQ] {ticker_symbol}: menos de 4 trimestres")
            return None, None, None

        # Ordenar más reciente primero
        fin_q = fin_q.sort_values("asOfDate", ascending=False)

        # ── Revenue ───────────────────────────────────────────────────────
        rev_col = "TotalRevenue" if "TotalRevenue" in fin_q.columns else "OperatingRevenue"
        if rev_col not in fin_q.columns:
            return None, None, None

        rev_ttm_now = float(fin_q[rev_col].iloc[:4].sum())

        if len(fin_q) >= 8:
            rev_ttm_prev = float(fin_q[rev_col].iloc[4:8].sum())
            modo_rev = "TTM vs TTM"
        else:
            if fin_a is None or fin_a.empty or rev_col not in fin_a.columns:
                return None, None, None
            fin_a_s = fin_a.sort_values("asOfDate", ascending=False)
            rev_ttm_prev = float(fin_a_s[rev_col].iloc[0])
            modo_rev = "TTM vs Anual"

        if rev_ttm_prev <= 0:
            return None, None, None

        rev_growth_ttm = (rev_ttm_now / rev_ttm_prev) - 1

        # ── OCF y CapEx ───────────────────────────────────────────────────
        if cf_q is None or cf_q.empty or len(cf_q) < 4:
            if TTM_DEBUG:
                print(f"[TTM YQ] {ticker_symbol}: sin CF trimestral. Rev={rev_growth_ttm:.2%}")
            return rev_growth_ttm, None, None

        cf_q = cf_q.sort_values("asOfDate", ascending=False)
        ocf_col   = "OperatingCashFlow"
        capex_col = "CapitalExpenditure"

        if ocf_col not in cf_q.columns or capex_col not in cf_q.columns:
            return rev_growth_ttm, None, None

        ocf_now   = float(cf_q[ocf_col].iloc[:4].sum())
        capex_now = float(cf_q[capex_col].iloc[:4].sum())
        # BUG B3 FIX: abs() para signo consistente (yahooquery puede dar pos o neg)
        fcf_now   = ocf_now - abs(capex_now)

        if len(cf_q) >= 8:
            ocf_prev   = float(cf_q[ocf_col].iloc[4:8].sum())
            capex_prev = float(cf_q[capex_col].iloc[4:8].sum())
            fcf_prev   = ocf_prev - abs(capex_prev)
            modo_fcf   = "TTM vs TTM"
        else:
            if cf_a is None or cf_a.empty:
                return rev_growth_ttm, None, fcf_now
            cf_a_s = cf_a.sort_values("asOfDate", ascending=False)
            if ocf_col not in cf_a_s.columns or capex_col not in cf_a_s.columns:
                return rev_growth_ttm, None, fcf_now
            ocf_a   = float(cf_a_s[ocf_col].iloc[0])
            capex_a = float(cf_a_s[capex_col].iloc[0])
            fcf_prev = ocf_a - abs(capex_a)
            modo_fcf = "TTM vs Anual"

        # ── Crecimiento FCF ───────────────────────────────────────────────
        if fcf_prev <= 0 and fcf_now > 0:
            fcf_growth_ttm = 1.0
        elif fcf_now < 0:
            fcf_growth_ttm = -0.5
        elif fcf_prev <= 0:
            fcf_growth_ttm = None
        else:
            raw = (fcf_now / fcf_prev) - 1
            fcf_growth_ttm = (
                None if (math.isnan(raw) or math.isinf(raw)) else raw
            )

        if TTM_DEBUG:
            print(
                f"[TTM YQ] {ticker_symbol}: OK "
                f"Rev={rev_growth_ttm:.2%} ({modo_rev}) | "
                f"FCF={fcf_growth_ttm:.2%} ({modo_fcf}) | "
                f"FCF_ttm={fcf_now/1e9:.1f}B"
            )
        return rev_growth_ttm, fcf_growth_ttm, fcf_now

    except Exception as e:
        if TTM_DEBUG:
            print(f"[TTM YQ] {ticker_symbol}: excepción → {e}")
        return None, None, None


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK — TTM VÍA yfinance (función original, sin cambios lógicos)
# BUG B3 FIX aplicado: abs() en la rama de FCF anual también
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_metricas_ttm(tk, ticker_symbol="?"):
    """
    Calcula Revenue Growth y FCF usando Trailing Twelve Months (TTM).
    Versión original yfinance — usada como fallback si yahooquery falla.

    BUG B3 FIX: rama FCF anual ahora usa abs(capex) consistentemente.
    """
    try:
        fin_q = tk.quarterly_financials
        cf_q  = tk.quarterly_cashflow
        fin_a = tk.financials

        # ── 1. Revenue trimestral ─────────────────────────────────────────
        rev_q = _find_row(fin_q, [["total revenue"], ["operating revenue"]])
        if rev_q is None or len(rev_q) < 4:
            return None, None, None

        rev_ttm_now = float(rev_q.iloc[0:4].sum())

        # ── 2. Revenue periodo anterior ───────────────────────────────────
        if len(rev_q) >= 8:
            rev_ttm_prev = float(rev_q.iloc[4:8].sum())
            modo_rev = "TTM vs TTM"
        else:
            rev_a = _find_row(fin_a, [["total revenue"], ["operating revenue"]])
            if rev_a is None or len(rev_a) < 1:
                return None, None, None
            rev_ttm_prev = float(rev_a.iloc[0])
            modo_rev = "TTM vs Anual"

        if rev_ttm_prev <= 0:
            return None, None, None

        rev_growth_ttm = (rev_ttm_now / rev_ttm_prev) - 1

        # ── 3. OCF y CapEx trimestrales ───────────────────────────────────
        ocf_q   = _find_row(cf_q, [["operating cash flow"],
                                    ["cash flow from continuing operating"]])
        capex_q = _find_row(cf_q, [["capital expenditure"],
                                    ["purchase of ppe"],
                                    ["net ppe purchase"]])

        if ocf_q is None or capex_q is None or len(ocf_q) < 4 or len(capex_q) < 4:
            return rev_growth_ttm, None, None

        ocf_now   = float(ocf_q.iloc[0:4].sum())
        capex_now = float(capex_q.iloc[0:4].sum())
        fcf_now   = ocf_now - abs(capex_now)

        # ── 4. FCF periodo anterior ───────────────────────────────────────
        if len(ocf_q) >= 8 and len(capex_q) >= 8:
            ocf_prev   = float(ocf_q.iloc[4:8].sum())
            capex_prev = float(capex_q.iloc[4:8].sum())
            fcf_prev   = ocf_prev - abs(capex_prev)
            modo_fcf   = "TTM vs TTM"
        else:
            cf_a      = tk.cash_flow
            ocf_a_s   = _find_row(cf_a, [["operating cash flow"]])
            capex_a_s = _find_row(cf_a, [["capital expenditure"]])
            if ocf_a_s is None or capex_a_s is None or len(ocf_a_s) < 1:
                return rev_growth_ttm, None, fcf_now
            # BUG B3 FIX: abs() aquí también para consistencia
            fcf_prev = float(ocf_a_s.iloc[0]) - abs(float(capex_a_s.iloc[0]))
            modo_fcf = "TTM vs Anual"

        # ── 5. Crecimiento FCF ────────────────────────────────────────────
        if fcf_prev <= 0 and fcf_now > 0:
            fcf_growth_ttm = 1.0
        elif fcf_now < 0:
            fcf_growth_ttm = -0.5
        elif fcf_prev <= 0:
            fcf_growth_ttm = None
        else:
            raw = (fcf_now / fcf_prev) - 1
            fcf_growth_ttm = None if (math.isnan(raw) or math.isinf(raw)) else raw

        if TTM_DEBUG:
            print(
                f"[TTM YF] {ticker_symbol}: OK "
                f"Rev={rev_growth_ttm:.2%} ({modo_rev}) | "
                f"FCF={fcf_growth_ttm:.2%} ({modo_fcf}) | "
                f"FCF_ttm={fcf_now/1e9:.1f}B"
            )
        return rev_growth_ttm, fcf_growth_ttm, fcf_now

    except Exception as e:
        if TTM_DEBUG:
            print(f"[TTM YF] {ticker_symbol}: excepción → {e}")
        return None, None, None


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES — Aliases, sectores, peers
# ─────────────────────────────────────────────────────────────────────────────

TICKER_ALIASES = {
    "SPX": "^GSPC", "SP500": "^GSPC", "SP-500": "^GSPC",
    "NASDAQ": "^IXIC", "NDX": "^NDX", "NASDAQ100": "^NDX",
    "DOW": "^DJI", "DJI": "^DJI",
    "VIX": "^VIX", "RUT": "^RUT",
    "GOLD": "GLD", "OIL": "USO",
    "BTC": "BTC-USD", "ETH": "ETH-USD",
}

SECTOR_ETFS = {
    "Technology": "XLK", "Healthcare": "XLV",
    "Financial Services": "XLF", "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP", "Industrials": "XLI",
    "Energy": "XLE", "Utilities": "XLU",
    "Real Estate": "XLRE", "Basic Materials": "XLB",
    "Communication Services": "XLC",
}

INDUSTRY_PEERS = {
    "Software - Application":      ["NOW", "CRM", "WDAY", "INTU", "ADBE", "HUBS"],
    "Software - Infrastructure":   ["MSFT", "ORCL", "SNOW", "MDB", "DDOG", "NET"],
    "Semiconductors":               ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN"],
    "Internet Content & Information":["GOOGL", "META", "SNAP", "PINS"],
    "Internet Retail":              ["AMZN", "BABA", "MELI", "SE", "JD"],
    "Consumer Electronics":         ["AAPL", "SONY"],
    "Auto Manufacturers":           ["TSLA", "F", "GM", "TM", "RIVN"],
}


def resolve_ticker(ticker_symbol):
    """Resuelve alias de tickers populares (SPX → ^GSPC)."""
    return TICKER_ALIASES.get(ticker_symbol.upper(), ticker_symbol)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE TÉCNICOS (reutilizados por fetch_stock_data y fetch_batch)
# ─────────────────────────────────────────────────────────────────────────────

def _hist_to_list(hist: pd.DataFrame) -> list:
    """Convierte el DataFrame histórico a lista de {time, value} para el chart."""
    result = []
    for date, row in hist.iterrows():
        try:
            result.append({
                "time": date.strftime("%Y-%m-%d"),
                "value": round(float(row["Close"]), 2),
            })
        except Exception:
            pass
    return result


def _calc_vwap_list(hist: pd.DataFrame, window: int = 20) -> list:
    """Calcula VWAP móvil y retorna lista de {time, value}."""
    result = []
    if "Volume" not in hist.columns or "High" not in hist.columns:
        return result
    tp = (hist["High"] + hist["Low"] + hist["Close"]) / 3
    vp = tp * hist["Volume"]
    rolling_vwap = vp.rolling(window).sum() / hist["Volume"].rolling(window).sum()
    for date, val in rolling_vwap.dropna().items():
        try:
            result.append({"time": date.strftime("%Y-%m-%d"), "value": round(float(val), 2)})
        except Exception:
            pass
    return result


def _calc_vwap_scalar(hist: pd.DataFrame, window: int) -> float | None:
    """Calcula el último valor del VWAP móvil."""
    if hist.empty or "Volume" not in hist.columns or len(hist) < window:
        return None
    tp = (hist["High"] + hist["Low"] + hist["Close"]) / 3
    vp = tp * hist["Volume"]
    series = vp.rolling(window).sum() / hist["Volume"].rolling(window).sum()
    val = series.iloc[-1]
    return float(val) if not pd.isna(val) else None


def _calc_support_resistance(hist: pd.DataFrame) -> list:
    """Detecta soportes y resistencias por swing highs/lows (scipy)."""
    levels = []
    if hist.empty or "High" not in hist.columns or "Low" not in hist.columns:
        return levels
    try:
        from scipy.signal import argrelextrema

        orden = 10
        indices_pisos  = argrelextrema(hist["Low"].values,  np.less,    order=orden)[0]
        indices_techos = argrelextrema(hist["High"].values, np.greater, order=orden)[0]

        precio_actual = float(hist["Close"].iloc[-1])
        umbral = 0.015

        # ── NUEVO SISTEMA DE PISOS CON VOLUMEN ──
        vol_ma20 = hist["Volume"].rolling(window=20).mean().values
        volumenes = hist["Volume"].values

        pisos_estandar = []
        pisos_volumen_confirmado = []

        for idx in indices_pisos:
            p = float(hist["Low"].iloc[idx])
            if p < precio_actual:
                pisos_estandar.append(p)
                v = float(volumenes[idx])
                v_ma = float(vol_ma20[idx])
                if not np.isnan(v_ma) and v >= 1.2 * v_ma:
                    pisos_volumen_confirmado.append(p)

        if len(pisos_volumen_confirmado) >= 2:
            pisos_finales = pisos_volumen_confirmado
            modo_pisos = "Confirmado por volumen"
        else:
            pisos_finales = pisos_estandar
            modo_pisos = "Estándar (fallback)"

        # Clustering Techos (se mantiene original)
        zonas_resistencia = []
        for precio in hist["High"].iloc[indices_techos].values:
            encontrado = False
            for zona in zonas_resistencia:
                prom = sum(zona["precios"]) / len(zona["precios"])
                if abs(precio - prom) / prom <= umbral:
                    zona["precios"].append(precio)
                    zona["toques"] += 1
                    encontrado = True
                    break
            if not encontrado:
                zonas_resistencia.append({"precios": [precio], "toques": 1})

        techos_confirmados = [
            sum(z["precios"]) / len(z["precios"])
            for z in zonas_resistencia
            if z["toques"] >= 2 and sum(z["precios"]) / len(z["precios"]) > precio_actual
        ]

        if pisos_finales:
            levels.append({
                "precio": round(float(max(pisos_finales)), 2),
                "tipo": "Piso", "fuerza": "Fuerte", "volumen": 0,
                "modo": modo_pisos
            })
        if techos_confirmados:
            levels.append({
                "precio": round(float(min(techos_confirmados)), 2),
                "tipo": "Techo", "fuerza": "Fuerte", "volumen": 0,
            })
    except ImportError:
        pass
    except Exception:
        pass
    return levels


def _enrich_with_history(data: dict, hist: pd.DataFrame) -> dict:
    """
    Rellena data con VWAP, señal, gráfico, técnicos y soportes a partir
    del DataFrame histórico de precios. Compartido por ambas rutas.
    """
    data["vwap_actual"] = None
    data["senal_vwap"]  = "N/A"
    data["vwap"]        = []
    data["vwap_30"]     = None
    data["vwap_50"]     = None
    data["history"]     = []
    data["volume_profile"] = []
    data["technicals"]  = {}

    if hist.empty:
        return data

    # Historia para el gráfico
    data["history"] = _hist_to_list(hist)

    # VWAP 20/30/50
    data["vwap"]    = _calc_vwap_list(hist, 20)
    data["vwap_30"] = _calc_vwap_scalar(hist, 30)
    data["vwap_50"] = _calc_vwap_scalar(hist, 50)

    if data["vwap"]:
        data["vwap_actual"] = data["vwap"][-1]["value"]
        price = data.get("price") or (
            float(hist["Close"].iloc[-1]) if not hist.empty else None
        )
        if price and data["vwap_actual"]:
            data["senal_vwap"] = (
                "Descuento Institucional (Comprar)"
                if price < data["vwap_actual"]
                else "Sobreprecio (Paciencia)"
            )

    # Soportes/Resistencias
    data["volume_profile"] = _calc_support_resistance(hist)

    # Técnicos
    data["technicals"] = calculate_technicals(hist)

    return data


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PÚBLICA PRINCIPAL — Ticker individual
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False, max_entries=100)
def fetch_stock_data(ticker_symbol):
    """
    Obtiene todos los datos de un ticker.
    Plan A: yahooquery para fundamentales.
    Plan B (fallback): yfinance si Plan A falla.
    Capa B siempre: yfinance para precio histórico y técnicos.
    """
    display_ticker = ticker_symbol.upper()
    resolved = resolve_ticker(display_ticker)
    yq_ticker = _normalize_for_yq(resolved)

    # ══ PLAN A: yahooquery (fundamentales) ════════════════════════════════
    yq_success = False
    data = {}
    try:
        from yahooquery import Ticker
        yq = Ticker(yq_ticker, asynchronous=False, validate=True, session=_get_session())
        data = _yq_fundamentals(resolved, yq_obj=yq)

        if data and data.get("price") is not None:
            yq_success = True
            # TTM vía yahooquery
            rv, fg, fa = _calcular_metricas_ttm_yq(yq, display_ticker, yq_ticker)
            data["revenue_growth_ttm"] = rv
            data["fcf_growth_ttm"]     = fg
            data["fcf_actual_ttm"]     = fa
    except Exception as e:
        if TTM_DEBUG:
            print(f"[YQ] {display_ticker} falló completamente: {e}")

    # ══ PLAN B: yfinance fallback (si yahooquery no entregó datos) ════════
    if not yq_success:
        if TTM_DEBUG:
            print(f"[FALLBACK YF] {display_ticker}")
        tk = yf.Ticker(resolved)
        try:
            # Fallback seguro sin datos sintéticos
            info = tk.info or {}
            if not info: return {} # signal = False
        except Exception:
            return {} # signal = False

        quote_type = info.get("quoteType", "").upper()

        data = {
            "quote_type":       quote_type,
            "name":             info.get("shortName") or info.get("longName") or display_ticker,
            "long_name":        info.get("longName", ""),
            "sector":           info.get("sector", "N/A"),
            "industry":         info.get("industry", "N/A"),
            "description":      info.get("longBusinessSummary", ""),
            "price":            info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap":       info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "shares_out":       info.get("sharesOutstanding"),
            "fifty_two_high":   info.get("fiftyTwoWeekHigh"),
            "fifty_two_low":    info.get("fiftyTwoWeekLow"),
            "avg_volume":       info.get("averageVolume"),
            "beta":             info.get("beta"),
            "dividend_rate":    info.get("dividendRate"),
            "payout_ratio":     info.get("payoutRatio"),
            "trailing_pe":      info.get("trailingPE"),
            "forward_pe":       info.get("forwardPE"),
            "peg_ratio":        info.get("pegRatio"),
            "price_to_book":    info.get("priceToBook"),
            "price_to_sales":   info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda":     info.get("enterpriseToEbitda"),
            "ev_to_revenue":    info.get("enterpriseToRevenue"),
            "revenue":          info.get("totalRevenue"),
            "revenue_growth":   info.get("revenueGrowth"),
            "gross_margins":    info.get("grossMargins"),
            "operating_margins":info.get("operatingMargins"),
            "profit_margins":   info.get("profitMargins"),
            "roe":              info.get("returnOnEquity"),
            "roa":              info.get("returnOnAssets"),
            "roic":             None,   # calculado abajo con datos reales
            "trailing_eps":     info.get("trailingEps"),
            "forward_eps":      info.get("forwardEps"),
            "earnings_growth":  info.get("earningsGrowth"),
            "total_assets":     info.get("totalAssets"),
            "goodwill":         info.get("goodwill"),
            "intangible_assets":info.get("intangibleAssets"),
            "net_income":       info.get("netIncomeToCommon"),
            "short_term_debt":  info.get("shortTermDebt"),
            "total_cash":       info.get("totalCash"),
            "total_debt":       info.get("totalDebt"),
            "debt_to_equity":   info.get("debtToEquity"),
            "current_ratio":    info.get("currentRatio"),
            "quick_ratio":      info.get("quickRatio"),
            "operating_cf":     info.get("operatingCashflow"),
            "free_cf":          info.get("freeCashflow"),
            "ebitda":           info.get("ebitda"),
            "target_high":      info.get("targetHighPrice"),
            "target_low":       info.get("targetLowPrice"),
            "target_mean":      info.get("targetMeanPrice"),
            "target_median":    info.get("targetMedianPrice"),
            "recommendation":   info.get("recommendationKey"),
            "num_analysts":     info.get("numberOfAnalystOpinions"),
            "interest_expense": None,
            "shares_growth":    None,
        }

        # BUG B4 FIX: interest_expense siempre extraído del income_stmt
        try:
            inc_stmt = tk.income_stmt
            if inc_stmt is not None and not inc_stmt.empty:
                ie_row = _find_row(
                    inc_stmt,
                    [["interest", "expense", "non", "operating"],
                     ["interest", "expense"]]
                )
                if ie_row is not None and len(ie_row) > 0:
                    data["interest_expense"] = abs(float(ie_row.iloc[0]))
        except Exception:
            pass

        # Shares growth desde yfinance
        try:
            inc_stmt = tk.income_stmt
            if inc_stmt is not None and not inc_stmt.empty:
                shares_s = None
                if "Diluted Average Shares" in inc_stmt.index:
                    shares_s = inc_stmt.loc["Diluted Average Shares"].dropna()
                elif "Basic Average Shares" in inc_stmt.index:
                    shares_s = inc_stmt.loc["Basic Average Shares"].dropna()
                if shares_s is not None and len(shares_s) >= 2:
                    s_rec = shares_s.iloc[0]
                    s_old = shares_s.iloc[1]
                    if s_old > 0:
                        data["shares_growth"] = (s_rec / s_old) - 1
        except Exception:
            pass

        # Short term debt fallback
        if not data.get("short_term_debt"):
            try:
                bs = tk.balance_sheet
                if bs is not None and not bs.empty:
                    st_row = _find_row(bs, [["short", "debt"], ["current", "debt"]])
                    if st_row is not None and len(st_row) > 0:
                        data["short_term_debt"] = float(st_row.iloc[0])
            except Exception:
                pass

        # TTM vía yfinance (fallback)
        quote_type_yf = info.get("quoteType", "").upper()
        is_index_yf = (
            quote_type_yf in ("INDEX", "FUTURE", "ETF") or resolved.startswith("^")
        )
        if not is_index_yf:
            rv, fg, fa = _calcular_metricas_ttm(tk, display_ticker)
            data["revenue_growth_ttm"] = rv
            data["fcf_growth_ttm"]     = fg
            data["fcf_actual_ttm"]     = fa
        else:
            data["revenue_growth_ttm"] = None
            data["fcf_growth_ttm"]     = None
            data["fcf_actual_ttm"]     = None

    # ══ CAMPOS COMUNES — rellenar defaults para claves esperadas ══════════
    quote_type = data.get("quote_type", "")
    is_index = (
        quote_type in ("INDEX", "FUTURE", "ETF") or resolved.startswith("^")
    )

    data.setdefault("ticker",          display_ticker)
    data.setdefault("resolved_ticker", resolved)
    data.setdefault("is_index",        is_index)
    data.setdefault("quote_type",      quote_type)
    data.setdefault("dividend_yield",  None)
    data.setdefault("fcf_yield",       None)
    data.setdefault("fcf_growth",      None)
    data.setdefault("revenue_growth_ttm", None)
    data.setdefault("fcf_growth_ttm",     None)
    data.setdefault("fcf_actual_ttm",     None)
    data.setdefault("shares_growth",   None)

    # Precio: fallback si no vino de los módulos
    if not data.get("price"):
        try:
            hist_tmp = yf.Ticker(resolved).history(period="5d")
            if not hist_tmp.empty:
                data["price"] = float(hist_tmp["Close"].iloc[-1])
        except Exception:
            pass

    # Sector para índices
    if is_index and data.get("sector") in (None, "N/A", ""):
        data["sector"] = "Índice de Mercado"
    if is_index and data.get("industry") in (None, "N/A", ""):
        data["industry"] = quote_type.title() if quote_type else "N/A"

    # Dividend yield desde tasa / precio
    div_rate = data.get("dividend_rate")
    price = data.get("price")
    if div_rate and price and price > 0:
        data["dividend_yield"] = div_rate / price

    # FCF Yield (fuente de verdad única)
    mc = data.get("market_cap")
    if mc and mc > 0:
        fcf_para_yield = (
            data.get("fcf_actual_ttm") or data.get("free_cf")
        )
        if fcf_para_yield is not None:
            data["fcf_yield"] = fcf_para_yield / mc

    # FCF Growth: preferir TTM, fallback a anual desde yfinance
    if data.get("fcf_growth_ttm") is not None:
        data["fcf_growth"] = data["fcf_growth_ttm"]
    elif not is_index and not yq_success:
        # Solo si estamos en modo fallback yfinance
        try:
            tk_tmp = yf.Ticker(resolved)
            cf_df = tk_tmp.cash_flow
            if (
                cf_df is not None and not cf_df.empty
                and "Operating Cash Flow" in cf_df.index
                and "Capital Expenditure" in cf_df.index
            ):
                ocf_a   = cf_df.loc["Operating Cash Flow"].dropna()
                capex_a = cf_df.loc["Capital Expenditure"].dropna()
                fcf_series = (ocf_a + capex_a).dropna()
                if len(fcf_series) >= 2:
                    fcf_recent = fcf_series.iloc[0]
                    idx_old = min(3, len(fcf_series) - 1)
                    fcf_old = fcf_series.iloc[idx_old]
                    if fcf_recent < 0:
                        data["fcf_growth"] = -0.5
                    elif fcf_old < 0 and fcf_recent > 0:
                        data["fcf_growth"] = 1.0
                    elif fcf_old > 0 and fcf_recent >= 0:
                        crec = (fcf_recent / fcf_old) ** (1 / idx_old) - 1
                        if not (math.isnan(crec) or math.isinf(crec)):
                            data["fcf_growth"] = crec
        except Exception:
            pass

    # ══ CAPA B: yfinance para histórico y técnicos (SIEMPRE) ══════════════
    try:
        tk_hist = yf.Ticker(resolved)
        hist = tk_hist.history(period="1y")
        if 'Close' in hist.columns:
            hist = hist.dropna(subset=['Close'])
        if hist.empty and not data.get("price"):
            data["price"] = None
        data = _enrich_with_history(data, hist)
    except Exception:
        data.setdefault("history",        [])
        data.setdefault("vwap",           [])
        data.setdefault("vwap_actual",    None)
        data.setdefault("vwap_30",        None)
        data.setdefault("vwap_50",        None)
        data.setdefault("volume_profile", [])
        data.setdefault("technicals",     {})
        data.setdefault("senal_vwap",     "N/A")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PÚBLICA — Ticker individual LITE (para el Radar)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False, max_entries=500)
def fetch_stock_data_radar(ticker_symbol: str) -> dict:
    """
    Versión LITE de fetch_stock_data optimizada para el Radar masivo.

    HTTP calls: ~2 en vez de ~10
      1. yahooquery: financial_data + key_stats + summary_detail +
                     asset_profile + quote_type  (todo en 1 request)
      2. yfinance:   history(period='1y')         (OHLCV para técnicos)

    Campos omitidos (quedan None):
      - roic, interest_expense, shares_growth (requieren DataFrames contables)
      - revenue_growth_ttm, fcf_growth_ttm    (requieren quarterly statements)

    El Radar usa revenue_growth, profit_margins, roe, debt_to_equity,
    current_ratio, free_cf, fcf_yield, market_cap —  todos vienen de los
    módulos planos de yahooquery.

    El análisis individual completo sigue usando fetch_stock_data (todas las
    métricas disponibles).
    """
    display_ticker = ticker_symbol.upper()
    resolved = resolve_ticker(display_ticker)
    yq_ticker = _normalize_for_yq(resolved)

    data = {}

    # ══ PLAN A: yahooquery (solo módulos planos — 1 HTTP call) ═══════════
    yq_success = False
    try:
        from yahooquery import Ticker
        yq = Ticker(yq_ticker, asynchronous=False, validate=False, session=_get_session())
        
        # 1 Sola llamada HTTP para todos los módulos planos
        modules_data = yq.get_modules(["financialData", "defaultKeyStatistics", "summaryDetail", "assetProfile", "quoteType"])
        
        if isinstance(modules_data, dict) and yq_ticker in modules_data:
            res = modules_data[yq_ticker]
            if isinstance(res, dict):
                fd = res.get("financialData", {})
                ks = res.get("defaultKeyStatistics", {})
                sd = res.get("summaryDetail", {})
                ap = res.get("assetProfile", {})
                qt = res.get("quoteType", {})

                # Check price en fd o sd
                price = fd.get("currentPrice") or sd.get("regularMarketPrice") or fd.get("regularMarketPrice")

                if price is not None:
                    quote_type = qt.get("quoteType", "").upper()
                    is_index   = quote_type in ("INDEX", "FUTURE", "ETF") or resolved.startswith("^")

                    data = {
                        "ticker":          display_ticker,
                        "resolved_ticker": resolved,
                        "is_index":        is_index,
                        "quote_type":      quote_type,
                        "name":            fd.get("shortName") or ap.get("longName") or display_ticker,
                        "long_name":       ap.get("longName", ""),
                        "sector":          ap.get("sector") or ("Índice de Mercado" if is_index else "N/A"),
                        "industry":        ap.get("industry") or (quote_type.title() if quote_type else "N/A"),
                        "description":     "",
                        "price":           price,
                        "market_cap":      sd.get("marketCap") or ks.get("marketCap"),
                        "enterprise_value":ks.get("enterpriseValue"),
                        "shares_out":      ks.get("sharesOutstanding"),
                "fifty_two_high":  sd.get("fiftyTwoWeekHigh"),
                "fifty_two_low":   sd.get("fiftyTwoWeekLow"),
                "avg_volume":      sd.get("averageVolume"),
                "beta":            ks.get("beta"),
                "dividend_rate":   sd.get("dividendRate"),
                "dividend_yield":  None,
                "payout_ratio":    sd.get("payoutRatio"),
                "trailing_pe":     sd.get("trailingPE"),
                "forward_pe":      ks.get("forwardPE"),
                "peg_ratio":       ks.get("pegRatio"),
                "price_to_book":   ks.get("priceToBook"),
                "price_to_sales":  sd.get("priceToSalesTrailing12Months"),
                "ev_to_ebitda":    ks.get("enterpriseToEbitda"),
                "ev_to_revenue":   ks.get("enterpriseToRevenue"),
                "revenue":         fd.get("totalRevenue"),
                "revenue_growth":  fd.get("revenueGrowth"),
                "gross_margins":   fd.get("grossMargins"),
                "operating_margins":fd.get("operatingMargins"),
                "profit_margins":  fd.get("profitMargins"),
                "roe":             fd.get("returnOnEquity"),
                "roa":             fd.get("returnOnAssets"),
                "roic":            None,   # omitido en lite (requiere balance_sheet)
                "trailing_eps":    ks.get("trailingEps"),
                "forward_eps":     ks.get("forwardEps"),
                "earnings_growth": fd.get("earningsGrowth"),
                "net_income":      fd.get("netIncomeToCommon"),
                "total_cash":      fd.get("totalCash"),
                "total_debt":      fd.get("totalDebt"),
                "debt_to_equity":  fd.get("debtToEquity"),
                "current_ratio":   fd.get("currentRatio"),
                "quick_ratio":     fd.get("quickRatio"),
                "operating_cf":    fd.get("operatingCashflow"),
                "free_cf":         fd.get("freeCashflow"),
                "ebitda":          fd.get("ebitda"),
                "target_high":     fd.get("targetHighPrice"),
                "target_low":      fd.get("targetLowPrice"),
                "target_mean":     fd.get("targetMeanPrice"),
                "target_median":   fd.get("targetMedianPrice"),
                "recommendation":  fd.get("recommendationKey"),
                "num_analysts":    fd.get("numberOfAnalystOpinions"),
                # campos contables omitidos en lite
                "total_assets":    None,
                "goodwill":        None,
                "intangible_assets":None,
                "short_term_debt": None,
                "interest_expense":None,
                "shares_growth":   None,
                # TTM omitidos en lite
                "revenue_growth_ttm": None,
                "fcf_growth_ttm":     None,
                "fcf_actual_ttm":     None,
                "fcf_yield":       None,
                "fcf_growth":      None,
            }

            # Dividend yield
            div_rate = data.get("dividend_rate")
            p = data.get("price")
            if div_rate and p and p > 0:
                data["dividend_yield"] = div_rate / p

            # FCF Yield desde free_cf anual (sin TTM)
            mc = data.get("market_cap")
            fcf = data.get("free_cf")
            if mc and mc > 0 and fcf is not None:
                data["fcf_yield"]  = fcf / mc
                data["fcf_growth"] = None  # sin quarterly → None

            yq_success = True

    except Exception:
        pass

    # ══ PLAN B: yfinance info (fallback si YQ falla) ═══════════════════
    if not yq_success:
        try:
            tk = yf.Ticker(resolved)
            info = tk.info or {}
            if info.get("currentPrice") or info.get("regularMarketPrice"):
                qt_yf      = info.get("quoteType", "").upper()
                is_index_b = qt_yf in ("INDEX", "FUTURE", "ETF") or resolved.startswith("^")
                data = {
                    "ticker":          display_ticker,
                    "resolved_ticker": resolved,
                    "is_index":        is_index_b,
                    "quote_type":      qt_yf,
                    "name":            info.get("shortName") or display_ticker,
                    "long_name":       info.get("longName", ""),
                    "sector":          info.get("sector") or ("Índice de Mercado" if is_index_b else "N/A"),
                    "industry":        info.get("industry", "N/A"),
                    "description":     "",
                    "price":           info.get("currentPrice") or info.get("regularMarketPrice"),
                    "market_cap":      info.get("marketCap"),
                    "enterprise_value":info.get("enterpriseValue"),
                    "shares_out":      info.get("sharesOutstanding"),
                    "fifty_two_high":  info.get("fiftyTwoWeekHigh"),
                    "fifty_two_low":   info.get("fiftyTwoWeekLow"),
                    "avg_volume":      info.get("averageVolume"),
                    "beta":            info.get("beta"),
                    "dividend_rate":   info.get("dividendRate"),
                    "dividend_yield":  None,
                    "payout_ratio":    info.get("payoutRatio"),
                    "trailing_pe":     info.get("trailingPE"),
                    "forward_pe":      info.get("forwardPE"),
                    "peg_ratio":       info.get("pegRatio"),
                    "price_to_book":   info.get("priceToBook"),
                    "price_to_sales":  info.get("priceToSalesTrailing12Months"),
                    "ev_to_ebitda":    info.get("enterpriseToEbitda"),
                    "ev_to_revenue":   info.get("enterpriseToRevenue"),
                    "revenue":         info.get("totalRevenue"),
                    "revenue_growth":  info.get("revenueGrowth"),
                    "gross_margins":   info.get("grossMargins"),
                    "operating_margins":info.get("operatingMargins"),
                    "profit_margins":  info.get("profitMargins"),
                    "roe":             info.get("returnOnEquity"),
                    "roa":             info.get("returnOnAssets"),
                    "roic":            None,
                    "trailing_eps":    info.get("trailingEps"),
                    "forward_eps":     info.get("forwardEps"),
                    "earnings_growth": info.get("earningsGrowth"),
                    "net_income":      info.get("netIncomeToCommon"),
                    "total_cash":      info.get("totalCash"),
                    "total_debt":      info.get("totalDebt"),
                    "debt_to_equity":  info.get("debtToEquity"),
                    "current_ratio":   info.get("currentRatio"),
                    "quick_ratio":     info.get("quickRatio"),
                    "operating_cf":    info.get("operatingCashflow"),
                    "free_cf":         info.get("freeCashflow"),
                    "ebitda":          info.get("ebitda"),
                    "target_high":     info.get("targetHighPrice"),
                    "target_low":      info.get("targetLowPrice"),
                    "target_mean":     info.get("targetMeanPrice"),
                    "target_median":   info.get("targetMedianPrice"),
                    "recommendation":  info.get("recommendationKey"),
                    "num_analysts":    info.get("numberOfAnalystOpinions"),
                    "total_assets":    None, "goodwill": None, "intangible_assets": None,
                    "short_term_debt": None, "interest_expense": None, "shares_growth": None,
                    "revenue_growth_ttm": None, "fcf_growth_ttm": None, "fcf_actual_ttm": None,
                    "fcf_yield":       None, "fcf_growth": None,
                }
                div_r = data.get("dividend_rate"); pr = data.get("price")
                if div_r and pr and pr > 0:
                    data["dividend_yield"] = div_r / pr
                mc_b = data.get("market_cap"); fcf_b = data.get("free_cf")
                if mc_b and mc_b > 0 and fcf_b is not None:
                    data["fcf_yield"] = fcf_b / mc_b
        except Exception:
            pass

    if not data or not data.get("price"):
        return {}

    # ══ CAPA B: yfinance history — OHLCV + técnicos (1 HTTP call) ════════
    try:
        hist = yf.Ticker(resolved).history(period="1y")
        if 'Close' in hist.columns:
            hist = hist.dropna(subset=['Close'])
        data = _enrich_with_history(data, hist)
    except Exception:
        for k in ("history", "vwap", "vwap_actual", "vwap_30", "vwap_50",
                  "volume_profile", "technicals", "senal_vwap"):
            data.setdefault(k, [] if k in ("history", "vwap", "volume_profile") else
                            {} if k == "technicals" else None if k != "senal_vwap" else "N/A")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PÚBLICA — Lote para el Radar masivo
# ─────────────────────────────────────────────────────────────────────────────

def fetch_batch_fundamentals(tickers_list: list) -> dict:
    """
    Descarga fundamentales + OHLCV en lote para el Radar masivo.

    Usa yahooquery para fundamentales (1 llamada HTTP por lote) y
    yfinance.download para OHLCV vectorial. 10-20x más rápido que
    iterar fetch_stock_data() ticker por ticker.

    Args:
        tickers_list: lista de tickers (formato yfinance, e.g. "BRK.B")

    Returns:
        dict {ticker: data_dict} con las MISMAS CLAVES que fetch_stock_data()
    """
    from yahooquery import Ticker

    results = {}
    batch = list(tickers_list)  # copia para no mutar el original

    if not batch:
        return results

    # Normalizar para yahooquery (BRK.B → BRK-B)
    yq_tickers = [_normalize_for_yq(t) for t in batch]
    # Mapa inverso: yq_ticker → ticker original
    yq_to_orig = {yq: orig for yq, orig in zip(yq_tickers, batch)}

    # ── A. yahooquery en lote ─────────────────────────────────────────────
    yq_batch = None
    try:
        yq_batch = Ticker(yq_tickers, asynchronous=False, validate=False, session=_get_session())
        fd_all = yq_batch.financial_data
        ks_all = yq_batch.key_stats
        sd_all = yq_batch.summary_detail
        ap_all = yq_batch.asset_profile
        qt_all = yq_batch.quote_type

        # DataFrames contables — columna "symbol" identifica el ticker
        bs_all  = yq_batch.balance_sheet(frequency="annual",    trailing=False)
        inc_all = yq_batch.income_statement(frequency="annual", trailing=False)
        cf_all  = yq_batch.cash_flow(frequency="annual",        trailing=False)
        inc_q   = yq_batch.income_statement(frequency="quarterly", trailing=False)
        cf_q    = yq_batch.cash_flow(frequency="quarterly",     trailing=False)

    except Exception as e:
        if TTM_DEBUG:
            print(f"[BATCH YQ] Error en lote: {e}. Fallback individual.")
        for t in batch:
            try:
                results[t] = fetch_stock_data(t)
            except Exception:
                pass
        return results

    # ── B. yfinance.download para OHLCV vectorial ─────────────────────────
    hist_batch = None
    try:
        hist_batch = yf.download(
            batch,
            period="1y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception:
        hist_batch = None

    # ── C. Construir data dict por ticker ──────────────────────────────────
    for orig_ticker, yq_ticker in zip(batch, yq_tickers):
        try:
            fd = (fd_all.get(yq_ticker) or {}) if isinstance(fd_all, dict) else {}
            ks = (ks_all.get(yq_ticker) or {}) if isinstance(ks_all, dict) else {}
            sd = (sd_all.get(yq_ticker) or {}) if isinstance(sd_all, dict) else {}
            ap = (ap_all.get(yq_ticker) or {}) if isinstance(ap_all, dict) else {}
            qt = (qt_all.get(yq_ticker) or {}) if isinstance(qt_all, dict) else {}

            # Si YQ devuelve error string → micro-fallback individual
            if isinstance(fd, str) or not fd or not fd.get("currentPrice"):
                results[orig_ticker] = fetch_stock_data(orig_ticker)
                continue

            # Fundamentales planos
            price = fd.get("currentPrice") or sd.get("regularMarketPrice")
            quote_type = qt.get("quoteType", "").upper()
            is_index = (
                quote_type in ("INDEX", "FUTURE", "ETF")
                or orig_ticker.startswith("^")
            )

            d = {
                "ticker":          orig_ticker.upper(),
                "resolved_ticker": orig_ticker,
                "is_index":        is_index,
                "quote_type":      quote_type,
                "name":            fd.get("shortName") or ap.get("longName", orig_ticker),
                "long_name":       ap.get("longName", ""),
                "sector":          ap.get("sector") or ("Índice de Mercado" if is_index else "N/A"),
                "industry":        ap.get("industry") or (quote_type.title() if quote_type else "N/A"),
                "description":     ap.get("longBusinessSummary", ""),
                "price":           price,
                "market_cap":      sd.get("marketCap"),
                "enterprise_value":ks.get("enterpriseValue"),
                "shares_out":      ks.get("sharesOutstanding"),
                "fifty_two_high":  sd.get("fiftyTwoWeekHigh"),
                "fifty_two_low":   sd.get("fiftyTwoWeekLow"),
                "avg_volume":      sd.get("averageVolume"),
                "beta":            ks.get("beta"),
                "dividend_rate":   sd.get("dividendRate"),
                "dividend_yield":  None,
                "payout_ratio":    sd.get("payoutRatio"),
                "trailing_pe":     sd.get("trailingPE"),
                "forward_pe":      ks.get("forwardPE"),
                "peg_ratio":       ks.get("pegRatio"),
                "price_to_book":   ks.get("priceToBook"),
                "price_to_sales":  sd.get("priceToSalesTrailing12Months"),
                "ev_to_ebitda":    ks.get("enterpriseToEbitda"),
                "ev_to_revenue":   ks.get("enterpriseToRevenue"),
                "revenue":         fd.get("totalRevenue"),
                "revenue_growth":  fd.get("revenueGrowth"),
                "gross_margins":   fd.get("grossMargins"),
                "operating_margins":fd.get("operatingMargins"),
                "profit_margins":  fd.get("profitMargins"),
                "roe":             fd.get("returnOnEquity"),
                "roa":             fd.get("returnOnAssets"),
                "roic":            None,
                "trailing_eps":    ks.get("trailingEps"),
                "forward_eps":     ks.get("forwardEps"),
                "earnings_growth": fd.get("earningsGrowth"),
                "net_income":      fd.get("netIncomeToCommon"),
                "total_cash":      fd.get("totalCash"),
                "total_debt":      fd.get("totalDebt"),
                "debt_to_equity":  fd.get("debtToEquity"),
                "current_ratio":   fd.get("currentRatio"),
                "quick_ratio":     fd.get("quickRatio"),
                "operating_cf":    fd.get("operatingCashflow"),
                "free_cf":         fd.get("freeCashflow"),
                "ebitda":          fd.get("ebitda"),
                "target_high":     fd.get("targetHighPrice"),
                "target_low":      fd.get("targetLowPrice"),
                "target_mean":     fd.get("targetMeanPrice"),
                "target_median":   fd.get("targetMedianPrice"),
                "recommendation":  fd.get("recommendationKey"),
                "num_analysts":    fd.get("numberOfAnalystOpinions"),
                "total_assets":    None,
                "goodwill":        None,
                "intangible_assets":None,
                "short_term_debt": None,
                "interest_expense":None,
                "shares_growth":   None,
                "fcf_yield":       None,
                "fcf_growth":      None,
                "revenue_growth_ttm": None,
                "fcf_growth_ttm":     None,
                "fcf_actual_ttm":     None,
            }

            # Balance Sheet del lote
            _invested_capital = None
            try:
                if bs_all is not None and not bs_all.empty and "symbol" in bs_all.columns:
                    bs_t = bs_all[bs_all["symbol"] == yq_ticker].sort_values("asOfDate")
                    if not bs_t.empty:
                        bs_l = bs_t.iloc[-1]
                        d["total_assets"]      = bs_l.get("TotalAssets")
                        d["goodwill"]          = bs_l.get("Goodwill")
                        d["intangible_assets"] = bs_l.get("OtherIntangibleAssets")
                        d["short_term_debt"]   = bs_l.get("CurrentDebt")
                        equity    = bs_l.get("StockholdersEquity")
                        net_debt  = (d.get("total_debt") or 0) - (d.get("total_cash") or 0)
                        _invested_capital = (equity or 0) + net_debt
            except Exception:
                pass

            # Income Statement anual del lote (interest_expense, shares_growth, ROIC)
            try:
                if inc_all is not None and not inc_all.empty and "symbol" in inc_all.columns:
                    inc_t = inc_all[inc_all["symbol"] == yq_ticker].sort_values("asOfDate")
                    if not inc_t.empty:
                        inc_l = inc_t.iloc[-1]
                        # interest_expense (BUG B4 fix)
                        ie = inc_l.get("InterestExpense")
                        if ie is not None:
                            try:
                                d["interest_expense"] = abs(float(ie))
                            except (TypeError, ValueError):
                                pass
                        # shares_growth
                        if len(inc_t) >= 2:
                            rs = inc_l.get("DilutedAverageShares")
                            ps = inc_t.iloc[-2].get("DilutedAverageShares")
                            if rs and ps and float(ps) > 0:
                                try:
                                    d["shares_growth"] = float(rs) / float(ps) - 1
                                except Exception:
                                    pass
                        # ROIC real sin proxies (BUG B1 fix + C4)
                        ebit     = inc_l.get("OperatingIncome")
                        tax_prov = inc_l.get("TaxProvision")
                        pretax   = inc_l.get("PretaxIncome")
                        if (
                            ebit is not None and tax_prov is not None
                            and pretax is not None and pretax != 0
                            and _invested_capital is not None and _invested_capital > 0
                        ):
                            try:
                                real_tax = float(tax_prov) / float(pretax)
                                real_tax = max(0.0, min(real_tax, 0.50))
                                d["roic"] = float(ebit) * (1 - real_tax) / float(_invested_capital)
                            except Exception:
                                pass
            except Exception:
                pass

            # TTM trimestral del lote
            if not is_index:
                try:
                    rv, fg, fa = _calcular_metricas_ttm_yq(
                        yq_batch, orig_ticker, yq_ticker
                    )
                    d["revenue_growth_ttm"] = rv
                    d["fcf_growth_ttm"]     = fg
                    d["fcf_actual_ttm"]     = fa
                except Exception:
                    pass

            # Dividend yield
            div_rate = d.get("dividend_rate")
            p = d.get("price")
            if div_rate and p and p > 0:
                d["dividend_yield"] = div_rate / p

            # FCF Yield
            mc = d.get("market_cap")
            if mc and mc > 0:
                fcf_py = d.get("fcf_actual_ttm") or d.get("free_cf")
                if fcf_py is not None:
                    d["fcf_yield"] = fcf_py / mc

            # FCF Growth
            if d.get("fcf_growth_ttm") is not None:
                d["fcf_growth"] = d["fcf_growth_ttm"]

            # ── OHLCV y técnicos desde yf.download vectorial ─────────────
            hist = pd.DataFrame()
            if hist_batch is not None and not hist_batch.empty:
                try:
                    if len(batch) > 1:
                        # multi-ticker: índice multi-nivel
                        if orig_ticker in hist_batch.columns.get_level_values(0):
                            hist = hist_batch[orig_ticker].dropna(how="all")
                        elif hasattr(hist_batch.columns, "levels"):
                            # Intentar con el nombre normalizado
                            pass
                    else:
                        hist = hist_batch.dropna(how="all")
                        
                    if not hist.empty and 'Close' in hist.columns:
                        hist = hist.dropna(subset=['Close'])
                except Exception:
                    hist = pd.DataFrame()

            d = _enrich_with_history(d, hist)
            results[orig_ticker] = d

        except Exception as e:
            if TTM_DEBUG:
                print(f"[BATCH] {orig_ticker}: excepción → {e}. Fallback individual.")
            try:
                results[orig_ticker] = fetch_stock_data(orig_ticker)
            except Exception:
                pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES DE APP — Peers y ETF de sector
# ─────────────────────────────────────────────────────────────────────────────

def fetch_peers(ticker_symbol, sector, industry, max_peers=4):
    """Obtiene datos básicos de peers/competidores del mismo sector."""
    peers_list = []
    for ind_key, tickers in INDUSTRY_PEERS.items():
        if ind_key.lower() in industry.lower() or industry.lower() in ind_key.lower():
            peers_list = [t for t in tickers if t.upper() != ticker_symbol.upper()]
            break

    peers_list = peers_list[:max_peers]
    peers_data = []

    for peer_ticker in peers_list:
        try:
            tk = yf.Ticker(peer_ticker)
            info = tk.info or {}
            if not info.get("currentPrice") and not info.get("regularMarketPrice"):
                continue
            peers_data.append({
                "ticker":          peer_ticker,
                "name":            info.get("shortName", peer_ticker),
                "price":           info.get("currentPrice") or info.get("regularMarketPrice"),
                "market_cap":      info.get("marketCap"),
                "trailing_pe":     info.get("trailingPE"),
                "forward_pe":      info.get("forwardPE"),
                "peg_ratio":       info.get("pegRatio"),
                "revenue_growth":  info.get("revenueGrowth"),
                "gross_margins":   info.get("grossMargins"),
                "operating_margins":info.get("operatingMargins"),
                "profit_margins":  info.get("profitMargins"),
                "roe":             info.get("returnOnEquity"),
                "debt_to_equity":  info.get("debtToEquity"),
                "free_cf":         info.get("freeCashflow"),
                "ev_to_ebitda":    info.get("enterpriseToEbitda"),
            })
        except Exception:
            continue

    return peers_data


def fetch_sector_etf(sector):
    """Obtiene datos del ETF del sector para comparar rendimiento."""
    etf_ticker = SECTOR_ETFS.get(sector)
    if not etf_ticker:
        return None
    try:
        tk = yf.Ticker(etf_ticker)
        info = tk.info or {}
        hist = tk.history(period="1y")
        ytd_return = None
        if len(hist) > 0:
            ytd_return = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1)
        return {
            "ticker":     etf_ticker,
            "name":       info.get("shortName", etf_ticker),
            "price":      info.get("regularMarketPrice") or (
                float(hist["Close"].iloc[-1]) if len(hist) > 0 else None
            ),
            "ytd_return": ytd_return,
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# INDICADORES TÉCNICOS — sin cambios de lógica respecto al original
# ─────────────────────────────────────────────────────────────────────────────

def calculate_technicals(hist):
    """Calcula indicadores técnicos a partir del historial de precios."""
    close  = hist["Close"]
    volume = hist["Volume"]
    tech   = {}

    # Moving Averages
    if len(close) >= 20:
        tech["sma_20"] = float(close.rolling(20).mean().iloc[-1])
    if len(close) >= 50:
        tech["sma_50"] = float(close.rolling(50).mean().iloc[-1])
    if len(close) >= 200:
        tech["sma_200"] = float(close.rolling(200).mean().iloc[-1])

    current = float(close.iloc[-1])
    tech["price"] = current

    # YTD return
    tech["ytd_return"] = (close.iloc[-1] / close.iloc[0] - 1)

    # Trend
    above_50  = current > tech.get("sma_50",  0)
    above_200 = current > tech.get("sma_200", 0)
    if above_50 and above_200:
        tech["trend"] = "Alcista"
    elif not above_50 and not above_200:
        tech["trend"] = "Bajista"
    else:
        tech["trend"] = "Mixta/Consolidación"

    # RSI (14)
    if len(close) >= 15:
        delta = close.diff()
        gain  = delta.where(delta > 0, 0).rolling(14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        tech["rsi"] = float(rsi.iloc[-1])
        if tech["rsi"] > 70:
            tech["rsi_signal"] = "Sobrecompra 🔴"
        elif tech["rsi"] <= 30:
            tech["rsi_signal"] = "Sobreventa 🟢"
        elif tech["rsi"] <= 45:
            tech["rsi_signal"] = "Zona Francotirador 🎯"
        else:
            tech["rsi_signal"] = "Neutral 🟡"

    # MACD
    if len(close) >= 26:
        ema12       = close.ewm(span=12).mean()
        ema26       = close.ewm(span=26).mean()
        macd_line   = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        histogram   = macd_line - signal_line
        tech["macd"]        = float(macd_line.iloc[-1])
        tech["macd_signal"] = float(signal_line.iloc[-1])
        tech["macd_hist"]   = float(histogram.iloc[-1])
        tech["macd_reading"] = (
            "Alcista 🟢" if tech["macd"] > tech["macd_signal"] else "Bajista 🔴"
        )

    # Bollinger Bands
    if len(close) >= 20:
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        tech["bb_upper"] = float((sma20 + 2 * std20).iloc[-1])
        tech["bb_lower"] = float((sma20 - 2 * std20).iloc[-1])

    # Volume trend
    if len(volume) >= 20:
        avg_vol_20  = volume.rolling(20).mean().iloc[-1]
        current_vol = volume.iloc[-1]
        tech["vol_vs_avg"] = (
            (current_vol / avg_vol_20 - 1) * 100 if avg_vol_20 > 0 else 0
        )

    # Support/Resistance simples
    if len(close) >= 20:
        recent = close.tail(60) if len(close) >= 60 else close
        tech["support_1"]    = float(recent.min())
        tech["resistance_1"] = float(recent.max())
        tech["support_2"]    = float(close.min())
        tech["resistance_2"] = float(close.max())

    # 52-week position
    tech["fifty_two_position"] = None
    high = float(close.max())
    low  = float(close.min())
    if high != low:
        tech["fifty_two_position"] = (current - low) / (high - low) * 100

    return tech


# ─────────────────────────────────────────────────────────────────────────────
# A3 — BúSCADOR DE TICKER POR NOMBRE DE EMPRESA
# ─────────────────────────────────────────────────────────────────────────────

def search_ticker_by_name(query: str, max_results: int = 6) -> list:
    """
    Busca tickers por nombre de empresa usando yf.Search.

    Args:
        query:       Texto libre ("Apple", "nvidia corporation", etc.)
        max_results: Máximo de resultados a devolver.

    Returns:
        Lista de dicts con {symbol, name, exchange, type}, o [] si falla.
    """
    try:
        import yfinance as yf
        res = yf.Search(
            query,
            max_results=max_results,
            enable_fuzzy_query=True,
        )
        quotes = res.quotes or []
        result = []
        for q in quotes:
            symbol = q.get("symbol", "")
            if not symbol:
                continue
            result.append({
                "symbol":   symbol,
                "name":     q.get("shortname") or q.get("longname", ""),
                "exchange": q.get("exchange", ""),
                "type":     q.get("quoteType", ""),
            })
        return result
    except Exception:
        return []
