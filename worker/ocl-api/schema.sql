-- ocl-api D1 schema (openchecklists-users)
-- Matches queries in index.js. Safe to re-run.

CREATE TABLE IF NOT EXISTS users (
  id                TEXT PRIMARY KEY,          -- Zitadel sub
  email             TEXT,
  username          TEXT UNIQUE,               -- optional, for anonymity
  display_name      TEXT,
  joined_at         TEXT,
  total_points      INTEGER NOT NULL DEFAULT 0,
  level             INTEGER NOT NULL DEFAULT 1,
  share_leaderboard INTEGER NOT NULL DEFAULT 0 -- opt-in only
);

CREATE TABLE IF NOT EXISTS points_ledger (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id   TEXT NOT NULL,
  event     TEXT NOT NULL,
  points    INTEGER NOT NULL DEFAULT 0,
  detail    TEXT,
  earned_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ledger_user ON points_ledger(user_id);

CREATE TABLE IF NOT EXISTS user_aircraft (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      TEXT NOT NULL,
  make         TEXT,
  model        TEXT,
  registration TEXT,
  profile_toml TEXT,
  added_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_aircraft_user ON user_aircraft(user_id);

CREATE TABLE IF NOT EXISTS favorite_airports (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       TEXT NOT NULL,
  airport_ident TEXT NOT NULL,
  airport_name  TEXT,
  added_at      TEXT,
  UNIQUE(user_id, airport_ident)
);

CREATE TABLE IF NOT EXISTS preflight_logs (
  id              TEXT PRIMARY KEY,            -- uuid
  user_id         TEXT NOT NULL,
  checklist_id    TEXT NOT NULL,
  checklist_hash  TEXT,
  checklist_title TEXT,
  aircraft_id     INTEGER,
  completed_at    TEXT,
  items_total     INTEGER NOT NULL DEFAULT 0,
  items_checked   INTEGER NOT NULL DEFAULT 0,
  log_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_user ON preflight_logs(user_id, completed_at);

CREATE TABLE IF NOT EXISTS training_progress (
  user_id         TEXT NOT NULL,
  cert_id         TEXT NOT NULL,
  requirement_key TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'not_started',
  value           TEXT,
  updated_at      TEXT,
  PRIMARY KEY (user_id, cert_id, requirement_key)
);

CREATE TABLE IF NOT EXISTS saved_checklists (
  id             TEXT PRIMARY KEY,
  user_id        TEXT NOT NULL,
  title          TEXT,
  checklist_json TEXT,
  review_status  TEXT,
  review_notes   TEXT,
  is_public      INTEGER NOT NULL DEFAULT 1,   -- public on creation
  saved_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_checklists_public ON saved_checklists(is_public, saved_at);

CREATE TABLE IF NOT EXISTS flight_plans (
  id                TEXT PRIMARY KEY,
  user_id           TEXT,
  created_at        TEXT NOT NULL,
  aircraft_snapshot TEXT NOT NULL,
  departure         TEXT NOT NULL,
  destination       TEXT NOT NULL,
  alternate         TEXT,
  depart_at         TEXT,
  fuel_onboard      REAL,
  reserve_min       INTEGER DEFAULT 30,
  snapshot          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flight_plans_user ON flight_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_flight_plans_created ON flight_plans(created_at DESC);
