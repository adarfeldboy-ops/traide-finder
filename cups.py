# מבנים טכניים: קאפ אנד הנדל (ספל וידית).
#   עלייה -> שפה שמאלית (שיא) -> ירידה מעוגלת והתאוששות (צורת U) -> שפה ימנית ליד אותו גובה ->
#   ידית: ירידה קטנה בחצי העליון של הספל -> נקודת פריצה (pivot) = השיא של השפה הימנית.
#   "לפני פריצה" = הידית קיימת והמחיר מתחת לנקודת הפריצה. "פריצה" = הסגירה הראשונה מעליה.
#   התקופה (קצרה / בינונית / ארוכה) = משך הספל משפה לשפה.
# כלל חשוב: ביום i משתמשים רק בנקודות מפנה שהתאשרו לפני יום i ובנרות עד יום i-1 (בלי הצצה לעתיד).
# התוצאות הן איתותים לבדיקה - לא המלצות קנייה או מכירה.

import numpy as np

import settings
from data import is_crypto
from indicators import sma_col
from levels import find_swings

CUP_NAME = "קאפ אנד הנדל"
SHORT, MEDIUM, LONG = "קצרה", "בינונית", "ארוכה"
PERIODS = (SHORT, MEDIUM, LONG)
CUP_OPTIONS = [f"{CUP_NAME} – {p}" for p in PERIODS]
CUP_PERIOD_OF = dict(zip(CUP_OPTIONS, PERIODS))
STATE_ALL, STATE_BEFORE, STATE_BREAKOUT = "הכל", "לפני פריצה", "פריצה"
CUP_STATES = (STATE_ALL, STATE_BEFORE, STATE_BREAKOUT)


def time_scale(symbol):
    """כמה נרות יש בחודש ביחס למניה. ההגדרות כתובות בימי מסחר של מניות (כ-21 בחודש);
    קריפטו נסחר כל יום (כ-30 נרות בחודש) - לכן שם כל משך זמן ארוך פי 365/252."""
    return 365 / 252 if is_crypto(symbol) else 1.0


def period_of(length, scale=1.0):
    """התקופה לפי משך הספל בנרות, או None אם קצר/ארוך מדי. scale = time_scale של הנכס."""
    if length < settings.CUP_MIN_BARS * scale or length > settings.CUP_MAX_BARS * scale:
        return None
    if length < settings.CUP_MEDIUM_BARS * scale:
        return SHORT
    return MEDIUM if length < settings.CUP_LONG_BARS * scale else LONG


def tolerances(df):
    """לכל יום: כמה צריך לסגור מעל נקודת הפריצה כדי שזו תהיה פריצה (0.2 ATR של היום הקודם)."""
    return settings.CUP_BREAK_ATR * df["ATR"].shift(1).to_numpy()


def check_cup(H, L, C, left, right, period):
    """בודק את הספל בין השפה השמאלית לימנית. מחזיר (תחתית, מיקום התחתית, עומק) או None."""
    lp, lprice = left[0], left[1]
    rp, rprice = right[0], right[1]
    if not lprice * (1 - settings.CUP_LIP_BELOW_PCT / 100) <= rprice <= lprice * (1 + settings.CUP_LIP_ABOVE_PCT / 100):
        return None  # השפה הימנית לא חזרה לגובה של השמאלית
    inside = slice(lp + 1, rp)
    if H[inside].max() > lprice:
        return None  # המחיר עבר את השפה השמאלית באמצע - זה לא ספל
    bottom_pos = lp + 1 + int(np.argmin(L[inside]))
    bottom = L[bottom_pos]
    depth = (lprice - bottom) / lprice * 100
    max_depth = settings.CUP_DEPTH_MAX_LONG_PCT if period == LONG else settings.CUP_DEPTH_MAX_PCT
    if not settings.CUP_DEPTH_MIN_PCT <= depth <= max_depth:
        return None
    where = (bottom_pos - lp) / (rp - lp)
    lo, hi = settings.CUP_BOTTOM_POSITION
    if not lo <= where <= hi:
        return None  # התחתית צמודה לאחת השפות
    # צורת U: זמן משמעותי ליד התחתית (בשליש התחתון של העומק). ב-V חד המחיר רק נוגע ועולה.
    near_bottom = C[inside] <= bottom + settings.CUP_ROUND_ZONE * (lprice - bottom)
    if near_bottom.mean() < settings.CUP_ROUND_MIN_FRAC:
        return None
    # בלי "קוץ": סביב השפל המחיר לא מזנק מיד (תחתית מעוגלת, לא V חד)
    w = max(2, round(settings.CUP_BOTTOM_WINDOW * (rp - lp)))
    around = C[max(lp + 1, bottom_pos - w):min(rp, bottom_pos + w + 1)]
    if around.max() > bottom + settings.CUP_BOTTOM_MAX_RISE * (lprice - bottom):
        return None
    return bottom, bottom_pos, depth


def prior_uptrend(C, left, length, scale=1.0):
    """האם לפני השפה השמאלית הייתה עלייה של CUP_PRIOR_RISE_PCT לפחות - בתוך CUP_PRIOR_MIN_BARS
    הנרות שלפניה, או כאורך הספל אם הוא ארוך יותר (לספל ארוך - מגמה ארוכה)."""
    lp, lprice = left[0], left[1]
    start = max(0, lp - max(round(settings.CUP_PRIOR_MIN_BARS * scale), length))
    if lp - start < 20:
        return False  # אין מספיק נתונים לפני הספל
    return lprice >= C[start:lp].min() * (1 + settings.CUP_PRIOR_RISE_PCT / 100)


def cups_at(df, swings, i, arrays=None, scale=1.0):
    """{תקופה: ספל} - הספלים עם ידית שהיו ידועים ביום i (נקודות מפנה שאושרו לפני i, נרות
    עד i-1). לכל תקופה - הספל עם השפה הימנית החדשה ביותר (ובה השפה השמאלית הקרובה ביותר)."""
    H, L, C, V, tol = arrays or (df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy(),
                                 df["Volume"].to_numpy(), tolerances(df))
    highs = [s for s in swings if s[3] and s[2] < i]
    longest_handle = max(settings.HANDLE_MAX_BARS.values()) * scale
    found = {}
    for r in range(len(highs) - 1, -1, -1):
        right = highs[r]
        rp, pivot = right[0], right[1]
        handle_bars = i - 1 - rp  # הנרות שאחרי השפה הימנית, עד אתמול
        if handle_bars > longest_handle:
            break  # שפות ימניות ישנות יותר - הידית שלהן ארוכה מדי
        if handle_bars < settings.HANDLE_MIN_BARS * scale:
            continue
        handle = slice(rp + 1, i)
        if H[handle].max() > pivot or (C[handle] > pivot + tol[handle]).any():
            continue  # המחיר כבר עבר את השפה - זו לא ידית (או שהפריצה כבר קרתה)
        handle_low_pos = rp + 1 + int(np.argmin(L[handle]))
        handle_low = L[handle_low_pos]
        handle_depth = (pivot - handle_low) / pivot * 100
        if not settings.HANDLE_MIN_PCT <= handle_depth <= settings.HANDLE_MAX_PCT:
            continue
        for left in reversed(highs[:r]):
            length = rp - left[0]
            if length < settings.CUP_MIN_BARS * scale:
                continue
            period = period_of(length, scale)
            if period is None:
                break  # שפות שמאליות ישנות יותר - ארוכות מדי
            if period in found:
                continue
            cup = check_cup(H, L, C, left, right, period)
            if cup is None or not prior_uptrend(C, left, length, scale):
                continue
            bottom, bottom_pos, depth = cup
            # הידית: בחצי העליון של הספל, לא עמוקה משליש הספל, וקצרה מספיק
            if (handle_low < bottom + 0.5 * (left[1] - bottom)
                    or handle_depth > depth * settings.HANDLE_MAX_DEPTH_FRAC
                    or handle_bars > min(settings.HANDLE_MAX_BARS[period] * scale,
                                         settings.HANDLE_MAX_FRAC * length)):
                continue
            cup_vol = V[left[0]:rp + 1].mean()
            found[period] = {
                "period": period, "left": left[0], "left_price": left[1], "right": rp,
                "pivot": pivot, "bottom": bottom_pos, "bottom_price": bottom, "depth": depth,
                "handle_low": handle_low_pos, "handle_low_price": handle_low, "handle_depth": handle_depth,
                "cup_bars": length, "handle_bars": handle_bars,
                # ווליום בידית לעומת הספל (מתחת ל-1 = "מתייבש" - סימן טוב, רק להצגה)
                "handle_vol": V[handle].mean() / cup_vol if cup_vol else np.nan,
            }
    return found


def make_row(df, symbol, i, cup, state, dist_pct):
    """שורה בטבלה: הספל, מצבו, ומצב הממוצעים/CCI/ווליום ביום האיתות."""
    row, dates = df.iloc[i], df.index
    result = {
        "symbol": symbol,
        "option": f"{CUP_NAME} – {cup['period']}",
        "period": cup["period"],
        "state": state,
        "direction": "למעלה" if state == STATE_BREAKOUT else "",
        "date": dates[i].date(),
        "days_ago": len(df) - 1 - i,
        "dist_pct": dist_pct,
        "pivot": cup["pivot"],
        "depth_pct": cup["depth"],
        "handle_pct": cup["handle_depth"],
        "cup_bars": cup["cup_bars"],
        "handle_bars": cup["handle_bars"],
        "handle_vol": cup["handle_vol"],
        "left_date": dates[cup["left"]].date(), "left_price": cup["left_price"],
        "bottom_date": dates[cup["bottom"]].date(), "bottom_price": cup["bottom_price"],
        "right_date": dates[cup["right"]].date(), "right_price": cup["pivot"],
        "handle_low_date": dates[cup["handle_low"]].date(), "handle_low_price": cup["handle_low_price"],
        "close": row["Close"],
        "cci": row["CCI"],
        "vol_ratio": row["VolRatio"],
    }
    for period in (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG):
        result[f"above_{sma_col(period)}"] = bool(row["Close"] > row[sma_col(period)])
    return result


def cup_signals(df, symbol, lookback=None, min_move_atr=settings.SWING_MIN_MOVE_ATR, swings=None):
    """פריצות ב-lookback הנרות האחרונים + ספלים "לפני פריצה" כרגע. df עם אינדיקטורים.
    ספל נפרץ פעם אחת: אחרי הסגירה מעל נקודת הפריצה הוא כבר לא עובר את בדיקת הידית."""
    lookback = lookback or settings.LOOKBACK_DAYS
    swings = find_swings(df, min_move_atr) if swings is None else swings
    arrays = (df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy(),
              df["Volume"].to_numpy(), tolerances(df))
    closes, tol = arrays[2], arrays[4]
    scale = time_scale(symbol)  # קריפטו: חודש = כ-30 נרות, לא 21
    current = closes[-1]
    rows = []
    for i in range(max(settings.SWING_BARS + 1, len(df) - lookback), len(df)):
        for cup in cups_at(df, swings, i, arrays, scale).values():
            if closes[i] > cup["pivot"] + tol[i]:
                dist = (current - cup["pivot"]) / cup["pivot"] * 100
                rows.append(make_row(df, symbol, i, cup, STATE_BREAKOUT, dist))
    for cup in cups_at(df, swings, len(df), arrays, scale).values():
        dist = max((cup["pivot"] - current) / current * 100, 0.0)
        if dist <= settings.SR_NEAR_MAX_PCT:
            rows.append(make_row(df, symbol, len(df) - 1, cup, STATE_BEFORE, dist))
    return rows


# בדיקה: הספלים הפעילים בכמה נכסים
if __name__ == "__main__":
    from data import fetch
    from indicators import add_indicators

    for sym in ["AAPL", "NVDA", "MSFT", "BTC/USDT"]:
        df = add_indicators(fetch(sym))
        cups = cups_at(df, find_swings(df), len(df), scale=time_scale(sym))
        print(sym, {p: (df.index[c["left"]].date(), round(c["depth"], 1), round(c["handle_depth"], 1))
                    for p, c in cups.items()} or "אין ספל")
