# Cómo usar este sistema

## Instalación
1. Instalar Python 3.10+
2. Ejecutar: pip install -r requirements.txt

## Usar la interfaz web
streamlit run app.py

## Correr un torneo nuevo
python lab/strategy_tournament.py --tickers SPY --period full --max-combos 500 --top-n 10 --walk-forward --bootstrap 1000 --slippage 0.0001 --commission 0.0 --output output_spy_tournament.txt

## Calcular la canasta de hoy
python lab/daily_allocator.py --results output_sp500_daytrading_full_results.csv --capital 10000 --vix 18.5 --output allocations/allocation_hoy.txt
