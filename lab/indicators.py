import pandas as pd
import numpy as np

def rsi(df: pd.DataFrame, period=14) -> pd.Series:
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd_hist(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.Series:
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line

def bollinger_pctB(df: pd.DataFrame, period=20, std=2) -> pd.Series:
    sma = df['Close'].rolling(window=period).mean()
    rolling_std = df['Close'].rolling(window=period).std()
    upper_band = sma + (rolling_std * std)
    lower_band = sma - (rolling_std * std)
    return (df['Close'] - lower_band) / (upper_band - lower_band)

def mfi(df: pd.DataFrame, period=14) -> pd.Series:
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    raw_money_flow = typical_price * df['Volume']
    
    positive_flow = np.where(typical_price > typical_price.shift(1), raw_money_flow, 0)
    negative_flow = np.where(typical_price < typical_price.shift(1), raw_money_flow, 0)
    
    positive_mf = pd.Series(positive_flow, index=df.index).rolling(window=period).sum()
    negative_mf = pd.Series(negative_flow, index=df.index).rolling(window=period).sum()
    
    mfi_ratio = positive_mf / negative_mf
    return 100 - (100 / (1 + mfi_ratio))

def williams_r(df: pd.DataFrame, period=14) -> pd.Series:
    highest_high = df['High'].rolling(window=period).max()
    lowest_low = df['Low'].rolling(window=period).min()
    return -100 * ((highest_high - df['Close']) / (highest_high - lowest_low))

def stochastic_k(df: pd.DataFrame, k=14, d=3) -> pd.Series:
    lowest_low = df['Low'].rolling(window=k).min()
    highest_high = df['High'].rolling(window=k).max()
    stoch_k = 100 * ((df['Close'] - lowest_low) / (highest_high - lowest_low))
    return stoch_k.rolling(window=d).mean()

def ema_discount(df: pd.DataFrame, period=200) -> pd.Series:
    ema = df['Close'].ewm(span=period, adjust=False).mean()
    return ((ema - df['Close']) / ema) * 100

def adx(df: pd.DataFrame, period=14) -> pd.Series:
    """Average Directional Index — fuerza de la tendencia, no dirección"""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = abs(100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr))
    
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    adx_series = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx_series
