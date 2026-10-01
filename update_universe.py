# עדכון רשימות המדדים (S&P 500, Nasdaq 100, S&P 400, S&P 600) מוויקיפדיה לתיקיית universe.
# הפעלה: .venv\Scripts\python.exe update_universe.py
# כדאי להריץ מדי פעם (פעם בחודש מספיק) - הרכב המדדים משתנה לאט.

import urllib.request
from datetime import date
from io import StringIO

import pandas as pd

from universe import NASDAQ100, SP400, SP500, SP600, UNIVERSE

SOURCES = {
    SP500: ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol", "sp500.txt"),
    NASDAQ100: ("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies", "Ticker",
                "nasdaq100.txt"),
    SP400: ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", "Symbol", "sp400.txt"),
    SP600: ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", "Symbol", "sp600.txt"),
}


def download_html(url):
    # ויקיפדיה חוסמת בקשות בלי "שם דפדפן" (User-Agent)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (scanner)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def read_symbols(url, column):
    """הסימולים מהטבלה הראשונה בדף שיש בה עמודה בשם column."""
    for table in pd.read_html(StringIO(download_html(url))):
        if column in table.columns:
            symbols = table[column].dropna().astype(str).str.strip()
            # ב-Yahoo נקודה בסימול נכתבת כמקף: BRK.B -> BRK-B
            return [s.replace(".", "-") for s in symbols if s]
    raise ValueError(f"לא נמצאה טבלה עם עמודה {column}")


def save(path, title, symbols):
    header = f"# {title} - עודכן {date.today().isoformat()} מוויקיפדיה ({len(symbols)} סימולים)\n"
    path.write_text(header + "\n".join(symbols) + "\n", encoding="utf-8")


if __name__ == "__main__":
    UNIVERSE.mkdir(exist_ok=True)
    for name, (url, column, filename) in SOURCES.items():
        try:
            symbols = list(dict.fromkeys(read_symbols(url, column)))
            save(UNIVERSE / filename, name, symbols)
            print(f"{name}: {len(symbols)} סימולים נשמרו ב-{filename}")
        except Exception as e:
            print(f"{name}: נכשל - {e} (הקובץ הקיים לא שונה)")
