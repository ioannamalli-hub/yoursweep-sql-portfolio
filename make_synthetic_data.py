"""Makes a SYNTHETIC YourSweep dataset (1 Jan - 31 Oct 2026) for the public portfolio.

Nothing here reads the real store exports. Every row is drawn at random from
rough, rounded patterns (US-heavy payers, Apple launch in late May, a Play
download spike in January, a free-trial offer from late June, many day-0
cancels, more annual plans on Apple). The volumes are about 3x the real ones,
so no number in the output matches YoursGlobal's real figures.

Same columns as the real combined CSVs, so build_db.py and the SQL run unchanged.
Run:  python3 make_synthetic_data.py      (writes the CSVs to ./data)
"""
import csv, os, random
from collections import defaultdict
from datetime import date, timedelta

random.seed(2026)                      # same seed = same data every run
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
START, END = date(2026, 1, 1), date(2026, 10, 31)
APPLE_LAUNCH = date(2026, 5, 26)
OFFER_START = date(2026, 6, 26)        # Play free-trial offer 'freesummer'
SCALE = 3                              # synthetic volume vs a small real app


def poisson(lam):
    """Random whole number with average lam (numpy-free)."""
    n, p, limit = 0, 1.0, 2.718281828 ** -lam
    while True:
        p *= random.random()
        if p < limit:
            return n
        n += 1


def days(a, b):
    return [a + timedelta(d) for d in range((b - a).days + 1)]


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, 28))


def pick(weights):
    return random.choices(list(weights), list(weights.values()))[0]


# ---------------------------------------------------------------------------
# Downloads: who downloads, and how many per month
# ---------------------------------------------------------------------------
DL_COUNTRY = {"US": 26, "IN": 8, "BR": 4.5, "RU": 3.5, "MX": 3, "GB": 3, "ID": 2.5,
              "CA": 2.5, "IR": 2, "AU": 2, "TH": 2, "ZA": 2, "DE": 1.5, "FR": 1.5,
              "PH": 1.5, "PK": 1.5, "NG": 1.5, "EG": 1.2, "TR": 1.2, "VN": 1.2,
              "IT": 1, "ES": 1, "UA": 1, "PL": 1, "JP": 1, "KR": 0.8, "TW": 0.8,
              "SE": 0.8, "EE": 0.6, "NL": 0.8, "AR": 0.8, "CO": 0.8, "BD": 0.8,
              "MY": 0.8, "SA": 0.8, "AE": 0.8, "GR": 0.6, "PT": 0.6, "CL": 0.6,
              "PE": 0.6, "KE": 0.6, "ZZ": 0.5}
for c in ("AT BE CH CZ DK FI HU IE IL NO NZ RO SG SK BG HR RS LT LV SI DZ MA TN GH "
          "ET UG TZ CM SN CI LK NP MM KH LA UZ KZ GE AM AZ BY MD JO LB IQ KW QA OM "
          "BH YE EC VE BO PY UY CR PA GT HN SV DO JM").split():
    DL_COUNTRY[c] = round(random.uniform(0.1, 0.5), 2)

# rough downloads per month (before SCALE); January has a launch spike on Play
PLAY_DL = {1: 900, 2: 70, 3: 25, 4: 15, 5: 20, 6: 35, 7: 30, 8: 30, 9: 90, 10: 300}
APPLE_DL = {5: 25, 6: 50, 7: 40, 8: 45, 9: 35, 10: 40}

downloads = []
for store, per_month in (("google_play", PLAY_DL), ("apple", APPLE_DL)):
    for d in days(START, END):
        if store == "apple" and d < APPLE_LAUNCH:
            continue
        month_days = [x for x in days(date(2026, d.month, 1), add_months(date(2026, d.month, 1), 1) - timedelta(1))
                      if store == "google_play" or x >= APPLE_LAUNCH]
        lam = per_month.get(d.month, 0) * SCALE / len(month_days)
        if store == "google_play" and d.month == 1:       # 85% of January in one week
            lam = per_month[1] * SCALE * (0.85 / 8 if 4 <= d.day <= 11 else 0.15 / 23)
        per_country = defaultdict(int)
        for _ in range(poisson(lam)):
            per_country[pick(DL_COUNTRY)] += 1
        for c, n in sorted(per_country.items()):
            if store == "apple":
                downloads.append([store, d, c, n, sum(random.random() < 0.08 for _ in range(n)),
                                  poisson(0.3), ""])
            else:
                unins = sum(random.random() < 0.6 for _ in range(n)) + poisson(0.3)
                downloads.append([store, d, c, n, "", poisson(n * 0.3), unins])

# ---------------------------------------------------------------------------
# Customers: when they start, where from, which plan, how long they stay
# ---------------------------------------------------------------------------
PAY_COUNTRY = {"US": 72, "GB": 6, "CA": 4, "DE": 3, "SE": 3, "EE": 3, "TW": 3, "AU": 3, "FR": 3}
# country: (currency, monthly price, annual price, usd rate, VAT share in price)
PRICES = {"US": ("USD", 8.99, 89.99, 1.0, 0), "GB": ("GBP", 8.99, 89.99, 1.27, 0.20),
          "CA": ("CAD", 11.99, 119.99, 0.73, 0), "DE": ("EUR", 9.99, 99.99, 1.08, 0.19),
          "FR": ("EUR", 9.99, 99.99, 1.08, 0.20), "EE": ("EUR", 9.99, 99.99, 1.08, 0.22),
          "SE": ("SEK", 119.0, 1190.0, 0.095, 0.25), "TW": ("TWD", 300.0, 2990.0, 0.031, 0.05),
          "AU": ("AUD", 14.99, 149.99, 0.66, 0.10)}
STORE_CUT = {"apple": 0.30, "google_play": 0.15}
RENEW = {"apple": 0.35, "google_play": 0.60}        # chance of paying again next month

# average new subscriptions per month (before SCALE)
PAID_STARTS = {"google_play": {1: 4, 2: 1, 3: 0.3, 4: 0.3, 5: 1, 6: 1, 7: 0.5, 8: 0.3, 9: 0.5, 10: 1},
               "apple": {5: 1, 6: 3, 7: 3, 8: 0.5, 9: 0.5, 10: 3}}
TRIALS = {("google_play", "freesummer", "monthly", 7, 0.5): {6: 0.5, 7: 0.5, 8: 0.3, 9: 2, 10: 4},
          ("apple", "One Month", "monthly", 7, 0.2): {6: 3, 7: 1, 8: 2},
          ("apple", "Evacode", "annual", 14, 0.5): {10: 2}}


def random_day(store, month, first=None):
    lo = date(2026, month, 1)
    hi = add_months(lo, 1) - timedelta(1)
    if store == "apple":
        lo = max(lo, APPLE_LAUNCH)
    if first:
        lo = max(lo, first)
    return random.choice(days(lo, min(hi, END)))


customers = []          # one dict per person who started something
for store, per_month in PAID_STARTS.items():
    for month, lam in per_month.items():
        for _ in range(poisson(lam * SCALE)):
            annual_share = 0.5 if store == "apple" else 0.12
            customers.append(dict(store=store, start=random_day(store, month), offer="", trial_days=0,
                                  converts=True, plan="annual" if random.random() < annual_share else "monthly"))
for (store, offer, plan, length, convert), per_month in TRIALS.items():
    for month, lam in per_month.items():
        first = OFFER_START if offer == "freesummer" else (date(2026, 10, 18) if offer == "Evacode" else None)
        for _ in range(poisson(lam * SCALE)):
            customers.append(dict(store=store, start=random_day(store, month, first), offer=offer,
                                  trial_days=length, converts=random.random() < convert, plan=plan))
# one Play annual on the old $49.99 price (02_cleaning flags it as 'unusual')
customers.append(dict(store="google_play", start=date(2026, 2, 17), offer="", trial_days=0,
                      converts=True, plan="annual"))
customers.sort(key=lambda c: c["start"])

payments, events = [], []
same_day = set()        # positions of the planted "paid and cancelled the same day" rows
active = []             # (store, plan, offer, country, from, to, trial_until)
n = {"apple": 0, "google_play": 0}
for c in customers:
    store, plan, country = c["store"], c["plan"], pick(PAY_COUNTRY)
    cur, m_price, a_price, rate, vat = PRICES[country]
    price = a_price if plan == "annual" else m_price
    if store == "google_play" and plan == "annual" and c["start"] < date(2026, 3, 1):
        cur, price, rate, vat = "USD", 49.99, 1.0, 0        # old Play annual price
        country = "US"
    proceeds = round(price * (1 - vat) * (1 - STORE_CUT[store]), 2)
    n[store] += 1
    cid = ("A-SYN" if store == "apple" else "G-SYN") + f"{n[store]:04d}"
    order = "" if store == "apple" else f"SYN-{n[store]:04d}"
    product = "One Year of Pro" if plan == "annual" else "One Month of Pro"
    offer_type = "Free Trial" if store == "apple" and c["offer"] else ""

    def event(d, ev, periods="", days_before="", reason="", name=""):
        if d <= END:
            events.append([store, d, ev, plan, c["offer"], offer_type, country, 1,
                           periods if store == "apple" else "", c["start"] if store == "apple" else "",
                           days_before if store == "apple" else "", reason if store == "apple" else "", name])

    # free trial first?
    first_pay = c["start"]
    if c["trial_days"]:
        event(c["start"], "free_trial_start", 1, name="Start Offer Code" if store == "apple" else "New Subscriptions")
        first_pay = c["start"] + timedelta(c["trial_days"])
        if not c["converts"] or first_pay > END:
            if c["converts"] is False:
                event(first_pay, "cancel", 1, random.choice([0, 0, 0, 0, 2]), "Canceled",
                      "Cancel" if store == "apple" else "Cancelled Subscriptions")
            active.append((store, plan, c["offer"], country, c["start"], min(first_pay, END), first_pay))
            continue
        if store == "apple":            # Play doesn't report trial conversions
            event(first_pay, "trial_converted_to_paid", 2, name="Paid Subscription from Offer Code")
    else:
        event(first_pay, "new_paid_subscription", 1, name="Subscribe" if store == "apple" else "New Subscriptions")

    # how many payments, and how it ends
    refund = store == "apple" and plan == "monthly" and random.random() < 0.08
    same_day_cancel = store == "google_play" and plan == "monthly" and not c["trial_days"] and random.random() < 0.12
    pay_dates = [first_pay]
    if plan == "monthly" and not refund and not same_day_cancel:
        while add_months(pay_dates[-1], 1) <= END and random.random() < RENEW[store]:
            pay_dates.append(add_months(pay_dates[-1], 1))
    trial_flag = "yes" if c["trial_days"] else "no"
    for i, d in enumerate(pay_dates, start=1):
        payments.append([store, d, cid, plan, product, "payment", i, trial_flag,
                         c["offer"] if store == "google_play" else "", country, cur, price, proceeds,
                         round(price * rate, 2), round(proceeds * rate, 2), order])
        if i > 1 and store == "apple":  # Play renewals are only in payments
            event(d, "renewal", i, name="Renew")
    period_end = add_months(pay_dates[-1], 12 if plan == "annual" else 1)
    if refund:
        r = first_pay + timedelta(random.randint(2, 6))
        payments.append([store, r, cid, plan, product, "refund", "", trial_flag, "", country, cur,
                         -price, -proceeds, -round(price * rate, 2), -round(proceeds * rate, 2), order])
        event(r, "refund", 1, reason="Canceled", name="Refund")
        period_end = r
    elif same_day_cancel:
        event(first_pay, "cancel", name="Cancelled Subscriptions")
        same_day.add(len(events) - 1)
    elif plan == "monthly":
        day0 = random.random() < 0.75
        event(period_end, "cancel", len(pay_dates), 0 if day0 else random.randint(1, 29), "Canceled",
              "Cancel" if store == "apple" else "Cancelled Subscriptions")
    trial_until = first_pay if c["trial_days"] else c["start"]
    active.append((store, plan, c["offer"], country, c["start"], min(period_end, END), trial_until))

# Other cancels must not land by chance on someone's first-payment day
# (store + date + country + plan), or 02_cleaning's same-day rule would
# wrongly drop that payer. Move such a cancel one day later.
first_pay_keys = {(p[0], p[1], p[9], p[3]) for p in payments if p[6] == 1}
for i, e in enumerate(events):
    while e[2] == "cancel" and i not in same_day and (e[0], e[1], e[6], e[3]) in first_pay_keys:
        e[1] += timedelta(1)
events = [e for e in events if e[1] <= END]

# Play only reports daily counts: add up rows that only differ in quantity
grouped = defaultdict(int)
for e in events:
    grouped[tuple(e[:7] + e[8:])] += 1
events = [list(k[:7]) + [q] + list(k[7:]) for k, q in grouped.items()]
events.sort(key=lambda e: (e[1], e[0], e[2]))
payments.sort(key=lambda p: (p[1], p[0], p[2]))

# ---------------------------------------------------------------------------
# Active subscriptions per day
# ---------------------------------------------------------------------------
act = defaultdict(lambda: [0, 0, 0])
for store, plan, offer, country, a, b, trial_until in active:
    for d in days(a, b - timedelta(1) if b > a else a):
        row = act[(store, d, plan, offer, country)]
        row[0] += 1
        row[1 if d >= trial_until else 2] += 1
active_rows = [[s, d, p, o, c, t] + ([paid, tr] if s == "apple" else ["", ""])
               for (s, d, p, o, c), (t, paid, tr) in sorted(act.items(), key=lambda x: (x[0][0], x[0][1]))]

# ---------------------------------------------------------------------------
# Reviews (made-up wording, Google Play only)
# ---------------------------------------------------------------------------
REVIEWS = [(5, "Great for checking a hotel room in a new city.", "Thank you! Safe travels."),
           (5, "", ""), (4, "Does what it says. Would like more languages.", "Thanks, more languages are coming."),
           (5, "", ""), (3, "Useful but the scan took a while on my phone.", "Thanks, we're working on speed."),
           (5, "Peace of mind when I travel for work.", "Thank you for the kind words!"),
           (1, "", ""), (4, "", ""), (5, "Simple and clear.", "Thanks for the review!"),
           (2, "Wish there was a longer free trial.", "Thanks for the feedback, we hear you."),
           (5, "", ""), (4, "Good app, a bit pricey monthly.", "Thanks! The yearly plan saves money.")]
reviews = []
for stars, text, reply in REVIEWS:
    d = random.choice(days(START, END))
    reviews.append(["google_play", d, stars, "en", random.choice(["", "1.0.2", "1.1.0", "1.2.1"]), "", text, reply])
reviews.sort(key=lambda r: r[1])

# ---------------------------------------------------------------------------
# Write the CSVs
# ---------------------------------------------------------------------------
FILES = {
    "payments": ("store,date,customer_id,plan,product,type,payment_number,came_from_trial,offer,"
                 "country,currency,price,proceeds,price_usd_approx,proceeds_usd_approx,order_id", payments),
    "subscription_events": ("store,date,event,plan,offer,offer_type,country,quantity,paid_periods_so_far,"
                            "original_start_date,days_before_canceling,cancellation_reason,original_event_name", events),
    "active_subscriptions": ("store,date,plan,offer,country,active_total,active_paid,active_free_trial", active_rows),
    "downloads": ("store,date,country,downloads,redownloads,updates,uninstalls",
                  sorted(downloads, key=lambda r: (r[1], r[0], r[2]))),
    "reviews": ("store,date,stars,language,app_version,title,text,developer_reply", reviews),
}
os.makedirs(OUT, exist_ok=True)
for name, (header, rows) in FILES.items():
    with open(os.path.join(OUT, name + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header.split(","))
        w.writerows(rows)
    print(f"{name}.csv: {len(rows)} rows")
