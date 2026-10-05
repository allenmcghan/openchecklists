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

CREATE TABLE IF NOT EXISTS checklist_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  checklist_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  stars INTEGER NOT NULL,
  comment TEXT,
  created_at TEXT,
  UNIQUE(checklist_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_reviews_cl ON checklist_reviews(checklist_id);

CREATE TABLE IF NOT EXISTS checklist_usage (
  checklist_id TEXT PRIMARY KEY,
  uses INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT
);

-- Pilot flight logbook (the real logbook — distinct from preflight_logs, which
-- are checklist completions). Entries can be manual or imported from saved
-- flight plans / preflight records; source_ref dedupes imports.
CREATE TABLE IF NOT EXISTS logbook_entries (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  flight_date TEXT,                -- YYYY-MM-DD
  dep         TEXT,
  arr         TEXT,
  route       TEXT,                -- full route string, e.g. "KBNA KHSV KMEM"
  aircraft    TEXT,                -- display: make/model/registration
  total_time  REAL NOT NULL DEFAULT 0,
  pic_time    REAL NOT NULL DEFAULT 0,
  landings    INTEGER NOT NULL DEFAULT 0,
  remarks     TEXT,
  source      TEXT NOT NULL DEFAULT 'manual',   -- manual | plan | preflight
  source_ref  TEXT,                              -- plan id / preflight log id (import dedupe)
  created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_logbook_user ON logbook_entries(user_id, flight_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_logbook_srcref ON logbook_entries(user_id, source_ref);

-- Fixed-window rate-limit / dedupe counters (email relay, submissions, plans,
-- usage counter, points caps). Rows expire; the worker prunes them lazily.
CREATE TABLE IF NOT EXISTS rate_limits (
  key        TEXT PRIMARY KEY,
  count      INTEGER NOT NULL DEFAULT 0,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limits_exp ON rate_limits(expires_at);

-- AI review verdicts keyed by content hash, so resubmitting identical content
-- never pays for a second review call.
CREATE TABLE IF NOT EXISTS review_cache (
  content_hash TEXT PRIMARY KEY,
  verdict      TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

-- Currency fields for logbook entries, kept in a side table so logbook_entries
-- (and the original POST /api/me/logbook contract) stay unchanged. One row per
-- entry; rows whose entry was deleted are pruned by the daily housekeeping.
CREATE TABLE IF NOT EXISTS logbook_entry_extra (
  entry_id        TEXT PRIMARY KEY,
  user_id         TEXT NOT NULL,
  day_landings    INTEGER NOT NULL DEFAULT 0,   -- day full-stop landings
  night_landings  INTEGER NOT NULL DEFAULT 0,   -- night full-stop landings (61.57(b))
  night_time      REAL NOT NULL DEFAULT 0,
  approaches      INTEGER NOT NULL DEFAULT 0,
  flight_review   INTEGER NOT NULL DEFAULT 0,   -- 61.56 flight review completed on this flight
  updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_lbextra_user ON logbook_entry_extra(user_id);

-- Per-pilot settings: currency inputs (flight review, medical) and the opt-in
-- morning weather digest (local hour + IANA timezone; last_digest_date is the
-- pilot's local date of the last digest, so each pilot gets at most one a day).
CREATE TABLE IF NOT EXISTS pilot_settings (
  user_id              TEXT PRIMARY KEY,
  flight_review_date   TEXT,               -- YYYY-MM-DD, manual entry
  medical_kind         TEXT,               -- first | second | third | basicmed | none
  medical_exam_date    TEXT,               -- YYYY-MM-DD (BasicMed: CMEC exam date)
  medical_age_at_exam  INTEGER,
  medical_privileges   TEXT,               -- atp | commercial | private
  basicmed_course_date TEXT,               -- YYYY-MM-DD, BasicMed online course
  digest_enabled       INTEGER NOT NULL DEFAULT 0,
  digest_hour          INTEGER NOT NULL DEFAULT 6,
  digest_tz            TEXT NOT NULL DEFAULT 'America/Chicago',
  last_digest_date     TEXT,
  updated_at           TEXT
);
CREATE INDEX IF NOT EXISTS idx_pilot_digest ON pilot_settings(digest_enabled);

-- The only source of truth for where email may be sent: filled exclusively from
-- Zitadel userinfo with email_verified=true, re-checked when older than 7 days.
CREATE TABLE IF NOT EXISTS verified_emails (
  user_id     TEXT PRIMARY KEY,
  email       TEXT NOT NULL,
  verified_at TEXT NOT NULL
);

-- One quiz credit per question per pilot.
CREATE TABLE IF NOT EXISTS quiz_credits (
  user_id    TEXT NOT NULL,
  test_id    TEXT NOT NULL,
  question_n INTEGER NOT NULL,
  earned_at  TEXT NOT NULL,
  PRIMARY KEY (user_id, test_id, question_n)
);
