import pandas as pd

"""
Motor de reglas dinámico basado en régimen de mercado + calidad fundamental.
"""

RULE_SETS = {
    "CALM": {
        "requires_fundamental": True,
        "min_stars": 10,          # era 15 — imposible en mercado normal
        "indicators": {
            "primary":   [("EMA200_disc", 5.0)],  # era 15% — solo el 1% del SP500 llega
            "secondary": [],
        },
        "min_signals": 1,
        "rationale": "CALM con momentum: calidad fundamental + encima de EMA200."
    },
    
    "SLOW_BEAR": {
        "requires_fundamental": True,
        "min_stars": 8,           # añadimos filtro fundamental mínimo en bear
        "indicators": {
            "primary":   [("EMA200_disc", 8.0)],
            "secondary": [("BB_pctB", 0.3), ("Stoch_K", 35.0)],
        },
        "min_signals": 2,
        "rationale": "Bear lento: combos de osciladores maximizan edge (+6.85pp)."
    },

    "FAST_CRASH": {
        "requires_fundamental": True,
        "min_stars": 10,          # era 15 — imposible en pánico
        "indicators": {
            "primary":   [("EMA200_disc", 12.0)],  # era 15% en crash, razonable
            "secondary": [],
        },
        "min_signals": 1,
        "rationale": "Crash: solo estructural. Osciladores dan señal demasiado pronto."
    }
}

def calculate_confidence(indicators_triggered: list, regime: str, fundamental_ok: bool) -> float:
    if not indicators_triggered:
        return 0.0
        
    score = 0.0
    score += 50
    
    num_secondaries = len(indicators_triggered) - 1
    if num_secondaries >= 1:
        score += 25
    if num_secondaries >= 2:
        score += 15
    if num_secondaries >= 3:
        score += 10
        
    if fundamental_ok:
        score += 20
        
    if regime == "SLOW_BEAR":
        score += 10
        
    normalized = (score / 130.0) * 100.0
    return min(100.0, normalized)

def evaluate_signal(indicator_values: dict, regime: str, fundamental_stars: int) -> dict:
    if regime not in RULE_SETS:
        regime = "CALM"
        
    rules = RULE_SETS[regime]
    
    fundamental_ok = fundamental_stars >= rules["min_stars"]
    if rules["requires_fundamental"] and not fundamental_ok:
        return {
            "signal": False,
            "regime": regime,
            "rule_set": rules,
            "indicators_active": [],
            "indicators_triggered": [],
            "fundamental_ok": fundamental_ok,
            "confidence": 0.0,
            "rationale": f"Falla filtro fundamental ({fundamental_stars} < {rules['min_stars']})"
        }
        
    indicators_triggered = []
    
    primary_passed = False
    for ind_name, th in rules["indicators"]["primary"]:
        val = indicator_values.get(ind_name)
        if val is None or pd.isna(val): continue
        direction = 'above' if ind_name == 'EMA200_disc' else 'below'
        if direction == 'above' and val >= th:
            primary_passed = True
            indicators_triggered.append(ind_name)
        elif direction == 'below' and val <= th:
            primary_passed = True
            indicators_triggered.append(ind_name)
            
    if not primary_passed:
        return {
            "signal": False,
            "regime": regime,
            "rule_set": rules,
            "indicators_active": [],
            "indicators_triggered": [],
            "fundamental_ok": fundamental_ok,
            "confidence": 0.0,
            "rationale": "No cumple señal primaria"
        }
        
    for ind_name, th in rules["indicators"]["secondary"]:
        val = indicator_values.get(ind_name)
        if val is None or pd.isna(val): continue
        direction = 'above' if ind_name == 'EMA200_disc' else 'below'
        if direction == 'above' and val >= th:
            indicators_triggered.append(ind_name)
        elif direction == 'below' and val <= th:
            indicators_triggered.append(ind_name)
            
    num_signals = len(indicators_triggered)
    if num_signals < rules["min_signals"]:
        return {
            "signal": False,
            "regime": regime,
            "rule_set": rules,
            "indicators_active": rules["indicators"]["primary"] + rules["indicators"]["secondary"],
            "indicators_triggered": indicators_triggered,
            "fundamental_ok": fundamental_ok,
            "confidence": 0.0,
            "rationale": f"No alcanza señales mínimas ({num_signals} < {rules['min_signals']})"
        }
        
    confidence = calculate_confidence(indicators_triggered, regime, fundamental_ok)
    
    return {
        "signal": True,
        "regime": regime,
        "rule_set": rules,
        "indicators_active": rules["indicators"]["primary"] + rules["indicators"]["secondary"],
        "indicators_triggered": indicators_triggered,
        "fundamental_ok": fundamental_ok,
        "confidence": confidence,
        "rationale": rules["rationale"]
    }

def validate_intraday_signal(mc_prob_1pct: float, ema_disc: float, rsi: float, volume: float, volume_avg: float, vix: float) -> dict:
    """
    Filtro de validez de señal INTRADAY estricto.
    Las 5 condiciones deben cumplirse juntas.
    """
    reasons = []
    
    # 1. Monte Carlo P(>1%) >= 40%
    if mc_prob_1pct < 0.40:
        reasons.append(f"MC P(>1%) = {mc_prob_1pct*100:.1f}% < 40%")
        
    # 2. EMA200 alineada (precio > EMA200 -> ema_disc < 0)
    if ema_disc >= 0 or pd.isna(ema_disc):
        reasons.append(f"Precio debajo de EMA200 (ema_disc = {ema_disc:.2f}%)" if pd.notna(ema_disc) else "EMA200_disc es NaN")
        
    # 3. RSI 30-75 (ampliado)
    if not (30 <= rsi <= 75) or pd.isna(rsi):
        reasons.append(f"RSI = {rsi:.1f} fuera de rango [30, 75]" if pd.notna(rsi) else "RSI es NaN")
        
    # 4. Volumen > 50% promedio 20 días
    if volume <= (volume_avg * 0.5) or pd.isna(volume):
        reasons.append(f"Volumen = {volume} <= 50% Avg = {volume_avg*0.5}")
        
    # 5. VIX < 25
    if vix >= 25 or pd.isna(vix):
        reasons.append(f"VIX = {vix:.2f} >= 25")
        
    is_valid = len(reasons) == 0
    
    return {
        "is_valid": is_valid,
        "reasons": reasons,
        "rationale": "Válido (cumple las 5 reglas Intraday)" if is_valid else "Falla: " + ", ".join(reasons)
    }
