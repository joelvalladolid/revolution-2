import numpy as np
import scipy.optimize as sco
from typing import Dict, Any

def optimize_convex_kelly_allocation(
    expected_returns: np.ndarray, 
    covariance_matrix: np.ndarray, 
    kelly_fraction: float = 0.5, 
    max_concentration_per_asset: float = 0.40,
    asset_sectors: list = None,
    sector_cap: float = 0.25
) -> Dict[str, Any]:
    """
    Optimizador convexo estricto para despliegue de capital institucional.
    Calcula la curva de máxima eficiencia de crecimiento geométrico de portafolio.
    """
    n_assets = len(expected_returns)
    
    def _negative_kelly_utility(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> float:
        portfolio_return = np.dot(weights, mu)
        portfolio_variance = np.dot(weights.T, np.dot(cov, weights))
        
        adjusted_variance = portfolio_variance / kelly_fraction
        return float((0.5 * adjusted_variance) - portfolio_return)

    constraints = [
        {'type': 'ineq', 'fun': lambda w: 1.0 - np.sum(w)}
    ]
    
    if asset_sectors is not None and len(asset_sectors) == n_assets:
        unique_sectors = set(asset_sectors)
        for sector in unique_sectors:
            if sector == 'Unknown' or sector is None:
                continue
            constraints.append({
                'type': 'ineq',
                'fun': lambda w, sec=sector: sector_cap - sum(w[i] for i, s in enumerate(asset_sectors) if s == sec)
            })
    
    bounds = tuple((0.0, max_concentration_per_asset) for _ in range(n_assets))
    
    initial_weights = np.array(n_assets * [1.0 / n_assets])
    
    optimization_output = sco.minimize(
        fun=_negative_kelly_utility,
        x0=initial_weights,
        args=(expected_returns, covariance_matrix),
        method='SLSQP',
        bounds=bounds,
        constraints=constraints,
        options={'ftol': 1e-9, 'disp': False, 'maxiter': 1000}
    )
    
    if not optimization_output.success:
        return {
            'status': 'FAILED_CONVERGENCE',
            'error_message': optimization_output.message,
            'optimal_weights': initial_weights
        }
        
    stabilized_weights = np.round(optimization_output.x, 6)
    
    return {
        'status': 'SUCCESS',
        'message': 'Cúspide convexa de Kelly alcanzada estocásticamente.',
        'optimal_weights': stabilized_weights
    }
