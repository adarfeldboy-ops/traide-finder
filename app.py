# האתר: בחירת קבוצות נכסים ומה לחפש, טבלת תוצאות אחת (כל התנאים יחד) + גרף לכל נכס.
# הפעלה: .venv\Scripts\python.exe -m streamlit run app.py

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import settings
import ui_art
from channels import CHANNEL_KISSES, CHANNEL_OPTIONS, active_channel, channel_at, line_at
from triangles import (TRIANGLE_INFO, TRIANGLE_KISSES, TRIANGLE_OPTIONS, TRIANGLE_TYPES,
                       active_triangles, triangle_at)
from triangles import line_at as triangle_line
from data import fetch, is_crypto, load_assets
from indicators import add_indicators, sma_col
from levels import (KISS, RES_BREAK, RESISTANCE, SR_OPTIONS, SUP_BREAK, SUPPORT, chart_zones,
                    find_swings)
from signals import (CCI_DIRECTION, DOWN, MATCH_ALL, MATCH_ANY, UP, combine_signals,
                     filter_latest, scan_all, signal_pairs)
from universe import ALL_GROUPS, load_universe

APP_NAME = "SWING MASTER"
CHART_CANDLES = 250  # כמה נרות להציג בגרף
SMA_PERIODS = (settings.SMA_SHORT, settings.SMA_MID, settings.SMA_LONG)

# --- עיצוב: כהה ומאופק, צבע הדגשה אחד. אותם ערכים ב-.streamlit/config.toml ---
BG, SURFACE, BORDER = "#0f1114", "#181b20", "#262b33"      # רקע, משטח, קו גבול דק
TEXT, TEXT_2, MUTED = "#e6e8eb", "#a4abb6", "#848c98"       # טקסט ראשי / משני / חלש (ניגודיות ≥ 4.5)
ACCENT = "#3987e5"                                          # צבע ההדגשה היחיד (כפתורים, בחירה)
POS, NEG = "#0ca30c", "#e66767"                             # חיובי / שלילי - רק כשיש לזה משמעות
GRID = "#1c2026"                                            # קווי רשת בגרף
# צבעי הקווים בגרף - לפי סדר קבוע שנבדק לעיוורון צבעים (כחול, כתום, טורקיז, צהוב, מגנטה)
SMA_COLORS = dict(zip(SMA_PERIODS, ("#3987e5", "#d95926", "#199e70")))
CHANNEL_COLOR, TRIANGLE_COLOR = "#c98500", "#d55181"
FONT = "Heebo, 'Segoe UI', Arial, sans-serif"

RESULTS_VERSION = 6  # עולה כשמבנה התוצאות משתנה - תוצאות ישנות בזיכרון נזרקות
CCI_MANUAL = "טווח ידני"
CCI_WITH_SIGNAL = "בכיוון האיתות"
MATCH_LABELS = {"כל התנאים (וגם)": MATCH_ALL, "לפחות אחד (או)": MATCH_ANY}

st.set_page_config(page_title=APP_NAME, page_icon=":material/candlestick_chart:", layout="wide")


def inject_css():
    """בלוק CSS אחד לכל האתר: כיוון מימין לשמאל, מרווחים, ומסכים צרים (טלפון).
    סקאלת מרווחים: 4 / 8 / 12 / 16 / 24 / 32 פיקסלים."""
    st.markdown(f"""<style>
.stApp {{direction: rtl; text-align: right;}}
.block-container {{padding: 24px 32px 48px; max-width: 1440px;}}
h1 {{letter-spacing: 0.06em; margin-bottom: 0;}}
h2, h3 {{letter-spacing: 0.01em;}}
/* תווית קטנה מעל קבוצה בסרגל הצד */
.sm-label {{font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; color: {MUTED};
            margin: 12px 0 0; text-transform: uppercase;}}
.sm-sub {{color: {TEXT_2}; font-size: 0.9rem; margin: 4px 0 16px;}}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{gap: 8px;}}
section[data-testid="stSidebar"] hr {{margin: 8px 0; border-color: {BORDER};}}
[data-testid="stExpander"] details {{border-color: {BORDER};}}
[data-testid="stExpander"] summary p {{font-weight: 500;}}
hr {{border-color: {BORDER};}}
/* טבלאות וגרף לא חורגים מהמסך - גלילה אופקית בתוך המיכל שלהם */
[data-testid="stDataFrame"], [data-testid="stPlotlyChart"] {{max-width: 100%; overflow-x: auto;}}
/* טלפון / מסך צר */
@media (max-width: 640px) {{
  .block-container {{padding: 16px 16px 32px;}}
  h1:not(.sm-word) {{font-size: 1.45rem !important;}}
  h2 {{font-size: 1.1rem !important;}}
  h3 {{font-size: 1rem !important;}}
  .sm-sub {{font-size: 0.82rem; margin-bottom: 12px;}}
  [data-testid="stCaptionContainer"] {{font-size: 0.8rem;}}
  section[data-testid="stSidebar"] {{max-width: 88vw;}}
  [data-testid="stHorizontalBlock"] {{flex-wrap: wrap;}}
}}
/* אייקונים בסרגל הצד, הלוגו, ואנימציית הטעינה (הציורים עצמם ב-ui_art.py) */
{ui_art.icons_css()}
{ui_art.header_css(TEXT, TEXT_2)}
{ui_art.loader_css()}
</style>""", unsafe_allow_html=True)


inject_css()


@st.cache_data(ttl=3600, show_spinner=False)
def load_chart_frame(symbol):
    """נתונים + אינדיקטורים (כולל ATR) לגרף. נשמר בזיכרון לשעה."""
    return add_indicators(fetch(symbol))


def above_below(above):
    return "▲ מעל" if above else "▼ מתחת"


def cci_text(value):
    """קצה מחוון ה-CCI כטקסט: הקצוות פתוחים (300 = '300 ומעלה')."""
    if value >= settings.CCI_LIMIT:
        return f"≥{value}"
    if value <= -settings.CCI_LIMIT:
        return f"≤{value}"
    return str(value)


def price(values):
    """עיגול מחירים: 2 ספרות אחרי הנקודה, ובמחיר קטן מ-1 (מטבעות זולים) - 4 ספרות משמעותיות."""
    return values.map(lambda v: round(v, 2) if abs(v) >= 1 else float(f"{v:.4g}"))


def add_sma_columns(out, table):
    for period in SMA_PERIODS:
        out[sma_col(period)] = table[f"above_{sma_col(period)}"].map(above_below)
    out["CCI"] = table["cci"].round(1)
    out["פי ווליום"] = table["vol_ratio"].round(2)
    return out


def format_cross_table(table):
    """טבלת החציות עם כותרות בעברית."""
    return pd.DataFrame({
        "נכס": table["symbol"],
        "איתות": table["signal"],
        "כיוון": table["direction"].map({UP: "▲ " + UP, DOWN: "▼ " + DOWN}),
        "תאריך": table["date"],
        "לפני (נרות)": table["days_ago"],
        "סגירה": price(table["close"]),
        "פי ווליום": table["vol_ratio"].round(2),
        "CCI": table["cci"].round(1),
    })


def format_zone_table(table, kiss=False):
    """טבלת פריצות / נשיקות עם כותרות בעברית."""
    out = pd.DataFrame({
        "נכס": table["symbol"],
        "איתות": table["option"],
        "אזור מ-": price(table["zone_low"]),
        "אזור עד": price(table["zone_high"]),
        "נגיעות": table["touches"],
        "נגיעה אחרונה": table["last_touch"],
        "ווליום בנגיעות": table["touch_vol"].round(2),
        "תאריך": table["date"],
    })
    if kiss:
        out["מרחק מהאזור %"] = table["dist_pct"].round(2)
        out["מיקום"] = table["inside"].map({True: "בתוך האזור", False: "מחוץ לאזור"})
    else:
        out["לפני (נרות)"] = table["days_ago"]
        out["מרחק כעת מהקצה %"] = table["dist_pct"].round(2)
    out["סגירה"] = price(table["close"])
    return add_sma_columns(out, table)


def ago(days):
    return "בנר האחרון" if days == 0 else f"לפני {days} נרות"


def one_price(value):
    return price(pd.Series([value])).iloc[0]


def describe(name, hit):
    """תיאור קצר של מה שהתאים לתנאי אחד בנכס אחד ("—" = לא התאים)."""
    if hit is None:
        return "—"
    if name in TRIANGLE_OPTIONS:
        touches = f"{hit['low_touches']}+{hit['high_touches']} נגיעות"
        if name in TRIANGLE_KISSES:
            line = "מהקו התחתון" if "התחתון" in name else "מהקו העליון"
            return (f"{hit['pattern']} · {touches} · {hit['dist_pct']:.1f}% {line} · "
                    f"קודקוד בעוד {hit['apex_in']:.0f} נרות")
        volume = "" if pd.isna(hit["vol_ratio"]) else f" · ווליום ×{hit['vol_ratio']:.1f}"
        return f"{ago(hit['days_ago'])} · {touches}{volume}"
    if name in CHANNEL_OPTIONS:
        touches = f"{hit['low_touches']}+{hit['high_touches']} נגיעות"
        if name in CHANNEL_KISSES:
            line = "מהקו התחתון" if name == CHANNEL_KISSES[0] else "מהקו העליון"
            return f"תעלה עולה · {touches} · {hit['dist_pct']:.1f}% {line}"
        volume = "" if pd.isna(hit["vol_ratio"]) else f" · ווליום ×{hit['vol_ratio']:.1f}"
        return f"{ago(hit['days_ago'])} · {touches}{volume}"
    if name in SR_OPTIONS and SR_OPTIONS[name][0] == KISS:
        where = "בתוך האזור" if hit["inside"] else f"{hit['dist_pct']:.1f}%"
        return (f"{one_price(hit['zone_low'])}–{one_price(hit['zone_high'])} · {where} · "
                f"{hit['touches']} נגיעות")
    if name in SR_OPTIONS:
        volume = "" if pd.isna(hit["vol_ratio"]) else f" · ווליום ×{hit['vol_ratio']:.1f}"
        return f"{ago(hit['days_ago'])} · {hit['touches']} נגיעות{volume}"
    arrow = "▲" if hit["direction"] == UP else "▼"
    return f"{arrow} {hit['direction']} · {ago(hit['days_ago'])}"


def format_unified_table(table, criteria):
    """הטבלה המאוחדת: נכס, מחיר, עמודה לכל תנאי שנבחר, ומצב הנר האחרון."""
    out = pd.DataFrame({"נכס": table["symbol"], "מחיר סגירה אחרון": price(table["close"])})
    for name in criteria:
        out[name] = [describe(name, hit) for hit in table[name]]
    return add_sma_columns(out, table)


def format_channel_table(table):
    """טבלת איתותי תעלה (לפירוט)."""
    out = pd.DataFrame({
        "נכס": table["symbol"],
        "איתות": table["option"],
        "תאריך": table["date"],
        "לפני (נרות)": table["days_ago"],
        "קו תחתון": price(table["lower"]),
        "קו עליון": price(table["upper"]),
        "נגיעות (תחתון+עליון)": table["low_touches"].astype(str) + "+" + table["high_touches"].astype(str),
        "שיפוע % ל-20 נרות": table["slope_pct_20"].round(1),
        "התחלה": table["start_date"],
        "מרחק %": table["dist_pct"].round(2),
        "סגירה": price(table["close"]),
    })
    return add_sma_columns(out, table)


def format_triangle_table(table):
    """טבלת איתותי משולש (לפירוט)."""
    out = pd.DataFrame({
        "נכס": table["symbol"],
        "איתות": table["option"],
        "תאריך": table["date"],
        "לפני (נרות)": table["days_ago"],
        "קו תחתון": price(table["lower"]),
        "קו עליון": price(table["upper"]),
        "נגיעות (תחתון+עליון)": table["low_touches"].astype(str) + "+" + table["high_touches"].astype(str),
        "שיפוע תחתון % ל-20 נרות": table["lower_slope_pct_20"].round(1),
        "שיפוע עליון % ל-20 נרות": table["upper_slope_pct_20"].round(1),
        "קודקוד בעוד (נרות)": table["apex_in"].round(0),
        "התחלה": table["start_date"],
        "מרחק %": table["dist_pct"].round(2),
        "סגירה": price(table["close"]),
    })
    return add_sma_columns(out, table)


def cell_color(value):
    """צבע לתא: ▲ = ירוק, ▼ = אדום (הסימן עצמו נושא את המשמעות גם בלי צבע)."""
    if isinstance(value, str):
        return f"color: {POS}" if value.startswith("▲") else f"color: {NEG}" if value.startswith("▼") else ""
    return ""


def styled(out):
    """טבלה מעוצבת: ירוק/אדום רק לכיוונים, ול-CCI ו"שינוי %" לפי הסימן."""
    signed = [c for c in ("CCI", "שינוי %") if c in out.columns]
    floats = [c for c in out.columns if pd.api.types.is_float_dtype(out[c])]
    return (out.style.map(cell_color)
            .map(lambda v: "" if pd.isna(v) else f"color: {POS}" if v > 0 else
                 f"color: {NEG}" if v < 0 else "", subset=signed)
            .format(lambda v: f"{v:.10g}", subset=floats, na_rep="—"))


def show_df(out):
    # ברוחב המיכל; בטבלה רחבה (טלפון) - גלילה אופקית בתוך הטבלה עצמה
    st.dataframe(styled(out), hide_index=True, width="stretch")


def format_latest_table(table):
    """טבלת "סורק" - הנר האחרון של כל נכס."""
    out = pd.DataFrame({
        "נכס": table["symbol"],
        "תאריך": table["date"],
        "סגירה": price(table["close"]),
        "שינוי %": table["change_pct"].round(2),
    })
    return add_sma_columns(out, table)


def triangle_lines(df, swings, triangle_exits):
    """[(משולש, יום אחרון לציור)] לגרף: המשולש כפי שהיה ביום הפריצה/שבירה (לכל סוג שיש
    לו יציאה בתוצאות), ואחרת המשולשים הפעילים כעת."""
    dates = list(df.index.date)
    found = []
    for kind, tri in active_triangles(df, swings).items():
        if kind not in triangle_exits:
            found.append((tri, len(df)))
    for kind, day in triangle_exits.items():
        if day in dates:
            exit_day = dates.index(day)
            tri = triangle_at(df, swings, exit_day, kind)
            if tri:
                found.append((tri, exit_day + 1))
    return found


def make_chart(df, symbol, marks, min_touches, touch_vol_min, swing_atr, zone_atr,
               channel_date=None, triangle_exits=None):
    """גרף בשלוש קומות: נרות + ממוצעים + אזורים, ווליום, CCI.
    marks = טבלה עם date / close / direction לסימון איתותים (חציות ופריצות).
    האזורים נבחרים באותם כללים כמו בטבלאות (נגיעות, ווליום בנגיעות, הגדרות הסריקה).
    channel_date = תאריך פריצה/שבירה של תעלה: מציירים את התעלה כפי שהייתה ביום הזה
    (אחרי היציאה היא כבר לא פעילה). None = התעלה הפעילה כעת, אם יש.
    triangle_exits = {סוג משולש: תאריך יציאה} - אותו רעיון למשולשים."""
    zones = chart_zones(df, min_touches, touch_vol_min, min_move_atr=swing_atr, zone_atr=zone_atr)
    swings = find_swings(df, swing_atr)
    first_shown = max(len(df) - CHART_CANDLES, 0)
    full_len = len(df)
    dates = list(df.index.date)
    if channel_date is not None and channel_date in dates:
        exit_day = dates.index(channel_date)
        channel = channel_at(df, swings, exit_day)
        full_len = exit_day + 1  # הקווים עד יום היציאה
    else:
        channel = active_channel(df, swings)
    triangles = triangle_lines(df, swings, triangle_exits or {})
    df = df.tail(CHART_CANDLES)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    # קומה 1: נרות + אזורים (פסים צבועים) + ממוצעים נעים + תעלה + משולש + סימון איתותים
    # (הנרות קודם: Plotly לא מצייר פס בקומה שעדיין אין בה נתונים)
    # נר עולה = חלול, נר יורד = מלא: הכיוון נקרא גם בלי להבחין בין ירוק לאדום
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                 low=df["Low"], close=df["Close"], name=symbol, showlegend=False,
                                 increasing=dict(line=dict(color=POS, width=1), fillcolor=BG),
                                 decreasing=dict(line=dict(color=NEG, width=1), fillcolor=NEG)),
                  row=1, col=1)
    if channel:
        # שני קווי התעלה מתחילת התעלה (או מתחילת הגרף) עד הנר האחרון - פריט אחד במקרא
        pos = list(range(max(channel["start"], first_shown), full_len))
        x = df.index[[p - first_shown for p in pos]]
        for k, which in enumerate(("low", "high")):
            fig.add_trace(go.Scatter(x=x, y=[line_at(channel, p, which) for p in pos],
                                     name="תעלה עולה", legendgroup="channel", showlegend=k == 0,
                                     line=dict(color=CHANNEL_COLOR, width=1.5)), row=1, col=1)
    for tri, end in triangles:
        # שני קווי המשולש מתחילתו (או מתחילת הגרף) עד הנר האחרון / יום היציאה
        pos = list(range(max(tri["start"], first_shown), end))
        x = df.index[[p - first_shown for p in pos]]
        for k, which in enumerate(("low", "high")):
            fig.add_trace(go.Scatter(x=x, y=[triangle_line(tri, p, which) for p in pos],
                                     name=tri["kind"], legendgroup=tri["kind"], showlegend=k == 0,
                                     line=dict(color=TRIANGLE_COLOR, width=1.5)), row=1, col=1)
    for kind, color in ((SUPPORT, POS), (RESISTANCE, NEG)):
        mine = [z for z, k in zones if k == kind]
        for zone in mine:
            fig.add_hrect(y0=zone["low"], y1=zone["high"], fillcolor=color, opacity=0.12,
                          line_width=0, row=1, col=1)
        if mine:
            # פריט במקרא במקום כיתוב על הגרף - כיתובים צפופים היו עולים זה על זה
            touches = ", ".join(str(z["touches"]) for z in mine)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=f"{kind} ({touches} נגיעות)",
                                     marker=dict(symbol="square", size=10, color=color, opacity=0.5)),
                          row=1, col=1)
    for period, color in SMA_COLORS.items():
        fig.add_trace(go.Scatter(x=df.index, y=df[sma_col(period)], name=sma_col(period),
                                 line=dict(color=color, width=1.5)), row=1, col=1)
    for direction, shape, color in ((UP, "triangle-up", POS), (DOWN, "triangle-down", NEG)):
        s = marks[marks["direction"] == direction] if not marks.empty else marks
        if not s.empty:
            fig.add_trace(go.Scatter(x=pd.to_datetime(s["date"]), y=s["close"], mode="markers",
                                     name=f"איתות {direction}",
                                     marker=dict(symbol=shape, size=11, color=color,
                                                 line=dict(color=BG, width=1.5))), row=1, col=1)

    # קומה 2: ווליום + הממוצע שלו (הקומה מסבירה את עצמה - בלי פריטים במקרא)
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="ווליום", showlegend=False,
                         marker=dict(color="#2b313a", line_width=0)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["VolAvg"], name="ממוצע ווליום", showlegend=False,
                             line=dict(color=TEXT_2, width=1)), row=2, col=1)

    # קומה 3: CCI + קווי ייחוס (קווים דקים ורציפים)
    fig.add_trace(go.Scatter(x=df.index, y=df["CCI"], name="CCI", showlegend=False,
                             line=dict(color=ACCENT, width=1.5)), row=3, col=1)
    for level in (100, 0, -100):
        fig.add_hline(y=level, line_width=1, line_color=BORDER, row=3, col=1)

    fig.update_layout(
        height=680, autosize=True, xaxis_rangeslider_visible=False, template="plotly_dark",
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(family=FONT, size=12, color=TEXT_2),
        margin=dict(l=8, r=8, t=8, b=8), hovermode="x unified",
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, font=dict(family=FONT, color=TEXT)),
        # המקרא מתחת לגרף: בטלפון הוא נשבר לכמה שורות בלי לעלות על הנרות
        legend=dict(orientation="h", yanchor="top", y=-0.06, x=0, font=dict(size=11),
                    bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor=GRID, linecolor=BORDER, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=BORDER, zeroline=False, tickfont=dict(color=MUTED))
    for row, title in ((2, "ווליום"), (3, "CCI")):
        fig.update_yaxes(title_text=title, title_font=dict(size=11, color=MUTED), row=row, col=1)
    if not is_crypto(symbol):
        # מניות לא נסחרות בסופ"ש - מסתירים את הרווחים בגרף
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


def run_scan(groups, lookback, refresh, swing_atr, zone_atr):
    """מוריד וסורק את הקבוצות שנבחרו, עם פס התקדמות. שומר את התוצאות בזיכרון האתר."""
    started = time.time()
    # אנימציה (שני שחקני כדורסל מוסרים כדור) מעל פס ההתקדמות. היא רצה בדפדפן (CSS),
    # כך שהיא זזה גם כשהשרת עסוק בסריקה, ונמחקת בסוף - גם אם הסריקה נכשלה.
    loader = st.empty()
    loader.html(ui_art.LOADER_HTML)
    bar = st.progress(0.0, text="טוען את רשימות הנכסים...")

    def progress(part, text):
        bar.progress(min(part, 1.0), text=text)

    try:
        symbols, group_errors = load_universe(groups, progress)
        if not symbols:
            st.session_state.pop("results", None)  # לא משאירים תוצאות ישנות שנראות כמו חדשות
            for group, msg in group_errors:
                st.error(f"לא הצלחתי לטעון את הקבוצה '{group}': {msg}")
            st.error("אין נכסים לסריקה - הסריקה לא בוצעה.")
            return
        res = scan_all(symbols, lookback, progress, refresh, swing_atr, zone_atr)
    finally:
        loader.empty()
        bar.empty()
    res.update(version=RESULTS_VERSION, group_errors=group_errors, total=len(symbols),
               lookback=lookback, swing_atr=swing_atr, zone_atr=zone_atr,
               seconds=time.time() - started)
    st.session_state.results = res
    load_chart_frame.clear()  # הנתונים אולי התעדכנו - שהגרף לא יציג גרסה ישנה


def show_problems(title, items):
    """רשימת שגיאות/דילוגים בתוך חלונית סגורה - לא עשרות הודעות אדומות."""
    if items:
        with st.expander(f"{title} ({len(items)})"):
            st.dataframe(pd.DataFrame(items, columns=["נכס", "סיבה"]), hide_index=True)


def show_table(title, caption, table, formatter):
    st.subheader(f"{title} ({len(table)})")
    st.caption(caption)
    if table.empty:
        st.write("לא נמצאו תוצאות.")
    else:
        show_df(formatter(table))


# --- סרגל צד ---
# כל קבוצת חיפוש היא "מגירה" סגורה; בכותרת שלה רואים כמה נבחרו בלי לפתוח אותה.
# לכל פקד יש key - כך הבחירות נשמרות גם כשהמגירה סגורה ובין ריצות.
ss = st.session_state
SMA_NAMES = [name for name, _, _ in signal_pairs()]
TRIANGLE_KEYS = dict(zip(TRIANGLE_TYPES, ("tri_sym", "tri_asc")))  # מפתח לבחירות של כל סוג משולש


def label(title, n=0, note=""):
    """כותרת מגירה: השם, ואם יש - כמה נבחרו / מה מוגדר.
    (הכותרת משתנה תוך כדי בחירה, לכן לכל מגירה יש key קבוע - בלי key, Streamlit סוגר
    מגירה שהכותרת שלה השתנתה, כלומר היא הייתה נסגרת אחרי כל לחיצה בתוכה.)"""
    if note:
        return f"{title} · {note}"
    if not n:
        return title
    return f"{title} · נבחר 1" if n == 1 else f"{title} · {n} נבחרו"


def section(text, icon_class=""):
    st.markdown(f"<p class='sm-label {icon_class}'>{text}</p>", unsafe_allow_html=True)


def short(prefix):
    """מציג את האפשרות בלי שם המבנה (בתוך המגירה שלו השם כבר ידוע)."""
    return lambda option: option.replace(prefix, "", 1)


with st.sidebar:
    section("נכסים לסריקה", "sm-ic-assets")
    groups = st.pills("קבוצות נכסים", ALL_GROUPS, selection_mode="multi", default=ALL_GROUPS,
                      key="groups", label_visibility="collapsed",
                      help="כברירת מחדל - הכול (S&P 1500, נאסד\"ק 100, קרנות סל, קריפטו והרשימה "
                           "שלך). נכס שמופיע בכמה קבוצות נסרק פעם אחת. מניות מתחת ל-"
                           f"{settings.MIN_STOCK_PRICE:.0f}$ או עם מחזור מסחר נמוך מדולגות.")
    scan_clicked = st.button("סרוק עכשיו", type="primary", width="stretch",
                             icon=":material/search:")
    st.caption("אחרי הסריקה כל בחירה למטה מעדכנת את התוצאות מיד - בלי להוריד שוב.")

    section("מה לחפש")
    match_label = st.segmented_control(
        "התאמה", list(MATCH_LABELS), default=list(MATCH_LABELS)[0], key="match",
        help="כל התנאים: רק נכסים שעומדים בכל מה שנבחר למטה.  \n"
             "לפחות אחד: נכסים שעומדים בתנאי אחד או יותר.")
    match = MATCH_LABELS.get(match_label, MATCH_ALL)  # בלי בחירה = כל התנאים

    with st.expander(label("חציות ממוצעים נעים", len(ss.get("sma_choices") or [])), key="exp_sma"):
        st.caption("חצייה של ממוצע נע 50 את 150, או של המחיר את ממוצע 150, בנרות האחרונים.")
        sma_choices = st.pills("חציות", SMA_NAMES, selection_mode="multi", key="sma_choices",
                               label_visibility="collapsed")

    with st.expander(label("אזורי תמיכה והתנגדות", len(ss.get("sr_choices") or [])), key="exp_sr"):
        st.caption("אזור = טווח מחירים שבו המחיר התהפך כמה פעמים ועדיין לא נחצה. "
                   "פריצה = הסגירה הראשונה מעבר לאזור. נשיקה = המחיר קרוב לאזור מהצד שלו.")
        sr_choices = st.pills("תמיכה והתנגדות", list(SR_OPTIONS), selection_mode="multi",
                              key="sr_choices", label_visibility="collapsed")

    section("מבנים טכניים")
    with st.expander(label("תעלה עולה", len(ss.get("channel_choices") or [])), key="exp_channel"):
        st.caption("שני קווים מקבילים שעולים: התחתון דרך שפלים, העליון דרך שיאים. כל שפל ושיא "
                   "גבוהים מהקודמים, ולפחות 2 נגיעות בכל קו.")
        channel_choices = st.pills("תעלה עולה", CHANNEL_OPTIONS, selection_mode="multi",
                                   key="channel_choices", label_visibility="collapsed",
                                   format_func=short("תעלה עולה – "))

    triangle_count = sum(len(ss.get(k) or []) for k in TRIANGLE_KEYS.values())
    with st.expander(label("משולש מתכנס", triangle_count), key="exp_triangle"):
        st.caption("שני קווים שמתכנסים לקודקוד, ולפחות 2 נגיעות בכל קו. בחר/י סוג משולש ואז את "
                   "האיתותים שלו.")
        picked = []
        # לשונית לכל סוג משולש. התוכן של כל הלשוניות קיים תמיד - כך בחירה בלשונית אחת
        # לא נמחקת כשעוברים לאחרת
        for tab, kind in zip(st.tabs(list(TRIANGLE_TYPES)), TRIANGLE_TYPES):
            with tab:
                picked += st.pills(kind, [o for o in TRIANGLE_OPTIONS if TRIANGLE_INFO[o][0] == kind],
                                   selection_mode="multi", key=TRIANGLE_KEYS[kind],
                                   label_visibility="collapsed", format_func=short(f"{kind} – "))
        triangle_choices = [o for o in TRIANGLE_OPTIONS if o in picked]  # סדר קבוע

    kiss_chosen = (any(SR_OPTIONS[c][0] == KISS for c in sr_choices)
                   or any(c in CHANNEL_KISSES for c in channel_choices)
                   or any(c in TRIANGLE_KISSES for c in triangle_choices))

    section("מסננים")
    near_now = ss.get("near_range", settings.SR_NEAR_RANGE)
    with st.expander(label("טווח נשיקה", note=f"{near_now[0]:g}%–{near_now[1]:g}%"), key="exp_near"):
        near_range = st.slider("מרחק מהאזור / מהקו (%)", 0.0, settings.SR_NEAR_MAX_PCT,
                               settings.SR_NEAR_RANGE, 0.5, key="near_range",
                               disabled=not kiss_chosen,
                               help="כמה רחוק מקצה האזור או מקו התעלה / המשולש המחיר יכול להיות "
                                    "כדי להיחשב 'נשיקה'. משותף לכולם.")
        if not kiss_chosen:
            st.caption("פעיל כשבוחרים נשיקה כלשהי.")

    if ss.get("use_cci"):
        mode_now = ss.get("cci_mode") or CCI_MANUAL
        lo, hi = ss.get("cci_range", settings.CCI_RANGE)
        cci_note = CCI_WITH_SIGNAL if mode_now == CCI_WITH_SIGNAL else f"{cci_text(lo)} עד {cci_text(hi)}"
    else:
        cci_note = "כבוי"
    with st.expander(label("CCI", note=cci_note), key="exp_cci"):
        use_cci = st.toggle("סנן לפי CCI", key="use_cci",
                            help="CCI מודד מומנטום: מעל 0 = מעל הממוצע, מעל 100 = חזק במיוחד.")
        cci_mode = st.segmented_control("אופן הסינון", [CCI_MANUAL, CCI_WITH_SIGNAL],
                                        default=CCI_MANUAL, disabled=not use_cci, key="cci_mode",
                                        help=f"{CCI_WITH_SIGNAL}: איתות למעלה (חצייה למעלה, פריצת "
                                             "התנגדות) - CCI מעל 0; איתות למטה (חצייה למטה, שבירת "
                                             "תמיכה) - CCI מתחת ל-0. נשיקות לא מסוננות (אין להן כיוון).")
        cci_range = st.slider("טווח CCI", -settings.CCI_LIMIT, settings.CCI_LIMIT,
                              settings.CCI_RANGE, 10, key="cci_range",
                              disabled=not use_cci or cci_mode == CCI_WITH_SIGNAL,
                              help="רק איתותים שה-CCI ביום האיתות בטווח הזה.")
        st.caption(f"הקצוות פתוחים: {settings.CCI_LIMIT} = '{settings.CCI_LIMIT} ומעלה', "
                   f"-{settings.CCI_LIMIT} = '-{settings.CCI_LIMIT} ומטה'. הטווח חל על כל האיתותים - "
                   "שבירות תמיכה בדרך כלל עם CCI שלילי, אז טווח חיובי יסתיר אותן.")

    vol_note = f"≥ ×{ss.get('vol_min', settings.VOLUME_MULTIPLIER):.1f}" if ss.get("use_volume") else "כבוי"
    with st.expander(label("ווליום", note=vol_note), key="exp_volume"):
        use_volume = st.toggle("סנן לפי ווליום", key="use_volume",
                               help=f"ווליום ביום האיתות לעומת ממוצע {settings.VOLUME_AVG_DAYS} "
                                    "הימים שלפניו.")
        vol_min = st.slider(f"לפחות פי X מממוצע {settings.VOLUME_AVG_DAYS} יום", 1.0,
                            settings.VOLUME_MAX_MULTIPLIER, settings.VOLUME_MULTIPLIER, 0.1,
                            format="×%.1f", disabled=not use_volume, key="vol_min")

    # כמה הגדרות מתקדמות שונו מברירת המחדל (מוצג בכותרת)
    ADVANCED_DEFAULTS = {"lookback": settings.LOOKBACK_DAYS, "min_touches": settings.SR_MIN_TOUCHES,
                         "use_touch_vol": False, "swing_atr": settings.SWING_MIN_MOVE_ATR,
                         "zone_atr": settings.ZONE_WIDTH_ATR, "refresh": False}
    changed = sum(k in ss and ss[k] != v for k, v in ADVANCED_DEFAULTS.items())
    with st.expander(label("הגדרות מתקדמות", note=("שונתה 1" if changed == 1 else f"{changed} שונו") if changed else ""),
                      key="exp_advanced"):
        lookback = st.number_input("חלון איתותים (נרות אחרונים)", min_value=1,
                                   max_value=CHART_CANDLES, value=settings.LOOKBACK_DAYS,
                                   key="lookback",
                                   help="חציות ופריצות שקרו בכמה הנרות האחרונים.")
        min_touches = st.slider("מינימום נגיעות באזור", 2, settings.SR_MAX_TOUCHES,
                                settings.SR_MIN_TOUCHES, key="min_touches",
                                help="יותר נגיעות = אזור חזק ומבוסס יותר.")
        use_touch_vol = st.toggle("רק אזורים עם ווליום גבוה בנגיעות", key="use_touch_vol",
                                  help="קונים/מוכרים חזקים נכנסו באזור: הווליום הממוצע "
                                       "בנרות הנגיעה גבוה מהרגיל.")
        touch_vol_min = st.slider("ווליום ממוצע בנגיעות - לפחות", 1.0, 3.0,
                                  settings.TOUCH_VOLUME_MIN, 0.1, format="×%.1f",
                                  disabled=not use_touch_vol, key="touch_vol_min")
        swing_atr = st.slider("רגישות נקודות מפנה (היפוך של פי X ATR)", 1.0, 3.0,
                              settings.SWING_MIN_MOVE_ATR, 0.25, key="swing_atr",
                              help="ATR = התנודה היומית הממוצעת. גבוה יותר = רק היפוכים חדים, "
                                   "פחות אזורים. חל מהסריקה הבאה.")
        zone_atr = st.slider("רוחב אזור (פי ATR)", 0.25, 1.5, settings.ZONE_WIDTH_ATR, 0.05,
                             key="zone_atr", help="כמה רחב כל אזור. חל מהסריקה הבאה.")
        refresh = st.toggle("הורד נתונים מחדש (בלי המטמון)", key="refresh")

# --- כותרת ---
# לוגו: סמל של תנודת מחיר עם חץ למעלה + SWING MASTER (הציור והעיצוב ב-ui_art.py)
st.html(ui_art.header_html("איתותים טכניים על S&amp;P 1500, נאסד\"ק 100, קרנות סל וקריפטו"))
st.warning("התוצאות הן איתותים לבדיקה בלבד - לא המלצות קנייה או מכירה.")

if scan_clicked:
    if groups:
        run_scan(groups, int(lookback), refresh, swing_atr, zone_atr)
    else:
        st.error("בחר/י לפחות קבוצת נכסים אחת לסריקה.")

# תוצאות מגרסה קודמת של האתר (מבנה אחר) - לא משתמשים בהן
if st.session_state.get("results", {}).get("version") != RESULTS_VERSION:
    st.session_state.pop("results", None)

# --- תוצאות ---
cci_filter = None
if use_cci:
    cci_filter = CCI_DIRECTION if cci_mode == CCI_WITH_SIGNAL else tuple(cci_range)
vol_filter = vol_min if use_volume else None
touch_filter = touch_vol_min if use_touch_vol else None
criteria = list(sma_choices) + list(sr_choices) + list(channel_choices) + list(triangle_choices)
unified = latest = pd.DataFrame()
found = {}  # כל המופעים לכל תנאי (לפירוט ולגרף)

if "results" not in st.session_state:
    st.info("בחר/י בסרגל הצד קבוצות נכסים ומה לחפש, ולחצ/י על 'סרוק עכשיו'.")
else:
    res = st.session_state.results
    ok = res["total"] - len(res["skipped"]) - len(res["errors"])
    st.caption(f"נסרקו {res['total']} נכסים: {ok} תקינים, {len(res['skipped'])} דולגו, "
               f"{len(res['errors'])} שגיאות ({res['seconds']:.0f} שניות).")
    for group, msg in res["group_errors"]:
        st.error(f"לא הצלחתי לטעון את הקבוצה '{group}': {msg}")
    show_problems("שגיאות", res["errors"])
    show_problems("דולגו (מעט היסטוריה / מחיר נמוך / מעט מסחר)", res["skipped"])

    window = int(lookback)
    if window > res["lookback"]:
        st.warning(f"הסריקה האחרונה חיפשה רק ב-{res['lookback']} נרות אחרונים. "
                   "לחצ/י שוב על 'סרוק עכשיו' כדי לחפש בחלון הגדול יותר.")
        window = res["lookback"]
    if (swing_atr, zone_atr) != (res["swing_atr"], res["zone_atr"]):
        st.info("שינית את רגישות נקודות המפנה / רוחב האזור - זה ישפיע מהסריקה הבאה.")

    filters = []
    if cci_filter == CCI_DIRECTION:
        filters.append("CCI בכיוון האיתות")
    elif cci_filter:
        filters.append(f"CCI בין {cci_text(cci_range[0])} ל-{cci_text(cci_range[1])}")
    if use_volume:
        filters.append(f"ווליום ≥ ×{vol_min:.1f} מהממוצע")
    if filters:
        st.caption("מסננים פעילים: " + " · ".join(filters) + " - חלים על כל התוצאות, "
                   "לפי הנר של יום האיתות (בנשיקה ובסורק - הנר האחרון).")
    if (isinstance(cci_filter, tuple) and cci_range[0] >= 0 and SUP_BREAK in sr_choices) or \
            (isinstance(cci_filter, tuple) and cci_range[1] <= 0 and RES_BREAK in sr_choices):
        st.info("שים/י לב: טווח ה-CCI הנוכחי מסתיר כמעט את כל "
                + ("שבירות התמיכה (CCI שלילי)" if cci_range[0] >= 0 else "פריצות ההתנגדות (CCI חיובי)")
                + f". אפשר לבחור '{CCI_WITH_SIGNAL}'.")

    if not criteria:
        if cci_filter == CCI_DIRECTION and not use_volume:
            st.info(f"'{CCI_WITH_SIGNAL}' דורש לבחור איתות (בלי איתות אין כיוון). "
                    "לסינון כל הנכסים לפי CCI - בחר/י 'טווח ידני'.")
        elif filters:
            # מצב "סורק": אין איתות נבחר - מציגים נכסים שהנר האחרון שלהם עומד בתנאים
            latest = filter_latest(res["latest"], cci_filter, vol_filter)
            show_table("נכסים שעומדים בתנאים", "לא נבחר איתות - מוצגים כל הנכסים שהנר "
                       "האחרון שלהם עומד במסנני ה-CCI / הווליום. הווליום הגבוה ראשון."
                       + (f" (מסנן '{CCI_WITH_SIGNAL}' לא חל כאן - אין איתות ולכן אין כיוון.)"
                          if cci_filter == CCI_DIRECTION else ""),
                       latest, format_latest_table)
        else:
            st.info("בחר/י בסרגל הצד מה לחפש: חצייה, פריצה, נשיקה, תעלה או משולש - "
                    "או הפעל/י מסנן CCI / ווליום כדי לסנן את כל הנכסים.")

    if criteria:
        unified, found = combine_signals(res, criteria, window, match, min_touches, near_range,
                                         touch_filter, cci_filter, vol_filter)
        how = "בכל התנאים" if match == MATCH_ALL else "לפחות באחד מהתנאים"
        notes = [f"נכסים שעומדים {how}: " + " · ".join(criteria) + ".",
                 f"חציות ופריצות - ב-{window} הנרות האחרונים (מוצגת החדשה ביותר). "
                 "נשיקה - לפי הנר האחרון (מוצג האזור הקרוב ביותר)."]
        if channel_choices:
            notes.append(f"תעלה עולה: נגיעות = שפלים על הקו התחתון + שיאים על העליון; "
                         f"נשיקה = {near_range[0]}%-{near_range[1]}% מהקו.")
        if triangle_choices:
            notes.append("משולשים: נגיעות = שפלים על הקו התחתון + שיאים על העליון; "
                         f"נשיקה = {near_range[0]}%-{near_range[1]}% מהקו מבפנים; "
                         "'קודקוד בעוד' = בעוד כמה נרות הקווים נפגשים.")
        if sr_choices:
            notes.append(f"אזורים עם {min_touches} נגיעות לפחות"
                         + (f" וווליום ממוצע ≥ ×{touch_vol_min:.1f} בנגיעות" if use_touch_vol else "")
                         + (f"; נשיקה = {near_range[0]}%-{near_range[1]}% מהאזור או בתוכו"
                            if kiss_chosen else "") + ".")
        notes.append("SMA / CCI / פי ווליום בסוף הטבלה - של הנר האחרון. החדשים ראשונים.")
        st.subheader(f"תוצאות ({len(unified)})")
        st.caption("  \n".join(notes))
        if unified.empty:
            st.write("לא נמצאו נכסים שעומדים בתנאים."
                     + (" אפשר לבחור פחות תנאים, או 'לפחות אחד (או)' למעלה."
                        if match == MATCH_ALL and len(criteria) > 1 else ""))
        else:
            show_df(format_unified_table(unified, criteria))
            with st.expander("פירוט לפי סוג איתות"):
                for name in criteria:
                    st.markdown(f"**{name}** ({len(found[name])})")
                    if found[name].empty:
                        st.write("—")
                    elif name in CHANNEL_OPTIONS:
                        show_df(format_channel_table(found[name]))
                    elif name in TRIANGLE_OPTIONS:
                        show_df(format_triangle_table(found[name]))
                    elif name in SR_OPTIONS:
                        show_df(format_zone_table(found[name], SR_OPTIONS[name][0] == KISS))
                    else:
                        show_df(format_cross_table(found[name]))

# --- גרף ---
st.subheader("גרף")
shown = unified if not unified.empty else latest
if not shown.empty:
    options = list(shown["symbol"])
else:
    try:
        options = load_assets()
    except OSError:
        options = []  # אין קובץ רשימה אישית - פשוט אין מה להציע
if not options:
    st.info("אין נכסים להצגה בגרף - הרץ/י סריקה או הוסף/י נכסים ל-assets.txt.")
else:
    symbol = st.selectbox("בחר/י נכס", options)
    st.caption("פסים ירוקים = אזורי תמיכה, אדומים = התנגדות (הקרובים שעדיין מחזיקים). "
               "קווים בצהוב = תעלה עולה פעילה (או, בפריצה/שבירה - התעלה שנפרצה, "
               "עד יום היציאה). קווים במגנטה = משולש (אותו כלל). נר חלול = עולה, מלא = יורד.")
    # סימון החציות והפריצות של הנכס (לנשיקות אין סימון - רואים את האזור / הקו עצמו)
    marks = [t[t["symbol"] == symbol][["date", "close", "direction"]]
             for name, t in found.items()
             if not t.empty and name not in CHANNEL_KISSES and name not in TRIANGLE_KISSES
             and not (name in SR_OPTIONS and SR_OPTIONS[name][0] == KISS)]
    marks = pd.concat(marks) if any(not m.empty for m in marks) else pd.DataFrame()
    # הגרף משתמש באותן הגדרות כמו הסריקה האחרונה, כדי שיתאים לטבלאות
    scanned = st.session_state.get("results", {})
    chart_swing = scanned.get("swing_atr", swing_atr)
    chart_zone = scanned.get("zone_atr", zone_atr)
    # אם הנכס נבחר בגלל פריצה/שבירה של תעלה - מציירים את התעלה שנפרצה (החדשה ביותר)
    exits = [t[t["symbol"] == symbol] for name, t in found.items()
             if name in CHANNEL_OPTIONS and name not in CHANNEL_KISSES and not t.empty]
    exits = pd.concat(exits) if exits else pd.DataFrame()
    channel_date = None if exits.empty else exits.sort_values("days_ago")["date"].iloc[0]
    # אותו דבר למשולשים: לכל סוג משולש שנפרץ/נשבר - יום היציאה החדש ביותר
    triangle_exits = {}
    for name, t in found.items():
        if name in TRIANGLE_OPTIONS and name not in TRIANGLE_KISSES and not t.empty:
            mine = t[t["symbol"] == symbol]
            kind = TRIANGLE_INFO[name][0]
            if not mine.empty and kind not in triangle_exits:
                triangle_exits[kind] = mine.sort_values("days_ago")["date"].iloc[0]
    try:
        st.plotly_chart(make_chart(load_chart_frame(symbol), symbol, marks, min_touches,
                                   touch_filter, chart_swing, chart_zone, channel_date,
                                   triangle_exits), theme=None, width="stretch",
                        config={"responsive": True, "displaylogo": False})
    except Exception as e:
        st.error(f"לא הצלחתי לטעון את {symbol}: {e}")
