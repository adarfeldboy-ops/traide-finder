# קבוצות נכסים לסריקה ("יקום"): מדדים, קרנות סל, קריפטו והרשימה האישית.
# רשימות המדדים נשמרות כקבצי טקסט בתיקיית universe (מתעדכנות ע"י update_universe.py).

import settings
from data import BASE, CACHE, fetch_many, load_assets, make_exchange, utc_today

UNIVERSE = BASE / settings.UNIVERSE_DIR

SP500 = "S&P 500"
NASDAQ100 = "Nasdaq 100"
ETFS = "קרנות סל (ETF)"
CRYPTO = f"קריפטו - {settings.CRYPTO_TOP_N} המובילים"
MY_LIST = "הרשימה שלי"
SP400 = "S&P MidCap 400"
SP600 = "S&P SmallCap 600"
GROUPS = [MY_LIST, SP500, NASDAQ100, ETFS, CRYPTO]  # הקבוצות המקוריות (backtest.py משתמש בהן)
ALL_GROUPS = GROUPS + [SP400, SP600]               # כל הקבוצות באתר (S&P 1500 + קרנות + קריפטו)

# קבוצות שהרשימה שלהן שמורה בקובץ
GROUP_FILES = {
    SP500: UNIVERSE / "sp500.txt",
    NASDAQ100: UNIVERSE / "nasdaq100.txt",
    ETFS: UNIVERSE / "etfs.txt",
    SP400: UNIVERSE / "sp400.txt",
    SP600: UNIVERSE / "sp600.txt",
    MY_LIST: BASE / settings.ASSETS_FILE,
}

# --- מה לא נכנס לרשימת הקריפטו ---
# מטבעות יציבים (צמודים לדולר/יורו) - זוג מול USDT כמעט לא זז
STABLECOINS = {"U", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDE", "USDS", "PYUSD",
               "USD1", "RLUSD", "BFUSD", "XUSD", "USDD", "EUR", "EURI", "AEUR", "EURC"}
GOLD = {"XAUT", "PAXG"}  # צמודים למחיר הזהב
WRAPPED = {"WBTC", "WETH", "WBETH", "BETH", "WSTETH", "STETH", "BTCB", "CBBTC"}  # עותקים של מטבע אחר
# מניות "מטוקנות" ב-Binance (NVDAB = מניית NVDA). אין להן סימון רשמי, לכן שלוש בדיקות:
# רשימה ידועה, סיומת B על סימול של מניה מוכרת, ודפוס ההרשאות שלהן ב-Binance (ראו is_tokenized_stock).
TOKENIZED = {"NVDAB", "TSLAB", "GOOGLB", "MSTRB", "CRCLB", "SNDKB", "MUB", "SPCXB", "SNXXB",
             "SOXLB", "AAPLB", "MSFTB", "AMZNB", "METAB", "SPYB", "QQQB", "COINB", "GMEB"}
REAL_COINS_ENDING_B = {"DGB"}  # מטבע אמיתי שבמקרה נראה כמו מניה + B (DigiByte, לא Dollar General)
STABLE_RANGE_PCT = 1.0  # טווח מחירים ב-30 יום קטן מזה = כנראה צמוד (יציב) - לא מעניין לסריקה


def stock_tickers():
    """כל הסימולים של מניות/ETF ברשימות (לזיהוי מניות מטוקנות)."""
    tickers = set()
    # בכוונה בלי S&P 400/600: סימולים קצרים שם (למשל AR) היו גורמים למטבעות אמיתיים
    # (ARB) להיראות כמו מניה + B
    for group in (SP500, NASDAQ100, ETFS):
        if GROUP_FILES[group].exists():
            tickers |= set(load_assets(GROUP_FILES[group]))
    return tickers


def is_tokenized_stock(market, stocks):
    """האם הזוג הוא מניה מטוקנת (ולא מטבע דיגיטלי)."""
    base = market["base"]
    if base in TOKENIZED:
        return True
    if not base.endswith("B") or base in REAL_COINS_ENDING_B:
        return False
    if base[:-1] in stocks:
        return True
    # נבדק ידנית (אוקטובר 2026): כל המניות המטוקנות חסרות את קבוצת ההרשאות TRD_GRP_016,
    # וכל המטבעות האמיתיים שמסתיימים ב-B (BNB, ARB, SHIB...) - יש להם אותה.
    permissions = (market.get("info", {}).get("permissionSets") or [[]])[0]
    return bool(permissions) and "TRD_GRP_016" not in permissions


def candidate_pairs(exchange):
    """זוגות USDT פעילים, ממוינים לפי מחזור מסחר ב-24 שעות, בלי הזוגות שלא רוצים."""
    tickers = exchange.fetch_tickers()
    stocks = stock_tickers()
    pairs = []
    for symbol, t in tickers.items():
        market = exchange.markets.get(symbol, {})
        base = market.get("base")
        if not (market.get("spot") and market.get("active") and market.get("quote") == "USDT"):
            continue
        if base in STABLECOINS | GOLD | WRAPPED or is_tokenized_stock(market, stocks):
            continue
        pairs.append((t.get("quoteVolume") or 0, symbol))
    return [s for _, s in sorted(pairs, reverse=True)]


def is_stable(df):
    """המחיר כמעט לא זז ב-30 הימים האחרונים (מטבע יציב שלא ברשימה)."""
    closes = df["Close"].tail(30)
    return (closes.max() - closes.min()) / closes.mean() * 100 < STABLE_RANGE_PCT


def top_crypto(n=settings.CRYPTO_TOP_N, progress=None):
    """n זוגות ה-USDT עם מחזור המסחר הגבוה ביותר, אחרי הסינון. נשמר במטמון ליום (UTC).
    הבדיקה מורידה נתונים - הם נשמרים במטמון ומשמשים גם את הסריקה עצמה."""
    path = CACHE / f"crypto_top_{utc_today().isoformat()}.txt"
    if path.exists():
        return load_assets(path)
    candidates = candidate_pairs(make_exchange())
    chosen = []
    for k in range(0, len(candidates), 20):  # בודקים 20 בכל פעם עד שמגיעים ל-n
        batch = candidates[k:k + 20]
        if progress:
            progress(min(len(chosen) / n, 1.0), f"בונה רשימת קריפטו: {len(chosen)}/{n}")
        frames, _ = fetch_many(batch)
        # זוג שההורדה שלו נכשלה נשאר - הסריקה תדווח עליו כשגיאה
        chosen += [s for s in batch if s not in frames or not is_stable(frames[s])]
        if len(chosen) >= n:
            break
    chosen = chosen[:n]
    path.write_text("\n".join(chosen), encoding="utf-8")
    return chosen


def load_group(name, progress=None):
    """רשימת הסימולים של קבוצה אחת."""
    if name == CRYPTO:
        return top_crypto(progress=progress)
    return load_assets(GROUP_FILES[name])


def load_universe(names, progress=None):
    """מאחד כמה קבוצות לרשימה אחת בלי כפילויות.
    מחזיר (סימולים, [(קבוצה, שגיאה)]) - קבוצה שנכשלה לא עוצרת את השאר."""
    symbols, errors = [], []
    for name in names:
        try:
            symbols += load_group(name, progress)
        except Exception as e:
            errors.append((name, str(e)))
    return list(dict.fromkeys(symbols)), errors  # dict שומר על הסדר ומסיר כפילויות


# בדיקה: מדפיס כמה סימולים יש בכל קבוצה
if __name__ == "__main__":
    for group in ALL_GROUPS:
        try:
            print(group, len(load_group(group)))
        except Exception as e:
            print(group, "שגיאה:", e)
