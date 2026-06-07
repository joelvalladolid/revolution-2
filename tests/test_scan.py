import sys, os, datetime
sys.path.insert(0, r"c:\Users\Alumno\Desktop\SMF\revolution-main\REVOLUTION_ENTREGABLE")
import warnings
warnings.filterwarnings("ignore")

from app import analyze_ticker_for_today
from lab_tickers import fetch_sp500_tickers_wiki_v2
from concurrent.futures import ThreadPoolExecutor, as_completed

def run():
    regime = "CALM"
    tnx_yield = 4.2
    end = datetime.date.today().strftime('%Y-%m-%d')
    start = (datetime.date.today() - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

    tickers = fetch_sp500_tickers_wiki_v2()
    print(f"Verificando {len(tickers)} tickers...")
    results = []
    passed_ema = 0
    passed_rsi = 0
    passed_vol = 0
    passed_fund = 0
    
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(analyze_ticker_for_today, t, regime, tnx_yield, start, end, False, "MOMENTUM"): t for t in tickers}
        for i, fut in enumerate(as_completed(futures)):
            if i % 50 == 0:
                print(f"Progreso: {i}/{len(tickers)}...")
            try:
                res = fut.result()
                if res:
                    if res['primary_met']: passed_ema += 1
                    if res.get('passed_rsi'): passed_rsi += 1
                    if res.get('passed_vol'): passed_vol += 1
                    if res.get('signal', {}).get('fundamental_ok'): 
                        passed_fund += 1
                        # Logging MC for debug
                        mc = res.get('mc')
                        if mc:
                            print(f"[MC DEBUG] {res['ticker']} -> P(>2%): {mc.get('prob_gt_2pct',0)*100:.1f}%, p10: {mc.get('p10',0)*100:.1f}%, req P: {mc.get('req_p',0)*100:.1f}%, req p10: {mc.get('req_p10',0)*100:.1f}%")
                        else:
                            print(f"[MC DEBUG] {res['ticker']} -> NO MC DATA")
                    
                    if res.get('signal', {}).get('signal', False):
                        results.append(res)
            except Exception as e:
                pass

    # Sort results
    results = sorted(results, key=lambda x: x.get('mc', {}).get('prob_gt_2pct', 0) if isinstance(x.get('mc'), dict) else 0, reverse=True)

    print("\n=== RESULTADOS FINALES ===")
    print(f"Pasaron EMA200: {passed_ema}")
    print(f"Pasaron RSI (45-65): {passed_rsi}")
    print(f"Pasaron Volumen (>500k): {passed_vol}")
    print(f"Pasaron Fundamentales (Stars >= 15): {passed_fund}")
    print(f"Tickers que pasan TODOS los filtros: {len(results)}\n")
    print(f"{'TICKER':<8} {'PRECIO':>8} {'EMA DISC':>10} {'STARS':>6} {'P(>2%)':>8} {'P90/P10':>12}")
    print("-" * 65)
    for r in results:
        mc = r.get('mc', {})
        t = r['ticker']
        p = r['price']
        ema = r['ema_disc']
        s = r['stars']
        pgt2 = mc.get('prob_gt_2pct', 0) * 100
        p90 = mc.get('p90', 0) * 100
        p10 = mc.get('p10', 0) * 100
        print(f"{t:<8} ${p:>7.2f} {ema:>9.1f}% {s:>6}/16 {pgt2:>7.1f}%  +{p90:>4.1f}%/{p10:>4.1f}%")

if __name__ == "__main__":
    run()
