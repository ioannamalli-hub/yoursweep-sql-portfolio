-- =====================================================================
-- 03_who_pays_and_when_clean.sql  |  Q1 + Q2
-- Q1. What turns someone into a payer?
-- Q2. When do they pay?
-- The "funnel": download -> free trial -> first payment.
-- Big-data rule: no typed-in IDs or dates. Use customers
-- (WHERE count_as_payer = 1) and compute any cut-off date.
-- Run (from the sql folder, after 02_cleaning_clean.sql):
--   sqlite3 -header -column yoursweep.db < 03_who_pays_and_when_clean.sql
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1. What turns someone into a payer?
-- ---------------------------------------------------------------------

-- 1a. The funnel per store, all dates: downloads -> trials -> payers.
WITH d AS (
    SELECT store, SUM(downloads) AS total_downloads
    FROM downloads
    GROUP BY store
),
t AS (
    SELECT store, SUM(quantity) AS total_trials
    FROM subscription_events
    WHERE event = 'free_trial_start'
    GROUP BY store
),
p AS (
    SELECT store, COUNT(*) AS total_payers
    FROM customers
    WHERE count_as_payer = 1
    GROUP BY store
)
SELECT d.store, d.total_downloads, t.total_trials, p.total_payers
FROM d
JOIN t ON d.store = t.store
JOIN p ON d.store = p.store;

-- Finding (all dates):
--   apple:  711 downloads -> 20 trials -> 33 payers
--   play:  4423 downloads -> 24 trials -> 40 payers
-- * Apple has more payers than trials: most people pay straight away.
-- * Not a fair store comparison yet: Play data starts months earlier (see 1b).
-- Total: 5134

-- 1b. Fair comparison: same period for both stores, plus conversion rate.
--     The start date is computed (latest of the stores' first payment
--     dates), not typed, so it updates itself.
WITH start AS (
    SELECT MAX(first_date) AS start_date
    FROM (SELECT store, MIN(date) AS first_date FROM payments GROUP BY store)
),
d AS (
    SELECT store, SUM(downloads) AS total_downloads
    FROM downloads, start
    WHERE date >= start.start_date
    GROUP BY store
),
t AS (
    SELECT store, SUM(quantity) AS total_trials
    FROM subscription_events, start
    WHERE event = 'free_trial_start' AND date >= start.start_date
    GROUP BY store
),
p AS (
    SELECT store, COUNT(*) AS total_payers
    FROM customers, start
    WHERE count_as_payer = 1 AND first_payment_date >= start.start_date
    GROUP BY store
)
SELECT d.store, d.total_downloads, t.total_trials, p.total_payers,
       ROUND(p.total_payers * 100.0 / d.total_downloads, 2) AS conversion_pct
FROM d
JOIN t ON d.store = t.store
JOIN p ON d.store = p.store;

-- How many times better does the best store convert than the worst?
--   (same CTEs as above, then MAX / MIN of the rate)
WITH start AS (
    SELECT MAX(first_date) AS start_date
    FROM (SELECT store, MIN(date) AS first_date FROM payments GROUP BY store)
),
d AS (
    SELECT store, SUM(downloads) AS total_downloads
    FROM downloads, start
    WHERE date >= start.start_date
    GROUP BY store
),
p AS (
    SELECT store, COUNT(*) AS total_payers
    FROM customers, start
    WHERE count_as_payer = 1 AND first_payment_date >= start.start_date
    GROUP BY store
),
rate AS (
    SELECT d.store, p.total_payers * 100.0 / d.total_downloads AS conversion_pct
    FROM d JOIN p ON d.store = p.store
)
SELECT ROUND(MAX(conversion_pct) / MIN(conversion_pct), 1) AS best_vs_worst_x
FROM rate;

-- Finding (from 27 May 2026, when Apple data starts):
--   apple:  697 downloads, 20 trials, 33 payers -> 4.73% convert
--   play:  1464 downloads, 24 trials, 17 payers -> 1.16% convert
-- * Apple converts 4.1x better than Play over the same period.
-- * (* 100.0, not * 100, so SQLite doesn't do integer division.)


-- 1c. Did payers come from a trial or pay straight away?
SELECT store, came_from_trial, COUNT(*) AS payers
FROM customers
WHERE count_as_payer = 1
GROUP BY store, came_from_trial;

-- Finding: 60 of 73 payers paid straight away (Apple 30, Play 30).
--   13 came from a trial (Apple 3, Play 10).


-- 1d. Did an offer help? Payers by first offer.
SELECT store, COALESCE(first_offer, 'no offer') AS offer, COUNT(*) AS payers
FROM customers
WHERE count_as_payer = 1
GROUP BY store, first_offer
ORDER BY store, payers DESC;

-- Finding:
-- * Play: 10 of 40 payers came through 'freesummer', 30 with no offer.
-- * Apple: all 33 show 'no offer'. Apple offer codes (One Month, Evacode)
--   are in subscription_events but not in payments, so the 3 Apple trial
--   payers also show 'no offer' here.
-- * The free-trial offer is starting to bring payers on Play.


-- 1e. Which countries produce payers? Downloads vs payers per country.
--     LEFT JOIN keeps countries with downloads but 0 payers.
WITH d AS (
    SELECT country, SUM(downloads) AS total_downloads
    FROM downloads
    GROUP BY country
),
p AS (
    SELECT country, COUNT(*) AS total_payers
    FROM customers
    WHERE count_as_payer = 1
    GROUP BY country
)
SELECT d.country, d.total_downloads,
       COALESCE(p.total_payers, 0) AS total_payers,
       ROUND(COALESCE(p.total_payers, 0) * 100.0 / d.total_downloads, 2) AS conversion_pct,
       -- share of ALL downloads / payers: SUM(...) OVER () = the grand total
       ROUND(d.total_downloads * 100.0 / SUM(d.total_downloads) OVER (), 1) AS pct_of_downloads,
       ROUND(COALESCE(p.total_payers, 0) * 100.0 / SUM(COALESCE(p.total_payers, 0)) OVER (), 1) AS pct_of_payers
FROM d
LEFT JOIN p ON d.country = p.country
ORDER BY total_payers DESC, d.total_downloads DESC;

-- Finding (all dates, 104 countries, 5134 downloads):
-- * Only 8 countries have payers: US 56 (of 1254 downloads, 4.47%),
--   SE 4, GB 3, EE 3, DE 2, FR 2, TW 2, CA 1.
-- * The US gives 24.4% of downloads but 76.7% of payers.
-- * Big download countries IN (383), BR (233), RU (170), MX (139) have 0 payers.
-- -> Paying users are mostly in the US.
-- * ZZ = unknown country.


-- ---------------------------------------------------------------------
-- Q2. When do people pay?
-- ---------------------------------------------------------------------

-- 2a. New payers per month, including months with 0.
--     The month list comes from downloads (it has every month), then
--     LEFT JOIN the payers and turn blanks into 0.
WITH m AS (
    SELECT DISTINCT substr(date, 1, 7) AS month
    FROM downloads
),
p AS (
    SELECT substr(first_payment_date, 1, 7) AS month, COUNT(*) AS new_payers
    FROM customers
    WHERE count_as_payer = 1
    GROUP BY month
)
SELECT m.month, COALESCE(p.new_payers, 0) AS new_payers
FROM m
LEFT JOIN p ON m.month = p.month
ORDER BY m.month;

-- Finding:
--   Jan 26: 14 | Feb: 5 | Mar: 1 | Apr: 1 | May: 4 | Jun: 11 | Jul: 13
--   Aug: 2 | Sep: 0 | Oct: 22
-- * Three busy periods: Jan (Play launch spike), Jun-Jul (just after the
--   Apple launch) and Oct (freesummer trials converting + Apple annuals).
--   Quiet months in between: 0-5.


-- 2b. Days from trial start to paying, for payers who came from a trial.
--     subscription_events has no customer_id, so match the trial on
--     store + country + plan, and take the closest trial BEFORE the payment
--     (MAX of the earlier dates).
WITH trial_payers AS (
    SELECT c.customer_id, c.store, c.country, c.first_payment_date,
           MAX(se.date) AS trial_start_date
    FROM customers c
    JOIN subscription_events se
      ON  c.store      = se.store
      AND c.country    = se.country
      AND c.first_plan = se.plan
    WHERE c.count_as_payer = 1
      AND c.came_from_trial = 'yes'
      AND se.event = 'free_trial_start'
      AND se.date < c.first_payment_date
    GROUP BY c.customer_id, c.store, c.country, c.first_payment_date
)
SELECT customer_id, store, country, first_payment_date, trial_start_date,
       julianday(first_payment_date) - julianday(trial_start_date) AS days_trial_to_payment
FROM trial_payers
ORDER BY first_payment_date;

-- Finding: most trial payers paid 7 days after the trial started, i.e.
--   when the free trial ended and the store charged them.
-- Limitation: trials are matched by store + country + plan, not by person.
--   When several US trials start close together, SQL picks the closest
--   one, which can be someone else's, so a few show 3 or 5 days.
--   Fix: user-level store data.


-- 2c. Do payments line up with download spikes? Downloads and payers per week.
WITH downloads_per_week AS (
    SELECT strftime('%Y-%W', date) AS week, SUM(downloads) AS total_downloads
    FROM downloads
    GROUP BY week
),
payers_per_week AS (
    SELECT strftime('%Y-%W', first_payment_date) AS week, COUNT(*) AS total_payers
    FROM customers
    WHERE count_as_payer = 1
    GROUP BY week
)
SELECT d.week, d.total_downloads, COALESCE(p.total_payers, 0) AS total_payers
FROM downloads_per_week d
LEFT JOIN payers_per_week p ON d.week = p.week
ORDER BY d.total_downloads DESC, d.week;

-- Typical week: average vs median (SQLite has no MEDIAN: sort, take the middle).
WITH downloads_per_week AS (
    SELECT strftime('%Y-%W', date) AS week, SUM(downloads) AS total_downloads
    FROM downloads
    GROUP BY week
)
SELECT ROUND(AVG(total_downloads), 0) AS avg_weekly_downloads
FROM downloads_per_week;

WITH downloads_per_week AS (
    SELECT strftime('%Y-%W', date) AS week, SUM(downloads) AS total_downloads
    FROM downloads
    GROUP BY week
)
SELECT total_downloads AS median_weekly_downloads
FROM downloads_per_week
ORDER BY total_downloads
LIMIT 1 OFFSET (SELECT COUNT(*) FROM downloads_per_week) / 2;

-- Biggest week vs a typical (median) week:
WITH downloads_per_week AS (
    SELECT strftime('%Y-%W', date) AS week, SUM(downloads) AS total_downloads
    FROM downloads
    GROUP BY week
),
median AS (
    SELECT total_downloads AS median_downloads
    FROM downloads_per_week
    ORDER BY total_downloads
    LIMIT 1 OFFSET (SELECT COUNT(*) FROM downloads_per_week) / 2
)
SELECT MAX(total_downloads) AS biggest_week,
       (SELECT median_downloads FROM median) AS median_week,
       ROUND(MAX(total_downloads) * 1.0 / (SELECT median_downloads FROM median), 0) AS biggest_vs_median_x
FROM downloads_per_week;

-- Finding:
-- * A typical week has 50 downloads (median). The average is 117, pulled
--   up by one huge week.
-- * Biggest bursts:
--     first week of Jan 2026 (Play): 1972 downloads (39x typical), 1 payer
--     late Sep - Oct 2026:           225-242 a week, 4-6 payers a week
-- * So more downloads bring more payers, but a spike alone isn't enough:
--   Oct (free trial offer) converted far better than Jan.
-- Limitation: 73 payers in total, so a pattern to watch, not proof.
