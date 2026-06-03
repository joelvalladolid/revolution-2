import pandas as pd

"""
Motor de reglas dinámico basado en régimen de mercado + calidad fundamental.
"""

RULE_SETS = {
    "CALM": {
        "requires_fundamental": True,
        "min_stars": 15,
        "indicators": {
            "primary":   [("EMA200_disc", 15.0)],
            "secondary": [],
        },
        "min_signals": 1,
        "rationale": "CALM sin calidad = cuchillo. CALM con calidad = oportunidad táctica."
    },
    
    "SLOW_BEAR": {
        "requires_fundamental": False,
        "min_stars": 0,
        "indicators": {
            "primary":   [("EMA200_disc", 12.0)],
            "secondary": [("BB_pctB", 0.2), ("Stoch_K", 20.0)],
        },
        "min_signals": 2,
        "rationale": "Bear lento: combos de osciladores maximizan edge (+6.85pp)."
    },

    "FAST_CRASH": {
        "requires_fundamental": True,
        "min_stars": 15,
        "indicators": {
            "primary":   [("EMA200_disc", 15.0)],
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
