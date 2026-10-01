# חישוב אינדיקטורים: ממוצעים נעים, ווליום ו-CCI.
# מקבל טבלת נרות (מ-data.py) ומחזיר אותה עם עמודות נוספות.

import numpy as np
import pandas as pd

import settings


def sma_col(period):
    """שם העמודה של ממוצע נע, למשל SMA50."""
    return f"SMA{period}"


def add_sma(df):
    """מוסיף עמודה לכל ממוצע נע: ממוצע הסגירה של N הימים האחרונים."""
    for period in (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG):
        df[sma_col(period)] = df["Close"].rolling(period).mean()
    return df


def add_volume(df):
    """ממוצע הווליום של הימים שלפני היום הנוכחי, ופי כמה היום גבוה ממנו."""
    # shift(1) = מזיז יום אחד אחורה, כך שהיום עצמו לא נכלל בממוצע
    df["VolAvg"] = df["Volume"].shift(1).rolling(settings.VOLUME_AVG_DAYS).mean()
    df["VolRatio"] = df["Volume"] / df["VolAvg"]
    return df


def add_cci(df):
    """CCI = (מחיר טיפוסי - הממוצע שלו) / (0.015 * סטיית הממוצע)."""
    period = settings.CCI_PERIOD
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    typical_avg = typical.rolling(period).mean()
    # כמה בממוצע המחיר הטיפוסי רחוק מהממוצע שלו, בתוך כל חלון של 20 ימים.
    # (מחושב לכל החלונות בבת אחת - הרבה יותר מהיר מלולאה, אותה תוצאה)
    mean_dev = np.full(len(df), np.nan)
    if len(df) >= period:
        windows = np.lib.stride_tricks.sliding_window_view(typical.to_numpy(), period)
        mean_dev[period - 1:] = np.abs(windows - windows.mean(axis=1, keepdims=True)).mean(axis=1)
    df["CCI"] = (typical - typical_avg) / (0.015 * mean_dev)
    return df


def add_atr(df):
    """ATR = ממוצע "הטווח האמיתי" של כל נר: כמה המחיר זז ביום רגיל (מדד תנודתיות).
    טווח אמיתי = הגדול מבין: גבוה-נמוך, |גבוה-סגירה קודמת|, |נמוך-סגירה קודמת|."""
    prev_close = df["Close"].shift(1)
    true_range = pd.concat([df["High"] - df["Low"],
                            (df["High"] - prev_close).abs(),
                            (df["Low"] - prev_close).abs()], axis=1).max(axis=1)
    # החלקת Wilder (כמו ברוב תוכנות הגרפים): כל יום = 13/14 מהערך הקודם + 1/14 מהיום
    df["ATR"] = true_range.ewm(alpha=1 / settings.ATR_PERIOD, adjust=False,
                               min_periods=settings.ATR_PERIOD).mean()
    return df


def add_indicators(df):
    """מחשב את כל האינדיקטורים ומחזיר טבלה חדשה (לא משנה את המקורית)."""
    df = df.copy()
    add_sma(df)
    add_volume(df)
    add_cci(df)
    add_atr(df)
    return df


# בדיקה: מחשב אינדיקטורים ל-AAPL ומדפיס את 3 הימים האחרונים
if __name__ == "__main__":
    from data import fetch

    df = add_indicators(fetch("AAPL"))
    cols = ["Close", "SMA20", "SMA50", "SMA150", "Volume", "VolAvg", "VolRatio", "CCI"]
    print(df[cols].tail(3).round(2).to_string())
