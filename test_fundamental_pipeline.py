# -*- coding: utf-8 -*-
"""
test_fundamental_pipeline.py
Replica EXACTA de la logica de fundamental en app.py - sin Streamlit.
Corre: python test_fundamental_pipeline.py
"""
import sys, os
# Fix encoding para Windows PowerShell
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import datetime

# ---- Imports del sistema (igual que app.py) ----------------------------------
print("Cargando modulos...")

try:
    from estrategia import evaluar_protocolo_accion
    ESTRAT_OK = True
    print("[OK] estrategia.py cargado")
except ImportError as e:
    print(f"[ERR] estrategia.py: {e}")
    ESTRAT_OK = False

try:
    from data_fetcher import fetch_stock_data
    FETCHER_OK = True
    print("[OK] data_fetcher.py cargado")
except ImportError as e:
    print(f"[ERR] data_fetcher.py: {e}")
    FETCHER_OK = False

if not (ESTRAT_OK and FETCHER_OK):
    print("FATAL: modulos criticos no disponibles")
    sys.exit(1)

try:
    from data.fetcher import fetch_history
    from lab.indicators import ema_discount, rsi as calc_rsi
    TECH_AVAILABLE = True
    print("[OK] lab/indicators + data/fetcher cargados")
except ImportError as e:
    print(f"[WARN] Modulos tecnicos no disponibles: {e}")
    TECH_AVAILABLE = False

print()

# ---- Constantes (igual que app.py) ------------------------------------------
THRESHOLDS_BY_REGIME = {
    "CALM":       {"EMA200_disc": 5.0},
    "SLOW_BEAR":  {"EMA200_disc": 8.0},
    "FAST_CRASH": {"EMA200_disc": 12.0},
}

REGIME          = "CALM"
TNX_YIELD       = 4.49
MIN_MOM_STARS   = 5
EXPECTED_CHECKS = 10

SEPARATOR = "=" * 65

# ---- get_fundamental_stars: COPIA EXACTA de app.py -------------------------
def get_fundamental_stars(ticker, tnx_yield, current_price,
                           df=None, ind_vals=None, scan_mode='DIP'):
    try:
        data = fetch_stock_data(ticker)

        tech_real = {}
        if ind_vals:
            tech_real['rsi'] = ind_vals.get('RSI', 50)

        if df is not None and not df.empty:
            tech_real['sma_200'] = df['Close'].rolling(window=200).mean().iloc[-1]
            low_52  = df['Low'].rolling(window=252).min().iloc[-1]
            high_52 = df['High'].rolling(window=252).max().iloc[-1]
            if high_52 > low_52:
                tech_real['fifty_two_position'] = ((current_price - low_52) / (high_52 - low_52)) * 100
            else:
                tech_real['fifty_two_position'] = 50
        else:
            tech_real['sma_200'] = current_price
            tech_real['fifty_two_position'] = 50

        res = evaluar_protocolo_accion(
            data, tech_real, tnx_yield, current_price,
            soportes=[], profile='B', scan_mode=scan_mode
        )

        passed = int(res.get('passed', 0))
        total  = int(res.get('total', 1))

        # Normalizacion EXACTA de app.py
        if total >= EXPECTED_CHECKS:
            normalized = passed
        elif total >= 3:
            normalized = round((passed / total) * EXPECTED_CHECKS)
        else:
            normalized = 0

        return normalized, passed, total, res.get('verdicts', []), data
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 0, 0, 0, [], {}


# ---- analyze_ticker: replica del flujo de app.py ----------------------------
def analyze_ticker(ticker, regime="CALM", scan_mode="MOMENTUM"):
    print(f"\n{SEPARATOR}")
    print(f"  TICKER: {ticker}  |  REGIMEN: {regime}  |  MODO: {scan_mode}")
    print(SEPARATOR)

    df = None
    ind_vals = None
    price = 100.0

    # 1. Datos tecnicos
    if TECH_AVAILABLE:
        end   = datetime.date.today().strftime('%Y-%m-%d')
        start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')
        try:
            result = fetch_history([ticker], start=start, end=end)
            df_raw = result.get(ticker)
            if df_raw is None or len(df_raw) < 252:
                n = len(df_raw) if df_raw is not None else 0
                print(f"  [WARN] Historico insuficiente ({n} dias). Usando df=None.")
            else:
                df = df_raw.copy()
                df['EMA200_disc'] = ema_discount(df)
                df['RSI']         = calc_rsi(df)
                last     = df.iloc[-1]
                ema_disc = float(last['EMA200_disc']) if pd.notna(last['EMA200_disc']) else float('nan')
                rsi_val  = float(last['RSI'])          if pd.notna(last['RSI'])          else float('nan')
                price    = float(last['Close'])
                ind_vals = {'EMA200_disc': ema_disc, 'RSI': rsi_val}

                print(f"\n  [TECNICO]")
                print(f"     Precio:      ${price:.2f}")
                print(f"     EMA200 disc: {ema_disc:+.2f}%  (negativo = encima del EMA200)")
                print(f"     RSI:         {rsi_val:.1f}")

                # Filtros de app.py
                if scan_mode == "MOMENTUM":
                    primary_met = not pd.isna(ema_disc) and (-50.0 <= ema_disc <= 0.0)
                    rsi_ok      = not pd.isna(rsi_val)  and (40 <= rsi_val <= 75)
                    vol_avg     = df['Volume'].tail(20).mean() if 'Volume' in df.columns else 0
                    vol_ok      = vol_avg > 300000

                    print(f"\n  [FILTROS MOMENTUM]")
                    print(f"     EMA en -50 a 0  : {'SI' if primary_met else 'NO'}  [{ema_disc:+.2f}%]")
                    print(f"     RSI 40-75       : {'SI' if rsi_ok else 'NO'}  [{rsi_val:.1f}]")
                    print(f"     Volumen >300k   : {'SI' if vol_ok else 'NO'}  [{vol_avg:,.0f}]")

                    if not primary_met:
                        print(f"  [BLOQUEADO] No pasa EMA. Fin.")
                        return False
        except Exception as e:
            import traceback
            print(f"  [WARN] Error tecnico: {e}")
            traceback.print_exc()

    # 2. Fundamental
    print(f"\n  [FUNDAMENTAL] Llamando get_fundamental_stars...")
    normalized, passed, total, verdicts, raw_data = get_fundamental_stars(
        ticker, TNX_YIELD, price, df=df, ind_vals=ind_vals, scan_mode=scan_mode
    )

    # Datos que Yahoo devolvio
    print(f"\n  [DATOS YAHOO - campos clave]")
    campos = [
        ('description',     'Descripcion'        ),
        ('total_cash',      'Cash total'         ),
        ('total_debt',      'Deuda total'        ),
        ('current_ratio',   'Current ratio'      ),
        ('gross_margins',   'Margen bruto'       ),
        ('profit_margins',  'Margen neto'        ),
        ('revenue_growth',  'Crec. revenue'      ),
        ('earnings_growth', 'Crec. earnings'     ),
        ('roe',             'ROE'                ),
        ('roic',            'ROIC'               ),
        ('shares_growth',   'Crec. acciones'     ),
        ('forward_eps',     'Forward EPS'        ),
        ('trailing_eps',    'Trailing EPS'       ),
        ('ebitda',          'EBITDA'             ),
        ('revenue_growth_ttm', 'Rev growth TTM' ),
        ('fcf_growth_ttm',     'FCF growth TTM' ),
    ]
    for key, label in campos:
        val = raw_data.get(key)
        if key == 'description':
            if not val:
                val_str = "[VACIO - None o '']"
            else:
                val_str = f"OK ({len(val)} chars)"
        elif val is None:
            val_str = "None (sin dato)"
        elif isinstance(val, float):
            val_str = f"{val:,.4f}"
        else:
            val_str = str(val)
        print(f"     {label:<22}: {val_str}")

    # Verdicts
    print(f"\n  [VERDICTS] {passed} passed / {total} evaluados")
    for nombre, status in verdicts:
        if status is True:
            mark = "[PASS]"
        elif status is False:
            mark = "[FAIL]"
        else:
            mark = "[N/A ]"
        print(f"     {mark} {nombre}")

    # Resultado
    print(f"\n  [RESULTADO FINAL]")
    print(f"     passed raw    : {passed}")
    print(f"     total checks  : {total}")
    print(f"     normalized    : {normalized}/10")
    print(f"     min requerido : {MIN_MOM_STARS}/10")

    pasa = normalized >= MIN_MOM_STARS
    if pasa:
        print(f"     => PASA FUNDAMENTAL [SI]")
    else:
        print(f"     => PASA FUNDAMENTAL [NO]  (faltan {MIN_MOM_STARS - normalized} estrellas)")

    return pasa


# ---- Main -------------------------------------------------------------------
if __name__ == "__main__":
    print()
    print(SEPARATOR)
    print("  DIAGNOSTICO PIPELINE FUNDAMENTAL - FRANCOTIRADOR")
    print(SEPARATOR)
    print(f"  Regimen: {REGIME} | Modo: MOMENTUM | Min stars: {MIN_MOM_STARS}/10")
    print(f"  TNX Yield: {TNX_YIELD}%")
    print()

    # Tickers de prueba — mix de sectores y calidades conocidas
    TEST_TICKERS = ["AAPL", "MSFT", "NVDA", "JPM", "UNH"]

    resultados = {}
    for ticker in TEST_TICKERS:
        try:
            r = analyze_ticker(ticker, regime=REGIME, scan_mode="MOMENTUM")
            resultados[ticker] = r
        except Exception as e:
            import traceback
            print(f"\n[ERROR] {ticker}: {e}")
            traceback.print_exc()
            resultados[ticker] = None

    # Resumen
    print(f"\n\n{SEPARATOR}")
    print("  RESUMEN")
    print(SEPARATOR)
    pasaron  = [t for t, r in resultados.items() if r is True]
    fallaron = [t for t, r in resultados.items() if r is False]
    errores  = [t for t, r in resultados.items() if r is None]
    print(f"  Pasaron  : {pasaron  or 'ninguno'}")
    print(f"  Fallaron : {fallaron or 'ninguno'}")
    print(f"  Errores  : {errores  or 'ninguno'}")
    print()
