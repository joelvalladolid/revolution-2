import numba
import numpy as np
import pandas as pd

@numba.njit(cache=True, nogil=True, boundscheck=False, fastmath=True)
def _numba_sltp_path_solver(
    index_vals: np.ndarray, 
    high_vals: np.ndarray, 
    low_vals: np.ndarray, 
    entry_prices: np.ndarray,
    tp_prices: np.ndarray, 
    sl_prices: np.ndarray, 
    out_exit_price: np.ndarray, 
    out_exit_index: np.ndarray
) -> None:
    n_rows = len(index_vals)
    
    for idx_entry in range(n_rows - 1):
        if np.isnan(entry_prices[idx_entry]):
            continue
            
        tp_target = tp_prices[idx_entry]
        sl_target = sl_prices[idx_entry]
        
        for idx_exit in range(idx_entry + 1, n_rows):
            current_high = high_vals[idx_exit]
            current_low = low_vals[idx_exit]
            
            if current_low <= sl_target:
                out_exit_price[idx_entry] = sl_target
                out_exit_index[idx_entry] = index_vals[idx_exit]
                break
                
            elif current_high >= tp_target:
                out_exit_price[idx_entry] = tp_target
                out_exit_index[idx_entry] = index_vals[idx_exit]
                break
                
        if np.isnan(out_exit_price[idx_entry]):
            out_exit_price[idx_entry] = high_vals[n_rows - 1]
            out_exit_index[idx_entry] = index_vals[n_rows - 1]

def vectorized_atr_backtest_engine(df: pd.DataFrame) -> pd.DataFrame:
    n_records = len(df)
    
    exit_price_arr = np.full(n_records, np.nan, dtype=np.float64)
    exit_index_arr = np.full(n_records, np.nan, dtype=np.float64)
    
    index_float = df.index.values.astype("float64")
    
    _numba_sltp_path_solver(
        index_vals=index_float,
        high_vals=df['High'].values,
        low_vals=df['Low'].values,
        entry_prices=df['EntryPrice'].values,
        tp_prices=df['TP_Price'].values,
        sl_prices=df['SL_Price'].values,
        out_exit_price=exit_price_arr,
        out_exit_index=exit_index_arr
    )
    
    df_result = df.copy(deep=False)
    df_result['ActualExitPrice'] = exit_price_arr
    
    df_result['ExitDate'] = pd.to_datetime(exit_index_arr, errors='coerce')
    
    df_result['PnL'] = np.where(
        ~df_result['EntryPrice'].isna(),
        df_result['ActualExitPrice'] - df_result['EntryPrice'],
        np.nan
    )
    
    return df_result
