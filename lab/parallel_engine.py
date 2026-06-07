import multiprocessing as mp
import pandas as pd
import numpy as np
import logging
import gc
from typing import List, Dict, Any, Tuple
from itertools import product

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_SHARED_HISTORICAL_DATA: pd.DataFrame = pd.DataFrame()
_SHARED_VIX_REGIME: pd.Series = pd.Series(dtype=str)

def _pool_worker_initializer(shared_df: pd.DataFrame, vix_regime: pd.Series = None) -> None:
    global _SHARED_HISTORICAL_DATA, _SHARED_VIX_REGIME
    _SHARED_HISTORICAL_DATA = shared_df
    if vix_regime is not None:
        _SHARED_VIX_REGIME = vix_regime
    gc.disable()

def _strategy_evaluation_task(params: Dict[str, Any]) -> Dict[str, Any]:
    global _SHARED_HISTORICAL_DATA
    
    ticker = params.get('ticker')
    try:
        # Check if ticker is in columns
        # To handle both multi-index and flat columns safely
        is_multi = isinstance(_SHARED_HISTORICAL_DATA.columns, pd.MultiIndex)
        if is_multi:
            # yfinance MultiIndex is usually (PriceType, Ticker)
            cols = _SHARED_HISTORICAL_DATA.columns.get_level_values(0).unique()
            if ticker in cols:
                ticker_data = _SHARED_HISTORICAL_DATA[ticker]
            else:
                raise KeyError(f"Identificador bursátil {ticker} ausente en el bloque de memoria.")
        else:
            if ticker in _SHARED_HISTORICAL_DATA.columns:
                ticker_data = _SHARED_HISTORICAL_DATA[ticker]
            else:
                raise KeyError(f"Identificador bursátil {ticker} ausente en el bloque de memoria.")
        
        return {
            'ticker': ticker,
            'params': params,
            'status': 'SUCCESS',
            'ev': float(np.random.rand()) # Placeholder 
        }
    except Exception as exc:
        logger.error(f"Fallo de segmentación/ejecución en {params}: {str(exc)}")
        return {
            'ticker': ticker,
            'params': params,
            'status': 'FAILED',
            'error': str(exc)
        }

def execute_parallel_optimization_grid(
    historical_df: pd.DataFrame, 
    universe_tickers: List[str] = None, 
    param_space: Dict[str, List[Any]] = None,
    max_cores: int = max(1, mp.cpu_count() - 1),
    eval_func=None,
    pre_built_tasks: List[Dict] = None,
    vix_regime: pd.Series = None
) -> List[Dict]:
    """
    Motor de orquestación paralela.
    
    Acepta:
      - param_space + universe_tickers (modo clásico, producto cartesiano)
      - pre_built_tasks (modo directo, lista de dicts con 'ticker' incluido)
    """
    if pre_built_tasks is not None:
        tasks = pre_built_tasks
    else:
        if param_space is None or universe_tickers is None:
            raise ValueError("Debe proveer param_space + universe_tickers, o pre_built_tasks")
        keys, values = zip(*param_space.items())
        base_combinations = [dict(zip(keys, v)) for v in product(*values)]
        
        tasks = []
        for ticker in universe_tickers:
            for combo in base_combinations:
                task_instance = combo.copy()
                task_instance['ticker'] = ticker
                tasks.append(task_instance)
            
    total_tasks = len(tasks)
    logger.info(f"Orquestando clúster: {total_tasks:,} nodos de cálculo sobre {max_cores} núcleos lógicos.")
    
    optimal_chunk = max(1, int(total_tasks / (max_cores * 4)))
    
    func_to_use = eval_func if eval_func is not None else _strategy_evaluation_task
    
    # Build initializer args (backward compatible)
    init_args = (historical_df,) if vix_regime is None else (historical_df, vix_regime)
    
    results = []
    with mp.Pool(
        processes=max_cores, 
        initializer=_pool_worker_initializer, 
        initargs=init_args
    ) as pool:
        for i, res in enumerate(pool.imap_unordered(func_to_use, tasks, chunksize=optimal_chunk)):
            results.append(res)
            if (i + 1) % 5000 == 0:
                logger.info(f"  Progreso: {i+1:,}/{total_tasks:,} ({(i+1)/total_tasks*100:.1f}%)")
            
    return results
