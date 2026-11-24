"""
YourSweep: polished portfolio charts
====================================

The "presentation" version of the practice charts (q1-q4). Every number on
every chart comes from a SQL query against yoursweep.db, so when the database
is rebuilt from fresh store exports, rerunning this script redraws all charts
with the new numbers, titles included.

How to run (from the repo folder, after building the database):
    python3 python/portfolio_charts.py

The figures go to figures/
(the database is opened read-only, nothing in it is changed).

Optional: point it at another database or output folder:
    YOURSWEEP_DB=/path/to/copy.db YOURSWEEP_FIGURES=/path/to/folder python3 portfolio_charts.py
"""

import os
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to files, no window
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from matplotlib.patches import FancyBboxPatch

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent            # .../python
SQL_DIR = HERE.parent / "sql"                      # .../sql
DB = Path(os.environ.get("YOURSWEEP_DB", SQL_DIR / "yoursweep.db"))
OUT = Path(os.environ.get("YOURSWEEP_FIGURES", HERE.parent / "figures"))
OUT.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)   # read-only


def q(sql):
    return pd.read_sql(sql, conn)


# List prices are a decision, not data (see 02_cleaning: price_flag).
MONTHLY_PRICE = 8.99
ANNUAL_PRICE = 89.99

# ---------------------------------------------------------------------------
# Style: one look for every chart
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
REST = "#d6d4cc"        # de-emphasised fill ("everything else")

APPLE = "#2a78d6"       # store identity, same on every chart
PLAY = "#eb6834"
STORE_COLOR = {"apple": APPLE, "google_play": PLAY}
STORE_NAME = {"apple": "Apple App Store", "google_play": "Google Play"}

US = "#1baf7a"          # highlight for the US
ANNUAL = "#6250d6"      # plan identity
MONTHLY = "#b5b3ab"

SOURCE = "Source: SYNTHETIC data shaped like App Store Connect + Google Play exports, cleaned in SQL"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "Lato", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": INK2,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "legend.frameon": False,
    "text.parse_math": False,   # so "$" in text is just a dollar sign
})


def style(ax, grid="y"):
    """Hairline grid, no box, only the baseline."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    if grid == "x":
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color(AXIS)


def frame(fig, title, subtitle, source=SOURCE, sql_ref=""):
    """Insight title, plain subtitle, source line. Same place on every chart."""
    h = fig.get_figheight()
    fig.text(0.035, 1 - 0.28 / h, title, ha="left", va="top",
             fontsize=15, weight="bold", color=INK)
    fig.text(0.035, 1 - 0.66 / h, subtitle, ha="left", va="top",
             fontsize=10.5, color=INK2, linespacing=1.4)
    note = source + (f"  ·  {sql_ref}" if sql_ref else "")
    fig.text(0.035, 0.16 / h, note, ha="left", va="bottom", fontsize=8, color=MUTED)


def margins(fig, top_in=1.25, bottom_in=0.7, left=0.08, right=0.97, **kw):
    h = fig.get_figheight()
    fig.subplots_adjust(top=1 - top_in / h, bottom=bottom_in / h, left=left, right=right, **kw)


def save(fig, name):
    fig.savefig(OUT / name, dpi=220)
    plt.close(fig)
    print("  saved", name)


def nice_date(d):
    d = pd.to_datetime(d)
    return f"{d.day} {d:%b %Y}"


def month_label(m, first=False):
    d = pd.to_datetime(m + "-01")
    return f"{d:%b}\n{d:%Y}" if (first or d.month == 1) else f"{d:%b}"


def totals_pad(totals):
    """Room above a bar for its number, then the event label."""
    return totals.max() * 0.17


# Shared SQL pieces -----------------------------------------------------------
START = """
    start AS (
        SELECT MAX(first_date) AS start_date
        FROM (SELECT store, MIN(date) AS first_date FROM payments GROUP BY store)
    )"""

RETENTION = """
    last AS (SELECT MAX(substr(date, 1, 7)) AS last_month FROM clean_payments),
    retention AS (
        SELECT COUNT(DISTINCT b.customer_id || substr(b.date, 1, 7)) AS came_back,
               COUNT(DISTINCT a.customer_id || substr(a.date, 1, 7)) AS paid,
               COUNT(DISTINCT b.customer_id || substr(b.date, 1, 7)) * 1.0
             / COUNT(DISTINCT a.customer_id || substr(a.date, 1, 7)) AS r
        FROM clean_payments a
        LEFT JOIN clean_payments b
          ON  b.customer_id = a.customer_id
          AND substr(b.date, 1, 7) = strftime('%Y-%m', date(a.date, '+1 month'))
        CROSS JOIN last
        WHERE a.plan = 'monthly' AND substr(a.date, 1, 7) < last.last_month
    )"""

COUNTRY = {
    "US": "United States", "IN": "India", "BR": "Brazil", "RU": "Russia",
    "MX": "Mexico", "GB": "United Kingdom", "DE": "Germany", "FR": "France",
    "CA": "Canada", "TR": "Türkiye", "ID": "Indonesia", "PH": "Philippines",
    "PK": "Pakistan", "NG": "Nigeria", "EG": "Egypt", "VN": "Vietnam",
    "IT": "Italy", "ES": "Spain", "UA": "Ukraine", "PL": "Poland",
    "AU": "Australia", "JP": "Japan", "KR": "South Korea", "TW": "Taiwan",
    "SE": "Sweden", "EE": "Estonia", "NL": "Netherlands", "AR": "Argentina",
    "CO": "Colombia", "ZA": "South Africa", "BD": "Bangladesh", "TH": "Thailand",
    "MY": "Malaysia", "SA": "Saudi Arabia", "AE": "UAE", "GR": "Greece",
    "PT": "Portugal", "CL": "Chile", "PE": "Peru", "KE": "Kenya",
    "IR": "Iran", "ZZ": "Unknown",
}


# ===========================================================================
# 00  Summary tiles
# ===========================================================================
def chart_summary():
    k = q(f"""
        WITH {START},
        d AS (SELECT store, SUM(downloads) AS dl FROM downloads, start
              WHERE date >= start_date GROUP BY store),
        p AS (SELECT store, COUNT(*) AS payers FROM customers, start
              WHERE count_as_payer = 1 AND first_payment_date >= start_date GROUP BY store),
        rate AS (SELECT d.store, p.payers * 1.0 / d.dl AS conv FROM d JOIN p USING (store)),
        {RETENTION},
        all_payers AS (SELECT * FROM customers WHERE count_as_payer = 1)
        SELECT
          (SELECT COUNT(*) FROM all_payers)                                   AS payers,
          (SELECT SUM(came_from_trial = 'no') FROM all_payers)                AS paid_straight,
          (SELECT MAX(conv) / MIN(conv) FROM rate)                            AS store_x,
          (SELECT 100.0 * SUM(country = 'US') / COUNT(*) FROM all_payers)     AS us_pct,
          (SELECT r FROM retention)                                           AS r
    """).iloc[0]
    r = k["r"]
    value_x = ANNUAL_PRICE / (MONTHLY_PRICE * sum(r ** i for i in range(12)))

    tiles = [
        (f"{k['payers']:.0f}", "real paying customers\nafter cleaning"),
        (f"{k['store_x']:.1f}x", "better download-to-payer\nconversion on Apple"),
        (f"{k['us_pct']:.0f}%", "of payers are in the US"),
        (f"{k['paid_straight']:.0f} of {k['payers']:.0f}", "paid straight away,\nwithout a free trial"),
        (f"{r * 100:.0f}%", "of monthly payers\nrenew each month"),
        (f"{value_x:.1f}x", "more value from an annual\ncustomer over 12 months"),
    ]

    fig = plt.figure(figsize=(10, 4.8))
    frame(fig, "YourSweep: who pays, when, and who stays",
          "Six numbers from the SQL analysis (synthetic data shaped like the App Store and Google Play exports)",
          sql_ref="03-05_*_clean.sql")
    cols, rows = 3, 2
    x0, y0, w, h, gap = 0.035, 0.12, (0.93 - 0.04) / 3, 0.30, 0.025
    for i, (big, small) in enumerate(tiles):
        c, rr = i % cols, i // cols
        x = x0 + c * (w + gap)
        y = y0 + (rows - 1 - rr) * (h + gap)
        fig.patches.append(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
            transform=fig.transFigure, facecolor="white", edgecolor=GRID, linewidth=1))
        fig.text(x + 0.025, y + h - 0.05, big, fontsize=30, weight="bold",
                 color=INK, va="top")
        fig.text(x + 0.025, y + 0.045, small, fontsize=10.5, color=INK2,
                 va="bottom", linespacing=1.35)
    save(fig, "00_summary.png")


# ===========================================================================
# 01  Funnel per store: trials and payers per 1,000 downloads
# ===========================================================================
def chart_funnel():
    f = q(f"""
        WITH {START},
        d AS (SELECT store, SUM(downloads) AS downloads FROM downloads, start
              WHERE date >= start_date GROUP BY store),
        t AS (SELECT store, SUM(quantity) AS trials FROM subscription_events, start
              WHERE event = 'free_trial_start' AND date >= start_date GROUP BY store),
        p AS (SELECT store, COUNT(*) AS payers FROM customers, start
              WHERE count_as_payer = 1 AND first_payment_date >= start_date GROUP BY store)
        SELECT d.store, start.start_date, d.downloads,
               COALESCE(t.trials, 0) AS trials, COALESCE(p.payers, 0) AS payers,
               1000.0 * COALESCE(t.trials, 0) / d.downloads AS trials_per_1000,
               1000.0 * COALESCE(p.payers, 0) / d.downloads AS payers_per_1000
        FROM d CROSS JOIN start
        LEFT JOIN t ON t.store = d.store
        LEFT JOIN p ON p.store = d.store
        ORDER BY d.store DESC
    """)
    a = f.set_index("store")
    ratio = a.loc["apple", "payers_per_1000"] / a.loc["google_play", "payers_per_1000"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True)
    margins(fig, top_in=1.35, bottom_in=0.75, left=0.17, right=0.95, wspace=0.12)
    frame(fig, f"Apple turns downloads into payers {ratio:.1f}x better than Google Play",
          f"Per 1,000 downloads, same period for both stores (from {nice_date(f.start_date[0])}).\n"
          "Apple has more payers than trials: most people pay straight away.",
          sql_ref="03_who_pays_and_when_clean.sql 1b")
    y = range(len(f))
    for ax, col, count, label in [
        (axes[0], "trials_per_1000", "trials", "Free trials started"),
        (axes[1], "payers_per_1000", "payers", "New paying customers"),
    ]:
        ax.barh(y, f[col], color=[STORE_COLOR[s] for s in f.store], height=0.55)
        for yi, (_, row) in zip(y, f.iterrows()):
            ax.text(row[col] + 0.8, yi, f"{row[col]:.1f}", va="center", fontsize=12,
                    weight="bold", color=INK)
            ax.text(row[col] + 0.8, yi - 0.3, f"{row[count]:.0f} of {row.downloads:,.0f} downloads",
                    va="top", fontsize=8.5, color=INK2)
        ax.set_title(label + " per 1,000 downloads", pad=10)
        style(ax, grid="x")
        ax.set_yticks(list(y))
        ax.set_yticklabels([STORE_NAME[s] for s in f.store] if ax is axes[0] else [])
        ax.set_ylim(-0.7, len(f) - 0.4)
    axes[0].tick_params(axis="y", labelsize=11)
    axes[0].set_xlim(0, max(f.trials_per_1000.max(), f.payers_per_1000.max()) * 1.35)
    save(fig, "01_funnel_per_store.png")


# ===========================================================================
# 02  The US: share of downloads -> trials -> payers
# ===========================================================================
def chart_us():
    s = q("""
        SELECT 'Downloads' AS step,
               100.0 * SUM(CASE WHEN country = 'US' THEN downloads ELSE 0 END) / SUM(downloads) AS us_pct
        FROM downloads
        UNION ALL
        SELECT 'Free trials',
               100.0 * SUM(CASE WHEN country = 'US' THEN quantity ELSE 0 END) / SUM(quantity)
        FROM subscription_events WHERE event = 'free_trial_start'
        UNION ALL
        SELECT 'Paying customers', 100.0 * SUM(country = 'US') / COUNT(*)
        FROM customers WHERE count_as_payer = 1
    """)
    tr = q("""
        WITH d AS (SELECT country = 'US' AS is_us, SUM(downloads) AS dl FROM downloads GROUP BY is_us),
             t AS (SELECT country = 'US' AS is_us, SUM(quantity) AS trials FROM subscription_events
                   WHERE event = 'free_trial_start' GROUP BY is_us)
        SELECT d.is_us, 100.0 * COALESCE(t.trials, 0) / d.dl AS trial_rate
        FROM d LEFT JOIN t USING (is_us)
    """).set_index("is_us")["trial_rate"]

    fig, ax = plt.subplots(figsize=(10, 4.4))
    margins(fig, top_in=1.45, bottom_in=0.7, left=0.17, right=0.95)
    dl, pay = s.us_pct.iloc[0], s.us_pct.iloc[-1]
    frame(fig, f"The US is {dl:.0f}% of downloads but {pay:.0f}% of paying customers",
          f"Share of each step that comes from the US, all dates. US downloads start a free trial "
          f"{tr[1]:.2f}% of the time,\nother countries {tr[0]:.2f}%: most non-US users leave before even trying.",
          sql_ref="03_who_pays_and_when_clean.sql 1e")
    y = list(range(len(s)))[::-1]
    ax.barh(y, s.us_pct, color=US, height=0.58, edgecolor=SURFACE, linewidth=2, label="United States")
    ax.barh(y, 100 - s.us_pct, left=s.us_pct, color=REST, height=0.58,
            edgecolor=SURFACE, linewidth=2, label="Rest of the world")
    for yi, v in zip(y, s.us_pct):
        ax.text(v - 1.5, yi, f"{v:.0f}%", ha="right", va="center", fontsize=12, weight="bold", color=INK)
        ax.text(v + 1.5, yi, f"{100 - v:.0f}%", ha="left", va="center", fontsize=10, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(s.step, fontsize=11)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    style(ax, grid=None)
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=9.5,
              handlelength=1, handleheight=1)
    save(fig, "02_us_share.png")


# ===========================================================================
# 03  Top download countries: who pays?
# ===========================================================================
def chart_countries():
    c = q("""
        WITH d AS (SELECT country, SUM(downloads) AS dl FROM downloads GROUP BY country),
             p AS (SELECT country, COUNT(*) AS payers FROM customers
                   WHERE count_as_payer = 1 GROUP BY country)
        SELECT d.country, d.dl, COALESCE(p.payers, 0) AS payers,
               (SELECT COUNT(*) FROM d) AS n_countries,
               (SELECT COUNT(*) FROM p) AS n_paying_countries
        FROM d LEFT JOIN p USING (country)
        ORDER BY d.dl DESC
        LIMIT 10
    """)
    zero = int((c.payers == 0).sum())
    fig, ax = plt.subplots(figsize=(10, 5.6))
    margins(fig, top_in=1.35, bottom_in=0.7, left=0.17, right=0.93)
    frame(fig, f"{zero} of the top 10 download countries have no paying customers yet",
          f"Downloads per country, all dates. Green = at least one payer. "
          f"Only {c.n_paying_countries[0]} of {c.n_countries[0]} countries have any payer.",
          sql_ref="03_who_pays_and_when_clean.sql 1e")
    y = list(range(len(c)))[::-1]
    ax.barh(y, c.dl, color=[US if p > 0 else REST for p in c.payers], height=0.62)
    for yi, (_, row) in zip(y, c.iterrows()):
        who = f"{row.payers} payer" + ("" if row.payers == 1 else "s")
        ax.text(row.dl + c.dl.max() * 0.01, yi, f"{row.dl:,}  ·  {who}", va="center",
                fontsize=9.5, color=INK if row.payers else INK2,
                weight="bold" if row.payers else "normal")
    ax.set_yticks(y)
    ax.set_yticklabels([COUNTRY.get(x, x) for x in c.country], fontsize=10.5)
    ax.set_xlim(0, c.dl.max() * 1.22)
    ax.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    style(ax, grid="x")
    save(fig, "03_countries.png")


# ===========================================================================
# 04  Timeline: downloads and new payers per month, with events
# ===========================================================================
def chart_timeline():
    months = q("SELECT DISTINCT substr(date, 1, 7) AS month FROM downloads ORDER BY month").month
    dl = (q("SELECT substr(date, 1, 7) AS month, store, SUM(downloads) AS n FROM downloads GROUP BY 1, 2")
          .pivot(index="month", columns="store", values="n").reindex(months).fillna(0))
    pay = (q("""SELECT substr(first_payment_date, 1, 7) AS month, store, COUNT(*) AS n
                FROM customers WHERE count_as_payer = 1 GROUP BY 1, 2""")
           .pivot(index="month", columns="store", values="n").reindex(months).fillna(0))
    events = q("""
        SELECT 'Official launch' AS label, substr(MIN(date), 1, 7) AS month
        FROM payments WHERE store = 'google_play'
        UNION ALL
        SELECT 'Apple launch', substr(MIN(date), 1, 7) FROM downloads WHERE store = 'apple'
        UNION ALL
        SELECT 'freesummer trials pay', substr(MIN(date), 1, 7) FROM payments WHERE offer = 'freesummer'
    """)
    stores = [s for s in ("apple", "google_play") if s in dl.columns]
    x = list(range(len(months)))

    fig, (top, bot) = plt.subplots(2, 1, figsize=(11, 6.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.32})
    margins(fig, top_in=1.3, bottom_in=0.95, left=0.075, right=0.98)
    frame(fig, "New payers arrive in bursts, right after a launch or an offer",
          "Downloads and new paying customers per month, by store. Between events, only a few new payers a month.",
          sql_ref="03_who_pays_and_when_clean.sql 2a, 2c")

    for ax, data, title in [(top, dl, "Downloads"), (bot, pay, "New paying customers")]:
        bottom = pd.Series(0.0, index=months)
        for s in stores:
            ax.bar(x, data[s].values, bottom=bottom.values, width=0.68, color=STORE_COLOR[s],
                   edgecolor=SURFACE, linewidth=1.5, label=STORE_NAME[s])
            bottom += data[s]
        style(ax)
        ax.set_title(title, pad=8)
        totals = data[stores].sum(axis=1)
        if ax is bot:
            for xi, v in zip(x, totals):
                if v > 0:
                    ax.text(xi, v + 0.15, f"{v:.0f}", ha="center", va="bottom", fontsize=9.5, color=INK)
            ax.set_ylim(0, totals.max() * 1.6)
            ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        else:
            peak = totals.idxmax()
            ax.text(x[list(months).index(peak)] + 0.45, totals.max() * 0.97,
                    f"{totals.max():,.0f}", ha="left", va="top", fontsize=9.5, color=INK)
            ax.set_ylim(0, totals.max() * 1.18)
            ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))

    # Events: a bold label above that month's payer bar (no lines across the bars)
    pay_totals = pay[stores].sum(axis=1)
    for _, e in events.iterrows():
        if e.month in list(months):
            xi = list(months).index(e.month)
            last = xi == len(months) - 1
            bot.text(xi + (0.35 if last else 0), pay_totals[e.month] + totals_pad(pay_totals), e.label,
                     ha="right" if last else "center", va="bottom", fontsize=9, color=INK2,
                     weight="bold")
    top.legend(loc="upper right", ncol=2, fontsize=9.5, handlelength=1, handleheight=1)
    bot.set_xticks(x)
    bot.set_xticklabels([month_label(m, first=(i == 0)) for i, m in enumerate(months)], fontsize=9)
    bot.set_xlim(-0.6, len(x) - 0.4)
    save(fig, "04_timeline.png")


# ===========================================================================
# 05  When Apple users cancel
# ===========================================================================
def chart_cancel_day():
    c = q("""
        SELECT days_before_canceling AS day, SUM(quantity) AS cancels
        FROM subscription_events
        WHERE event = 'cancel' AND days_before_canceling IS NOT NULL
        GROUP BY day ORDER BY day
    """)
    n0 = int(c.loc[c.day == 0, "cancels"].sum())
    n = int(c.cancels.sum())
    fig, ax = plt.subplots(figsize=(10, 4.4))
    margins(fig, top_in=1.35, bottom_in=0.85, left=0.06, right=0.97)
    frame(fig, f"{n0} of {n} Apple cancellations happen on day 0",
          "Days from subscription start to cancelling (Apple only, Google Play doesn't report it).\n"
          "People start, then switch off auto-renew straight away.",
          sql_ref="04_drop_off_clean.sql 3b")
    last_day = max(31, int(c.day.max()) + 1)
    ax.bar(c.day, c.cancels, width=0.8, color=[APPLE if d == 0 else REST for d in c.day])
    for _, row in c.iterrows():
        ax.text(row.day, row.cancels + 0.1, f"{row.cancels:.0f}", ha="center", va="bottom",
                fontsize=10, color=INK, weight="bold" if row.day == 0 else "normal")
    ax.set_xlim(-1, last_day)
    ax.set_ylim(0, c.cancels.max() * 1.25)
    ax.set_xticks([0, 7, 14, 21, 28])
    ax.set_xticklabels(["day 0", "day 7", "day 14", "day 21", "day 28"])
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_ylabel("cancellations")
    style(ax)
    save(fig, "05_cancel_day.png")


# ===========================================================================
# 06  Out of 100 monthly payers, how many are left?
# ===========================================================================
def chart_survivors():
    s = q(f"""
        WITH RECURSIVE {RETENTION},
        months(month_no, still_paying) AS (
            SELECT 1, 100.0
            UNION ALL
            SELECT month_no + 1, still_paying * (SELECT r FROM retention)
            FROM months WHERE month_no < 6
        )
        SELECT month_no, still_paying,
               (SELECT r FROM retention) AS r,
               (SELECT came_back FROM retention) AS came_back,
               (SELECT paid FROM retention) AS paid
        FROM months
    """)
    m4 = s.loc[s.month_no == 4, "still_paying"].iloc[0]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    margins(fig, top_in=1.35, bottom_in=0.8, left=0.07, right=0.97)
    frame(fig, f"By month 4, only {m4:.0f} of 100 monthly payers are still paying",
          f"Projection from {s.r[0] * 100:.0f}% monthly retention "
          f"({s.came_back[0]} of {s.paid[0]} monthly payments were followed by another the next month)",
          sql_ref="04_drop_off_clean.sql 3e")
    ax.fill_between(s.month_no, s.still_paying, color=APPLE, alpha=0.08, linewidth=0)
    ax.plot(s.month_no, s.still_paying, color=APPLE, linewidth=2, marker="o", markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2)
    for _, row in s.iterrows():
        ax.text(row.month_no, row.still_paying + 5, f"{row.still_paying:.0f}", ha="center",
                va="bottom", fontsize=11, weight="bold", color=INK)
    ax.set_xticks(s.month_no)
    ax.set_xticklabels([f"month {m}" for m in s.month_no])
    ax.set_ylim(0, 118)
    ax.set_xlim(0.7, s.month_no.max() + 0.3)
    ax.set_ylabel("still paying (of 100)")
    style(ax)
    save(fig, "06_monthly_survivors.png")


# ===========================================================================
# 07  12-month value: annual vs monthly
# ===========================================================================
def chart_value():
    v = q(f"""
        WITH RECURSIVE {RETENTION},
        months(month_no, still_paying) AS (
            SELECT 1, 1.0
            UNION ALL
            SELECT month_no + 1, still_paying * (SELECT r FROM retention)
            FROM months WHERE month_no < 12
        )
        SELECT month_no,
               SUM(still_paying * {MONTHLY_PRICE}) OVER (ORDER BY month_no) AS monthly_cum,
               {ANNUAL_PRICE} AS annual_cum,
               (SELECT r FROM retention) AS r
        FROM months
    """)
    m12 = v.monthly_cum.iloc[-1]
    x = ANNUAL_PRICE / m12
    fig, ax = plt.subplots(figsize=(10, 5))
    margins(fig, top_in=1.35, bottom_in=0.8, left=0.07, right=0.84)
    frame(fig, f"Over a year, an annual customer is worth {x:.1f}x a monthly one",
          f"Expected money from one customer, month by month, at list price "
          f"(${MONTHLY_PRICE}/month, ${ANNUAL_PRICE}/year)\nwith {v.r[0] * 100:.0f}% of monthly payers renewing each month",
          sql_ref="05_annual_clean.sql 4f")
    ax.fill_between(v.month_no, v.monthly_cum, v.annual_cum, color=ANNUAL, alpha=0.07, linewidth=0)
    ax.plot(v.month_no, v.annual_cum, color=ANNUAL, linewidth=2.2, drawstyle="steps-post")
    ax.plot(v.month_no, v.monthly_cum, color=MONTHLY, linewidth=2.2, marker="o", markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=1.5)
    end = v.month_no.max()
    ax.text(end + 0.3, ANNUAL_PRICE, f"${ANNUAL_PRICE:.2f}\nannual plan", va="center", fontsize=10.5,
            color=INK, weight="bold", linespacing=1.3)
    ax.text(end + 0.3, m12, f"${m12:.2f}\nmonthly plan", va="center", fontsize=10.5,
            color=INK2, weight="bold", linespacing=1.3)
    ax.text(end / 2 + 0.5, (ANNUAL_PRICE + m12) / 2, f"{x:.1f}x more", ha="center", va="center",
            fontsize=13, color=ANNUAL, weight="bold")
    ax.set_xticks(v.month_no)
    ax.set_xlim(1, end)
    ax.set_ylim(0, ANNUAL_PRICE * 1.15)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
    ax.set_xlabel("months since first payment")
    style(ax)
    save(fig, "07_annual_vs_monthly_value.png")


# ===========================================================================
# 08  Annual share per store
# ===========================================================================
def chart_annual_share():
    a = q("""
        SELECT store,
               SUM(first_plan = 'annual')  AS annual,
               SUM(first_plan = 'monthly') AS monthly,
               COUNT(*)                    AS payers,
               100.0 * SUM(first_plan = 'annual') / COUNT(*) AS annual_pct
        FROM customers WHERE count_as_payer = 1
        GROUP BY store ORDER BY store
    """).set_index("store")
    switched = q("""SELECT COUNT(*) AS n FROM (SELECT customer_id FROM clean_payments
                    GROUP BY customer_id HAVING COUNT(DISTINCT plan) > 1)""").n[0]
    fig, ax = plt.subplots(figsize=(10, 4))
    margins(fig, top_in=1.45, bottom_in=0.7, left=0.17, right=0.95)
    frame(fig, f"{a.annual_pct['apple']:.0f}% of Apple payers start on annual, "
               f"vs {a.annual_pct['google_play']:.0f}% on Google Play",
          ("First plan of each paying customer. "
           + ("Nobody" if switched == 0 else f"Only {switched}")
           + " switched plan later, so the first choice is the one that sticks."),
          sql_ref="05_annual_clean.sql 4a, 4d")
    stores = ["apple", "google_play"]
    y = [1, 0]
    ann = [a.annual_pct[s] for s in stores]
    ax.barh(y, ann, color=ANNUAL, height=0.55, edgecolor=SURFACE, linewidth=2, label="Annual plan")
    ax.barh(y, [100 - v for v in ann], left=ann, color=REST, height=0.55, edgecolor=SURFACE,
            linewidth=2, label="Monthly plan")
    for yi, s in zip(y, stores):
        p = a.annual_pct[s]
        if p >= 8:   # room inside the bar
            ax.text(p / 2, yi, f"{a.annual[s]} annual", ha="center", va="center", fontsize=10.5,
                    color="white", weight="bold")
        else:        # tiny bar: put the label just to its right
            ax.text(p + 1, yi, f"{a.annual[s]} annual", ha="left", va="center", fontsize=10.5,
                    color=INK, weight="bold")
        ax.text(p + (100 - p) / 2, yi, f"{a.monthly[s]} monthly", ha="center", va="center",
                fontsize=10.5, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{STORE_NAME[s]}\n{a.payers[s]} payers" for s in stores], fontsize=10.5)
    ax.set_xlim(0, 100)
    ax.set_xticks([])
    style(ax, grid=None)
    ax.spines["bottom"].set_visible(False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=9.5,
              handlelength=1, handleheight=1)
    save(fig, "08_annual_share_per_store.png")


# ===========================================================================
# 09  Money per payer so far
# ===========================================================================
def chart_proceeds():
    p = q("""
        SELECT first_plan, COUNT(*) AS payers,
               SUM(net_proceeds_usd) / COUNT(*) AS proceeds_per_payer
        FROM customers WHERE count_as_payer = 1
        GROUP BY first_plan ORDER BY proceeds_per_payer
    """).set_index("first_plan")
    x = p.proceeds_per_payer["annual"] / p.proceeds_per_payer["monthly"]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    margins(fig, top_in=1.35, bottom_in=0.7, left=0.17, right=0.92)
    frame(fig, f"So far, an annual payer has brought in {x:.1f}x the money of a monthly one",
          "Proceeds per paying customer after store fees, in US dollars, by first plan",
          sql_ref="05_annual_clean.sql 4e")
    plans = ["monthly", "annual"]
    ax.barh([0, 1], [p.proceeds_per_payer[k] for k in plans], height=0.55,
            color=[MONTHLY, ANNUAL])
    for yi, k in enumerate(plans):
        ax.text(p.proceeds_per_payer[k] + 0.8, yi, f"${p.proceeds_per_payer[k]:.2f}",
                va="center", fontsize=12, weight="bold", color=INK)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([f"{k.capitalize()} plan\n{p.payers[k]} payers" for k in plans], fontsize=10.5)
    ax.set_xlim(0, p.proceeds_per_payer.max() * 1.18)
    ax.xaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
    style(ax, grid="x")
    save(fig, "09_proceeds_per_payer.png")


# ===========================================================================
# 10  Google Play installs: downloads vs uninstalls
# ===========================================================================
def chart_play_installs():
    d = q("""
        SELECT month, downloads, uninstalls,
               SUM(downloads - uninstalls) OVER (ORDER BY month) AS still_installed
        FROM (SELECT substr(date, 1, 7) AS month, SUM(downloads) AS downloads,
                     SUM(uninstalls) AS uninstalls
              FROM downloads WHERE store = 'google_play' GROUP BY month)
        ORDER BY month
    """)
    peak = d.loc[d.downloads.idxmax()]
    peak_name = pd.to_datetime(peak.month + "-01").strftime("%B")
    pct = 100 * peak.uninstalls / peak.downloads
    x = list(range(len(d)))
    fig, (top, bot) = plt.subplots(2, 1, figsize=(11, 6.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.3})
    margins(fig, top_in=1.35, bottom_in=0.95, left=0.075, right=0.98)
    frame(fig, f"Google Play's {peak_name} spike didn't stick: {pct:.0f}% uninstalled the same month",
          "Google Play downloads (up) and uninstalls (down) per month, and how many are still installed.\n"
          "Apple's exports don't include uninstalls.",
          sql_ref="04_drop_off_clean.sql 3f")
    top.bar(x, d.downloads, width=0.68, color=PLAY, label="Downloads")
    top.bar(x, -d.uninstalls, width=0.68, color=REST, label="Uninstalls")
    top.axhline(0, color=AXIS, linewidth=0.8)
    i = int(d.downloads.idxmax())
    top.text(i + 0.45, peak.downloads, f"{peak.downloads:,} downloads", va="top", fontsize=9.5, color=INK)
    top.text(i + 0.45, -peak.uninstalls, f"{peak.uninstalls:,} uninstalls", va="bottom",
             fontsize=9.5, color=INK2)
    top.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{abs(v):,.0f}"))
    top.set_title("Downloads and uninstalls", pad=8)
    top.legend(loc="upper right", ncol=2, fontsize=9.5, handlelength=1, handleheight=1)
    style(top)
    top.spines["bottom"].set_visible(False)

    bot.plot(x, d.still_installed, color=PLAY, linewidth=2, marker="o", markersize=6,
             markeredgecolor=SURFACE, markeredgewidth=1.5)
    bot.fill_between(x, d.still_installed, color=PLAY, alpha=0.08, linewidth=0)
    bot.text(x[-1], d.still_installed.iloc[-1] + d.still_installed.max() * 0.08,
             f"{d.still_installed.iloc[-1]:,.0f}", ha="center", va="bottom", fontsize=10,
             weight="bold", color=INK)
    bot.set_title("Still installed (running total)", pad=8)
    bot.set_ylim(0, d.still_installed.max() * 1.3)
    bot.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    style(bot)
    bot.set_xticks(x)
    bot.set_xticklabels([month_label(m, first=(k == 0)) for k, m in enumerate(d.month)], fontsize=9)
    bot.set_xlim(-0.6, len(x) - 0.4)
    save(fig, "10_play_installs.png")


# ===========================================================================
if __name__ == "__main__":
    print(f"Database: {DB}")
    print(f"Figures:  {OUT}")
    for chart in (chart_summary, chart_funnel, chart_us, chart_countries, chart_timeline,
                  chart_cancel_day, chart_survivors, chart_value, chart_annual_share,
                  chart_proceeds, chart_play_installs):
        chart()
    conn.close()
    print("Done.")
