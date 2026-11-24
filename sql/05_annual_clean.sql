-- =====================================================================
-- 05_annual_clean.sql  |  Q4. Who goes annual?
-- Annual = $89.99/year, monthly = $8.99/month (annual = about 10 months'
-- price of monthly).
-- Big-data rule: no typed-in IDs or dates. Use clean_payments and
-- customers (WHERE count_as_payer = 1), and compute any rate you need.
-- Run (from the sql folder, after 02_cleaning_clean.sql):
--   sqlite3 -header -column yoursweep.db < 05_annual_clean.sql
-- =====================================================================


-- 4a. First plan per store: how many payers start annual vs monthly?
--     SUM(condition) counts the rows where it's true (true = 1, false = 0).
SELECT store,
       SUM(first_plan = 'monthly') AS monthly_payers,
       SUM(first_plan = 'annual')  AS annual_payers,
       ROUND(SUM(first_plan = 'annual') * 100.0 / COUNT(*), 1) AS annual_pct
FROM customers
WHERE count_as_payer = 1
GROUP BY store;

-- Finding:
--   apple: 17 monthly, 16 annual (48.5% annual)
--   play:  39 monthly,  1 annual (2.5% annual)
-- * 17 of 73 payers start on annual. Annual is much more common on Apple.


-- 4b. Annual vs monthly by country.
SELECT country,
       SUM(first_plan = 'monthly') AS monthly_payers,
       SUM(first_plan = 'annual')  AS annual_payers
FROM customers
WHERE count_as_payer = 1
GROUP BY country
ORDER BY annual_payers DESC, monthly_payers DESC;

-- Finding: US 43 monthly / 13 annual; SE, GB, TW, CA 1 annual each.
--   13 of the 17 annual payers are in the US.


-- 4c. Annual vs monthly by trial / no trial, and by offer.
SELECT came_from_trial,
       COALESCE(first_offer, 'no offer') AS offer,
       SUM(first_plan = 'monthly') AS monthly_payers,
       SUM(first_plan = 'annual')  AS annual_payers
FROM customers
WHERE count_as_payer = 1
GROUP BY came_from_trial, first_offer;

-- Finding: all 17 annual payers paid straight away, with no trial and no
--   offer. The 13 trial payers (10 freesummer, 3 Apple codes) all chose
--   monthly.


-- 4d. Does anyone switch monthly -> annual? (customers with both plans)
SELECT customer_id
FROM clean_payments
GROUP BY customer_id
HAVING COUNT(DISTINCT plan) > 1;

-- Finding: no rows, nobody switched plans. People stay on the plan they
--   start with, so the first choice matters.


-- 4e. Money per payer so far, by first plan (proceeds = after store fees).
SELECT first_plan,
       COUNT(*)                                 AS payers,
       ROUND(SUM(net_paid_usd) / COUNT(*), 2)     AS paid_per_payer,
       ROUND(SUM(net_proceeds_usd) / COUNT(*), 2) AS proceeds_per_payer
FROM customers
WHERE count_as_payer = 1
GROUP BY first_plan;

-- Annual vs monthly: how many times more proceeds per payer?
SELECT ROUND(
         (SELECT SUM(net_proceeds_usd) / COUNT(*) FROM customers
          WHERE count_as_payer = 1 AND first_plan = 'annual')
       / (SELECT SUM(net_proceeds_usd) / COUNT(*) FROM customers
          WHERE count_as_payer = 1 AND first_plan = 'monthly'), 1) AS annual_vs_monthly_x;

-- Finding:
--   annual:  17 payers, $90.44 paid, $61.45 proceeds per payer
--   monthly: 56 payers, $16.36 paid, $12.67 proceeds per payer
-- * So far an annual payer brings 4.8x the proceeds of a monthly payer
--   (see 4f for a 12-month view).


-- 4f. Over 12 months, which plan is worth more per customer?
--     Estimate: a monthly payer pays month 1, then keeps paying with the
--     monthly retention rate r from 04 (3e). Expected payments in 12 months
--     = 1 + r + r^2 + ... + r^11. r is computed here, not typed.
WITH RECURSIVE
last AS (
    SELECT MAX(substr(date, 1, 7)) AS last_month FROM clean_payments
),
retention AS (
    SELECT COUNT(DISTINCT b.customer_id || substr(b.date, 1, 7)) * 1.0
         / COUNT(DISTINCT a.customer_id || substr(a.date, 1, 7)) AS r
    FROM clean_payments a
    LEFT JOIN clean_payments b
      ON  b.customer_id = a.customer_id
      AND substr(b.date, 1, 7) = strftime('%Y-%m', date(a.date, '+1 month'))
    CROSS JOIN last
    WHERE a.plan = 'monthly'
      AND substr(a.date, 1, 7) < last.last_month
),
months(month_no, still_paying) AS (
    SELECT 1, 1.0
    UNION ALL
    SELECT month_no + 1, still_paying * (SELECT r FROM retention)
    FROM months
    WHERE month_no < 12
)
SELECT ROUND((SELECT r FROM retention) * 100, 1) AS monthly_retention_pct,
       ROUND(SUM(still_paying), 2)               AS expected_payments_12m,
       ROUND(SUM(still_paying) * 8.99, 2)        AS monthly_value_12m,
       89.99                                     AS annual_value_12m,
       ROUND(89.99 / (SUM(still_paying) * 8.99), 1) AS annual_vs_monthly_x
FROM months;

-- Finding: with 49% monthly retention, a monthly payer makes about 1.98
--   payments in 12 months = $17.77. An annual payer pays $89.99 up front,
--   about 5.1x more.
-- Limitation: based on 85 monthly payments, list prices (not proceeds), and
--   it assumes retention stays the same every month.
