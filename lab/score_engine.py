import numpy as np
from typing import Dict, Union, Any

class MasterScoreNormalizer:
    """
    Agente algorítmico responsable de la asignación del Score Maestro (Fase 2).
    Aplica una topología de escalado Min-Max seguida de funciones de penalización asimétrica.
    """
    
    def __init__(self):
        # Definición topológica del ponderador maestro (Suma exacta = 1.0)
        self.weights = {
            'win_rate': 0.20,
            'ev': 0.20,
            'profit_factor': 0.12,
            'sharpe_90d': 0.12,
            'sortino': 0.08,
            'edge_pp': 0.10,
            'consistency': 0.10,
            'calmar': 0.08
        }
    
    @staticmethod
    def _min_max_transform(val: float, val_min: float, val_max: float) -> float:
        """
        Escalador Min-Max atómico y robusto.
        Evade las divisiones por cero devolviendo la mediana distributiva ante varianzas planas.
        Aplica un clip rígido a la salida vectorial para estabilizar desviaciones por fuera de la muestra.
        """
        if val_max <= val_min:
            return 50.0 
            
        scaled = ((val - val_min) / (val_max - val_min)) * 100.0
        return float(np.clip(scaled, 0.0, 100.0))

    def compute_strategy_score(
        self, 
        metrics: Dict[str, float], 
        population_boundaries: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inferencia del rendimiento normalizado con multiplicadores correctivos asimétricos.
        
        Args:
            metrics: Evaluaciones matemáticas crudas de la estrategia en curso.
            population_boundaries: Extremos globales in/out-sample requeridos para fijar
                                   el límite inferior y superior del espectro algorítmico.
                                   Esquema: {'ev': {'min': -5.0, 'max': 12.0},...}
        """
        base_score = 0.0
        
        # 1. Integración Aritmética de Base de Datos Ponderada
        for key, weight in self.weights.items():
            raw_val = metrics.get(key, 0.0)
            pop_min = population_boundaries.get(key, {}).get('min', 0.0)
            pop_max = population_boundaries.get(key, {}).get('max', raw_val + 1e-9)
            
            normalized_component = self._min_max_transform(raw_val, pop_min, pop_max)
            base_score += (normalized_component * weight)
            
        final_score = base_score
        penalties_log = []
        disqualified_flag = False
        
        # 2. Vectores de Aniquilación Estructural (Penalidades Duras) 
        
        # Discriminador Letal: Expectativa Matemática Deficitaria
        if metrics.get('ev', 0.0) <= 0:
            final_score *= 0.0
            disqualified_flag = True
            penalties_log.append('EV <= 0')
            
        # Perfil de Riesgo: Degradación por insuficiencia de tasa de acierto pura
        if metrics.get('win_rate', 0.0) < 0.52:
            final_score *= 0.3
            penalties_log.append('Win Rate < 52%')
            
        # Aislamiento Estadístico: Invalidación por ruido estocástico masivo (H0 no rechazada)
        if metrics.get('p_value', 1.0) > 0.05:
            final_score *= 0.5
            penalties_log.append('P-Value > 0.05')
            
        # Concentración de Cola Larga: Sucesión ininterrumpida destructiva de pérdidas
        if metrics.get('max_consec_loss', 0) >= 10:
            final_score *= 0.7
            penalties_log.append('Racha Negativa >= 10')
            
        # Insuficiencia Muestral: Prevención de Sobreajuste (Overfitting) en base estrecha
        if metrics.get('n_signals', 0) < 50:
            final_score *= 0.4
            penalties_log.append('Carencia de Señales (n < 50)')
            
        # Condición Extremosa: Fragilidad estructural ante picos de volatilidad (VIX)
        if metrics.get('edge_crash', 0.0) < -3.0:
            final_score *= 0.6
            penalties_log.append('Caída de Borde Crítico < -3.0pp')
            
        # 3. Prima Condicional de Estabilidad Algorítmica (Bonus Factor) 
        is_all_weather = (
            metrics.get('edge_bull', 0.0) > 0 and 
            metrics.get('edge_bear', 0.0) > 0 and 
            metrics.get('edge_crash', 0.0) > 0
        )
        
        if is_all_weather and not disqualified_flag:
            final_score *= 1.15
            penalties_log.append('All-Weather Bonus [Impulso +15%]')
            
        return {
            'final_score': float(np.clip(final_score, 0.0, 100.0)),
            'base_score': float(np.clip(base_score, 0.0, 100.0)),
            'is_disqualified': disqualified_flag,
            'audit_trail': penalties_log
        }
