# זיהוי איתותים: חציות ממוצעים נעים + אזורי תמיכה/התנגדות, וסינון התוצאות.
# התוצאות הן איתותים לבדיקה - לא המלצות קנייה או מכירה.

import pandas as pd

import settings
from channels import CHANNEL_KISSES, CHANNEL_OPTIONS, channel_signals
from triangles import TRIANGLE_KISSES, TRIANGLE_OPTIONS, triangle_signals
from cups import CUP_OPTIONS, STATE_ALL, STATE_BEFORE, STATE_BREAKOUT, cup_signals
from data import fetch_many, is_crypto, load_assets
from indicators import add_indicators, sma_col
from levels import BREAKOUT, KISS, RESISTANCE, SR_OPTIONS, SUPPORT, find_swings, sr_signals

UP = "למעלה"
DOWN = "למטה"
SMA_PERIODS = (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG)


def signal_pairs():
    """אילו קווים בודקים לחצייה: (שם האיתות, קו מהיר, קו איטי)."""
    mid, long = sma_col(settings.SMA_MID), sma_col(settings.SMA_LONG)
    return [
        (f"{mid} חוצה {long}", mid, long),
        (f"מחיר חוצה {long}", "Close", long),
    ]


def find_crosses(df, fast, slow, lookback=None):
    """מחזיר [(מיקום הנר, כיוון)] לכל חצייה ב-lookback הנרות האחרונים."""
    lookback = lookback or settings.LOOKBACK_DAYS
    diff = df[fast] - df[slow]
    crosses = []
    start = max(1, len(df) - lookback)
    for i in range(start, len(df)):
        before, now = diff.iloc[i - 1], diff.iloc[i]
        if pd.isna(before) or pd.isna(now):
            continue
        if before <= 0 < now:
            crosses.append((i, UP))
        elif before >= 0 > now:
            crosses.append((i, DOWN))
    return crosses


def latest_row(df, symbol):
    """הנר האחרון של הנכס - לטבלת "סורק" (כשמסננים רק לפי CCI/ווליום)."""
    row = df.iloc[-1]
    result = {
        "symbol": symbol,
        "date": df.index[-1].date(),
        "close": row["Close"],
        "change_pct": (row["Close"] / df["Close"].iloc[-2] - 1) * 100,
        "vol_ratio": row["VolRatio"],
        "cci": row["CCI"],
    }
    for period in SMA_PERIODS:
        result[f"above_{sma_col(period)}"] = bool(row["Close"] > row[sma_col(period)])
    return result


def quality_problem(df, symbol):
    """סיבה לדלג על מניה "לא איכותית" (מחיר נמוך / מעט מסחר), או None. קריפטו לא נבדק."""
    if is_crypto(symbol):
        return None
    close = df["Close"].iloc[-1]
    if close < settings.MIN_STOCK_PRICE:
        return f"מחיר {close:.2f}$ - נמוך מ-{settings.MIN_STOCK_PRICE:.0f}$"
    recent = df.tail(settings.DOLLAR_VOLUME_DAYS)
    dollar_volume = (recent["Close"] * recent["Volume"]).mean()
    if dollar_volume < settings.MIN_DOLLAR_VOLUME:
        return (f"מחזור מסחר ממוצע {dollar_volume / 1e6:.1f} מיליון$ ביום - פחות מ-"
                f"{settings.MIN_DOLLAR_VOLUME / 1e6:.0f} מיליון$")
    return None


def scan_symbol(df, symbol, lookback=None, swing_atr=settings.SWING_MIN_MOVE_ATR,
                zone_atr=settings.ZONE_WIDTH_ATR):
    """מחפש איתותים בנכס אחד.
    מחזיר (חציות ממוצעים, איתותי תמיכה/התנגדות, איתותי תעלה, הנר האחרון)."""
    df = add_indicators(df)
    crosses = []
    for name, fast, slow in signal_pairs():
        for i, direction in find_crosses(df, fast, slow, lookback):
            row = df.iloc[i]
            crosses.append({
                "symbol": symbol,
                "signal": name,
                "direction": direction,
                "date": df.index[i].date(),
                "days_ago": len(df) - 1 - i,
                "close": row["Close"],
                "vol_ratio": row["VolRatio"],
                "cci": row["CCI"],
            })
    swings = find_swings(df, swing_atr)  # פעם אחת - משמש אזורים, תעלות ומשולשים
    sr_rows = sr_signals(df, symbol, lookback, swing_atr, zone_atr, swings)
    channel_rows = channel_signals(df, symbol, lookback, swing_atr, swings)
    triangle_rows = triangle_signals(df, symbol, lookback, swing_atr, swings)
    cup_rows = cup_signals(df, symbol, lookback, swing_atr, swings)
    return crosses, sr_rows, channel_rows, triangle_rows, cup_rows, latest_row(df, symbol)


def scan_all(symbols=None, lookback=None, progress=None, refresh=False,
             swing_atr=settings.SWING_MIN_MOVE_ATR, zone_atr=settings.ZONE_WIDTH_ATR):
    """סורק את כל הנכסים. progress(חלק 0..1, טקסט) מעדכן פס התקדמות.
    מחזיר מילון: crosses / sr / channels / triangles / cups / latest (טבלאות),
    errors / skipped (רשימות של (סימול, סיבה))."""
    if symbols is None:  # רק כשלא נמסרה רשימה בכלל. רשימה ריקה = אין מה לסרוק.
        symbols = load_assets()
    frames, errors = fetch_many(symbols, progress, refresh)
    crosses, sr_rows, channel_rows, triangle_rows, cup_rows, latest, skipped = [], [], [], [], [], [], []
    min_candles = settings.SMA_LONG + 1
    for n, symbol in enumerate(list(frames), 1):
        if progress and (n % 20 == 0 or n == len(frames)):
            progress(n / len(frames), f"מחשב איתותים: {n}/{len(frames)}")
        df = frames.pop(symbol)  # לא שומרים את הנתונים בזיכרון אחרי שסיימנו איתם
        if len(df) < min_candles:
            skipped.append((symbol, f"רק {len(df)} נרות - צריך לפחות {min_candles} בשביל SMA{settings.SMA_LONG}"))
            continue
        problem = quality_problem(df, symbol)
        if problem:
            skipped.append((symbol, problem))
            continue
        try:
            symbol_crosses, symbol_sr, symbol_channels, symbol_triangles, symbol_cups, symbol_latest = \
                scan_symbol(df, symbol, lookback, swing_atr, zone_atr)
            crosses.extend(symbol_crosses)
            sr_rows.extend(symbol_sr)
            channel_rows.extend(symbol_channels)
            triangle_rows.extend(symbol_triangles)
            cup_rows.extend(symbol_cups)
            latest.append(symbol_latest)
        except Exception as e:
            errors.append((symbol, str(e)))
    return dict(crosses=pd.DataFrame(crosses), sr=pd.DataFrame(sr_rows),
                channels=pd.DataFrame(channel_rows), triangles=pd.DataFrame(triangle_rows),
                cups=pd.DataFrame(cup_rows), latest=pd.DataFrame(latest), errors=errors,
                skipped=skipped)


# --- סינון התוצאות (מהיר - בלי להוריד ובלי לחשב מחדש) ---

CCI_DIRECTION = "direction"  # מצב CCI "בכיוון האיתות" (במקום טווח ידני)


def cci_mask(table, cci_range):
    """אילו שורות עוברות את מסנן ה-CCI.
    cci_range = (מינימום, מקסימום): קצוות המחוון פתוחים - CCI_LIMIT = "ומעלה",
                 מינוס CCI_LIMIT = "ומטה", כך שאיתות חזק במיוחד לא נזרק.
    cci_range = CCI_DIRECTION: איתות למעלה - CCI מעל 0, איתות למטה - CCI מתחת ל-0,
                 נשיקה (אין לה כיוון) - לא מסוננת."""
    cci = table["cci"]
    if cci_range == CCI_DIRECTION:
        direction = table["direction"]
        return ((direction == UP) & (cci > 0)) | ((direction == DOWN) & (cci < 0)) | (direction == "")
    low, high = cci_range
    low = -float("inf") if low <= -settings.CCI_LIMIT else low
    high = float("inf") if high >= settings.CCI_LIMIT else high
    return cci.between(low, high)


def apply_filters(table, cci_range=None, vol_min=None):
    """CCI (טווח או "בכיוון האיתות") ו/או ווליום מעל המכפיל - ביום האיתות של כל שורה.
    None = המסנן כבוי."""
    if table.empty:
        return table
    if cci_range is not None:
        table = table[cci_mask(table, cci_range)]
    if vol_min is not None:
        table = table[table["vol_ratio"] >= vol_min]
    return table


def filter_crosses(table, names, window, cci_range=None, vol_min=None):
    """חציות מהסוגים שנבחרו, ב-window הנרות האחרונים, אחרי המסננים. החדשות ראשונות."""
    if table.empty or not names:
        return table.iloc[0:0]
    table = table[table["signal"].isin(names) & (table["days_ago"] < window)]
    table = apply_filters(table, cci_range, vol_min)
    return table.sort_values(["days_ago", "symbol"]).reset_index(drop=True)


def sr_direction(table):
    """כיוון האיתות: פריצת התנגדות = למעלה, שבירת תמיכה = למטה, נשיקה = בלי כיוון."""
    up_or_down = table["level_kind"].map({RESISTANCE: UP, SUPPORT: DOWN})
    return up_or_down.where(table["type"] == BREAKOUT, "")


def filter_sr(table, options, window, min_touches=settings.SR_MIN_TOUCHES,
              near_range=settings.SR_NEAR_RANGE, touch_vol_min=None, cci_range=None, vol_min=None):
    """איתותי אזורים לפי האפשרויות שנבחרו (מתוך SR_OPTIONS). מחזיר (פריצות, נשיקות).
    פריצה: האזור החזק ביותר שנפרץ באותו יום - לפי נגיעות, אחר כך ווליום בנגיעות,
           ואחר כך הקרוב ביותר לסגירה. החדשות ראשונות.
    נשיקה: האזור הקרוב ביותר מכל צד, במרחק בטווח near_range (%). הקרובות ראשונות.
    touch_vol_min: רק אזורים שהווליום הממוצע בנגיעות שלהם לפחות כזה (None = כבוי)."""
    empty = table.iloc[0:0]
    if table.empty or not options:
        return empty, empty
    wanted = pd.Series(False, index=table.index)
    for option in options:
        signal_type, kind = SR_OPTIONS[option]
        wanted |= (table["type"] == signal_type) & (table["level_kind"] == kind)
    table = table[wanted & (table["touches"] >= min_touches)]
    table = table.assign(direction=sr_direction(table))
    if touch_vol_min is not None:
        table = table[table["touch_vol"] >= touch_vol_min]
    table = apply_filters(table, cci_range, vol_min)

    breakouts = table[(table["type"] == BREAKOUT) & (table["days_ago"] < window)]
    gap = (breakouts["close"] - breakouts["level"]).abs()  # מרחק האזור מהסגירה ביום הפריצה
    breakouts = (breakouts.assign(gap=gap)
                 .sort_values(["touches", "touch_vol", "gap"], ascending=[False, False, True])
                 .drop_duplicates(["symbol", "date", "level_kind"])
                 .sort_values(["days_ago", "touches", "symbol"], ascending=[True, False, True])
                 .drop(columns="gap").reset_index(drop=True))

    kisses = table[(table["type"] == KISS) & table["dist_pct"].between(*near_range)]
    kisses = (kisses.sort_values(["dist_pct", "symbol"])
              .drop_duplicates(["symbol", "level_kind"]).reset_index(drop=True))
    return breakouts, kisses


def filter_channels(table, option, window, near_range=settings.SR_NEAR_RANGE,
                    cci_range=None, vol_min=None):
    """איתותי מבנה (תעלה או משולש) מסוג אחד: פריצה/שבירה - ב-window הנרות האחרונים;
    נשיקה - הנר האחרון במרחק בטווח near_range (%) מהקו. אחרי מסנני CCI / ווליום."""
    if table.empty:
        return table
    table = table[table["option"] == option]
    if option in CHANNEL_KISSES or option in TRIANGLE_KISSES:
        table = table[table["dist_pct"].between(*near_range)]
    else:
        table = table[table["days_ago"] < window]
    table = apply_filters(table, cci_range, vol_min)
    return table.sort_values(["days_ago", "symbol"]).reset_index(drop=True)


def filter_cups(table, option, window, near_range=settings.SR_NEAR_RANGE, state=STATE_ALL,
                cci_range=None, vol_min=None):
    """קאפ אנד הנדל בתקופה אחת. "לפני פריצה" - הנר האחרון, במרחק בטווח near_range (%) מתחת
    לנקודת הפריצה; "פריצה" - ב-window הנרות האחרונים; "הכל" - שניהם. אחרי מסנני CCI / ווליום."""
    if table.empty:
        return table
    table = table[table["option"] == option]
    before = (table["state"] == STATE_BEFORE) & table["dist_pct"].between(*near_range)
    broke = (table["state"] == STATE_BREAKOUT) & (table["days_ago"] < window)
    table = table[(before if state != STATE_BREAKOUT else False) | (broke if state != STATE_BEFORE else False)]
    table = apply_filters(table, cci_range, vol_min)
    return table.sort_values(["days_ago", "symbol"]).reset_index(drop=True)


# --- טבלה אחת לכל התנאים שנבחרו ---

MATCH_ALL = "all"  # נכס חייב לעמוד בכל התנאים (וגם)
MATCH_ANY = "any"  # מספיק תנאי אחד (או)
LATEST_COLUMNS = ["close", "cci", "vol_ratio"] + [f"above_{sma_col(p)}" for p in SMA_PERIODS]


def criterion_matches(res, name, window, min_touches=settings.SR_MIN_TOUCHES,
                      near_range=settings.SR_NEAR_RANGE, touch_vol_min=None,
                      cci_range=None, vol_min=None, cup_state=STATE_ALL):
    """כל המופעים של תנאי אחד (חצייה / פריצה / נשיקה / תעלה / משולש / ספל) שעוברים את המסננים."""
    if name in CUP_OPTIONS:
        return filter_cups(res.get("cups", pd.DataFrame()), name, window, near_range, cup_state,
                           cci_range, vol_min)
    if name in CHANNEL_OPTIONS:
        return filter_channels(res.get("channels", pd.DataFrame()), name, window, near_range,
                               cci_range, vol_min)
    if name in TRIANGLE_OPTIONS:
        return filter_channels(res.get("triangles", pd.DataFrame()), name, window, near_range,
                               cci_range, vol_min)
    if name in SR_OPTIONS:
        breakouts, kisses = filter_sr(res["sr"], [name], window, min_touches, near_range,
                                      touch_vol_min, cci_range, vol_min)
        return kisses if SR_OPTIONS[name][0] == KISS else breakouts
    return filter_crosses(res["crosses"], [name], window, cci_range, vol_min)


def best_per_symbol(table, name):
    """המופע המייצג של כל נכס: נשיקה - הקרובה ביותר; פריצה - החדשה ביותר (בתיקו - החזקה
    ביותר); חצייה - החדשה ביותר. מחזיר טבלה שהאינדקס שלה הוא הסימול."""
    if table.empty:
        return pd.DataFrame(index=pd.Index([], name="symbol"))
    if name in CHANNEL_KISSES or name in TRIANGLE_KISSES:
        table = table.sort_values("dist_pct")
    elif name in SR_OPTIONS and SR_OPTIONS[name][0] == KISS:
        table = table.sort_values(["dist_pct", "touches"], ascending=[True, False])
    elif name in SR_OPTIONS:
        table = table.sort_values(["days_ago", "touches", "touch_vol"], ascending=[True, False, False])
    elif name in CHANNEL_OPTIONS or name in TRIANGLE_OPTIONS:
        table = table.sort_values("days_ago")
    elif name in CUP_OPTIONS:
        table = table.sort_values(["days_ago", "dist_pct"])
    else:
        table = table.sort_values("days_ago")
    return table.drop_duplicates("symbol").set_index("symbol")


def combine_signals(res, criteria, window, match=MATCH_ALL, min_touches=settings.SR_MIN_TOUCHES,
                    near_range=settings.SR_NEAR_RANGE, touch_vol_min=None, cci_range=None,
                    vol_min=None, cup_state=STATE_ALL):
    """טבלה אחת, שורה לכל נכס, לפי כל התנאים שנבחרו
    (criteria = שמות חציות ו/או SR_OPTIONS / CHANNEL_OPTIONS / TRIANGLE_OPTIONS / CUP_OPTIONS;
    cup_state = איזה מצב של קאפ אנד הנדל נחשב: הכל / לפני פריצה / פריצה).

    כל תנאי מתקיים אם יש לנכס לפחות מופע אחד שעובר את המסננים (CCI / ווליום ביום
    האיתות; בנשיקה - הנר האחרון). match=MATCH_ALL: הנכס עומד בכל התנאים;
    MATCH_ANY: לפחות באחד.
    מחזיר (טבלה, מופעים):
      טבלה - symbol, מצב הנר האחרון (LATEST_COLUMNS), newest (לפני כמה נרות האיתות
             החדש ביותר), ועמודה לכל תנאי עם המופע המייצג (dict) או None.
      מופעים - {תנאי: כל המופעים של הנכסים שבטבלה} (לפירוט ולגרף).
    """
    columns = ["symbol"] + LATEST_COLUMNS + ["newest"] + list(criteria)
    if not criteria or res["latest"].empty:
        return pd.DataFrame(columns=columns), {}
    latest = res["latest"].set_index("symbol")
    found, best = {}, {}
    for name in criteria:
        found[name] = criterion_matches(res, name, window, min_touches, near_range,
                                        touch_vol_min, cci_range, vol_min, cup_state)
        best[name] = best_per_symbol(found[name], name)

    sets = [set(b.index) for b in best.values()]
    symbols = set.intersection(*sets) if match == MATCH_ALL else set.union(*sets)
    rows = []
    for symbol in symbols & set(latest.index):
        row = {"symbol": symbol, **latest.loc[symbol, LATEST_COLUMNS].to_dict()}
        for name in criteria:
            row[name] = best[name].loc[symbol].to_dict() if symbol in best[name].index else None
        row["newest"] = min(row[name]["days_ago"] for name in criteria if row[name])
        rows.append(row)
    table = pd.DataFrame(rows, columns=columns)
    if not table.empty:
        table = table.sort_values(["newest", "symbol"]).reset_index(drop=True)
    shown = set(table["symbol"])
    found = {name: t[t["symbol"].isin(shown)] if not t.empty else t for name, t in found.items()}
    return table, found


def filter_latest(table, cci_range=None, vol_min=None):
    """מצב "סורק": נכסים שהנר האחרון שלהם עומד בתנאי CCI/ווליום. הווליום הגבוה ראשון.
    (ב"סורק" אין איתות ולכן אין כיוון - מצב "בכיוון האיתות" לא מסנן כאן.)"""
    if cci_range == CCI_DIRECTION:
        cci_range = None
    table = apply_filters(table, cci_range, vol_min)
    if table.empty:
        return table
    return table.sort_values("vol_ratio", ascending=False).reset_index(drop=True)


# בדיקה: סורק את הרשימה האישית ומדפיס את התוצאות
if __name__ == "__main__":
    res = scan_all()
    names = [name for name, _, _ in signal_pairs()]
    crosses = filter_crosses(res["crosses"], names, settings.LOOKBACK_DAYS)
    print(f"נמצאו {len(crosses)} חציות:\n")
    print(crosses.round(2).to_string())
    breakouts, kisses = filter_sr(res["sr"], list(SR_OPTIONS), settings.LOOKBACK_DAYS)
    print(f"\nפריצות - {len(breakouts)} שורות:\n")
    print(breakouts.round(2).to_string())
    print(f"\nנשיקות - {len(kisses)} שורות:\n")
    print(kisses.round(2).to_string())
    for symbol, msg in res["errors"] + res["skipped"]:
        print(f"{symbol}: {msg}")
