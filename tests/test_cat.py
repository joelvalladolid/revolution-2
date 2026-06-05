import sys
sys.path.insert(0, r"c:\Users\Alumno\Desktop\SMF\revolution-main\REVOLUTION_ENTREGABLE")
from app import analyze_ticker_for_today
res = analyze_ticker_for_today('CAT', 'CALM', 4.2, '2023-01-01', '2026-01-01', False, 'MOMENTUM')
if res:
    print("CAT RSI:", res['ind_vals'].get('RSI'))
    print("CAT Score:", res['signal']['confidence'])
    print("CAT Signal:", res['signal']['signal'])
