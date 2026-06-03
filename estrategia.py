import pandas_ta as ta
import pandas as pd
import numpy as np

SECTOR_EXEMPTIONS = {
    "Financial Services": ["debt_equity_check"],
    "Real Estate":        ["debt_equity_check", "fcf_check"],
    "Utilities":          ["debt_equity_check"],
}

def check_goodwill_intangibles(data: dict) -> bool | None:
    """
    Retorna True si (Goodwill + Intangibles) / Total Assets < 40% (60% para Tech).
    Retorna None si faltan datos (no penaliza).
    """
    goodwill = data.get("goodwill")
    intangibles = data.get("intangible_assets")
    total_assets = data.get("total_assets")
    sector = data.get("sector", "")

    if total_assets is None or total_assets <= 0:
        return None
        
    gw = goodwill or 0
    ia = intangibles or 0
    ratio = (gw + ia) / total_assets
    
    limite = 0.40
    if sector == "Technology":
        limite = 0.60
    elif sector == "Financial Services":
        limite = 0.65
        
    return ratio < limite

def check_accruals_ratio(data: dict) -> bool | None:
    """
    Accruals Ratio = (Net Income - Operating Cash Flow) / Total Assets
    Aprueba si ratio < 0.07 (beneficio respaldado por caja real).
    Retorna None si faltan datos.
    """
    net_income = data.get("net_income")
    op_cf = data.get("operating_cf")
    total_assets = data.get("total_assets")

    if net_income is None or op_cf is None or total_assets is None or total_assets <= 0:
        return None

    accruals = (net_income - op_cf) / total_assets
    return accruals < 0.07

def check_short_term_debt(data: dict) -> bool | None:
    """
    Short Term Debt / Total Debt < 35%.
    Retorna None si faltan datos.
    """
    short_debt = data.get("short_term_debt")
    total_debt = data.get("total_debt")

    if short_debt is None or total_debt is None or total_debt <= 0:
        return None

    ratio = short_debt / total_debt
    return ratio < 0.35

def apply_sector_exemptions(verdicts: list, sector: str) -> list:
    """
    Marca como None (no penaliza ni bonifica) los checks exentos para el sector.
    """
    exentos = SECTOR_EXEMPTIONS.get(sector, [])
    resultado = []
    for nombre, valor in verdicts:
        if "Deuda/Equity" in nombre and "debt_equity_check" in exentos:
            resultado.append((nombre + " [EXENTO]", None))
        elif "FCF" in nombre and "fcf_check" in exentos:
            resultado.append((nombre + " [EXENTO]", None))
        else:
            resultado.append((nombre, valor))
    return resultado

def calcular_indicadores_tecnicos(df):
    """
    Calcula los indicadores técnicos sobre un DataFrame histórico (OHLCV).
    Usado principalmente por el motor de backtesting para tener la película completa.
    """
    # VWAP 20 días
    if 'Volume' in df.columns:
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VP'] = df['Typical_Price'] * df['Volume']
        df['VWAP_20'] = df['VP'].rolling(window=20).sum() / df['Volume'].rolling(window=20).sum()
    else:
        df['VWAP_20'] = df['Close']
        
    df['SMA_20'] = ta.sma(df['Close'], length=20)
    df['SMA_50'] = ta.sma(df['Close'], length=50)
    df['SMA_200'] = ta.sma(df['Close'], length=200)
    df['RSI_14'] = ta.rsi(df['Close'], length=14)
    
    # Soporte Dinámico (mínimo de 20 días)
    df['Soporte_Dinamico'] = df['Low'].rolling(window=20).min()
    
    # Percentil 52 semanas (posición relativa)
    low_52 = df['Low'].rolling(window=252).min()
    high_52 = df['High'].rolling(window=252).max()
    df['Percentil_52'] = ((df['Close'] - low_52) / (high_52 - low_52)) * 100
    
    return df

def evaluar_protocolo_etf(precio, vwap, rsi, sma50, sma200, percentil_52, soportes=None, soporte_dinamico=None):
    """
    Evalúa las 3 reglas institucionales para un ETF o Índice.
    Retorna un diccionario con los estados y mensajes.
    """
    res = {}
    
    # Regla 1: Tendencia (SMA 50 > SMA 200)
    res['r1_ok'] = bool(sma50 is not None and sma200 is not None and sma50 > sma200)
    res['r1_label'] = f"SMA 50: ${sma50:,.2f} | SMA 200: ${sma200:,.2f}" if (sma50 and sma200) else "Métricas N/A"
    res['r1_hint'] = "SMA 50 debe ser mayor a SMA 200"
    
    # Regla 2: Fuerza del Ciclo (Percentil > 60)
    res['r2_ok'] = bool(percentil_52 is not None and percentil_52 > 60)
    res['r2_label'] = f"Percentil: {percentil_52:.1f}%" if percentil_52 is not None else "N/A"
    res['r2_hint'] = "Precio en el percentil > 60%"
    
    # Regla 3: Timing (Precio < VWAP, RSI <= 30, Soporte <= 5%)
    vwap_ok = bool(vwap is not None and precio < vwap)
    vwap_dist = ((vwap - precio) / precio * 100) if (vwap is not None and precio) else 0
    vwap_label = f"Descuento: {vwap_dist:+.1f}%" if vwap is not None else "VWAP N/A"
    
    r3a_ok = bool(rsi is not None and rsi <= 30)
    r3a_label = f"RSI: {rsi:.1f}" if rsi is not None else "RSI: N/A"
    
    # Lógica de Soporte
    r3b_ok = False
    r3b_label = "Sin niveles de soporte"
    
    if soportes and len(soportes) > 0:
        dists = [abs(precio - s) / s * 100 for s in soportes if s > 0]
        if dists:
            closest_dist = min(dists)
            closest_sup = soportes[dists.index(closest_dist)]
            r3b_ok = bool(closest_dist <= 5.0)
            if r3b_ok:
                r3b_label = f"Precio a {closest_dist:.1f}% del soporte (${closest_sup:,.2f})"
            else:
                r3b_label = f"El soporte más cercano (${closest_sup:,.2f}) está a {closest_dist:.1f}%"
    elif soporte_dinamico is not None and soporte_dinamico > 0:
        dist = abs(precio - soporte_dinamico) / soporte_dinamico * 100
        r3b_ok = bool(dist <= 5.0)
        r3b_label = f"A {dist:.1f}% del soporte dinámico (${soporte_dinamico:,.2f})"

    res['vwap_ok'] = vwap_ok
    res['vwap_label'] = vwap_label
    res['r3a_ok'] = r3a_ok
    res['r3a_label'] = r3a_label
    res['r3b_ok'] = r3b_ok
    res['r3b_label'] = r3b_label
    
    res['r3_ok'] = vwap_ok and r3a_ok and r3b_ok
    res['r3_hint'] = "Precio < VWAP, RSI ≤ 30 y a ≤5% de soporte"
    
    res['all_green'] = res['r3_ok']
    
    res.setdefault('r1_ok', False)
    res.setdefault('r1_label', '—')
    res.setdefault('r1_hint', '')
    res.setdefault('r2_ok', False)
    res.setdefault('r2_label', '—')
    res.setdefault('r2_hint', '')
    res.setdefault('r3_ok', False)
    res.setdefault('r3_label', '—')
    res.setdefault('r3_hint', '')
    res.setdefault('all_green', False)
    res.setdefault('passed', 0)
    res.setdefault('total', 0)
    res.setdefault('dealbreaker', False)
    res.setdefault('perfil_usado', 'A')

    return res

def evaluar_protocolo_accion(data, tech, tnx_yield, price, soportes=None, profile='B', scan_mode='DIP'):
    """
    Evalúa las reglas fundamentales y la Trinidad técnica usando el perfil indicado.
    Perfil B: Balanceado (F11_CashIntRSI)
    Perfil C: Alta Convicción (F21_UltraQ)
    """
    res = {}
    verdicts = []
    
    # Configuración de Perfil
    if profile == 'C':
        min_stars = 15
        cash_coverage_min = 1.0
        interest_coverage_min = 8
        peg_max = 2.5 # Límite estándar
        rsi_threshold = 33
        support_pct = 7.0
        ema200_req = 10.0 # Precio debe estar 10% bajo EMA 200
    else: # Default B
        min_stars = 15
        cash_coverage_min = 1.0
        interest_coverage_min = 8
        peg_max = 999.0 # Sin restricción de PEG
        rsi_threshold = 45
        support_pct = 7.0
        ema200_req = 0.0 # No requerido

    desc = data.get('description', '')
    
    cash_val = data.get('total_cash', 0) or 0
    debt_val = data.get('total_debt', 0) or 0
    
    ebitda = data.get('ebitda') or 0
    interest_expense = data.get('interest_expense') or (debt_val * 0.05)
    debt_to_equity = (data.get('debt_to_equity') or 0) / 100.0
    
    interest_coverage = ebitda / max(interest_expense, 1)
    
    # Evaluar Candado de Deuda Calidad (Cash & Interest Coverage)
    cash_coverage = cash_val / max(debt_val, 1)
    debt_is_quality = (cash_coverage >= cash_coverage_min) and (interest_coverage >= interest_coverage_min)
    
    if data.get('total_cash') is not None and data.get('total_debt') is not None:
        if cash_val < debt_val:
            if (interest_coverage > 8) and (debt_to_equity < 2.0):
                cash_gt_debt = False
            else:
                cash_gt_debt = False
                res['profitable'] = False # Forzamos kill switch si es deuda riesgosa
        else:
            cash_gt_debt = True
    else:
        cash_gt_debt = (data.get('current_ratio', 0) > 1.2)
        
    profitable = (data.get('gross_margins', 0) > 0 and data.get('profit_margins', 0) > 0)
    if not debt_is_quality:
        res['profitable'] = False # Filtro de calidad estricto del perfil

    # Regla 1: Negocio comprensible
    verdicts.append(("Negocio comprensible", bool(desc)))
    
    # Regla 2: Cash > Deuda
    verdicts.append(("Cash > Deuda (o Estratégica)", cash_gt_debt))
    
    # Regla 3: Rentabilidad
    verdicts.append(("Rentabilidad", profitable))
    
    # Regla 4: PEG
    limite_peg = 2.5 if data.get('sector') == 'Technology' else 1.5
    if tnx_yield and tnx_yield > 4.5: limite_peg = 1.5 if data.get('sector') == 'Technology' else 1.0
    if peg_max == 999.0: limite_peg = 999.0 # Perfil B anula el límite de PEG
    
    peg_val = data.get('peg_ratio')
    earnings_growth_val = data.get('earnings_growth')
    earnings_positive = earnings_growth_val is not None and earnings_growth_val > 0
    peg_ok = peg_val is not None and 0 < peg_val < limite_peg and earnings_positive
    if scan_mode != 'MOMENTUM':
        verdicts.append((f"0 < PEG < {limite_peg} (+ EPS>0)", peg_ok if peg_val is not None else None))
    
    # Regla 5: Revenue creciendo
    growth_ok = data.get('revenue_growth') is not None and data['revenue_growth'] > 0
    verdicts.append(("Revenue creciendo", growth_ok if data.get('revenue_growth') is not None else None))
    
    # Regla 6: EPS positivo y mejorando (o REIT)
    if data.get('sector') == 'Real Estate':
        verdicts.append(("REIT (EPS N/A)", True))
    else:
        eps_growing = data.get('forward_eps') is not None and data.get('trailing_eps') is not None and data['forward_eps'] > data['trailing_eps'] and data['forward_eps'] > 0
        verdicts.append(("EPS positivo y mejorando", bool(eps_growing) if data.get('forward_eps') is not None else None))
        
        fcf_yield_ok = data.get('fcf_yield') is not None and data['fcf_yield'] > 0.03
        fcf_growth_ok = data.get('fcf_growth') is not None and data['fcf_growth'] > 0 and data.get('free_cf') is not None and data['free_cf'] > 0
        fcf_ok = fcf_yield_ok or fcf_growth_ok
        if scan_mode != 'MOMENTUM':
            verdicts.append(("FCF Fuerte (>0 y Yield>3% o Crec>0)", fcf_ok if data.get('fcf_yield') is not None else None))
        
    # Regla 8: Euforia extrema
    en_maximos = tech.get('fifty_two_position') is not None and tech['fifty_two_position'] > 90
    sobrecompra = tech.get('rsi') is not None and tech['rsi'] > 75
    not_euphoria = not (en_maximos and sobrecompra)
    if scan_mode != 'MOMENTUM':
        verdicts.append(("No en euforia extrema", not_euphoria if tech.get('fifty_two_position') is not None else None))

    # Filtros Anti-Trampa de Valor
    rev_g = data.get('revenue_growth_ttm') if data.get('revenue_growth_ttm') is not None else data.get('revenue_growth')
    fcf_g = data.get('fcf_growth_ttm')     if data.get('fcf_growth_ttm')     is not None else data.get('fcf_growth')
    if rev_g is not None and fcf_g is not None:
        op_leverage_ok = fcf_g > rev_g
        verdicts.append(("Apalancamiento Op. Positivo (FCF%>Rev%)", op_leverage_ok))
    else:
        verdicts.append(("Apalancamiento Op. Positivo (FCF%>Rev%)", None))

    if earnings_growth_val is not None:
        verdicts.append(("Crec. Earnings Positivo (EPS>0%)", earnings_positive))
    else:
        verdicts.append(("Crec. Earnings Positivo (EPS>0%)", None))

    pm = data.get('profit_margins')
    om = data.get('operating_margins')
    if pm is not None and om is not None:
        margin_health_ok = pm >= (om * 0.4) if om > 0 else (pm > 0)
        verdicts.append(("Márgenes Saludables (Neto≥40% Op.)", margin_health_ok))
    else:
        verdicts.append(("Márgenes Saludables (Neto≥40% Op.)", None))

    # Regla 12: Anti-Dilución (Shares Growth <= 2%)
    shares_g = data.get('shares_growth')
    dilucion_ok = (shares_g <= 0.02) if shares_g is not None else False
    verdicts.append(("No Dilución (Acciones ≤ +2%)", dilucion_ok))
    
    # Regla 13: Eficiencia Capital (ROIC o ROE > 10%)
    roic = data.get('roic')
    roe = data.get('roe')
    roa = data.get('roa')
    val_eff = roic if roic is not None else (roe if roe is not None else roa)
    eff_ok = (val_eff > 0.10) if val_eff is not None else False
    verdicts.append(("Eficiencia Capital (ROIC/ROE > 10%)", eff_ok))

    # Reglas Nuevas
    extra_checks = [
        ("Goodwill+Intangibles < 40% (60% Tech)", check_goodwill_intangibles(data)),
        ("Accruals Ratio < 0.07", check_accruals_ratio(data)),
        ("Deuda CP < 35% Total", check_short_term_debt(data)),
    ]
    extra_checks = apply_sector_exemptions(extra_checks, data.get('sector', ''))
    verdicts.extend(extra_checks)

    # Conteo
    passed = sum(1 for _, r in verdicts if r)
    total  = sum(1 for _, r in verdicts if r is not None)
    
    vwap = data.get('vwap_actual')
    rsi = tech.get('rsi')
    sma200 = tech.get('sma_200')
    
    # ── Tarjeta 1: Calidad Estructural
    pasa_estrellas = passed >= min_stars if total >= min_stars else False
    candados_ok = dilucion_ok and eff_ok
    
    res['r1_ok'] = pasa_estrellas and candados_ok and res.get('profitable', True)
    if not res.get('profitable', True):
        res['r1_label'] = f"{passed}/{total} (Deuda Riesgo / Cobertura Baja)"
        res['r1_hint'] = f"Fallo Absoluto: CashCov<{cash_coverage_min} o IntCov<{interest_coverage_min}"
    elif pasa_estrellas and not candados_ok:
        res['r1_label'] = f"{passed}/{total} (Fallo en Candado)"
        res['r1_hint'] = "Falla por: Dilución o Eficiencia"
    else:
        res['r1_label'] = f"{passed}/{total} checks superados"
        res['r1_hint'] = f"Mínimo {min_stars}/{total} + Candados absolutos"
    
    # ── Tarjeta 2: Timing VWAP & EMA200
    r2_ok = bool(vwap is not None and price < vwap)
    ema200_dist = ((price - sma200) / sma200 * 100) if (sma200 and price) else 0
    res['ema200_dist'] = ema200_dist
    
    if ema200_req > 0:
        # Perfil C exige EMA200 discount
        r2_ok = r2_ok and (sma200 is not None) and (ema200_dist <= -ema200_req)
        
    res['r2_ok'] = r2_ok
    if vwap:
        vwap_dist = (vwap - price) / price * 100
        res['r2_label'] = f"VWAP: {vwap_dist:+.1f}% | EMA200: {ema200_dist:+.1f}%"
    else:
        res['r2_label'] = f"VWAP N/A | EMA200: {ema200_dist:+.1f}%"
        res['r2_ok'] = False
        
    if ema200_req > 0:
        res['r2_hint'] = f"Precio < VWAP 20d y {ema200_req}% bajo EMA 200"
    else:
        res['r2_hint'] = "Precio debe estar BAJO el VWAP 20d"
    
    # ── Tarjeta 3: Confirmación Técnica
    r3a_ok = bool(rsi is not None and rsi <= rsi_threshold)
    res['r3a_label']= f"RSI: {rsi:.1f}" if rsi else "RSI: N/A"
    
    r3b_ok = False
    res['r3b_label'] = "Sin niveles de soporte"
    if soportes and len(soportes) > 0:
        dists = [abs(price - s) / s * 100 for s in soportes if s > 0]
        if dists:
            closest_dist = min(dists)
            closest_sup = soportes[dists.index(closest_dist)]
            r3b_ok = bool(closest_dist <= support_pct)
            if r3b_ok:
                res['r3b_label'] = f"Precio a {closest_dist:.1f}% del soporte (${closest_sup:,.2f})"
            else:
                res['r3b_label'] = f"El soporte más cercano está a {closest_dist:.1f}%"
    
    res['r3a_ok'] = r3a_ok
    res['r3b_ok'] = r3b_ok
    res['r3_ok'] = r3a_ok and r3b_ok
    res['r3_hint'] = f"RSI ≤ {rsi_threshold} y precio a ≤{support_pct}% de soporte"
    
    res['all_green'] = res.get('r1_ok', False) and res.get('r2_ok', False) and res.get('r3_ok', False)
    
    res['verdicts'] = verdicts
    res['passed'] = passed
    res['total'] = total
    res['profitable'] = res.get('profitable', True)
    res['peg_ratio'] = data.get('peg_ratio')
    res['cash_coverage'] = cash_coverage
    res['interest_coverage'] = interest_coverage
    res['model_name'] = f"Perfil {profile}"
    
    res.setdefault('r1_ok', False)
    res.setdefault('r1_label', '—')
    res.setdefault('r1_hint', '')
    res.setdefault('r2_ok', False)
    res.setdefault('r2_label', '—')
    res.setdefault('r2_hint', '')
    res.setdefault('r3_ok', False)
    res.setdefault('r3_label', '—')
    res.setdefault('r3_hint', '')
    res.setdefault('all_green', False)
    res.setdefault('passed', 0)
    res.setdefault('total', 0)
    res.setdefault('dealbreaker', False)
    res.setdefault('perfil_usado', profile)
    
    return res
