-- Tiger Data (Postgres + TimescaleDB). Run once:  psql "$TIGER_DSN" -f sql/schema.sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS fans (
  id          TEXT PRIMARY KEY,
  handle      TEXT,
  phone_hash  TEXT UNIQUE,
  path        TEXT CHECK (path IN ('odysseus','telemachus')),
  entry_era   TEXT,
  games       TEXT[] DEFAULT '{}',
  drachmae    INT NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
  fan_id   TEXT,
  type     TEXT NOT NULL,      -- onboard | episode_play | relic | trial_entry | oracle_argos | watch | purchase | sponsored_impression
  source   TEXT NOT NULL,      -- web | ext | facetime | imessage
  meta     JSONB NOT NULL DEFAULT '{}'
);
SELECT create_hypertable('events', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS events_fan_ts ON events (fan_id, ts DESC);
CREATE INDEX IF NOT EXISTS events_type_ts ON events (type, ts DESC);

CREATE TABLE IF NOT EXISTS relics (
  id       TEXT PRIMARY KEY,
  era      TEXT NOT NULL,
  name     TEXT NOT NULL,
  rarity   TEXT NOT NULL,
  art_url  TEXT
);

CREATE TABLE IF NOT EXISTS fan_relics (
  fan_id    TEXT REFERENCES fans(id),
  relic_id  TEXT REFERENCES relics(id),
  earned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  via       TEXT,
  PRIMARY KEY (fan_id, relic_id)
);

CREATE TABLE IF NOT EXISTS trials (
  id      TEXT PRIMARY KEY,
  week    DATE NOT NULL,
  sponsor TEXT,
  prompt  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trial_entries (
  id        BIGSERIAL PRIMARY KEY,
  trial_id  TEXT,
  fan_id    TEXT REFERENCES fans(id),
  score     INT,
  verdict   TEXT,
  clip_url  TEXT,
  ts        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS purchases (
  id           BIGSERIAL PRIMARY KEY,
  fan_id       TEXT,
  sku          TEXT NOT NULL,    -- odyssey_pass | era_drop:<era> | sponsored_trial:<brand>
  amount_cents INT NOT NULL,
  ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Continuous aggregates powering the War Room
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_engagement
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', ts) AS day,
       count(DISTINCT fan_id)                                   AS active_fans,
       count(*) FILTER (WHERE type = 'relic')                   AS relics,
       count(*) FILTER (WHERE type = 'episode_play')            AS episodes,
       count(*) FILTER (WHERE type = 'watch')                   AS watches,
       count(*) FILTER (WHERE type = 'sponsored_impression')    AS sponsored_impressions
FROM events GROUP BY day WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS reactivated_fans_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', ts) AS day,
       count(DISTINCT fan_id) FILTER (WHERE meta->>'path' = 'odysseus')   AS reactivated,
       count(DISTINCT fan_id) FILTER (WHERE meta->>'path' = 'telemachus') AS new_fans
FROM events WHERE type = 'onboard' GROUP BY day WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS trial_entries_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', ts) AS day,
       count(*) AS trial_entries,
       avg((meta->>'score')::int) AS avg_score
FROM events WHERE type = 'trial_entry' GROUP BY day WITH NO DATA;

SELECT add_continuous_aggregate_policy('daily_engagement',      start_offset => INTERVAL '30 days', end_offset => NULL, schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);
SELECT add_continuous_aggregate_policy('reactivated_fans_daily', start_offset => INTERVAL '30 days', end_offset => NULL, schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);
SELECT add_continuous_aggregate_policy('trial_entries_daily',    start_offset => INTERVAL '30 days', end_offset => NULL, schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);
-- real-time aggregation so today's demo events show up instantly
ALTER MATERIALIZED VIEW daily_engagement       SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW reactivated_fans_daily SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW trial_entries_daily    SET (timescaledb.materialized_only = false);
