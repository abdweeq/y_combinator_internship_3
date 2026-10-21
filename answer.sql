-- Shiptivitas, Task 3: Analytics
-- Source: insidesherpa/-shiptivitas-3, shiptivity.db.
-- Kanban release date: 2018-06-02 (README).
-- Timestamps are Unix seconds; all calendar days below are UTC.
-- DAU is a login-based proxy: one user is counted once per day.
-- Calendar gaps are treated as zero activity within the observed date range.
-- These SELECT queries do not change the source database.

-- QUERY: daily_active_users
-- PART 1: Daily unique users and the mean before/after release.
WITH RECURSIVE
bounds AS (
    SELECT
        DATE(MIN(login_timestamp), 'unixepoch') AS first_day,
        DATE(MAX(login_timestamp), 'unixepoch') AS last_day
    FROM login_history
),
calendar(day) AS (
    SELECT first_day FROM bounds
    UNION ALL
    SELECT DATE(day, '+1 day')
    FROM calendar
    WHERE day < (SELECT last_day FROM bounds)
),
daily_logins AS (
    SELECT
        DATE(login_timestamp, 'unixepoch') AS day,
        COUNT(DISTINCT user_id) AS dau
    FROM login_history
    GROUP BY DATE(login_timestamp, 'unixepoch')
),
daily AS (
    SELECT
        calendar.day,
        CASE
            WHEN calendar.day < '2018-06-02' THEN 'Before release'
            ELSE 'After release'
        END AS period,
        COALESCE(daily_logins.dau, 0) AS dau
    FROM calendar
    LEFT JOIN daily_logins ON daily_logins.day = calendar.day
)
SELECT
    day,
    period,
    dau,
    ROUND(AVG(dau) OVER (PARTITION BY period), 4) AS period_average_dau,
    ROUND(
        AVG(dau) OVER (
            ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 4
    ) AS trailing_7_day_average
FROM daily
ORDER BY day;

-- QUERY: status_changes_by_card
-- PART 2: Include all cards, even cards with zero status changes.
-- Creation (oldStatus IS NULL) is not a status transition.
-- A priority-only edit is not a status transition either.
SELECT
    c.id AS card_id,
    c.name AS card_name,
    c.status AS current_status,
    COUNT(h.id) AS status_changes
FROM card AS c
LEFT JOIN card_change_history AS h
    ON h.cardID = c.id
    AND h.oldStatus IS NOT NULL
    AND h.newStatus IS NOT NULL
    AND h.oldStatus <> h.newStatus
GROUP BY c.id, c.name, c.status
ORDER BY status_changes DESC, c.id;

-- QUERY: matched_28_day_comparison
-- SUPPLEMENT: Equal-length, equal-weekday-composition windows.
-- Before: May 5--June 1. After: June 2--June 29. All dates inclusive.
WITH RECURSIVE
periods(period, start_day, end_day) AS (
    VALUES
        ('Before release', '2018-05-05', '2018-06-01'),
        ('After release', '2018-06-02', '2018-06-29')
),
calendar(day) AS (
    SELECT MIN(start_day) FROM periods
    UNION ALL
    SELECT DATE(day, '+1 day')
    FROM calendar
    WHERE day < (SELECT MAX(end_day) FROM periods)
),
daily_logins AS (
    SELECT
        DATE(login_timestamp, 'unixepoch') AS day,
        COUNT(DISTINCT user_id) AS dau
    FROM login_history
    GROUP BY DATE(login_timestamp, 'unixepoch')
)
SELECT
    p.period,
    p.start_day,
    p.end_day,
    COUNT(*) AS calendar_days,
    SUM(COALESCE(l.dau, 0)) AS active_user_days,
    ROUND(AVG(COALESCE(l.dau, 0)), 4) AS average_dau,
    (
        SELECT COUNT(DISTINCT user_id)
        FROM login_history
        WHERE DATE(login_timestamp, 'unixepoch')
            BETWEEN p.start_day AND p.end_day
    ) AS unique_users_in_window
FROM periods AS p
JOIN calendar AS c ON c.day BETWEEN p.start_day AND p.end_day
LEFT JOIN daily_logins AS l ON l.day = c.day
GROUP BY p.period, p.start_day, p.end_day
ORDER BY p.start_day;

-- QUERY: daily_status_changes_by_card
-- SUPPLEMENT: Daily activity per card, as requested in the task background.
-- Missing day/card combinations mean zero observed transitions.
SELECT
    DATE(timestamp, 'unixepoch') AS day,
    cardID AS card_id,
    COUNT(*) AS status_changes
FROM card_change_history
WHERE oldStatus IS NOT NULL
    AND newStatus IS NOT NULL
    AND oldStatus <> newStatus
GROUP BY DATE(timestamp, 'unixepoch'), cardID
ORDER BY day, cardID;

-- QUERY: transition_counts
-- SUPPLEMENT: Which directions did the cards move?
SELECT
    oldStatus AS from_status,
    newStatus AS to_status,
    COUNT(*) AS status_changes,
    COUNT(DISTINCT cardID) AS distinct_cards
FROM card_change_history
WHERE oldStatus IS NOT NULL
    AND newStatus IS NOT NULL
    AND oldStatus <> newStatus
GROUP BY oldStatus, newStatus
ORDER BY status_changes DESC, from_status, to_status;

-- QUERY: card_activity_summary
-- SUPPLEMENT: Evidence for product hypotheses.
-- Card age is measured at the latest card-history timestamp in the dataset,
-- not at the date on which this assignment is being completed.
WITH history AS (
    SELECT
        cardID,
        MIN(CASE WHEN oldStatus IS NULL THEN timestamp END) AS created_at,
        SUM(
            CASE
                WHEN oldStatus IS NOT NULL
                    AND newStatus IS NOT NULL
                    AND oldStatus <> newStatus
                THEN 1
                ELSE 0
            END
        ) AS status_changes
    FROM card_change_history
    GROUP BY cardID
),
cards AS (
    SELECT
        c.id,
        c.status,
        h.created_at,
        COALESCE(h.status_changes, 0) AS status_changes
    FROM card AS c
    LEFT JOIN history AS h ON h.cardID = c.id
)
SELECT
    COUNT(*) AS total_cards,
    SUM(status_changes) AS total_status_changes,
    SUM(status_changes = 0) AS cards_without_status_changes,
    SUM(status_changes <= 1) AS cards_with_at_most_one_status_change,
    SUM(status = 'backlog') AS backlog_cards,
    SUM(status = 'in-progress') AS in_progress_cards,
    SUM(status = 'complete') AS complete_cards,
    SUM(
        status = 'backlog'
        AND status_changes = 0
        AND created_at <= (
            SELECT MAX(timestamp) - 14 * 86400
            FROM card_change_history
        )
    ) AS unmoved_backlog_cards_at_least_14_days_old
FROM cards;
