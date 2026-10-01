# תמיכה והתנגדות כ"אזורים": טווחי מחיר שבהם המחיר התהפך כמה פעמים.
#   תמיכה  = אזור שבכל פעם שהמחיר ירד אליו - הוא עלה חזרה (קונים נכנסו שם).
#   התנגדות = אזור שבכל פעם שהמחיר עלה אליו - הוא ירד חזרה (מוכרים נכנסו שם).
#   פריצה  = הסגירה הראשונה מעבר לאזור שעד אתמול "החזיק". אחרי פריצה האזור "מת".
#   נשיקה  = המחיר קרוב לאזור שעדיין מחזיק (0%-X% מהצד שלו, או בתוך האזור).
# כלל חשוב: ביום i משתמשים רק במה שהיה ידוע לפני יום i (בלי "הצצה לעתיד").
# התוצאות הן איתותים לבדיקה - לא המלצות קנייה או מכירה.

import numpy as np

import settings
from indicators import sma_col

SUPPORT = "תמיכה"
RESISTANCE = "התנגדות"
BREAKOUT = "פריצה"
KISS = "נשיקה"

# ארבע האפשרויות שהמשתמש בוחר באתר: שם -> (סוג איתות, סוג אזור)
RES_BREAK = "פריצת התנגדות ↑"
SUP_BREAK = "שבירת תמיכה ↓"
RES_KISS = "נשיקה להתנגדות"
SUP_KISS = "נשיקה לתמיכה"
SR_OPTIONS = {
    RES_BREAK: (BREAKOUT, RESISTANCE),
    SUP_BREAK: (BREAKOUT, SUPPORT),
    RES_KISS: (KISS, RESISTANCE),
    SUP_KISS: (KISS, SUPPORT),
}
OPTION_NAME = {pair: name for name, pair in SR_OPTIONS.items()}


# --- שלב 1: נקודות מפנה משמעותיות ---

def confirm_swing(highs, lows, p, is_high, move):
    """היום שבו התאשר ההיפוך אחרי שיא/שפל ביום p, או None אם לא היה היפוך אמיתי.
    היפוך אמיתי = המחיר התרחק לפחות move מהשיא/השפל, לפני שעבר אותו."""
    end = min(len(highs), p + 1 + settings.SWING_CONFIRM_BARS)
    for j in range(p + 1, end):
        if is_high:
            if highs[j] > highs[p]:
                return None  # המחיר עבר את השיא - זה לא היה שיא
            if lows[j] <= highs[p] - move:
                return j
        else:
            if lows[j] < lows[p]:
                return None
            if highs[j] >= lows[p] + move:
                return j
    return None


def find_swings(df, min_move_atr=settings.SWING_MIN_MOVE_ATR):
    """[(מיקום, מחיר, יום האישור, האם שיא, ATR באותו יום)] של שיאים ושפלים שאחריהם
    היה היפוך משמעותי. שיא = גבוה מ-SWING_BARS הנרות שלפניו ולא נמוך מ-SWING_BARS
    הנרות שאחריו, ואחריו ירידה של לפחות min_move_atr * ATR. מותר להשתמש בו רק אחרי יום האישור."""
    bars = settings.SWING_BARS
    highs, lows = df["High"].to_numpy(), df["Low"].to_numpy()
    atr = df["ATR"].to_numpy()
    swings = []
    for p in range(bars, len(df) - bars):
        if np.isnan(atr[p]):
            continue
        move = min_move_atr * atr[p]  # ATR ביום p - ידוע כבר ביום p
        before, after = slice(p - bars, p), slice(p + 1, p + bars + 1)
        is_top = highs[p] > highs[before].max() and highs[p] >= highs[after].max()
        is_bottom = lows[p] < lows[before].min() and lows[p] <= lows[after].min()
        for is_high, ok, price in ((True, is_top, highs[p]), (False, is_bottom, lows[p])):
            if ok:
                confirmed = confirm_swing(highs, lows, p, is_high, move)
                if confirmed is not None:
                    swings.append((p, price, max(confirmed, p + bars), is_high, atr[p]))
    return swings


# --- שלב 2: קיבוץ לאזורים ---

def swing_width(swing, zone_atr=settings.ZONE_WIDTH_ATR):
    """רוחב אזור סביב נקודת מפנה: חלק מה-ATR ביום שלה, בין ZONE_MIN_PCT ל-ZONE_MAX_PCT
    מהמחיר. נקבע לפי נקודת המפנה עצמה - כך גבולות האזור לא זזים מיום ליום."""
    price, atr = swing[1], swing[4]
    return float(np.clip(zone_atr * atr, price * settings.ZONE_MIN_PCT / 100,
                         price * settings.ZONE_MAX_PCT / 100))


def tolerances(df):
    """כמה צריך לסגור מעבר לאזור כדי שזה ייחשב חצייה, לכל יום: 0.2 ATR של היום הקודם.
    (מספר קבוע לכל יום בהיסטוריה - לא משתנה לפי היום שבודקים.)"""
    return settings.BREAK_TOL_ATR * df["ATR"].shift(1).to_numpy()


def find_ranges(swings, i, zone_atr=settings.ZONE_WIDTH_ATR):
    """[(תחתית, ראש, נקודות מפנה)] - טווחי מחיר שבהם יש נקודות מפנה קרובות.
    רק נקודות מ-SR_LOOKBACK_CANDLES הנרות שלפני i, שאושרו לפני i.
    רוחב כל טווח לא עובר ZONE_MAX_PCT מהמחיר."""
    first_allowed = i - settings.SR_LOOKBACK_CANDLES
    known = sorted((s for s in swings if s[0] >= first_allowed and s[2] < i), key=lambda s: s[1])
    groups, group = [], []
    for swing in known:
        if group and swing[1] - group[0][1] > swing_width(group[0], zone_atr):
            groups.append(group)
            group = []
        group.append(swing)
    if group:
        groups.append(group)

    ranges = []
    for group in groups:
        prices = [s[1] for s in group]
        width = np.mean([swing_width(s, zone_atr) for s in group])
        mid = (min(prices) + max(prices)) / 2
        half = max(max(prices) - min(prices), width) / 2
        half = min(half, mid * settings.ZONE_MAX_PCT / 100 / 2)  # לא רחב מ-ZONE_MAX_PCT
        low, high = mid - half, mid + half
        if ranges and low <= ranges[-1][1]:  # חופף לטווח הקודם
            prev_low, prev_high, members = ranges[-1]
            merged_high = max(prev_high, high)
            cap = (prev_low + merged_high) / 2 * settings.ZONE_MAX_PCT / 100
            if merged_high - prev_low <= cap:
                ranges[-1] = (prev_low, merged_high, members + group)  # מאחדים לאזור אחד
                continue
            # איחוד ייצור אזור רחב מדי - מחלקים את החפיפה באמצע, אבל כך שכל נקודת מפנה
            # נשארת בתוך האזור שלה (הגבול בין השיא של הקודם לשפל של הנוכחי)
            border = (low + prev_high) / 2
            border = min(max(border, max(s[1] for s in members)), min(prices))
            ranges[-1] = (prev_low, border, members)
            low = border
        ranges.append((low, high, group))
    return ranges


def count_touches(positions):
    """הנגיעות שנספרות: רק כאלה שרחוקות לפחות TOUCH_GAP_BARS נרות מהנגיעה הקודמת."""
    counted = []
    for pos in sorted(positions):
        if not counted or pos - counted[-1] >= settings.TOUCH_GAP_BARS:
            counted.append(pos)
    return counted


def mean_ignore_nan(values):
    values = [v for v in values if not np.isnan(v)]
    return float(np.mean(values)) if values else np.nan


def held_zone(df, closes, tol, low, high, members, i, kind):
    """האזור בתפקיד kind ביום i, אם הוא "מחזיק" ויש לו מספיק נגיעות - אחרת None.

    התנגדות: נגיעות = שיאים באזור (מוכרים הפכו את המחיר למטה), שקרו אחרי הסגירה
    האחרונה מעל ראש האזור. כך אף סגירה מאז הנגיעה הראשונה לא עברה את האזור, וסגירה
    שפרצה אותו "מוחקת" את כל הנגיעות שלפניה - האזור לא יכול להיפרץ פעמיים.
    תמיכה: אותו דבר הפוך - שפלים, אחרי הסגירה האחרונה מתחת לתחתית האזור.
    (אזור שהיה התנגדות ונפרץ יכול להפוך לתמיכה - אם המחיר חזר ונבדק בו מלמעלה.)
    """
    if kind == RESISTANCE:
        beyond = np.nonzero(closes[:i] > high + tol[:i])[0]
    else:
        beyond = np.nonzero(closes[:i] < low - tol[:i])[0]
    since = beyond[-1] + 1 if len(beyond) else 0
    is_high = kind == RESISTANCE
    touches = count_touches([s[0] for s in members if s[3] == is_high and s[0] >= since])
    if len(touches) < settings.SR_MIN_TOUCHES:
        return None
    return {
        "low": low,
        "high": high,
        "touches": len(touches),
        "first": touches[0],
        "last": touches[-1],
        "touch_vol": mean_ignore_nan(df["VolRatio"].to_numpy()[touches]),  # ווליום בנרות הנגיעה
    }


def zones_at(df, swings, i, zone_atr=settings.ZONE_WIDTH_ATR, tol=None):
    """[(אזור, סוג)] - כל האזורים שמחזיקים ביום i (על סמך מה שידוע עד יום i-1)."""
    closes = df["Close"].to_numpy()
    tol = tolerances(df) if tol is None else tol
    found = []
    for low, high, members in find_ranges(swings, i, zone_atr):
        for kind in (RESISTANCE, SUPPORT):
            zone = held_zone(df, closes, tol, low, high, members, i, kind)
            if zone:
                found.append((zone, kind))
    return found


# --- שלב 3: איתותים ---

def make_row(df, symbol, i, signal_type, kind, zone, dist_pct, inside=False):
    """שורה בטבלה: האיתות, האזור, ומצב הממוצעים/CCI/ווליום ביום האיתות."""
    row = df.iloc[i]
    # הקצה הרלוונטי: בפריצת התנגדות ובנשיקה לתמיכה - הקצה העליון; באחרים - התחתון
    edge = zone["high"] if (signal_type == BREAKOUT) == (kind == RESISTANCE) else zone["low"]
    result = {
        "symbol": symbol,
        "option": OPTION_NAME[(signal_type, kind)],
        "type": signal_type,
        "level_kind": kind,
        "zone_low": zone["low"],
        "zone_high": zone["high"],
        "level": edge,  # הקצה שנפרץ (בפריצה) או הקצה הקרוב (בנשיקה)
        "touches": zone["touches"],
        "last_touch": df.index[zone["last"]].date(),
        "touch_vol": zone["touch_vol"],
        "date": df.index[i].date(),
        "days_ago": len(df) - 1 - i,
        "dist_pct": dist_pct,
        "inside": inside,
        "close": row["Close"],
        "cci": row["CCI"],
        "vol_ratio": row["VolRatio"],
    }
    for period in (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG):
        result[f"above_{sma_col(period)}"] = bool(row["Close"] > row[sma_col(period)])
    return result


def near_zones(df, swings, zone_atr=settings.ZONE_WIDTH_ATR):
    """[(אזור, סוג, מרחק %, בתוך האזור?)] לאזורים שמחזיקים כרגע, מהצד הנכון של המחיר:
    התנגדות - המחיר מתחתיה או בתוכה; תמיכה - המחיר מעליה או בתוכה.
    המרחק = מהסגירה האחרונה עד הקצה הקרוב (0 כשהמחיר בתוך האזור)."""
    close = df["Close"].iloc[-1]
    found = []
    # "יום הבדיקה" = אחרי הנר האחרון: כל הנרות עד האחרון (כולל) כבר ידועים
    for zone, kind in zones_at(df, swings, len(df), zone_atr):
        if kind == RESISTANCE:
            dist = (zone["low"] - close) / close * 100
        else:
            dist = (close - zone["high"]) / close * 100
        # האזור מחזיק, לכן המחיר לא מעבר לו: מרחק שלילי = המחיר בתוך האזור
        found.append((zone, kind, max(dist, 0.0), dist <= 0))
    return [f for f in found if keep_inside_role(df, f, found)]


def keep_inside_role(df, item, found):
    """המחיר בתוך אזור שמחזיק גם כתמיכה וגם כהתנגדות - מציגים נשיקה אחת בלבד, לפי
    הכיוון שממנו המחיר נכנס לאזור: ירד אליו מלמעלה = תמיכה, עלה אליו מלמטה = התנגדות."""
    zone, kind, _, inside = item
    twin = any(z is not zone and z["low"] == zone["low"] and z["high"] == zone["high"]
               and k != kind and ins for z, k, _, ins in found)
    if not inside or not twin:
        return True
    closes = df["Close"].to_numpy()
    outside = np.nonzero((closes > zone["high"]) | (closes < zone["low"]))[0]
    from_above = len(outside) > 0 and closes[outside[-1]] > zone["high"]
    return kind == (SUPPORT if from_above else RESISTANCE)


def sr_signals(df, symbol, lookback=None, min_move_atr=settings.SWING_MIN_MOVE_ATR,
               zone_atr=settings.ZONE_WIDTH_ATR, swings=None):
    """פריצות ב-lookback הנרות האחרונים + נשיקות כרגע. df חייב לכלול אינדיקטורים.

    מחזיר שורה לכל אזור שנפרץ / לכל אזור קרוב. הבחירה (האזור החזק ביותר בפריצה,
    הקרוב ביותר בנשיקה, מינימום נגיעות, טווח נשיקה) נעשית באתר - בלי לסרוק מחדש.
    swings = נקודות מפנה שכבר חושבו (חוסך חישוב כפול); None = מחשבים כאן.
    """
    lookback = lookback or settings.LOOKBACK_DAYS
    swings = find_swings(df, min_move_atr) if swings is None else swings
    closes = df["Close"].to_numpy()
    tol = tolerances(df)
    current = closes[-1]
    rows = []
    broken = []  # כל הפריצות שזוהו (גם חוזרות): (תחתית, ראש, סוג, יום הפריצה)

    # פריצה: הסגירה ביום i עברה אזור שהחזיק עד יום i-1.
    # מתחילים BREAK_MEMORY_BARS נרות לפני החלון רק כדי "לזכור" פריצות קודמות.
    # כל יום בודק רק פריצות מ-BREAK_MEMORY_BARS הנרות שלפניו - כך התוצאה של יום מסוים
    # זהה בכל גודל חלון.
    first_reported = len(df) - lookback
    start = max(settings.SWING_BARS + 1, first_reported - settings.BREAK_MEMORY_BARS)
    for i in range(start, len(df)):
        for zone, kind in zones_at(df, swings, i, zone_atr, tol):
            if kind == RESISTANCE:
                is_break, edge = closes[i] > zone["high"] + tol[i], zone["high"]
            else:
                is_break, edge = closes[i] < zone["low"] - tol[i], zone["low"]
            if not is_break:
                continue
            repeat = already_broken(broken, zone, kind, i)
            broken.append((zone["low"], zone["high"], kind, i))
            if i >= first_reported and not repeat:
                dist = (current - edge) / edge * 100
                rows.append(make_row(df, symbol, i, BREAKOUT, kind, zone, dist))

    # נשיקה: אזורים שעדיין מחזיקים, והמחיר קרוב אליהם מהצד שלהם או בתוכם
    for zone, kind, dist, inside in near_zones(df, swings, zone_atr):
        if dist <= settings.SR_NEAR_MAX_PCT and not already_broken(broken, zone, kind, len(df)):
            rows.append(make_row(df, symbol, len(df) - 1, KISS, kind, zone, dist, inside))
    return rows


def already_broken(broken, zone, kind, i):
    """האם זה (כמעט) אותו אזור שכבר נפרץ ב-BREAK_MEMORY_BARS הנרות שלפני יום i - חופף
    לאזור שנפרץ מאותו סוג, ואין לו נגיעה חדשה מאז הפריצה. (נקודת מפנה שהתאשרה מאוחר
    יכולה להזיז מעט את גבולות האזור ולגרום לו "להחזיק" שוב - כך פריצה אחת לא נספרת פעמיים.)"""
    return any(k == kind and i - settings.BREAK_MEMORY_BARS <= day < i
               and zone["low"] < high and low < zone["high"] and zone["last"] < day
               for low, high, k, day in broken)


def chart_zones(df, min_touches=settings.SR_MIN_TOUCHES, touch_vol_min=None, per_side=2,
                min_move_atr=settings.SWING_MIN_MOVE_ATR, zone_atr=settings.ZONE_WIDTH_ATR):
    """האזורים הקרובים ביותר שמחזיקים כרגע (לגרף): [(אזור, סוג)], עד per_side מכל צד.
    אותם כללים כמו בטבלאות: מינימום נגיעות, ווליום בנגיעות (None = כבוי)."""
    found = [z for z in near_zones(df, find_swings(df, min_move_atr), zone_atr)
             if z[0]["touches"] >= min_touches
             and (touch_vol_min is None or z[0]["touch_vol"] >= touch_vol_min)]
    result = []
    for kind in (SUPPORT, RESISTANCE):
        side = sorted((z for z in found if z[1] == kind), key=lambda z: z[2])
        result += [(zone, kind) for zone, kind, _, _ in side[:per_side]]
    return result


# בדיקה: מציג את האזורים שמחזיקים כרגע בכמה נכסים
if __name__ == "__main__":
    from data import fetch
    from indicators import add_indicators

    for sym in ["AAPL", "BTC/USDT"]:
        df = add_indicators(fetch(sym))
        print(f"\n{sym}: סגירה אחרונה {df['Close'].iloc[-1]:.2f}")
        for zone, kind, dist, inside in near_zones(df, find_swings(df)):
            where = "בתוך האזור" if inside else f"מרחק {dist:.2f}%"
            print(f"  {kind}: {zone['low']:.2f}-{zone['high']:.2f}, נגיעות {zone['touches']}, "
                  f"אחרונה {df.index[zone['last']].date()}, ווליום בנגיעות "
                  f"{zone['touch_vol']:.2f}, {where}")
