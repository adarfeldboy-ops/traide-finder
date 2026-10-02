# מבנים טכניים: משולשים מתכנסים (סימטרי ועולה).
#   משולש סימטרי = קו עליון יורד דרך שיאים (כל שיא נמוך מהקודם) וקו תחתון עולה דרך שפלים
#                  (כל שפל גבוה מהקודם). הקווים מתכנסים לקודקוד.
#   משולש עולה   = קו עליון שטוח (התנגדות אופקית - שיאים בערך באותה רמה) וקו תחתון עולה.
#   נשיקה  = המחיר כעת בתוך המשולש וקרוב לקו התחתון (מעליו) או לקו העליון (מתחתיו).
#   פריצה / שבירה = הסגירה הראשונה מעל הקו העליון / מתחת לקו התחתון. כל משולש נפרץ פעם אחת.
# כלל חשוב: ביום i משתמשים רק בנקודות מפנה שהתאשרו לפני יום i (בלי "הצצה לעתיד").
# התוצאות הן איתותים לבדיקה - לא המלצות קנייה או מכירה.

import numpy as np

import settings
from channels import rising_run, trim
from indicators import sma_col
from levels import find_swings

SYMMETRICAL = "משולש סימטרי"
ASCENDING = "משולש עולה"
TRIANGLE_TYPES = (SYMMETRICAL, ASCENDING)
KISS_LOW, KISS_HIGH = "נשיקה לקו התחתון", "נשיקה לקו העליון"
BREAK_UP, BREAK_DOWN = "פריצה למעלה", "שבירה למטה"
# כל אפשרות באתר -> (סוג המשולש, מה מחפשים)
TRIANGLE_INFO = {f"{kind} – {what}": (kind, what)
                 for kind in TRIANGLE_TYPES for what in (KISS_LOW, KISS_HIGH, BREAK_UP, BREAK_DOWN)}
TRIANGLE_OPTIONS = list(TRIANGLE_INFO)
TRIANGLE_KISSES = tuple(o for o, (_, what) in TRIANGLE_INFO.items() if what in (KISS_LOW, KISS_HIGH))


def option_name(kind, what):
    return f"{kind} – {what}"


def falling_run(points):
    """הרצף האחרון של נקודות שכל אחת נמוכה מהקודמת (מהסוף אחורה, בלי לדלג)."""
    run = points[-1:]
    for p in reversed(points[:-1]):
        if p[1] <= run[0][1]:
            break
        run.insert(0, p)
    return run


def flat_run(points):
    """הרצף האחרון של שיאים שכולם בטווח של TRI_FLAT_ATR * ATR זה מזה (קו שטוח)."""
    if not points:
        return []
    band = settings.TRI_FLAT_ATR * points[-1][4]
    run = points[-1:]
    for p in reversed(points[:-1]):
        prices = [s[1] for s in run] + [p[1]]
        if max(prices) - min(prices) > band:
            break
        run.insert(0, p)
    return run


def fitted_slope(group):
    """שיפוע הקו הישר שעובר הכי קרוב לנקודות (ריבועים פחותים)."""
    x = np.array([s[0] for s in group], float)
    y = np.array([s[1] for s in group], float)
    den = ((x - x.mean()) ** 2).sum()
    return ((x - x.mean()) * (y - y.mean())).sum() / den if den else 0.0


def line_at(tri, pos, which):
    """ערך הקו ("low" / "high") ביום pos."""
    return tri[f"a_{which}"] + tri[f"s_{which}"] * pos


def tolerances(df):
    """לכל יום: כמה צריך לסגור מעבר לקו כדי שזה ייחשב יציאה (0.3 ATR של היום הקודם)."""
    return settings.TRI_BREAK_ATR * df["ATR"].shift(1).to_numpy()


def left_triangle(tri, closes, tol, end):
    """האם סגירה כלשהי מתחילת המשולש עד end (לא כולל) יצאה ממנו מעבר לסובלנות."""
    pos = np.arange(tri["start"], end)
    seg, t = closes[tri["start"]:end], tol[tri["start"]:end]
    lower = tri["a_low"] + tri["s_low"] * pos
    upper = tri["a_high"] + tri["s_high"] * pos
    return bool(((seg > upper + t) | (seg < lower - t)).any())


def triangle_at(df, swings, i, kind, closes=None, tol=None):
    """המשולש מסוג kind שהיה ידוע ביום i (נקודות מפנה שאושרו לפני i, סגירות עד i-1), או None.
    מחזיר מילון: kind, start, last, a_low, s_low, a_high, s_high, נגיעות, apex (יום הקודקוד)."""
    closes = df["Close"].to_numpy() if closes is None else closes
    tol = tolerances(df) if tol is None else tol
    first_allowed = i - settings.TRI_LOOKBACK
    known = [s for s in swings if s[0] >= first_allowed and s[2] < i]
    lows = rising_run([s for s in known if not s[3]])
    highs_all = [s for s in known if s[3]]
    highs = flat_run(highs_all) if kind == ASCENDING else falling_run(highs_all)
    need = settings.TRI_MIN_TOUCHES
    if len(lows) < need or len(highs) < need:
        return None
    # המשולש מתחיל כששני הקווים "פעילים" (כמו בתעלה)
    start = max(lows[0][0], highs[0][0])
    lows, highs = trim(lows, start), trim(highs, start)
    if len(lows) < need or len(highs) < need:
        return None

    price = closes[i - 1]

    def pct_20(slope):  # שיפוע כאחוז מהמחיר ל-20 נרות
        return slope * 20 / price * 100

    s_low = fitted_slope(lows)
    if pct_20(s_low) < settings.TRI_MIN_SLOPE_PCT:
        return None  # הקו התחתון חייב לעלות
    if kind == ASCENDING:
        s_high = 0.0  # התנגדות אופקית
    else:
        s_high = fitted_slope(highs)
        if pct_20(s_high) > -settings.TRI_MIN_SLOPE_PCT:
            return None  # במשולש סימטרי הקו העליון חייב לרדת
        if max(-s_high, s_low) > settings.TRI_SYM_MAX_RATIO * min(-s_high, s_low):
            return None  # שיפועים לא מאוזנים - זה לא משולש סימטרי
    # הקו התחתון נשען על השפל הנמוך ביותר (ביחס לקו), העליון על השיא הגבוה ביותר
    a_low = min(s[1] - s_low * s[0] for s in lows)
    a_high = max(s[1] - s_high * s[0] for s in highs)

    def touches(group, a, slope):
        return int(sum(abs(s[1] - (a + slope * s[0])) <= settings.TRI_TOUCH_ATR * s[4]
                       for s in group))

    points = lows + highs
    first, last = min(s[0] for s in points), max(s[0] for s in points)
    # כל שיא/שפל מתחילת המשולש שייך לקו שלו. אחרת יש בתוך "המשולש" נקודה ששוברת את הכלל
    # (למשל במשולש עולה: שיא נמוך הרבה מההתנגדות - זו עוד הייתה עלייה, לא משולש)
    used = {(s[0], s[3]) for s in points}
    if any(s[0] >= first and (s[0], s[3]) not in used for s in known):
        return None
    tri = {"kind": kind, "start": first, "last": last, "a_low": a_low, "s_low": s_low,
           "a_high": a_high, "s_high": s_high,
           "low_touches": touches(lows, a_low, s_low), "high_touches": touches(highs, a_high, s_high),
           "apex": (a_high - a_low) / (s_low - s_high)}
    atr = df["ATR"].iloc[i - 1]
    if (tri["low_touches"] < need or tri["high_touches"] < need
            or last - first < settings.TRI_MIN_BARS
            or line_at(tri, first, "high") - line_at(tri, first, "low") < settings.TRI_MIN_WIDTH_ATR * atr):
        return None
    # הקודקוד לפנינו (הקווים עוד לא נפגשו), ולא רחוק מדי (אחרת הקווים כמעט מקבילים)
    if not (i - 1 < tri["apex"] <= i - 1 + settings.TRI_APEX_MAX_RATIO * (last - first)):
        return None
    # כל הסגירות מתחילת המשולש עד אתמול בתוך הקווים (אחרת הוא כבר נפרץ)
    if left_triangle(tri, closes, tol, i):
        return None
    return tri


def broken_before(breaks, tri, i):
    """האם זה (כמעט) אותו משולש שכבר נפרץ/נשבר ב-BREAK_MEMORY_BARS הנרות שלפני יום i:
    הוא התחיל לפני יום היציאה הקודמת. (כמו בתעלה - יציאה אחת לא נספרת פעמיים.)"""
    return any(tri["start"] < day < i and i - day <= settings.BREAK_MEMORY_BARS for day in breaks)


def scan_triangle(df, swings, kind, start, closes, tol):
    """עובר יום-יום מ-start עד הנר האחרון, למשולש מסוג kind. מחזיר
    ([(יום, פריצה/שבירה, משולש)] ליציאות שנספרות, המשולש הפעיל אחרי הנר האחרון או None)."""
    breaks, exits = [], []
    for i in range(start, len(df)):
        tri = triangle_at(df, swings, i, kind, closes, tol)
        if tri is None:
            continue
        if closes[i] > line_at(tri, i, "high") + tol[i]:
            what = BREAK_UP
        elif closes[i] < line_at(tri, i, "low") - tol[i]:
            what = BREAK_DOWN
        else:
            continue
        if not broken_before(breaks, tri, i):
            exits.append((i, what, tri))
        breaks.append(i)
    tri = triangle_at(df, swings, len(df), kind, closes, tol)
    if tri is not None and broken_before(breaks, tri, len(df)):
        tri = None  # "תחייה" של משולש שכבר נפרץ - לא פעיל
    return exits, tri


def active_triangles(df, swings=None, min_move_atr=settings.SWING_MIN_MOVE_ATR):
    """{סוג: משולש} - המשולשים שפעילים אחרי הנר האחרון (לגרף)."""
    swings = find_swings(df, min_move_atr) if swings is None else swings
    start = max(settings.SWING_BARS + 1, len(df) - settings.BREAK_MEMORY_BARS)
    closes, tol = df["Close"].to_numpy(), tolerances(df)
    found = {}
    for kind in TRIANGLE_TYPES:
        tri = scan_triangle(df, swings, kind, start, closes, tol)[1]
        if tri:
            found[kind] = tri
    return found


def make_row(df, symbol, i, kind, what, tri, dist_pct):
    """שורה בטבלה: האיתות, נתוני המשולש, ומצב הממוצעים/CCI/ווליום ביום האיתות."""
    row = df.iloc[i]
    result = {
        "symbol": symbol,
        "option": option_name(kind, what),
        "pattern": kind,
        "direction": {BREAK_UP: "למעלה", BREAK_DOWN: "למטה"}.get(what, ""),
        "date": df.index[i].date(),
        "days_ago": len(df) - 1 - i,
        "dist_pct": dist_pct,
        "lower": line_at(tri, i, "low"),
        "upper": line_at(tri, i, "high"),
        "low_touches": tri["low_touches"],
        "high_touches": tri["high_touches"],
        "start_date": df.index[tri["start"]].date(),
        "apex_in": tri["apex"] - i,  # בעוד כמה נרות הקווים נפגשים (מיום האיתות)
        "lower_slope_pct_20": tri["s_low"] * 20 / row["Close"] * 100,
        "upper_slope_pct_20": tri["s_high"] * 20 / row["Close"] * 100,
        "close": row["Close"],
        "cci": row["CCI"],
        "vol_ratio": row["VolRatio"],
    }
    for period in (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG):
        result[f"above_{sma_col(period)}"] = bool(row["Close"] > row[sma_col(period)])
    return result


def triangle_signals(df, symbol, lookback=None, min_move_atr=settings.SWING_MIN_MOVE_ATR,
                     swings=None):
    """פריצות/שבירות של משולשים ב-lookback הנרות האחרונים + נשיקות כרגע. df עם אינדיקטורים.
    כמו בתעלה: מתחילים BREAK_MEMORY_BARS נרות לפני החלון רק כדי לזכור יציאות קודמות."""
    lookback = lookback or settings.LOOKBACK_DAYS
    swings = find_swings(df, min_move_atr) if swings is None else swings
    closes, tol = df["Close"].to_numpy(), tolerances(df)
    first_reported = len(df) - lookback
    start = max(settings.SWING_BARS + 1, first_reported - settings.BREAK_MEMORY_BARS)
    current, last = closes[-1], len(df) - 1
    rows = []
    for kind in TRIANGLE_TYPES:
        exits, tri = scan_triangle(df, swings, kind, start, closes, tol)
        for i, what, t in exits:
            if i >= first_reported:
                edge = line_at(t, i, "high" if what == BREAK_UP else "low")
                rows.append(make_row(df, symbol, i, kind, what, t, (current - edge) / edge * 100))
        if tri is not None:
            to_low = max((current - line_at(tri, last, "low")) / current * 100, 0.0)
            to_high = max((line_at(tri, last, "high") - current) / current * 100, 0.0)
            for what, dist in ((KISS_LOW, to_low), (KISS_HIGH, to_high)):
                if dist <= settings.SR_NEAR_MAX_PCT:
                    rows.append(make_row(df, symbol, last, kind, what, tri, dist))
    return rows


# בדיקה: מציג את המשולשים הפעילים בכמה נכסים
if __name__ == "__main__":
    from data import fetch
    from indicators import add_indicators

    for sym in ["AAPL", "MSFT", "NVDA", "BTC/USDT"]:
        df = add_indicators(fetch(sym))
        found = active_triangles(df)
        if not found:
            print(f"{sym}: אין משולש פעיל")
        for kind, tri in found.items():
            last = len(df) - 1
            print(f"{sym}: {kind} מ-{df.index[tri['start']].date()}, נגיעות {tri['low_touches']}+"
                  f"{tri['high_touches']}, קודקוד בעוד {tri['apex'] - last:.0f} נרות")
