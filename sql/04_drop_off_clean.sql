-- =====================================================================
-- 04_drop_off_clean.sql  |  Q3. Why and when do people drop off?
-- Two kinds of drop-off:
--   (a) trial users who never pay
--   (b) payers who cancel or don't renew
-- Big-data rule: no typed-in IDs or dates. Use clean_payments and
-- customers (WHERE count_as_payer = 1), and compute any cut-off date.
-- Run (from the sql folder, after 02_cleaning_clean.sql):
--   sqlite3 -header -column yoursweep.db < 04_drop_off_clean.sql
-- =====================================================================


-- ---------------------------------------------------------------------
-- (a) Trial users who never pay
-- ---------------------------------------------------------------------

-- 3a. Trials started vs converted to paid, per store.
--     SUM(quantity), not COUNT(*): one event row can hold several people.
SELECT store,
       SUM(CASE WHEN event = 'free_trial_start'        THEN quantity ELSE 0 END) AS trials_started,
       SUM(CASE WHEN event = 'trial_converted_to_paid' THEN quantity ELSE 0 END) AS trials_converted
FROM subscription_events
GROUP BY store;

-- Finding:
--   apple: 20 trials started, 3 converted
--   play:  24 trials started, 0 converted
-- * Most trial users don't pay.
-- * Play doesn't report trial conversions as an event, yet 10 Play payers
--   came from a trial (03, 1c). So Play's "0" means "not reported", and
--   the real conversion is about 13 of 44 trials.


-- ---------------------------------------------------------------------
-- (b) Payers who cancel or don't renew
-- ---------------------------------------------------------------------

-- 3b. How many cancels, and after how many days?
SELECT store,
       SUM(quantity)                AS cancels,
       COUNT(days_before_canceling) AS rows_with_days
FROM subscription_events
WHERE event = 'cancel'
GROUP BY store;

SELECT days_before_canceling, COUNT(*) AS cancels
FROM subscription_events
WHERE event = 'cancel' AND days_before_canceling IS NOT NULL
GROUP BY days_before_canceling
ORDER BY days_before_canceling;

-- Finding:
-- * 67 cancels: 21 Apple, 46 Play.
-- * Only Apple reports days_before_canceling (Play leaves it blank).
-- * Apple: 19 of 20 cancel rows are day 0 (20 of 21 people, since one row
--   holds 2), 1 on day 8. People switch off auto-renew right after starting.
-- Limitation: 20 rows, Apple only.


-- 3c. What cancellation reasons are given?
SELECT store, COALESCE(cancellation_reason, '(blank)') AS reason,
       SUM(quantity) AS cancels
FROM subscription_events
WHERE event = 'cancel'
GROUP BY store, cancellation_reason;

-- Finding: no useful reasons. Apple only says 'Canceled' (21), Play leaves
--   it blank (46). The exports don't tell us WHY people leave.


-- 3d. How many payers renewed at least once?
SELECT store,
       COUNT(*)                                       AS payers,
       SUM(CASE WHEN payments > 1 THEN 1 ELSE 0 END)  AS renewed,
       ROUND(SUM(CASE WHEN payments > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS renewed_pct
FROM customers
WHERE count_as_payer = 1
GROUP BY store
UNION ALL
SELECT 'all', COUNT(*),
       SUM(CASE WHEN payments > 1 THEN 1 ELSE 0 END),
       ROUND(SUM(CASE WHEN payments > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
FROM customers
WHERE count_as_payer = 1;

-- Finding: 20 of 73 payers (27.4%) renewed at least once: Apple 5 of 33
--   (15.2%), Play 15 of 40 (37.5%).
-- Limitation: annual payers (16 Apple, 1 Play) can't have renewed yet, since
--   the data covers less than a year. Apple data is also only ~5 months old.


-- 3e. Monthly retention: of the people who paid for monthly in month X,
--     how many paid again in month X+1?
--     Self-JOIN: a = this month's payment, b = the same person next month.
--     The last month is left out (computed), because its "next month" isn't
--     in the data yet.
WITH last AS (
    SELECT MAX(substr(date, 1, 7)) AS last_month
    FROM clean_payments
)
SELECT substr(a.date, 1, 7)          AS month,
       COUNT(DISTINCT a.customer_id) AS paid_this_month,
       COUNT(DISTINCT b.customer_id) AS paid_next_month,
       ROUND(100.0 * COUNT(DISTINCT b.customer_id) / COUNT(DISTINCT a.customer_id), 0) AS retained_pct
FROM clean_payments a
LEFT JOIN clean_payments b
  ON  b.customer_id = a.customer_id
  AND substr(b.date, 1, 7) = strftime('%Y-%m', date(a.date, '+1 month'))
CROSS JOIN last
WHERE a.plan = 'monthly'
  AND substr(a.date, 1, 7) < last.last_month
GROUP BY month
ORDER BY month;

-- Overall and per store (same logic, summed up).
WITH last AS (
    SELECT MAX(substr(date, 1, 7)) AS last_month
    FROM clean_payments
),
monthly AS (
    SELECT a.store,
           substr(a.date, 1, 7)          AS month,
           COUNT(DISTINCT a.customer_id) AS paid_this_month,
           COUNT(DISTINCT b.customer_id) AS paid_next_month
    FROM clean_payments a
    LEFT JOIN clean_payments b
      ON  b.customer_id = a.customer_id
      AND substr(b.date, 1, 7) = strftime('%Y-%m', date(a.date, '+1 month'))
    CROSS JOIN last
    WHERE a.plan = 'monthly'
      AND substr(a.date, 1, 7) < last.last_month
    GROUP BY a.store, month
)
SELECT store,
       SUM(paid_this_month) AS total_paid,
       SUM(paid_next_month) AS came_back,
       ROUND(100.0 * SUM(paid_next_month) / SUM(paid_this_month), 1) AS retained_pct
FROM monthly
GROUP BY store
UNION ALL
SELECT 'all', SUM(paid_this_month), SUM(paid_next_month),
       ROUND(100.0 * SUM(paid_next_month) / SUM(paid_this_month), 1)
FROM monthly;

-- Finding (Jan-Sep 2026):
-- * Overall 42 of 85 monthly payments (49%) were followed by a payment the
--   next month: about half of monthly payers stay each month.
-- * Apple 8 of 17 (47%), Play 34 of 68 (50%).
-- * Weakest month: Aug (8 payers, only 2 came back).
-- Limitation: 2-15 payers a month, so one person moves the rate a lot.


-- 3f. Downloads vs uninstalls per month, with a running total.
--     The window SUM(...) OVER (ORDER BY month) adds up month by month.
SELECT month, downloads, uninstalls,
       ROUND(uninstalls * 100.0 / downloads, 0) AS uninstalls_pct_of_downloads,
       SUM(downloads - uninstalls) OVER (ORDER BY month) AS still_installed
FROM (
    SELECT substr(date, 1, 7) AS month,
           SUM(downloads)  AS downloads,
           SUM(uninstalls) AS uninstalls
    FROM downloads
    WHERE store = 'google_play'
    GROUP BY month
)
ORDER BY month;

-- Finding (Google Play only):
-- * Jan 2026 spike: 2640 downloads, but 1812 (69%) uninstalled that month.
--   The spike didn't stick.
-- * Since Sep downloads grow again (289, 926) with uninstalls at 78-81%,
--   so the installed base grows (897 in Aug -> 1156 in Oct).
-- Limitation: Apple exports have no uninstalls, so this is Play only.
--   Uninstalls can come from older downloads, so a monthly "kept %" can go
--   negative. The running total avoids that.
