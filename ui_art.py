# ציורים קטנים לאתר: אייקון לכל קבוצה בסרגל הצד, הלוגו, ואנימציית הטעינה.
# כל ציור הוא SVG קטן שמוצג כתמונת רקע ב-CSS (Streamlit מוחק תגיות <svg> מ-HTML,
# אבל תמונות רקע ב-CSS עוברות). כל האייקונים באותו סגנון: קו בעובי 1.8, פינות מעוגלות,
# צבע ההדגשה (כחול) + אפור לפרטים משניים.

from urllib.parse import quote

ACCENT, SOFT, BG = "#3987e5", "#a4abb6", "#0f1114"
BALL, SEAM = "#d95926", "#3a1d0e"


def svg(body, size=24, w=None, h=None):
    """עוטף ציור בתגית svg עם הסגנון המשותף של האייקונים."""
    w, h = w or size, h or size
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" '
            f'stroke="{ACCENT}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</svg>')


def data_uri(source):
    """SVG -> כתובת data: לשימוש ב-CSS (כל התווים המיוחדים מקודדים)."""
    return "data:image/svg+xml," + quote(source, safe="")


# --- אייקונים לסרגל הצד: מפתח -> ציור ---
ICONS = {
    # נכסים לסריקה: שני נרות יפניים
    "assets": svg(f'<line x1="8" y1="3" x2="8" y2="21"/><rect x="5.5" y="7" width="5" height="9" rx="1"/>'
                  f'<line x1="16" y1="5" x2="16" y2="19"/>'
                  f'<rect x="13.5" y="9" width="5" height="6" rx="1" fill="{ACCENT}" fill-opacity=".35"/>'),
    # התאמה (וגם / או): שני עיגולים חופפים
    "match": svg(f'<circle cx="9" cy="12" r="6"/><circle cx="15" cy="12" r="6" stroke="{SOFT}"/>'),
    # חציות ממוצעים: קו עולה וקו יורד שנחצים, נקודה במקום החצייה
    "sma": svg(f'<path d="M3 18 C9 17 13 9 21 6"/><path d="M3 7 C9 8 14 15 21 17" stroke="{SOFT}"/>'
               f'<circle cx="12" cy="12.3" r="1.9" fill="{ACCENT}" stroke="none"/>'),
    # אזורי תמיכה והתנגדות: שני פסים אופקיים, ומחיר שמתהפך ביניהם
    "zones": svg(f'<rect x="3" y="4" width="18" height="4" rx="1" fill="{ACCENT}" fill-opacity=".3" stroke="none"/>'
                 f'<rect x="3" y="16" width="18" height="4" rx="1" fill="{ACCENT}" fill-opacity=".3" stroke="none"/>'
                 f'<polyline points="4,15 8,9 12,15 16,9 20,13" stroke="{SOFT}" stroke-width="1.5"/>'),
    # תעלה עולה: שני קווים מקבילים שעולים, ומחיר שנע ביניהם
    "channel": svg(f'<line x1="3" y1="14" x2="21" y2="5"/><line x1="3" y1="20" x2="21" y2="11"/>'
                   f'<polyline points="4,17.5 8,12.5 12,15.5 17,9.5 20,11" stroke="{SOFT}" stroke-width="1.3"/>'),
    # משולש מתכנס: קו עליון יורד וקו תחתון עולה שנפגשים בקודקוד, ומחיר שמצטמצם ביניהם
    "triangle": svg(f'<line x1="3" y1="4" x2="20" y2="12"/><line x1="3" y1="20" x2="20" y2="12"/>'
                    f'<polyline points="4,7 7,17 10,9 13,15 16,11" stroke="{SOFT}" stroke-width="1.3"/>'),
    # לשונית משולש סימטרי: שני קווים מתכנסים באותה זווית
    "tri_sym": svg(f'<line x1="3" y1="4" x2="21" y2="12"/><line x1="3" y1="20" x2="21" y2="12"/>'
                   f'<circle cx="21" cy="12" r="1.6" fill="{ACCENT}" stroke="none"/>'),
    # לשונית משולש עולה: קו עליון שטוח וקו תחתון עולה
    "tri_asc": svg(f'<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="20" x2="21" y2="6"/>'
                   f'<circle cx="21" cy="6" r="1.6" fill="{ACCENT}" stroke="none"/>'),
    # קאפ אנד הנדל: ספל בצורת U, ידית קטנה מימין, וקו נקודת הפריצה מעליהם
    "cup": svg(f'<line x1="2" y1="6" x2="22" y2="6" stroke="{SOFT}" stroke-width="1.1" stroke-dasharray="2 2"/>'
               f'<path d="M3 6 C3.5 18 13.5 18 14 6"/><path d="M14 6 C15.5 9 18 9.5 20.5 7.5"/>'),
    # טווח נשיקה: מחיר שיורד, נוגע בקו ועולה חזרה
    "kiss": svg(f'<line x1="3" y1="17.5" x2="21" y2="17.5"/>'
                f'<path d="M3 5 C7 6 9 15 12 15.6 C15 15 17 9 21 7" stroke="{SOFT}"/>'
                f'<circle cx="12" cy="16" r="1.7" fill="{ACCENT}" stroke="none"/>'),
    # CCI: גל שעולה ויורד בין שני קווי ייחוס
    "cci": svg(f'<line x1="2" y1="6" x2="22" y2="6" stroke="{SOFT}" stroke-width="1.2"/>'
               f'<line x1="2" y1="18" x2="22" y2="18" stroke="{SOFT}" stroke-width="1.2"/>'
               f'<path d="M2 12 C4.5 3 7.5 3 10 12 C12.5 21 15.5 21 18 12 C19.5 7 21 6 22 7"/>'),
    # ווליום: עמודות בגבהים שונים
    "volume": svg(f'<rect x="3.5" y="14" width="3" height="6" rx=".6" fill="{ACCENT}" fill-opacity=".3"/>'
                  f'<rect x="8.5" y="9" width="3" height="11" rx=".6" fill="{ACCENT}" fill-opacity=".3"/>'
                  f'<rect x="13.5" y="12" width="3" height="8" rx=".6" fill="{ACCENT}" fill-opacity=".3"/>'
                  f'<rect x="18.5" y="5" width="3" height="15" rx=".6" fill="{ACCENT}" fill-opacity=".3"/>'),
    # הגדרות מתקדמות: שלושה מחוונים
    "advanced": svg(f'<line x1="3" y1="6" x2="21" y2="6" stroke="{SOFT}"/>'
                    f'<line x1="3" y1="12" x2="21" y2="12" stroke="{SOFT}"/>'
                    f'<line x1="3" y1="18" x2="21" y2="18" stroke="{SOFT}"/>'
                    f'<circle cx="15" cy="6" r="2.2" fill="{BG}"/><circle cx="8" cy="12" r="2.2" fill="{BG}"/>'
                    f'<circle cx="13" cy="18" r="2.2" fill="{BG}"/>'),
}

# איפה כל אייקון מופיע: בורר CSS -> שם אייקון. האייקון נכנס לפני הטקסט, כלומר מימין לו (RTL).
# Streamlit 1.64 מוסיף לכל רכיב עם key את המחלקה st-key-<key> (על העוטף של המגירה), וכותרת
# המגירה היא <summary> שהטקסט שלה בתוך <p>.
ICON_TARGETS = {
    ".sm-ic-assets": "assets",
    ".st-key-match [data-testid='stWidgetLabel'] p": "match",
    ".st-key-exp_sma summary p": "sma",
    ".st-key-exp_sr summary p": "zones",
    ".st-key-exp_channel summary p": "channel",
    ".st-key-exp_triangle summary p": "triangle",
    ".st-key-exp_triangle [data-testid='stTab']:nth-of-type(1) p": "tri_sym",
    ".st-key-exp_triangle [data-testid='stTab']:nth-of-type(2) p": "tri_asc",
    ".st-key-exp_cup summary p": "cup",
    ".st-key-exp_near summary p": "kiss",
    ".st-key-exp_cci summary p": "cci",
    ".st-key-exp_volume summary p": "volume",
    ".st-key-exp_advanced summary p": "advanced",
}

# --- הלוגו: נר-זיגזג של "סווינג" שמסתיים בחץ למעלה, בתוך ריבוע מעוגל ---
LOGO = svg(f'<rect x="1.5" y="1.5" width="45" height="45" rx="10" fill="#14233a" stroke="#2b4a73" stroke-width="1.5"/>'
           f'<polyline points="10,34 18,24 24,30 36,15" stroke-width="3.2"/>'
           f'<polyline points="29,14.5 36.5,14.5 36.5,22" stroke-width="3.2"/>', w=48, h=48)

# --- אנימציית טעינה: שני שחקני כדורסל ---
# שחקן שפונה ימינה (השני הוא תמונת מראה שלו): ראש, גופייה כחולה, ידיים קדימה (מסירת חזה), רגליים
PLAYER = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 96" fill="none" stroke-linecap="round" '
          f'stroke-linejoin="round"><circle cx="22" cy="12" r="8" fill="{SOFT}"/>'
          f'<polyline points="22,30 40,34 50,30" stroke="{SOFT}" stroke-width="6"/>'
          f'<polyline points="22,33 38,41 50,37" stroke="{SOFT}" stroke-width="6"/>'
          f'<line x1="22" y1="26" x2="22" y2="54" stroke="{ACCENT}" stroke-width="13"/>'
          f'<line x1="20" y1="58" x2="14" y2="90" stroke="{SOFT}" stroke-width="8"/>'
          f'<line x1="24" y1="58" x2="32" y2="90" stroke="{SOFT}" stroke-width="8"/></svg>')
# כדורסל: עיגול כתום עם תפרים
BALL_SVG = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="{SEAM}" '
            f'stroke-width=".9"><circle cx="8" cy="8" r="7.2" fill="{BALL}"/><path d="M8 .8 V15.2 M.8 8 H15.2"/>'
            f'<path d="M3 2.5 C6 6 6 10 3 13.5 M13 2.5 C10 6 10 10 13 13.5"/></svg>')

ALL_SVGS = {**ICONS, "logo": LOGO, "player": PLAYER, "ball": BALL_SVG}


def icons_css():
    """כללי CSS: אייקון קטן לפני כל כותרת בסרגל הצד."""
    rules = []
    for selector, name in ICON_TARGETS.items():
        size = 15 if selector.startswith(".sm-ic") else 18
        rules.append(f'{selector}::before {{content: ""; display: inline-block; width: {size}px; '
                     f'height: {size}px; margin-inline-end: 8px; vertical-align: -4px; '
                     f'background: url("{data_uri(ICONS[name])}") center / contain no-repeat;}}')
    return "\n".join(rules)


# --- כותרת ראשית: באמצע, ומאחוריה "שוק חי" - תעלה עולה לרוחב כל העמוד, קו מחיר שזורם בתוכה,
#     וחיצים: ירוקים עולים ואדומים יורדים. הכול בתנועת transform / opacity בלבד (קל למעבד הגרפי).
UP_ARROW = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 16" fill="none" stroke="#0ca30c" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15 V3"/>'
            '<path d="M2.5 7.5 L7 3 L11.5 7.5"/></svg>')
DOWN_ARROW = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 16" fill="none" stroke="#e66767" '
              'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 1 V13"/>'
              '<path d="M2.5 8.5 L7 13 L11.5 8.5"/></svg>')
# קו מחיר שחוזר על עצמו כל 400 פיקסלים (מתחיל ונגמר באותו גובה - כך התנועה רציפה בלי קפיצה)
PRICE_LINE = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80" fill="none" stroke="{ACCENT}" '
              'stroke-width="1.6" stroke-linejoin="round"><polyline points="0,52 40,40 70,56 110,30 140,44 '
              '180,22 210,38 250,26 290,48 330,30 365,46 400,52"/></svg>')
ALL_SVGS.update(up_arrow=UP_ARROW, down_arrow=DOWN_ARROW, price_line=PRICE_LINE)

# חיצים ברקע: (עולה?, מיקום אופקי %, משך שניות, השהיה שניות) - פזורים לרוחב, בקצבים שונים
HERO_ARROWS = [(True, 4, 6.5, 0), (False, 9, 7.5, 2.5), (True, 15, 5.5, 4), (False, 21, 8, 1),
               (True, 27, 7, 3), (False, 33, 6, 5), (True, 39, 8, 1.5), (False, 45, 6.5, 3.5),
               (True, 55, 6, 0.5), (False, 61, 7, 4.5), (True, 67, 7.5, 2), (False, 73, 6, 0),
               (True, 79, 6.5, 5), (False, 85, 7.5, 2), (True, 91, 5.5, 3.5), (False, 96, 7, 1)]


def header_css(text, muted):
    """הכותרת הראשית: לוגו + SWING MASTER באמצע, ורקע מונפש של שוק (תעלה, קו מחיר, חיצים)."""
    return f"""
.sm-hero {{position: relative; height: 200px; margin: 0 0 20px; display: flex; align-items: center;
           justify-content: center; overflow: hidden; border: 1px solid #262b33; border-radius: 12px;
           background: linear-gradient(180deg, #121821 0%, #0f1114 100%);}}
.sm-hero-bg {{position: absolute; inset: 0; pointer-events: none;}}
.sm-chan {{position: absolute; left: -6%; right: -6%; top: 50%; height: 120px;
           transform: translateY(-50%) rotate(-3deg);}}
.sm-chan-line {{position: absolute; left: 0; right: 0; height: 1px;
                background: linear-gradient(90deg, rgba(57,135,229,0), rgba(57,135,229,.5) 15%,
                            rgba(57,135,229,.5) 85%, rgba(57,135,229,0));}}
.sm-top {{top: 0;}}
.sm-bot {{bottom: 0;}}
.sm-price {{position: absolute; left: 0; top: 20px; height: 80px; width: calc(100% + 400px); opacity: .45;
            background: url("{data_uri(PRICE_LINE)}") left center / 400px 80px repeat-x;
            animation: sm-flow 24s linear infinite; will-change: transform;}}
.sm-arr {{position: absolute; width: 13px; height: 15px; opacity: 0; will-change: transform, opacity;
          background: center / contain no-repeat; animation: 6s ease-in-out infinite;}}
.sm-arr.up {{bottom: 10px; background-image: url("{data_uri(UP_ARROW)}"); animation-name: sm-rise;}}
.sm-arr.down {{top: 10px; background-image: url("{data_uri(DOWN_ARROW)}"); animation-name: sm-fall;}}
@keyframes sm-flow {{from {{transform: translateX(0);}} to {{transform: translateX(-400px);}}}}
@keyframes sm-rise {{0% {{transform: translateY(0); opacity: 0;}} 20%, 70% {{opacity: .55;}}
                     100% {{transform: translateY(-84px); opacity: 0;}}}}
@keyframes sm-fall {{0% {{transform: translateY(0); opacity: 0;}} 20%, 70% {{opacity: .5;}}
                     100% {{transform: translateY(84px); opacity: 0;}}}}
@keyframes sm-rise-m {{0% {{transform: translateY(0); opacity: 0;}} 20%, 70% {{opacity: .55;}}
                       100% {{transform: translateY(-60px); opacity: 0;}}}}
@keyframes sm-fall-m {{0% {{transform: translateY(0); opacity: 0;}} 20%, 70% {{opacity: .5;}}
                       100% {{transform: translateY(60px); opacity: 0;}}}}
/* מאחורי הטקסט: "הילה" כהה רכה, כדי שהכותרת תמיד תהיה קריאה מעל האנימציה */
.sm-hero-center {{position: relative; z-index: 1; text-align: center; padding: 18px 40px;
                  background: radial-gradient(ellipse at center, rgba(15,17,20,.94) 0%,
                              rgba(15,17,20,.82) 55%, rgba(15,17,20,0) 78%);}}
.sm-brand {{display: flex; align-items: center; justify-content: center; gap: 16px;}}
.sm-mark {{width: 60px; height: 60px; flex: none;
           background: url("{data_uri(LOGO)}") center / contain no-repeat;}}
.sm-word {{margin: 0; padding: 0; line-height: 1; font-weight: 800;
           font-size: clamp(2.1rem, 6vw, 3.6rem); letter-spacing: 0.04em; color: {text};}}
.sm-word .w2 {{margin-left: 0.3em; color: #3987e5;}}
/* צבע בהדרגה רק בדפדפן שתומך בזה - אחרת נשאר כחול אחיד (ולא טקסט שקוף שלא רואים) */
@supports ((-webkit-background-clip: text) or (background-clip: text)) {{
  .sm-word .w2 {{background: linear-gradient(90deg, #3987e5, #7fb3f0);
                -webkit-background-clip: text; background-clip: text; color: transparent;}}
}}
.sm-rule {{height: 2px; width: 120px; margin: 12px auto 0; border-radius: 2px;
           background: linear-gradient(90deg, rgba(57,135,229,0), #3987e5, rgba(57,135,229,0));}}
.sm-hero .sm-sub {{margin: 10px 0 0; text-align: center; color: {muted}; letter-spacing: 0.02em;}}
@media (max-width: 640px) {{
  .sm-hero {{height: 150px; margin-bottom: 14px; border-radius: 10px;}}
  .sm-chan {{height: 96px;}}
  .sm-price {{top: 8px;}}
  .sm-arr:nth-of-type(even) {{display: none;}}      /* בטלפון - חצי מהחיצים */
  /* התעלה נמוכה יותר בטלפון - החיצים זזים פחות, כדי להישאר בתוכה */
  .sm-arr.up {{animation-name: sm-rise-m;}}
  .sm-arr.down {{animation-name: sm-fall-m;}}
  .sm-hero-center {{padding: 12px 16px;}}
  .sm-mark {{width: 40px; height: 40px;}}
  .sm-brand {{gap: 10px;}}
  .sm-rule {{width: 90px; margin-top: 8px;}}
  .sm-hero .sm-sub {{font-size: 0.78rem; margin-top: 6px;}}
}}
@media (prefers-reduced-motion: reduce) {{
  .sm-price, .sm-arr {{animation: none;}}
  .sm-arr {{opacity: .35;}}
}}"""


def header_html(tagline):
    # הלוגו משמאל לימין (שם באנגלית) ובמרכז העמוד; הרקע המונפש מוסתר מקוראי מסך
    arrows = "".join(
        f'<span class="sm-arr {"up" if up else "down"}" '
        f'style="left:{x}%;animation-duration:{dur}s;animation-delay:-{delay}s"></span>'
        for up, x, dur, delay in HERO_ARROWS)
    return (f'<div class="sm-hero"><div class="sm-hero-bg" aria-hidden="true"><div class="sm-chan">'
            f'<div class="sm-chan-line sm-top"></div><div class="sm-chan-line sm-bot"></div>'
            f'<div class="sm-price"></div>{arrows}</div></div>'
            f'<div class="sm-hero-center"><div class="sm-brand" dir="ltr"><span class="sm-mark"></span>'
            f'<h1 class="sm-word"><span class="w1">SWING</span><span class="w2">MASTER</span></h1></div>'
            f'<div class="sm-rule"></div><p class="sm-sub">{tagline}</p></div></div>')


def loader_css():
    """אנימציית הטעינה: הכדור עובר בקשת בין שני השחקנים (תנועה אופקית קבועה + קשת אנכית),
    מסתובב, והשחקנים "נושמים" קלות. מי שביקש פחות תנועה - רואה תמונה סטטית."""
    return f"""
.sm-loader {{display: flex; justify-content: center; margin: 4px 0 8px;}}
.sm-court {{position: relative; width: 280px; max-width: 100%; height: 112px; direction: ltr;
            border-bottom: 1px solid #262b33;}}
.sm-player {{position: absolute; bottom: 4px; width: 56px; height: 96px;
             background: url("{data_uri(PLAYER)}") center / contain no-repeat;
             animation: sm-bob 1.8s ease-in-out infinite;}}
.sm-left {{left: 16px;}}
.sm-right {{right: 16px; transform: scaleX(-1); animation-name: sm-bob-flip; animation-delay: -0.9s;}}
.sm-ballx {{position: absolute; left: 60px; top: 34px; animation: sm-x 0.9s linear infinite alternate;}}
.sm-bally {{display: block; animation: sm-y 0.9s infinite;}}
.sm-ball {{display: block; width: 16px; height: 16px;
           background: url("{data_uri(BALL_SVG)}") center / contain no-repeat;
           animation: sm-spin 0.9s linear infinite;}}
@keyframes sm-x {{from {{transform: translateX(0);}} to {{transform: translateX(144px);}}}}
@keyframes sm-y {{0% {{transform: translateY(0); animation-timing-function: ease-out;}}
                  50% {{transform: translateY(-26px); animation-timing-function: ease-in;}}
                  100% {{transform: translateY(0);}}}}
@keyframes sm-spin {{to {{transform: rotate(360deg);}}}}
@keyframes sm-bob {{0%, 100% {{transform: translateY(0);}} 50% {{transform: translateY(2px);}}}}
@keyframes sm-bob-flip {{0%, 100% {{transform: scaleX(-1) translateY(0);}}
                         50% {{transform: scaleX(-1) translateY(2px);}}}}
@media (max-width: 320px) {{ .sm-court {{transform: scale(0.85); transform-origin: center top;}} }}
@media (prefers-reduced-motion: reduce) {{
  .sm-player, .sm-ballx, .sm-bally, .sm-ball {{animation: none;}}
  .sm-ballx {{transform: translateX(72px);}}
  .sm-bally {{transform: translateY(-26px);}}
}}"""


LOADER_HTML = ('<div class="sm-loader" role="img" aria-label="שני שחקני כדורסל מוסרים כדור - הסריקה רצה">'
               '<div class="sm-court"><span class="sm-player sm-left"></span>'
               '<span class="sm-player sm-right"></span>'
               '<span class="sm-ballx"><span class="sm-bally"><span class="sm-ball"></span></span></span>'
               '</div></div>')
