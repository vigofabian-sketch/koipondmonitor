-- Feature engineering for koi pond readings (SQLite 3.25+, window functions).
-- Input tables (loaded by build_features.py): readings, events

DROP VIEW IF EXISTS clean_readings;
DROP TABLE IF EXISTS features;

-- 1) Cleaning: drop missing values and DS18B20 disconnect glitches (-127)
CREATE VIEW clean_readings AS
SELECT
    datetime(timestamp) AS ts,
    date(timestamp)     AS day,
    temp_c, ph, turbidity
FROM readings
WHERE temp_c IS NOT NULL
  AND ph IS NOT NULL
  AND turbidity IS NOT NULL
  AND temp_c > -100;

-- 2) Features: rolling stats, rate of change, daily range, deviation from daily mean
CREATE TABLE features AS
WITH base AS (
    SELECT
        ts, day, temp_c, ph, turbidity,
        -- rolling mean over last 6 readings (~1 hour)
        AVG(temp_c)    OVER w6  AS temp_roll_1h,
        AVG(ph)        OVER w6  AS ph_roll_1h,
        AVG(turbidity) OVER w6  AS turb_roll_1h,
        -- rolling mean over last 144 readings (~24 hours)
        AVG(temp_c)    OVER w144 AS temp_roll_24h,
        AVG(ph)        OVER w144 AS ph_roll_24h,
        AVG(turbidity) OVER w144 AS turb_roll_24h,
        -- change since previous reading
        temp_c    - LAG(temp_c)    OVER ord AS temp_delta,
        ph        - LAG(ph)        OVER ord AS ph_delta,
        turbidity - LAG(turbidity) OVER ord AS turb_delta,
        -- daily min/max
        MIN(temp_c)    OVER (PARTITION BY day) AS temp_day_min,
        MAX(temp_c)    OVER (PARTITION BY day) AS temp_day_max,
        MIN(ph)        OVER (PARTITION BY day) AS ph_day_min,
        MAX(ph)        OVER (PARTITION BY day) AS ph_day_max,
        MAX(turbidity) OVER (PARTITION BY day) AS turb_day_max
    FROM clean_readings
    WINDOW
        ord  AS (ORDER BY ts),
        w6   AS (ORDER BY ts ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
        w144 AS (ORDER BY ts ROWS BETWEEN 143 PRECEDING AND CURRENT ROW)
)
SELECT
    b.*,
    -- deviation of current value from its 24h rolling mean
    b.turbidity - b.turb_roll_24h AS turb_dev_24h,
    b.ph        - b.ph_roll_24h   AS ph_dev_24h,
    -- join to event log: label is for EVALUATION ONLY, never a model input
    COALESCE(e.event_type, 'none') AS event_label
FROM base b
LEFT JOIN events e
    ON b.ts BETWEEN datetime(e.start) AND datetime(e.end);
