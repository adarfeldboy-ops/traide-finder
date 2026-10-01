# הורדת נתוני שוק: נרות יומיים לכל נכס ברשימה.
# כל הפונקציות מחזירות טבלה באותו מבנה:
#   אינדקס = תאריך, עמודות = Open, High, Low, Close, Volume
# נתונים שהורדו נשמרים במטמון בדיסק (תיקיית cache), ונחשבים "טריים" עד הסגירה הבאה
# של השוק - כך סריקה חוזרת מהירה, ונר שנסגר בינתיים יורד מחדש.

import shutil
import time
from pathlib import Path

import ccxt
import pandas as pd
import yfinance as yf

import settings

COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
BASE = Path(__file__).parent  # תיקיית הפרויקט - כל הנתיבים יחסיים אליה
CACHE = BASE / settings.CACHE_DIR
US_TZ = "America/New_York"
US_CLOSE_HOUR = 16       # הבורסה בניו יורק נסגרת ב-16:00 שעון ניו יורק
CACHE_KEEP_DAYS = 7      # קבצי מטמון ישנים מזה נמחקים


def load_assets(path=settings.ASSETS_FILE):
    """קורא רשימת נכסים מקובץ, בלי הערות ושורות ריקות.
    נתיב יחסי נחשב יחסית לתיקיית הפרויקט (לא לתיקייה שממנה הפעילו)."""
    path = Path(path)
    if not path.is_absolute():
        path = BASE / path
    with open(path, encoding="utf-8") as f:
        lines = [line.strip() for line in f]
    return [line for line in lines if line and not line.startswith("#")]


def is_crypto(symbol):
    """סימול עם / (כמו BTC/USDT) הוא קריפטו."""
    return "/" in symbol


def is_us_stock(symbol):
    """מניה/ETF אמריקאית: לא קריפטו ובלי סיומת בורסה (כמו TEVA.TA)."""
    return not is_crypto(symbol) and "." not in symbol


# --- מתי נסגר הנר האחרון ---

def utc_today():
    """התאריך של היום לפי UTC (נר יומי בקריפטו נסגר ב-00:00 UTC)."""
    return pd.Timestamp.now(tz="UTC").date()


def last_close_time(symbol):
    """הרגע (UTC) שבו נסגר הנר היומי האחרון של הנכס.
    מניות אמריקאיות: 16:00 ניו יורק ביום המסחר האחרון (בלי חגים - בחג סתם נוריד שוב).
    קריפטו ושאר הבורסות: חצות UTC."""
    if not is_us_stock(symbol):
        return pd.Timestamp.now(tz="UTC").normalize()
    now = pd.Timestamp.now(tz=US_TZ)
    close = now.normalize() + pd.Timedelta(hours=US_CLOSE_HOUR)
    if now < close:
        close -= pd.Timedelta(days=1)
    while close.weekday() >= 5:  # שבת/ראשון - חוזרים ליום שישי
        close -= pd.Timedelta(days=1)
    return close.tz_convert("UTC")


def drop_unclosed(df, symbol):
    """משמיט נר של היום אם הוא עדיין לא נסגר."""
    if is_crypto(symbol):
        return df[df.index.date < utc_today()]  # קריפטו נסחר 24/7 - הנר של היום פתוח
    if is_us_stock(symbol):
        now = pd.Timestamp.now(tz=US_TZ)
        if now.hour < US_CLOSE_HOUR:
            return df[df.index.date < now.date()]
    return df  # בורסות אחרות - בלי בדיקה (ראו מגבלות)


def clean(df, symbol):
    """ניקוי אחיד: שורות בלי מחיר נזרקות, ווליום חסר = 0, אינדקס = תאריך בלי שעה."""
    # שורה בלי אחד ממחירי הנר לא שמישה (נר שבור מקלקל ממוצעים ונקודות מפנה)
    df = df[COLUMNS].dropna(subset=["Open", "High", "Low", "Close"])
    # ווליום חסר (קורה ב-Yahoo) נחשב 0: הנר נשמר בשביל המחירים, ומסנן הווליום פשוט לא יעבור
    df = df.fillna({"Volume": 0}).astype(float)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    df = drop_unclosed(df, symbol)
    if df.empty:
        raise ValueError("לא התקבלו נתונים")
    return df


# --- מטמון בדיסק ---

def clean_old_cache():
    """מוחק קבצי מטמון ישנים (ותיקיות של הגרסה הקודמת), כדי שהתיקייה לא תתנפח."""
    CACHE.mkdir(parents=True, exist_ok=True)
    too_old = time.time() - CACHE_KEEP_DAYS * 24 * 3600
    for item in CACHE.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        elif item.stat().st_mtime < too_old:
            item.unlink(missing_ok=True)


def cache_file(symbol):
    # "/" אסור בשם קובץ - BTC/USDT נשמר בשם BTC_USDT
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / (symbol.replace("/", "_") + ".parquet")


def is_fresh(path, symbol):
    """הקובץ נשמר אחרי סגירת הנר האחרון? (זמן השמירה = זמן ההורדה)"""
    saved = pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC")
    return saved >= last_close_time(symbol)


def read_cache(symbol):
    """הנתונים מהמטמון, או None אם אין, אם הם ישנים, או אם הקובץ פגום."""
    path = cache_file(symbol)
    if not path.exists() or not is_fresh(path, symbol):
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def write_cache(symbol, df):
    try:
        df.to_parquet(cache_file(symbol))
    except Exception:
        pass  # מטמון הוא רק לנוחות - כישלון בשמירה לא עוצר את הסריקה


# --- הורדה ---

def pick_stock(raw, symbol):
    """מוציא נכס אחד מתוך תוצאת yf.download של כמה נכסים."""
    if isinstance(raw.columns, pd.MultiIndex):
        if symbol not in raw.columns.get_level_values(0):
            raise ValueError("לא התקבלו נתונים")
        raw = raw[symbol]
    # yf.download מיישר תאריכים בין כל הנכסים - שורות ריקות שייכות לנכסים אחרים ונזרקות ב-clean
    return clean(raw, symbol)


def download_stocks(symbols, on_step=None):
    """מוריד מניות ו-ETF מ-Yahoo בקבוצות (בקשה אחת לכל קבוצה).
    מחזיר ({סימול: טבלה}, [(סימול, שגיאה)])."""
    start = pd.Timestamp.now() - pd.Timedelta(days=settings.HISTORY_DAYS)
    frames, errors = {}, []
    for k in range(0, len(symbols), settings.DOWNLOAD_BATCH):
        batch = symbols[k:k + settings.DOWNLOAD_BATCH]
        try:
            raw = yf.download(batch, start=start, interval="1d", auto_adjust=True,
                              group_by="ticker", threads=True, progress=False)
        except Exception as e:
            raw = None
            errors += [(s, f"הורדה נכשלה: {e}") for s in batch]
        if raw is not None:
            for s in batch:
                try:
                    frames[s] = pick_stock(raw, s)
                except Exception as e:
                    errors.append((s, str(e)))
        if on_step:
            on_step(len(batch))
    return frames, errors


BINANCE_MARKET_DATA = "https://data-api.binance.vision/api/v3"


def make_exchange():
    """חיבור לבורסת הקריפטו, עם השהייה אוטומטית בין בקשות (כדי לא להיחסם).
    ב-Binance משתמשים בכתובת של נתוני שוק בלבד - היא לא חסומה גיאוגרפית (למשל בשרתים
    בארה"ב, כמו Streamlit Cloud), ומספיקה לנו כי אנחנו רק קוראים מחירים."""
    if settings.CRYPTO_EXCHANGE == "binance":
        exchange = ccxt.binance({"enableRateLimit": True, "options": {"fetchMarkets": ["spot"]}})
        exchange.urls["api"]["public"] = BINANCE_MARKET_DATA
        return exchange
    return getattr(ccxt, settings.CRYPTO_EXCHANGE)({"enableRateLimit": True})


def fetch_crypto(symbol, exchange=None, days=settings.HISTORY_DAYS):
    """מוריד נרות יומיים של מטבע דיגיטלי מהבורסה שבהגדרות."""
    exchange = exchange or make_exchange()
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    rows = exchange.fetch_ohlcv(symbol, timeframe="1d", since=since, limit=days)
    if not rows:
        raise ValueError(f"לא התקבלו נתונים עבור {symbol}")
    df = pd.DataFrame(rows, columns=["Date"] + COLUMNS)
    df["Date"] = pd.to_datetime(df["Date"], unit="ms")
    return clean(df.set_index("Date"), symbol)


def download_cryptos(symbols, on_step=None):
    """מוריד מטבעות אחד-אחד. מחזיר ({סימול: טבלה}, [(סימול, שגיאה)])."""
    frames, errors = {}, []
    exchange = make_exchange() if symbols else None
    for s in symbols:
        try:
            frames[s] = fetch_crypto(s, exchange)
        except Exception as e:
            errors.append((s, str(e)))
        if on_step:
            on_step(1)
    return frames, errors


def fetch_many(symbols, progress=None, refresh=False):
    """מוריד נתונים לרשימת נכסים. מה שבמטמון וטרי - נלקח משם.
    progress(חלק 0..1, טקסט) - לעדכון פס התקדמות. refresh=True מתעלם מהמטמון.
    מחזיר ({סימול: טבלה}, [(סימול, שגיאה)])."""
    clean_old_cache()
    frames = {}
    if not refresh:
        for s in symbols:
            df = read_cache(s)
            if df is not None:
                frames[s] = df
    missing = [s for s in symbols if s not in frames]
    done = [len(frames)]  # רשימה כדי שהפונקציה הפנימית תוכל לעדכן

    def on_step(n):
        done[0] += n
        if progress:
            progress(done[0] / max(len(symbols), 1), f"מוריד נתונים: {done[0]}/{len(symbols)}")

    on_step(0)
    stocks, stock_errors = download_stocks([s for s in missing if not is_crypto(s)], on_step)
    cryptos, crypto_errors = download_cryptos([s for s in missing if is_crypto(s)], on_step)
    for s, df in {**stocks, **cryptos}.items():
        write_cache(s, df)
        frames[s] = df
    return frames, stock_errors + crypto_errors


def fetch(symbol):
    """נתונים לנכס אחד (דרך המטמון)."""
    frames, errors = fetch_many([symbol])
    if symbol not in frames:
        raise ValueError(errors[0][1] if errors else f"לא התקבלו נתונים עבור {symbol}")
    return frames[symbol]


# בדיקה: הרצה ישירה של הקובץ מורידה שני נכסים ומדפיסה את הנרות האחרונים
if __name__ == "__main__":
    print("נכסים ברשימה:", load_assets())
    for sym in ["AAPL", "BTC/USDT"]:
        df = fetch(sym)
        print(f"\n=== {sym}: {len(df)} נרות, מ-{df.index[0].date()} עד {df.index[-1].date()} ===")
        print("הנר האחרון נסגר:", last_close_time(sym))
        print(df.tail(3))
