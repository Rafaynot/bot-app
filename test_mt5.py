"""Quick MT5 connectivity diagnostic."""
import glob
import os

import MetaTrader5 as mt5

paths = [
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
]
appdata = os.environ.get("APPDATA", "")
paths.extend(glob.glob(os.path.join(appdata, "MetaQuotes", "Terminal", "*", "terminal64.exe")))

print("=== MT5 Terminal Search ===")
found = [p for p in paths if os.path.isfile(p)]
for p in found:
    print(f"FOUND: {p}")
if not found:
    print("No terminal64.exe found")

print("\n=== MT5 Initialize (default) ===")
ok = mt5.initialize()
print(f"initialize: {ok}")
if not ok:
    print(f"last_error: {mt5.last_error()}")
    if found:
        print("\n=== Retry with explicit path ===")
        ok = mt5.initialize(path=found[0])
        print(f"initialize: {ok}")
        if not ok:
            print(f"last_error: {mt5.last_error()}")

if ok:
    info = mt5.account_info()
    if info:
        print(f"account: {info.login} @ {info.server}")
        print(f"balance: {info.balance}")
    else:
        print("account_info: None (not logged in?)")

    sym = None
    for name in ["XAUUSD", "XAUUSDm", "XAUUSD.", "GOLD", "Gold", "XAUUSD.a"]:
        si = mt5.symbol_info(name)
        if si:
            sym = name
            print(f"symbol found: {name} bid={si.bid} ask={si.ask}")
            break

    if not sym:
        print("Searching all symbols for XAU/USD...")
        for s in mt5.symbols_get() or []:
            if "XAU" in s.name.upper() and "USD" in s.name.upper():
                print(f"  candidate: {s.name}")
                sym = s.name
                break

    if sym:
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        if tick:
            print(f"LIVE TICK {sym}: bid={tick.bid} ask={tick.ask}")
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 5)
        if rates is not None and len(rates):
            print(f"M15 bars: {len(rates)} latest close={rates[-1]['close']}")

    mt5.shutdown()
