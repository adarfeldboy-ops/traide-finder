# מבנים טכניים: תעלה עולה.
#   תעלה עולה = המחיר נע בין שני קווים מקבילים שעולים - התחתון עובר דרך שפלים (קונים),
#   העליון דרך שיאים (מוכרים). כל שפל גבוה מהקודם וכל שיא גבוה מהקודם, ולפחות 2 נגיעות בכל קו.
#   נשיקה  = המחיר כעת קרוב לקו התחתון (מעליו) או לקו העליון (מתחתיו).
#   פריצה / שבירה = הסגירה הראשונה מעל הקו העליון / מתחת לקו התחתון. אחרי זה התעלה "מתה".
# כלל חשוב: ביום i משתמשים רק בנקודות מפנה שהתאשרו לפני יום i (בלי "הצצה לעתיד").
# התוצאות הן איתותים לבדיקה - לא המלצות קנייה או מכירה.

import numpy as np

import settings
from indicators import sma_col
from levels import find_swings

CH_KISS_LOW = "תעלה עולה – נשיקה לקו התחתון"
CH_KISS_HIGH = "תעלה עולה – נשיקה לקו העליון"
CH_BREAK_UP = "תעלה עולה – פריצה למעלה"
CH_BREAK_DOWN = "תעלה עולה – שבירה למטה"
CHANNEL_OPTIONS = [CH_KISS_LOW, CH_KISS_HIGH, CH_BREAK_UP, CH_BREAK_DOWN]
CHANNEL_KISSES = (CH_KISS_LOW, CH_KISS_HIGH)


def rising_run(points):
    """הרצף האחרון של נקודות שכל אחת גבוהה מהקודמת (מהסוף אחורה, בלי לדלג)."""
    run = points[-1:]
    for p in reversed(points[:-1]):
        if p[1] >= run[0][1]:
            break
        run.insert(0, p)
    return run


def trim(run, start):
    """הרצף מהנקודה האחרונה שלא אחרי start (כולל) ואילך."""
    before = [k for k, s in enumerate(run) if s[0] <= start]
    return run[before[-1]:] if before else run


def line_at(channel, pos, which):
    """ערך הקו ("low" / "high") ביום pos."""
    return channel[f"a_{which}"] + channel["slope"] * pos


def containment_breaks(channel, closes, tol, end):
    """ימים (מתחילת התעלה עד end, לא כולל) שבהם הסגירה יצאה מהתעלה מעבר לסובלנות."""
    pos = np.arange(channel["start"], end)
    seg, t = closes[channel["start"]:end], tol[channel["start"]:end]
    lower = channel["a_low"] + channel["slope"] * pos
    upper = channel["a_high"] + channel["slope"] * pos
    return np.nonzero((seg > upper + t) | (seg < lower - t))[0]


def channel_at(df, swings, i, closes=None, tol=None):
    """התעלה העולה שהייתה ידועה ביום i (על סמך נקודות מפנה שאושרו לפני i, וסגירות עד
    i-1), או None. מחזיר מילון: start, slope, a_low, a_high, נגיעות בכל קו, ATR."""
    closes = df["Close"].to_numpy() if closes is None else closes
    tol = channel_tolerances(df) if tol is None else tol
    first_allowed = i - settings.CHANNEL_LOOKBACK
    known = [s for s in swings if s[0] >= first_allowed and s[2] < i]
    lows = rising_run([s for s in known if not s[3]])
    highs = rising_run([s for s in known if s[3]])
    if len(lows) < settings.CHANNEL_MIN_TOUCHES or len(highs) < settings.CHANNEL_MIN_TOUCHES:
        return None
    # התעלה מתחילה כששני הקווים "פעילים": מהרצף שמתחיל מוקדם יותר נשארת רק הנקודה
    # האחרונה שלפני תחילת הרצף השני, וכל מה שאחריה
    start = max(lows[0][0], highs[0][0])
    lows, highs = trim(lows, start), trim(highs, start)
    if len(lows) < settings.CHANNEL_MIN_TOUCHES or len(highs) < settings.CHANNEL_MIN_TOUCHES:
        return None

    # שיפוע משותף לשני הקווים (רגרסיה עם חיתוך נפרד לכל קו) - כך הקווים מקבילים
    num = den = 0.0
    for group in (lows, highs):
        x = np.array([s[0] for s in group], float)
        y = np.array([s[1] for s in group], float)
        num += ((x - x.mean()) * (y - y.mean())).sum()
        den += ((x - x.mean()) ** 2).sum()
    slope = num / den if den else 0.0
    # עלייה מינימלית: 1% כל 20 נרות ביחס למחיר של אתמול (פחות מזה = טווח שטוח)
    if slope * 20 / closes[i - 1] * 100 < settings.CHANNEL_MIN_SLOPE_PCT:
        return None
    # הקו התחתון נשען על השפל הנמוך ביותר (ביחס לקו), העליון על השיא הגבוה ביותר
    a_low = min(s[1] - slope * s[0] for s in lows)
    a_high = max(s[1] - slope * s[0] for s in highs)

    def touches(group, a):
        return sum(abs(s[1] - (a + slope * s[0])) <= settings.CHANNEL_TOUCH_ATR * s[4] for s in group)

    low_touches, high_touches = touches(lows, a_low), touches(highs, a_high)
    points = lows + highs
    first, last = min(s[0] for s in points), max(s[0] for s in points)
    atr = df["ATR"].iloc[i - 1]
    channel = {"start": first, "last": last, "slope": slope, "a_low": a_low, "a_high": a_high,
               "low_touches": int(low_touches), "high_touches": int(high_touches)}
    if (low_touches < settings.CHANNEL_MIN_TOUCHES or high_touches < settings.CHANNEL_MIN_TOUCHES
            or last - first < settings.CHANNEL_MIN_BARS
            or a_high - a_low < settings.CHANNEL_MIN_WIDTH_ATR * atr):
        return None
    # כל הסגירות מתחילת התעלה עד אתמול בתוך הקווים (אחרת התעלה כבר נשברה)
    if len(containment_breaks(channel, closes, tol, i)):
        return None
    return channel


def channel_tolerances(df):
    """לכל יום: כמה צריך לסגור מעבר לקו כדי שזה ייחשב יציאה (0.3 ATR של היום הקודם)."""
    return settings.CHANNEL_BREAK_ATR * df["ATR"].shift(1).to_numpy()


def make_row(df, symbol, i, option, channel, dist_pct):
    """שורה בטבלה: האיתות, נתוני התעלה, ומצב הממוצעים/CCI/ווליום ביום האיתות."""
    row = df.iloc[i]
    direction = {CH_BREAK_UP: "למעלה", CH_BREAK_DOWN: "למטה"}.get(option, "")
    result = {
        "symbol": symbol,
        "option": option,
        "direction": direction,
        "date": df.index[i].date(),
        "days_ago": len(df) - 1 - i,
        "dist_pct": dist_pct,
        "lower": line_at(channel, i, "low"),
        "upper": line_at(channel, i, "high"),
        "low_touches": channel["low_touches"],
        "high_touches": channel["high_touches"],
        "start_date": df.index[channel["start"]].date(),
        # שיפוע: בכמה אחוזים הקו עולה ב-20 נרות (בערך חודש)
        "slope_pct_20": channel["slope"] * 20 / row["Close"] * 100,
        "close": row["Close"],
        "cci": row["CCI"],
        "vol_ratio": row["VolRatio"],
    }
    for period in (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG):
        result[f"above_{sma_col(period)}"] = bool(row["Close"] > row[sma_col(period)])
    return result


def broken_before(breaks, channel, i):
    """האם זו (כמעט) אותה תעלה שכבר נפרצה/נשברה ב-BREAK_MEMORY_BARS הנרות שלפני יום i:
    התעלה התחילה לפני יום היציאה הקודמת. (נקודת מפנה שהתאשרה אחרי היציאה יכולה להזיז
    מעט את הקווים כך שהסגירה של יום היציאה "חוזרת" לתוך התעלה - כך יציאה לא נספרת פעמיים.)"""
    return any(channel["start"] < day < i and i - day <= settings.BREAK_MEMORY_BARS
               for day in breaks)


def scan_channel(df, swings, start, closes, tol):
    """עובר יום-יום מ-start עד הנר האחרון. מחזיר ([(יום, סוג יציאה, תעלה)] ליציאות שנספרות,
    התעלה הפעילה אחרי הנר האחרון או None). כל יציאה נרשמת לזיכרון, גם חוזרת."""
    breaks, exits = [], []
    for i in range(start, len(df)):
        channel = channel_at(df, swings, i, closes, tol)
        if channel is None:
            continue
        if closes[i] > line_at(channel, i, "high") + tol[i]:
            option = CH_BREAK_UP
        elif closes[i] < line_at(channel, i, "low") - tol[i]:
            option = CH_BREAK_DOWN
        else:
            continue
        if not broken_before(breaks, channel, i):
            exits.append((i, option, channel))
        breaks.append(i)
    channel = channel_at(df, swings, len(df), closes, tol)
    if channel is not None and broken_before(breaks, channel, len(df)):
        channel = None  # "תחייה" של תעלה שכבר נשברה - לא פעילה
    return exits, channel


def active_channel(df, swings=None, min_move_atr=settings.SWING_MIN_MOVE_ATR):
    """התעלה שפעילה אחרי הנר האחרון (לנשיקות ולגרף), או None."""
    swings = find_swings(df, min_move_atr) if swings is None else swings
    start = max(settings.SWING_BARS + 1, len(df) - settings.BREAK_MEMORY_BARS)
    return scan_channel(df, swings, start, df["Close"].to_numpy(), channel_tolerances(df))[1]


def channel_signals(df, symbol, lookback=None, min_move_atr=settings.SWING_MIN_MOVE_ATR,
                    swings=None):
    """פריצות/שבירות של תעלה ב-lookback הנרות האחרונים + נשיקות כרגע. df עם אינדיקטורים.
    מחזיר שורה לכל איתות. סינון לפי טווח נשיקה / חלון נעשה באתר.
    מתחילים BREAK_MEMORY_BARS נרות לפני החלון רק כדי "לזכור" יציאות קודמות (תעלה נפרצת
    פעם אחת בלבד), וכל יום בודק רק את הזיכרון שלפניו - כך התוצאה לא תלויה בגודל החלון."""
    lookback = lookback or settings.LOOKBACK_DAYS
    swings = find_swings(df, min_move_atr) if swings is None else swings
    closes = df["Close"].to_numpy()
    tol = channel_tolerances(df)
    first_reported = len(df) - lookback
    start = max(settings.SWING_BARS + 1, first_reported - settings.BREAK_MEMORY_BARS)
    exits, channel = scan_channel(df, swings, start, closes, tol)
    rows = []
    current = closes[-1]
    for i, option, ch in exits:
        if i < first_reported:
            continue
        edge = line_at(ch, i, "high" if option == CH_BREAK_UP else "low")
        rows.append(make_row(df, symbol, i, option, ch, (current - edge) / edge * 100))

    if channel is not None:
        last, close = len(df) - 1, closes[-1]
        to_low = max((close - line_at(channel, last, "low")) / close * 100, 0.0)
        to_high = max((line_at(channel, last, "high") - close) / close * 100, 0.0)
        for option, dist in ((CH_KISS_LOW, to_low), (CH_KISS_HIGH, to_high)):
            if dist <= settings.SR_NEAR_MAX_PCT:
                rows.append(make_row(df, symbol, last, option, channel, dist))
    return rows


# בדיקה: מציג את התעלה הפעילה בכמה נכסים
if __name__ == "__main__":
    from data import fetch
    from indicators import add_indicators

    for sym in ["AAPL", "MSFT", "NVDA", "BTC/USDT"]:
        df = add_indicators(fetch(sym))
        ch = active_channel(df)
        if ch is None:
            print(f"{sym}: אין תעלה עולה פעילה")
            continue
        last = len(df) - 1
        print(f"{sym}: תעלה מ-{df.index[ch['start']].date()}, נגיעות {ch['low_touches']}+"
              f"{ch['high_touches']}, קו תחתון {line_at(ch, last, 'low'):.2f}, "
              f"עליון {line_at(ch, last, 'high'):.2f}, סגירה {df['Close'].iloc[-1]:.2f}")
