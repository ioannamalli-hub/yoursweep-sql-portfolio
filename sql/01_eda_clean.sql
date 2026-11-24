-- =====================================================================
-- 01_eda_clean.sql  |  Exploratory data analysis: what is in the data?
-- Goal: understand every table BEFORE cleaning or answering questions.
-- Order: 1. overview  2. values  3. missing values  4. duplicates
--        5. odd values  6. first look at the target (payers)
-- Run in Terminal (from the sql folder):
--   sqlite3 -header -column yoursweep.db < 01_eda_clean.sql
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. OVERVIEW: rows, date range and columns of every table
-- ---------------------------------------------------------------------

-- 1.1 Rows and date range per table, per store.
SELECT 'payments' AS tbl, store, COUNT(*) AS rows_, MIN(date), MAX(date) FROM payments GROUP BY store;
SELECT 'subscription_events' AS tbl, store, COUNT(*) AS rows_, MIN(date), MAX(date) FROM subscription_events GROUP BY store;
SELECT 'active_subscriptions' AS tbl, store, COUNT(*) AS rows_, MIN(date), MAX(date) FROM active_subscriptions GROUP BY store;
SELECT 'downloads' AS tbl, store, COUNT(*) AS rows_, MIN(date), MAX(date) FROM downloads GROUP BY store;
SELECT 'reviews' AS tbl, store, COUNT(*) AS rows_, MIN(date), MAX(date) FROM reviews GROUP BY store;

-- Finding:
--   table                 apple                        google_play
--   payments              43 rows, 27 May - 30 Oct 26  78 rows, 02 Jan - 18 Oct 26
--   subscription_events   82 rows, 27 May - 30 Oct 26  95 rows, 02 Jan - 31 Oct 26
--   active_subscriptions  829 rows, 27 May - 30 Oct 26 1112 rows, 02 Jan - 31 Oct 26
--   downloads             613 rows, 26 May - 31 Oct 26 2134 rows, 01 Jan - 31 Oct 26
--   reviews               none                         12 rows, 11 Feb - 21 Oct 26
-- * Apple data starts late May 2026 (iOS launch). Play starts in January.
--   -> Any store comparison over time must start when Apple starts.
-- * There are no Apple reviews.

-- 1.2 Column names and types of each table.
PRAGMA table_info(payments);
PRAGMA table_info(subscription_events);
PRAGMA table_info(active_subscriptions);
PRAGMA table_info(downloads);
PRAGMA table_info(reviews);

-- Finding: every column has a type (INTEGER, REAL or TEXT). Dates are TEXT
--   in 'YYYY-MM-DD' form, so MIN/MAX and date functions work on them.


-- ---------------------------------------------------------------------
-- 2. VALUES: what do the main columns contain?
-- ---------------------------------------------------------------------

-- 2.1 payments: type, plan, offer, currency.
SELECT type, COUNT(*) FROM payments GROUP BY type;
SELECT plan, COUNT(*) FROM payments GROUP BY plan;
SELECT offer, COUNT(*) FROM payments GROUP BY offer;
SELECT currency, COUNT(*) FROM payments GROUP BY currency ORDER BY COUNT(*) DESC;

-- Finding:
-- * type: 120 'payment', 1 'refund'.
-- * plan: 104 'monthly', 17 'annual'.
-- * offer: 111 blank (no offer), 10 'freesummer' (Play).
-- * currency: USD 95, EUR 10, SEK 6, GBP 5, TWD 4, CAD 1
--   -> use price_usd_approx to compare prices.

-- 2.2 subscription_events: rows per event, per store.
SELECT store, event, COUNT(*) AS rows_, SUM(quantity) AS people
FROM subscription_events
GROUP BY store, event
ORDER BY store, people DESC;

-- Finding:
-- * apple: new_paid 31, cancel 21, free_trial_start 20, renewal 8,
--   trial_converted 3, refund 1.
-- * play: cancel 46, new_paid 34, free_trial_start 24.
--   Play reports no renewals or trial conversions as events.
-- * One row can hold more than 1 person (rows_ < people), so count people
--   with SUM(quantity).

-- 2.3 payments: which countries?
SELECT country, COUNT(*) AS payments,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM payments), 1) AS pct_of_payments
FROM payments
GROUP BY country
ORDER BY payments DESC;

-- Finding: US 95 of 121 payments (78.5%), then SE 6, GB 5, TW 4, FR 4,
--   EE 3, DE 3, CA 1.


-- ---------------------------------------------------------------------
-- 3. MISSING VALUES: blanks in every column of every table
-- ---------------------------------------------------------------------
-- Pattern: SUM(CASE WHEN col IS NULL OR col = '' THEN 1 ELSE 0 END)
-- (numbers only need IS NULL). GROUP BY store shows where blanks come from.

-- 3.1 payments
SELECT store,
       COUNT(*) AS total_rows,
       SUM(CASE WHEN store IS NULL OR store = '' THEN 1 ELSE 0 END) AS store_nulls,
       SUM(CASE WHEN date IS NULL OR date = '' THEN 1 ELSE 0 END) AS date_nulls,
       SUM(CASE WHEN customer_id IS NULL OR customer_id = '' THEN 1 ELSE 0 END) AS customer_id_nulls,
       SUM(CASE WHEN plan IS NULL OR plan = '' THEN 1 ELSE 0 END) AS plan_nulls,
       SUM(CASE WHEN product IS NULL OR product = '' THEN 1 ELSE 0 END) AS product_nulls,
       SUM(CASE WHEN type IS NULL OR type = '' THEN 1 ELSE 0 END) AS type_nulls,
       SUM(CASE WHEN payment_number IS NULL THEN 1 ELSE 0 END) AS payment_number_nulls,
       SUM(CASE WHEN came_from_trial IS NULL OR came_from_trial = '' THEN 1 ELSE 0 END) AS came_from_trial_nulls,
       SUM(CASE WHEN offer IS NULL OR offer = '' THEN 1 ELSE 0 END) AS offer_nulls,
       SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS country_nulls,
       SUM(CASE WHEN currency IS NULL OR currency = '' THEN 1 ELSE 0 END) AS currency_nulls,
       SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) AS price_nulls,
       SUM(CASE WHEN proceeds IS NULL THEN 1 ELSE 0 END) AS proceeds_nulls,
       SUM(CASE WHEN price_usd_approx IS NULL THEN 1 ELSE 0 END) AS price_usd_approx_nulls,
       SUM(CASE WHEN proceeds_usd_approx IS NULL THEN 1 ELSE 0 END) AS proceeds_usd_approx_nulls,
       SUM(CASE WHEN order_id IS NULL OR order_id = '' THEN 1 ELSE 0 END) AS order_id_nulls
FROM payments
GROUP BY store;

SELECT * FROM payments WHERE payment_number IS NULL;

-- Finding: 13 of 16 columns are complete. Blanks:
-- * offer: blank on all 43 Apple rows and 68 of 78 Play rows = no offer
--   (Apple offer codes only show up in subscription_events).
-- * order_id: blank on all 43 Apple rows. Apple doesn't report it,
--   so order_id can't be a key for both stores.
-- * payment_number: 1 blank = the refund. OK, a refund isn't a new payment.

-- 3.2 downloads
SELECT store,
       COUNT(*) AS total_rows,
       SUM(CASE WHEN date IS NULL OR date = '' THEN 1 ELSE 0 END)       AS date_nulls,
       SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS country_nulls,
       SUM(CASE WHEN downloads IS NULL THEN 1 ELSE 0 END)   AS downloads_nulls,
       SUM(CASE WHEN redownloads IS NULL THEN 1 ELSE 0 END) AS redownloads_nulls,
       SUM(CASE WHEN updates IS NULL THEN 1 ELSE 0 END)     AS updates_nulls,
       SUM(CASE WHEN uninstalls IS NULL THEN 1 ELSE 0 END)  AS uninstalls_nulls
FROM downloads
GROUP BY store;

-- Finding:
-- * uninstalls: blank on all 613 Apple rows. Apple doesn't report it.
-- * redownloads: blank on all 2134 Play rows. Play doesn't report it.
-- -> blank = "not reported", NOT 0. Don't compare these across stores.
-- * downloads, updates, date, country: complete.

-- 3.3 subscription_events
SELECT store, event,
       COUNT(*) AS total_rows,
       SUM(CASE WHEN date IS NULL OR date = '' THEN 1 ELSE 0 END) AS date_nulls,
       SUM(CASE WHEN plan IS NULL OR plan = '' THEN 1 ELSE 0 END) AS plan_nulls,
       SUM(CASE WHEN offer IS NULL OR offer = '' THEN 1 ELSE 0 END) AS offer_nulls,
       SUM(CASE WHEN offer_type IS NULL OR offer_type = '' THEN 1 ELSE 0 END) AS offer_type_nulls,
       SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS country_nulls,
       SUM(CASE WHEN quantity IS NULL THEN 1 ELSE 0 END) AS quantity_nulls,
       SUM(CASE WHEN paid_periods_so_far IS NULL THEN 1 ELSE 0 END) AS paid_periods_nulls,
       SUM(CASE WHEN original_start_date IS NULL OR original_start_date = '' THEN 1 ELSE 0 END) AS orig_start_nulls,
       SUM(CASE WHEN days_before_canceling IS NULL THEN 1 ELSE 0 END) AS days_cancel_nulls,
       SUM(CASE WHEN cancellation_reason IS NULL OR cancellation_reason = '' THEN 1 ELSE 0 END) AS reason_nulls,
       SUM(CASE WHEN original_event_name IS NULL OR original_event_name = '' THEN 1 ELSE 0 END) AS orig_name_nulls
FROM subscription_events
GROUP BY store, event
ORDER BY store, event;

-- Finding: core columns (store, date, event, plan, country, quantity,
--   original_event_name) are complete. Blanks fall into 3 groups:
-- 1. Apple-only: paid_periods_so_far, original_start_date,
--    days_before_canceling, cancellation_reason, offer_type are blank on
--    every Play row. Play doesn't report them.
-- 2. Cancel-only (Apple): days_before_canceling and cancellation_reason
--    are only filled for cancels (reason also for the refund). Expected.
-- 3. offer / offer_type: blank when no offer was used. OK.
-- -> cancel timing and reasons can only be analysed for Apple.

-- 3.4 active_subscriptions
SELECT store,
       COUNT(*) AS total_rows,
       SUM(CASE WHEN date IS NULL OR date = '' THEN 1 ELSE 0 END) AS date_nulls,
       SUM(CASE WHEN plan IS NULL OR plan = '' THEN 1 ELSE 0 END) AS plan_nulls,
       SUM(CASE WHEN offer IS NULL OR offer = '' THEN 1 ELSE 0 END) AS offer_nulls,
       SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS country_nulls,
       SUM(CASE WHEN active_total IS NULL THEN 1 ELSE 0 END) AS active_total_nulls,
       SUM(CASE WHEN active_paid IS NULL THEN 1 ELSE 0 END) AS active_paid_nulls,
       SUM(CASE WHEN active_free_trial IS NULL THEN 1 ELSE 0 END) AS active_free_trial_nulls
FROM active_subscriptions
GROUP BY store;

-- Finding:
-- * active_paid and active_free_trial: blank on all 1112 Play rows.
--   Play only reports the total, not the paid / trial split.
--   -> paid vs trial only for Apple. To compare stores, use active_total.
-- * offer: mostly blank (585 Apple, 948 Play) = no offer. OK.
-- * date, plan, country, active_total: complete.

-- 3.5 reviews
SELECT store,
       COUNT(*) AS total_rows,
       SUM(CASE WHEN date IS NULL OR date = '' THEN 1 ELSE 0 END) AS date_nulls,
       SUM(CASE WHEN stars IS NULL THEN 1 ELSE 0 END) AS stars_nulls,
       SUM(CASE WHEN language IS NULL OR language = '' THEN 1 ELSE 0 END) AS language_nulls,
       SUM(CASE WHEN app_version IS NULL OR app_version = '' THEN 1 ELSE 0 END) AS app_version_nulls,
       SUM(CASE WHEN title IS NULL OR title = '' THEN 1 ELSE 0 END) AS title_nulls,
       SUM(CASE WHEN text IS NULL OR text = '' THEN 1 ELSE 0 END) AS text_nulls,
       SUM(CASE WHEN developer_reply IS NULL OR developer_reply = '' THEN 1 ELSE 0 END) AS developer_reply_nulls
FROM reviews
GROUP BY store;

-- Finding: 12 reviews, all Google Play.
-- * title: blank on all 12. Play reviews have no title.
-- * text: 5 of 12 are stars only. Normal, not a data problem.
-- * developer_reply: blank on the same 5, so the developer replied to every
--   review that had text.
-- * app_version: 3 blank. Minor with 12 reviews.
-- * stars, date, language: complete.


-- ---------------------------------------------------------------------
-- 4. DUPLICATES: every table
-- ---------------------------------------------------------------------
-- A = whole-row copies: all_rows should equal distinct_rows.
-- B = key repeats: the columns that make a row unique ("one row = one ___").
--     No rows printed = no duplicates.

-- 4.1 payments   (key: store + customer_id + date + type)
SELECT COUNT(*) AS all_rows,
       (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM payments)) AS distinct_rows
FROM payments;
SELECT store, customer_id, date, type, COUNT(*) AS times
FROM payments
GROUP BY store, customer_id, date, type
HAVING COUNT(*) > 1;

-- 4.2 downloads   (key: store + date + country)
SELECT COUNT(*) AS all_rows,
       (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM downloads)) AS distinct_rows
FROM downloads;
SELECT store, date, country, COUNT(*) AS times
FROM downloads
GROUP BY store, date, country
HAVING COUNT(*) > 1;

-- 4.3 subscription_events   (key: store + date + country + event + plan + offer)
SELECT COUNT(*) AS all_rows,
       (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM subscription_events)) AS distinct_rows
FROM subscription_events;
SELECT store, date, country, event, plan, offer, COUNT(*) AS times
FROM subscription_events
GROUP BY store, date, country, event, plan, offer
HAVING COUNT(*) > 1;

-- 4.4 active_subscriptions   (key: store + date + plan + offer + country)
SELECT COUNT(*) AS all_rows,
       (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM active_subscriptions)) AS distinct_rows
FROM active_subscriptions;
SELECT store, date, plan, offer, country, COUNT(*) AS times
FROM active_subscriptions
GROUP BY store, date, plan, offer, country
HAVING COUNT(*) > 1;

-- 4.5 reviews   (key: store + date + stars + text)
SELECT COUNT(*) AS all_rows,
       (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM reviews)) AS distinct_rows
FROM reviews;
SELECT store, date, stars, text, COUNT(*) AS times
FROM reviews
GROUP BY store, date, stars, text
HAVING COUNT(*) > 1;

-- Finding: no duplicates in any table.
-- * A: all_rows = distinct_rows everywhere (121, 2747, 177, 1941, 12).
-- * B: no key repeats in any table.
-- -> no deduplication needed. Rerun when new data is loaded.


-- ---------------------------------------------------------------------
-- 5. ODD VALUES: refunds and prices
-- ---------------------------------------------------------------------

-- 5.1 Refunds: which rows, and is the amount negative?
SELECT * FROM payments WHERE type = 'refund';
SELECT date, type, price FROM payments
WHERE customer_id IN (SELECT customer_id FROM payments WHERE type = 'refund')
ORDER BY date;

-- Finding: 1 refund. A US Apple customer paid 8.99 USD on 4 Oct 2026 and
--   was refunded -8.99 USD on 6 Oct. Refunds are stored as negative
--   amounts, so SUM(price) already nets them out.

-- 5.2 Prices per plan: min, max, average.
SELECT plan, COUNT(*), MIN(price_usd_approx), MAX(price_usd_approx),
       ROUND(AVG(price_usd_approx), 2) AS avg_price
FROM payments
WHERE type = 'payment'
GROUP BY plan;
SELECT store, date, country, price_usd_approx
FROM payments
WHERE plan = 'annual'
ORDER BY price_usd_approx;

-- Finding:
-- * monthly: 103 payments, $8.99-$11.42, typical $8.99.
-- * annual: 17 payments, $49.99-$114.29, typical $89.99.
-- * Outlier: $49.99 Play annual (Feb 2026, an old price). Other
--   differences come from local prices and currency conversion.


-- ---------------------------------------------------------------------
-- 6. FIRST LOOK AT THE TARGET: paying customers
-- ---------------------------------------------------------------------

-- 6.1 Unique paying customers per store, and who paid more than once.
SELECT store, COUNT(DISTINCT customer_id) AS customers FROM payments GROUP BY store;
SELECT customer_id, COUNT(*) AS times_paid
FROM payments
GROUP BY customer_id
HAVING COUNT(*) > 1
ORDER BY times_paid DESC;

-- Finding:
-- * 78 customers in payments: 34 Apple, 44 Play.
-- * 21 appear more than once (renewals). Top: 8 payments (Play).
--   One of the "2 times" is the payment + refund, not a renewal.

-- 6.2 How rare is paying? Downloads vs payers per store.
SELECT store, SUM(downloads) AS total_downloads FROM downloads GROUP BY store;
SELECT store, COUNT(DISTINCT customer_id) AS payers FROM payments GROUP BY store;

-- Downloads per payer (how many downloads it takes to get 1 payer):
WITH d AS (SELECT store, SUM(downloads) AS downloads FROM downloads GROUP BY store),
     p AS (SELECT store, COUNT(DISTINCT customer_id) AS payers FROM payments GROUP BY store)
SELECT d.store, d.downloads, p.payers,
       ROUND(d.downloads * 1.0 / p.payers, 0) AS downloads_per_payer
FROM d JOIN p ON d.store = p.store;

-- Finding:
-- * Downloads (all dates): Apple 711, Play 4423.
--   (SUM(downloads), not COUNT(*): COUNT gives rows, not downloads.)
-- * Payers: Apple 34, Play 44. After cleaning (02_cleaning_clean.sql, real
--   payers only): Apple 33, Play 40.
-- * Paying is rare: 1 payer per 21 downloads on Apple, per 101 on Play
--   (all dates; see 03 for a fair comparison from Apple's start).
