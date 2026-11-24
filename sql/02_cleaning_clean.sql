-- =====================================================================
-- 02_cleaning_clean.sql  |  Rule-based cleaning that still works in 5 years
-- Run (from the sql folder), every time new data is loaded:
--   python3 build_db.py
--   sqlite3 yoursweep.db < 02_cleaning_clean.sql
--
-- THE BIG RULE: write RULES, not lists.
--   Bad:  WHERE customer_id = 'A-SYN0012'   (1 person, today)
--   Good: WHERE type = 'refund'                      (1 or 1,000,000)
-- Habits:
--   * Never change raw tables. Build clean VIEWS on top of them.
--   * Never type a date or price you looked up by eye. Compute it.
--   * Cases a rule can't catch go in a small table (payer_exclusions):
--     you add rows, you don't edit code.
-- Each step: Problem / Rule / Why, then the query and a short Finding.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. Speed: indexes
-- ---------------------------------------------------------------------
-- Like the index in a book: SQLite jumps to a customer or date instead of
-- reading every row. No difference at 100 rows, huge at millions.
CREATE INDEX IF NOT EXISTS idx_payments_customer    ON payments (customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_store_date  ON payments (store, date);
CREATE INDEX IF NOT EXISTS idx_events_store_date    ON subscription_events (store, date);
CREATE INDEX IF NOT EXISTS idx_downloads_store_date ON downloads (store, date);


-- ---------------------------------------------------------------------
-- 1. Refunds
-- ---------------------------------------------------------------------
-- Problem: some people pay and then get their money back.
-- Rule:    any customer with at least one row where type = 'refund'.
-- Why:     they didn't end up paying, so they aren't real payers.
SELECT DISTINCT customer_id
FROM payments
WHERE type = 'refund';

-- Finding: 1 refunded customer (US, Apple, paid 4 Oct, refunded 6 Oct).


-- ---------------------------------------------------------------------
-- 2. Paid and cancelled the same day
-- ---------------------------------------------------------------------
-- Problem: some people pay and cancel straight away.
-- Catch:   subscription_events has NO customer_id, only counts per
--          store + date + country + plan. So we match on those columns.
-- Rule:    a first payment (payment_number = 1) with a 'cancel' event on the
--          same store, date, country and plan.
-- Why:     the closest match this data allows.
SELECT p.customer_id, p.store, p.date, p.country, p.plan
FROM payments p
JOIN subscription_events e
  ON  p.store   = e.store
  AND p.date    = e.date
  AND p.country = e.country
  AND p.plan    = e.plan
WHERE p.payment_number = 1
  AND e.event = 'cancel';

-- 2b. Check each match: was anyone ELSE in that store + country paying in
--     the 30 days before? If not, the cancel must be this person's.
--     (A correlated subquery: it re-runs once for every matched row.)
WITH matches AS (
  SELECT p.customer_id, p.store, p.date, p.country
  FROM payments p
  JOIN subscription_events e
    ON  p.store   = e.store
    AND p.date    = e.date
    AND p.country = e.country
    AND p.plan    = e.plan
  WHERE p.payment_number = 1
    AND e.event = 'cancel'
)
SELECT m.*,
       (SELECT COUNT(DISTINCT o.customer_id)
        FROM payments o
        WHERE o.store = m.store AND o.country = m.country
          AND o.customer_id <> m.customer_id
          AND o.date <  m.date
          AND o.date >= date(m.date, '-30 days')) AS others_paying_30d
FROM matches m
ORDER BY m.date;

-- Finding: 4 same-day cancels, all Google Play:
-- * GB, 9 Jan and 22 May 2026. Check 2b: 0 other GB Play payers in the
--   30 days before, so the cancel must be theirs.
-- * US, 20 Mar and 29 Jun 2026. Check 2b: 9 and 6 other US Play payers,
--   so the match is likely but not certain.
-- Limitation: on a busy day (500 US payments, 3 cancels) this JOIN would
--   flag all 500, and the 30-day check would always find others. The rule
--   only works while data is small. Real fix: store notifications with a
--   user id.


-- ---------------------------------------------------------------------
-- 3. Exceptions table (for anything a rule can't catch)
-- ---------------------------------------------------------------------
-- Add a row when you find a case by hand. The code never changes.
CREATE TABLE IF NOT EXISTS payer_exclusions (
  customer_id TEXT PRIMARY KEY,
  reason      TEXT,
  added_on    TEXT
);
-- Example (not run):
-- INSERT OR IGNORE INTO payer_exclusions VALUES ('<id>', '<why>', '2026-11-17');

-- Finding: empty for now. Rules 1 and 2 catch every case found so far.


-- ---------------------------------------------------------------------
-- 4. Prices: compare in USD and flag unusual ones
-- ---------------------------------------------------------------------
-- Problem: many currencies and local prices (monthly $8.99-$11.42,
--          annual $49.99-$114.29).
-- Rule:    use price_usd_approx. 'unusual' = more than 30% below or above
--          the list price ($8.99 monthly, $89.99 annual).
-- Why:     spot old prices or errors without deleting anything.
SELECT store, date, country, plan, price_usd_approx,
       CASE
         WHEN plan = 'annual'  AND price_usd_approx < 89.99 * 0.7 THEN 'unusual'
         WHEN plan = 'annual'  AND price_usd_approx > 89.99 * 1.3 THEN 'unusual'
         WHEN plan = 'monthly' AND price_usd_approx < 8.99 * 0.7  THEN 'unusual'
         WHEN plan = 'monthly' AND price_usd_approx > 8.99 * 1.3  THEN 'unusual'
         ELSE 'normal'
       END AS price_flag
FROM payments
WHERE type = 'payment'
ORDER BY price_flag DESC, plan, price_usd_approx;

-- Prices per currency and plan (to see where differences come from):
SELECT currency, plan, price_usd_approx, COUNT(*) AS n_payments
FROM payments
WHERE type = 'payment'
GROUP BY currency, plan, price_usd_approx
ORDER BY plan, n_payments DESC;

-- Finding: 1 of 120 payments is 'unusual': the $49.99 Play annual (US, Feb
--   2026), an old price. The rest are within 30%. Differences come from
--   local prices and currency (e.g. GBP 8.99 = $11.42).
-- Decision: flag, don't remove. Prices changed at some point, so unusual
--   = old price, not an error. 8.99 / 89.99 stay as typed list prices
--   (a price_history table would be the long-term fix).


-- ---------------------------------------------------------------------
-- 5. Fair comparison start date: compute, don't type
-- ---------------------------------------------------------------------
-- Problem: Apple data starts later than Play.
-- Rule:    start date = the LATEST of the stores' first payment dates.
-- Why:     it updates itself when new stores or data arrive.
WITH first_dates AS (
  SELECT store, MIN(date) AS first_date
  FROM payments
  GROUP BY store
)
SELECT MAX(first_date) AS fair_comparison_start_date
FROM first_dates;

-- Finding: 2026-05-27. Use this for any Apple vs Play comparison.


-- ---------------------------------------------------------------------
-- 6. Clean views: the rules put together
-- ---------------------------------------------------------------------
-- Views re-run every time you query them, so they're always up to date.

-- 6a. clean_payments: real payments only, with the price flag.
DROP VIEW IF EXISTS clean_payments;
CREATE VIEW clean_payments AS
SELECT store, date, customer_id, plan, type, payment_number,
       came_from_trial, offer, country, price_usd_approx,
       proceeds_usd_approx,
       CASE
         WHEN plan = 'annual'  AND price_usd_approx < 89.99 * 0.7 THEN 'unusual'
         WHEN plan = 'annual'  AND price_usd_approx > 89.99 * 1.3 THEN 'unusual'
         WHEN plan = 'monthly' AND price_usd_approx < 8.99 * 0.7  THEN 'unusual'
         WHEN plan = 'monthly' AND price_usd_approx > 8.99 * 1.3  THEN 'unusual'
         ELSE 'normal'
       END AS price_flag
FROM payments
WHERE type = 'payment';

-- 6b. customers: one row per customer, built from payments.
--   * MAX(CASE WHEN payment_number = 1 THEN x END) picks x from the FIRST
--     payment (MAX just squashes the group to one value).
--   * SUM(price_usd_approx) is already net: refund rows are negative.
--   * count_as_payer = 0 if rule 1 (refund) OR rule 2 (same-day cancel)
--     OR listed in payer_exclusions. Otherwise 1.
DROP VIEW IF EXISTS customers;
CREATE VIEW customers AS
SELECT
  customer_id,
  store,
  MAX(country)                                               AS country,
  SUM(CASE WHEN type = 'payment' THEN 1 ELSE 0 END)          AS payments,
  MIN(CASE WHEN type = 'payment' THEN date END)              AS first_payment_date,
  MAX(CASE WHEN type = 'payment' THEN date END)              AS last_payment_date,
  MAX(CASE WHEN payment_number = 1 THEN plan END)            AS first_plan,
  MAX(CASE WHEN payment_number = 1 THEN came_from_trial END) AS came_from_trial,
  MAX(CASE WHEN payment_number = 1 THEN offer END)           AS first_offer,
  MAX(CASE WHEN type = 'refund' THEN 1 ELSE 0 END)           AS refunded,
  ROUND(SUM(price_usd_approx), 2)                            AS net_paid_usd,
  ROUND(SUM(proceeds_usd_approx), 2)                         AS net_proceeds_usd,
  CASE
    WHEN MAX(CASE WHEN type = 'refund' THEN 1 ELSE 0 END) = 1
      OR customer_id IN (
           SELECT p.customer_id
           FROM payments p
           JOIN subscription_events e
             ON  p.store   = e.store
             AND p.date    = e.date
             AND p.country = e.country
             AND p.plan    = e.plan
           WHERE p.payment_number = 1
             AND e.event = 'cancel')
      OR customer_id IN (SELECT customer_id FROM payer_exclusions)
    THEN 0 ELSE 1
  END                                                        AS count_as_payer
FROM payments
GROUP BY customer_id, store;


-- ---------------------------------------------------------------------
-- 7. Checks (rerun after every data load)
-- ---------------------------------------------------------------------

-- 7a. Raw vs clean rows: the difference should be refund rows only.
SELECT (SELECT COUNT(*) FROM payments)                         AS raw_rows,
       (SELECT COUNT(*) FROM clean_payments)                   AS clean_rows,
       (SELECT COUNT(*) FROM payments WHERE type = 'refund')   AS refund_rows;

-- 7b. How many customers are excluded, and why?
SELECT count_as_payer, refunded, COUNT(*) AS customers
FROM customers
GROUP BY count_as_payer, refunded;

-- 7c. Does every customer have a first payment date?
SELECT COUNT(*) AS missing_first_payment_date
FROM customers
WHERE first_payment_date IS NULL;

-- 7d. Price flags in the clean view.
SELECT price_flag, COUNT(*) AS payments
FROM clean_payments
GROUP BY price_flag;

-- Finding:
-- * 7a: 121 raw rows, 120 clean, 1 refund row. Difference = refunds only.
-- * 7b: 78 customers, 73 real payers, 5 excluded:
--     1 Apple refund                   -> rule 1
--     4 Play same-day cancels          -> rule 2 (checked in 2b)
-- * 7c: 0 missing, every customer has a first payment date.
-- * 7d: 119 normal, 1 unusual (old $49.99 annual, kept).


-- ---------------------------------------------------------------------
-- When the data gets really big (note for future you)
-- ---------------------------------------------------------------------
-- Views re-run their query each time. At millions of rows, save the slow
-- ones as tables once per data load:
--   DROP TABLE IF EXISTS customers_t;
--   CREATE TABLE customers_t AS SELECT * FROM customers;
-- Later, move to Postgres or BigQuery: most of this SQL works unchanged.
