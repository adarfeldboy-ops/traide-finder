# בדיקה לאחור (Backtest): סימולציה של מסחר לפי כללי הניתוח של המשתמש, נר אחרי נר.
# כל החלטה ביום t מתבססת רק על מה שהיה ידוע בסגירת יום t. הביצוע - בפתיחה של יום המסחר הבא,
# חוץ מיציאה ביעד (התנגדות) שמבוצעת כפקודת מכירה מוגבלת במחיר האזור (שהיה ידוע מראש).
# התוצאות הן סימולציה היסטורית - לא המלצה ולא הבטחה לעתיד.
#
# כללי הכניסה (בסגירת יום האיתות):
#   חובה: CCI בין 0 ל-200, וווליום לפחות פי 1.5 מהממוצע.
#   ובנוסף לפחות אחד מהמצבים:
#     תמיכה     - המחיר 0%-5% מעל אזור תמיכה שמחזיק (או בתוכו), ונר עולה (סגירה > פתיחה, וגם > אתמול)
#     חציית SMA - SMA50 חצה את SMA150 כלפי מעלה ב-5 הנרות האחרונים, והמחיר מעל SMA150
#     נשיקה ל-SMA150 - הנמוך הגיע עד 2% מ-SMA150, הסגירה מעליו, ונר עולה מאתמול
# כללי היציאה:
#   יעד  - הגעה לאזור ההתנגדות הקרוב שמחזיק מעל מחיר הכניסה (מכירה בתחתית האזור)
#   סטופ - סגירה מתחת לרמת התמיכה (אזור / SMA150) פחות 0.5 ATR, ולא יותר מ-10% הפסד
#   סוף התקופה - פוזיציות פתוחות נסגרות במחיר הסגירה האחרון

from pathlib import Path

import numpy as np
import pandas as pd

import settings
from data import fetch_many
from indicators import add_indicators, sma_col
from levels import (RESISTANCE, SUPPORT, already_broken, find_swings, keep_inside_role,
                    tolerances, zones_at)
from universe import GROUPS, load_universe

START, END = pd.Timestamp("2025-09-10"), pd.Timestamp("2026-09-10")
MAX_POSITIONS = 4         # לא יותר מ-4 נכסים במקביל
START_CAPITAL = 100_000   # הון התחלתי (לחישוב בלבד)
FEE = 0.001               # עמלה 0.1% בכל צד (קנייה ומכירה)
CCI_MIN, CCI_MAX = 0, 200
VOL_MIN = 1.5
SUPPORT_NEAR_PCT = 5.0    # נשיקה לתמיכה: עד 5% מעל האזור
SMA_TOUCH_PCT = 2.0       # נשיקה ל-SMA150: הנמוך עד 2% מעליו
CROSS_RECENT = 5          # חציית SMA50/150 ב-5 הנרות האחרונים
STOP_ATR = 0.5            # הסטופ: 0.5 ATR מתחת לרמת התמיכה
MAX_LOSS = 0.10           # ...אבל לא יותר מ-10% מתחת למחיר הכניסה

SETUP_SUPPORT = "תמיכה"
SETUP_CROSS = "חציית SMA50/150"
SETUP_SMA150 = "נשיקה ל-SMA150"
EXIT_TARGET = "הגיע להתנגדות"
EXIT_STOP = "סטופ"
EXIT_END = "סוף התקופה"

RESULTS = Path(__file__).parent / "backtest_results"


def prepare(raw):
    """אינדיקטורים + נקודות מפנה לנכס אחד - רק עם נתונים עד סוף התקופה."""
    df = add_indicators(raw[raw.index <= END])
    if len(df) < settings.SMA_LONG + 10 or df.index[-1] < START:
        return None
    return {
        "df": df,
        "swings": find_swings(df),  # כל נקודת מפנה משמשת רק אחרי יום האישור שלה (בתוך zones_at)
        "tol": tolerances(df),
        "pos": {d: k for k, d in enumerate(df.index)},
        **{name: df[col].to_numpy() for name, col in (
            ("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("cci", "CCI"),
            ("vr", "VolRatio"), ("atr", "ATR"), ("s50", sma_col(settings.SMA_MID)),
            ("s150", sma_col(settings.SMA_LONG)))},
    }


def nearest_support(a, i):
    """אזור התמיכה הקרוב שמחזיק אחרי סגירת יום i, אם המחיר 0%-5% מעליו (או בתוכו)."""
    close, best = a["c"][i], None
    for zone, kind in zones_at(a["df"], a["swings"], i + 1, tol=a["tol"]):
        if kind != SUPPORT:
            continue
        dist = (close - zone["high"]) / close * 100
        if dist <= SUPPORT_NEAR_PCT and (best is None or dist < best[1]):
            best = (zone, dist)
    return best[0] if best else None


def find_signals(symbol, a):
    """כל ימי האיתות של נכס בתקופה. כל בדיקה משתמשת רק בנרות עד יום i (כולל)."""
    o, l, c, s50, s150 = a["o"], a["l"], a["c"], a["s50"], a["s150"]
    signals = []
    for i in range(CROSS_RECENT, len(c)):
        d = a["df"].index[i]
        if d < START or d >= END:
            continue
        # מסננים חובה (השוואה עם NaN מחזירה False - כלומר לא עובר)
        if not (CCI_MIN <= a["cci"][i] <= CCI_MAX and a["vr"][i] >= VOL_MIN):
            continue
        up_day = c[i] > c[i - 1]
        setups, levels = [], []
        crossed = any(s50[k] > s150[k] and s50[k - 1] <= s150[k - 1]
                      for k in range(i - CROSS_RECENT + 1, i + 1))
        if crossed and c[i] > s150[i]:
            setups.append(SETUP_CROSS)
            levels.append(s150[i])
        if up_day and c[i] > s150[i] and l[i] <= s150[i] * (1 + SMA_TOUCH_PCT / 100):
            setups.append(SETUP_SMA150)
            levels.append(s150[i])
        if up_day and c[i] > o[i]:
            zone = nearest_support(a, i)
            if zone:
                setups.append(SETUP_SUPPORT)
                levels.append(zone["low"])
        if setups:
            signals.append({"symbol": symbol, "i": i, "date": d, "setups": setups,
                            "level": max(levels), "atr": a["atr"][i],
                            "vol_ratio": a["vr"][i], "cci": a["cci"][i]})
    return signals


SITE_KISS = "נשיקה לתמיכה"
SITE_CROSS_MID = "SMA50 חוצה SMA150"
SITE_CROSS_PRICE = "מחיר חוצה SMA150"
SITE_CRITERIA = [SITE_KISS, SITE_CROSS_MID, SITE_CROSS_PRICE]  # מה מסומן באתר


def site_signals(symbol, a):
    """מה שהאתר היה מציג בכל יום (סריקה עם הנתונים עד אותו יום), בהגדרות:
    נשיקה לתמיכה (0%-5%) / SMA50 חוצה SMA150 / מחיר חוצה SMA150 - "לפחות אחד",
    CCI בטווח 0-200 וווליום פי 1.5 ביום האיתות (בנשיקה: הנר האחרון), חלון 5 נרות.
    קונים רק חציות כלפי מעלה. אותם כללים כמו בקוד של האתר (levels.py / signals.py)."""
    df, c, s50, s150 = a["df"], a["c"], a["s50"], a["s150"]
    tol, swings = a["tol"], a["swings"]
    cache = {}

    def zones(i):
        if i not in cache:
            cache[i] = zones_at(df, swings, i, tol=tol)
        return cache[i]

    def passes(k):
        return CCI_MIN <= a["cci"][k] <= CCI_MAX and a["vr"][k] >= VOL_MIN

    first = int(np.searchsorted(df.index, START))
    start = max(settings.SWING_BARS + 1, first - settings.BREAK_MEMORY_BARS - 1, CROSS_RECENT)
    broken, signals = [], []
    for i in range(start, len(c)):
        # פריצות של היום - האתר זוכר אותן כדי לא להציג נשיקה לאזור שנפרץ זה עתה
        for zone, kind in zones(i):
            if (c[i] > zone["high"] + tol[i]) if kind == RESISTANCE else (c[i] < zone["low"] - tol[i]):
                broken.append((zone["low"], zone["high"], kind, i))
        d = df.index[i]
        if d < START or d >= END:
            continue
        setups, levels = [], []
        # נשיקה לתמיכה: האזורים שמחזיקים אחרי סגירת יום i, כמו near_zones באתר
        if SITE_KISS in SITE_CRITERIA and passes(i):
            found = []
            for zone, kind in zones(i + 1):
                dist = ((zone["low"] - c[i]) if kind == RESISTANCE else (c[i] - zone["high"])) / c[i] * 100
                found.append((zone, kind, max(dist, 0.0), dist <= 0))
            dfi = df.iloc[:i + 1]
            sup = [f for f in found if keep_inside_role(dfi, f, found) and f[1] == SUPPORT
                   and f[2] <= SUPPORT_NEAR_PCT and not already_broken(broken, f[0], SUPPORT, i + 1)]
            if sup:
                setups.append(SITE_KISS)
                levels.append(min(sup, key=lambda f: f[2])[0]["low"])
        # חציות כלפי מעלה ב-5 הנרות האחרונים, שעברו את המסננים ביום החצייה
        for name, fast in ((SITE_CROSS_MID, s50), (SITE_CROSS_PRICE, c)):
            if name in SITE_CRITERIA and any(fast[k] > s150[k] and fast[k - 1] <= s150[k - 1] and passes(k)
                   for k in range(i - CROSS_RECENT + 1, i + 1)):
                setups.append(name)
                levels.append(s150[i])
        if setups:
            signals.append({"symbol": symbol, "i": i, "date": d, "setups": setups,
                            "level": max(levels), "atr": a["atr"][i],
                            "vol_ratio": a["vr"][i], "cci": a["cci"][i]})
    return signals


def target_zone(a, i, entry_price):
    """אזור ההתנגדות הקרוב שמחזיק ביום i (לפי מה שידוע עד אתמול) ונמצא מעל מחיר הכניסה."""
    best = None
    for zone, kind in zones_at(a["df"], a["swings"], i, tol=a["tol"]):
        if kind == RESISTANCE and zone["low"] > entry_price:
            if best is None or zone["low"] < best["low"]:
                best = zone
    return best


def run(symbols=None, signal_fn=find_signals):
    """מריץ את הסימולציה. signal_fn = איך מוצאים איתותים (find_signals או site_signals).
    מחזיר (טרנזקציות, עקומת הון, סיכום)."""
    if symbols is None:
        symbols, _ = load_universe(GROUPS)
    frames, _ = fetch_many(symbols)
    assets = {s: a for s, raw in frames.items() if (a := prepare(raw)) is not None}

    signals_by_date = {}
    all_and = 0
    for s, a in assets.items():
        for sig in signal_fn(s, a):
            signals_by_date.setdefault(sig["date"], []).append(sig)
            all_and += len(sig["setups"]) == 3

    dates = sorted({d for a in assets.values() for d in a["df"].index if START <= d <= END})
    cash, equity = START_CAPITAL, START_CAPITAL
    positions, pending_entry, pending_exit = {}, [], {}
    last_close, trades, curve = {}, [], []
    skipped_gap = 0

    def close_trade(sym, date, price, reason):
        nonlocal cash
        p = positions.pop(sym)
        cash += p["qty"] * price * (1 - FEE)
        trades.append({
            "symbol": sym, "setups": " + ".join(p["setups"]), "signal_date": p["signal_date"].date(),
            "entry_date": p["entry_date"].date(), "entry_price": p["entry_price"],
            "exit_date": date.date(), "exit_price": price, "reason": reason,
            "return_pct": (price * (1 - FEE) / (p["entry_price"] * (1 + FEE)) - 1) * 100,
            "pnl": p["qty"] * (price * (1 - FEE) - p["entry_price"] * (1 + FEE)),
            "days": (date - p["entry_date"]).days,
        })

    for d in dates:
        # 1. יציאות שהוחלטו אתמול (סטופ) - בפתיחה של היום
        for sym in list(pending_exit):
            a = assets[sym]
            if d in a["pos"]:
                close_trade(sym, d, a["o"][a["pos"][d]], pending_exit.pop(sym))

        # 2. כניסות שהוחלטו אתמול - בפתיחה של היום (בנר הבא של אותו נכס)
        for sig in list(pending_entry):
            a = assets[sig["symbol"]]
            nxt = sig["i"] + 1
            if nxt >= len(a["c"]) or a["df"].index[nxt] > END:
                pending_entry.remove(sig)
                continue
            if a["df"].index[nxt] != d:
                continue
            pending_entry.remove(sig)
            price = a["o"][nxt]
            stop = max(sig["level"] - STOP_ATR * sig["atr"], price * (1 - MAX_LOSS))
            if price <= stop or len(positions) >= MAX_POSITIONS:
                skipped_gap += price <= stop  # נפתח מתחת לתמיכה - האיתות כבר לא תקף
                continue
            alloc = min(cash, equity / MAX_POSITIONS)
            qty = alloc / (price * (1 + FEE))
            cash -= qty * price * (1 + FEE)
            positions[sig["symbol"]] = {
                "qty": qty, "entry_price": price, "entry_date": d, "entry_i": nxt,
                "stop": stop, "setups": sig["setups"], "signal_date": sig["date"]}

        # 3. במהלך היום: יעד (התנגדות) ; בסגירה: בדיקת סטופ למחר
        for sym in list(positions):
            a = assets[sym]
            if d not in a["pos"]:
                continue
            i = a["pos"][d]
            last_close[sym] = a["c"][i]
            zone = target_zone(a, i, positions[sym]["entry_price"])
            if zone and a["h"][i] >= zone["low"]:
                close_trade(sym, d, max(a["o"][i], zone["low"]), EXIT_TARGET)
            elif a["c"][i] < positions[sym]["stop"]:
                pending_exit[sym] = EXIT_STOP

        # 4. סוף התקופה - סוגרים הכול במחיר הסגירה האחרון
        if d == dates[-1]:
            for sym in list(positions):
                pending_exit.pop(sym, None)
                close_trade(sym, d, last_close.get(sym, positions[sym]["entry_price"]), EXIT_END)

        # 5. שווי התיק בסגירה
        for sym in positions:
            a = assets[sym]
            if d in a["pos"]:
                last_close[sym] = a["c"][a["pos"][d]]
        equity = cash + sum(p["qty"] * last_close.get(s, p["entry_price"]) for s, p in positions.items())
        curve.append({"date": d, "equity": equity, "positions": len(positions)})

        # 6. איתותים חדשים מהסגירה של היום -> כניסה מחר. אם יש יותר מהמקומות הפנויים,
        #    מעדיפים את הווליום החזק ביותר.
        if d < END:
            busy = set(positions) | {s["symbol"] for s in pending_entry}
            free = MAX_POSITIONS - (len(positions) - len(pending_exit)) - len(pending_entry)
            candidates = sorted((s for s in signals_by_date.get(d, []) if s["symbol"] not in busy),
                                key=lambda s: -s["vol_ratio"])
            pending_entry += candidates[:max(free, 0)]

    trades = pd.DataFrame(trades)
    curve = pd.DataFrame(curve).set_index("date")
    peak = curve["equity"].cummax()
    summary = {
        "symbols": len(assets),
        "signals": sum(len(v) for v in signals_by_date.values()),
        "signals_all_three_setups": all_and,
        "skipped_gap_below_stop": skipped_gap,
        "trades": len(trades),
        "final_equity": curve["equity"].iloc[-1],
        "total_return_pct": (curve["equity"].iloc[-1] / START_CAPITAL - 1) * 100,
        "max_drawdown_pct": ((curve["equity"] / peak - 1).min()) * 100,
        "win_rate_pct": (trades["return_pct"] > 0).mean() * 100 if len(trades) else np.nan,
        "avg_positions": curve["positions"].mean(),
    }
    # השוואה לקנייה והחזקה (גם כשהנכסים האלה לא חלק מהסריקה)
    benchmarks, _ = fetch_many(["SPY", "QQQ", "BTC/USDT"])
    for bench, b in benchmarks.items():
        b = b[(b.index >= START) & (b.index <= END)]
        summary[f"buy_hold_{bench}_pct"] = (b["Close"].iloc[-1] / b["Open"].iloc[0] - 1) * 100
    return trades, curve, summary


if __name__ == "__main__":
    import sys

    # python backtest.py             -> הכללים שלי (הסימולציה הראשונה)
    # python backtest.py site        -> רק מה שהאתר הציג
    # להוסיף stocks (למשל: site stocks) -> רק מניות ו-ETF, בלי קריפטו
    # להוסיף kiss -> באתר מסומנת רק "נשיקה לתמיכה"
    from data import is_crypto

    site = "site" in sys.argv[1:]
    stocks_only = "stocks" in sys.argv[1:]
    if "kiss" in sys.argv[1:]:
        SITE_CRITERIA[:] = [SITE_KISS]
    symbols = None
    if stocks_only:
        symbols = [s for s in load_universe(GROUPS)[0] if not is_crypto(s)]
    trades, curve, summary = run(symbols, signal_fn=site_signals if site else find_signals)
    prefix = ("site_" if site else "") + ("stocks_" if stocks_only else "") + \
             ("kiss_" if "kiss" in sys.argv[1:] else "")
    RESULTS.mkdir(exist_ok=True)
    trades.to_csv(RESULTS / f"{prefix}trades.csv", index=False, encoding="utf-8-sig")
    curve.to_csv(RESULTS / f"{prefix}equity.csv", encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    print(trades.round(2).to_string())
    print()
    for k, v in summary.items():
        print(f"{k}: {round(v, 2) if isinstance(v, float) else v}")
