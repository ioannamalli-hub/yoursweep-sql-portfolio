"""Builds yoursweep.db (SQLite) from the CSVs in ../data. Run (from the sql folder): python3 build_db.py

Every column has a declared type, so PRAGMA table_info(<table>) shows it:
  INTEGER = whole numbers (counts, stars, payment_number)
  REAL    = numbers with decimals (prices, proceeds)
  TEXT    = words, ids and dates. Dates are TEXT in 'YYYY-MM-DD' form,
            which sorts correctly and works with date(), julianday(), strftime().
Empty CSV cells become NULL.
"""
import csv, sqlite3, sys, os

here = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "data")
db_path = os.path.join(here, "yoursweep.db")

SCHEMA = {
    "payments": {
        "store": "TEXT", "date": "TEXT", "customer_id": "TEXT", "plan": "TEXT",
        "product": "TEXT", "type": "TEXT", "payment_number": "INTEGER",
        "came_from_trial": "TEXT", "offer": "TEXT", "country": "TEXT",
        "currency": "TEXT", "price": "REAL", "proceeds": "REAL",
        "price_usd_approx": "REAL", "proceeds_usd_approx": "REAL", "order_id": "TEXT",
    },
    "subscription_events": {
        "store": "TEXT", "date": "TEXT", "event": "TEXT", "plan": "TEXT",
        "offer": "TEXT", "offer_type": "TEXT", "country": "TEXT",
        "quantity": "INTEGER", "paid_periods_so_far": "INTEGER",
        "original_start_date": "TEXT", "days_before_canceling": "INTEGER",
        "cancellation_reason": "TEXT", "original_event_name": "TEXT",
    },
    "active_subscriptions": {
        "store": "TEXT", "date": "TEXT", "plan": "TEXT", "offer": "TEXT",
        "country": "TEXT", "active_total": "INTEGER", "active_paid": "INTEGER",
        "active_free_trial": "INTEGER",
    },
    "downloads": {
        "store": "TEXT", "date": "TEXT", "country": "TEXT", "downloads": "INTEGER",
        "redownloads": "INTEGER", "updates": "INTEGER", "uninstalls": "INTEGER",
    },
    "reviews": {
        "store": "TEXT", "date": "TEXT", "stars": "INTEGER", "language": "TEXT",
        "app_version": "TEXT", "title": "TEXT", "text": "TEXT", "developer_reply": "TEXT",
    },
}
CAST = {"INTEGER": int, "REAL": float, "TEXT": str}

if os.path.exists(db_path):
    os.remove(db_path)
db = sqlite3.connect(db_path)

for name, types in SCHEMA.items():
    with open(os.path.join(src, name + ".csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    cols = rows[0]
    missing = [c for c in cols if c not in types]
    if missing:
        sys.exit(f"{name}: new column(s) {missing} in the CSV. Add them to SCHEMA first.")
    db.execute(f"CREATE TABLE {name} ({', '.join(f'{c} {types[c]}' for c in cols)})")
    casts = [CAST[types[c]] for c in cols]
    db.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})",
                   [[None if v == "" else cast(v) for cast, v in zip(casts, r)] for r in rows[1:]])

# Only raw tables are loaded here. The clean_payments and customers views and
# the payer_exclusions table are built by you in
# 02_cleaning_clean.sql, so run that file after every rebuild:
#   sqlite3 yoursweep.db < 02_cleaning_clean.sql
db.commit()
for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
    print(t, db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
