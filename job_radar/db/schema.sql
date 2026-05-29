PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    organization TEXT,
    platform TEXT NOT NULL,
    parser_type TEXT NOT NULL DEFAULT 'manual_watch',
    config_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    detection_note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    sources_attempted INTEGER NOT NULL DEFAULT 0,
    jobs_found INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    run_id TEXT NOT NULL REFERENCES runs(id),
    title TEXT NOT NULL,
    organization TEXT,
    location TEXT,
    remote_status TEXT,
    source_url TEXT NOT NULL,
    source_job_id TEXT,
    raw_description TEXT NOT NULL DEFAULT '',
    normalized_description TEXT NOT NULL DEFAULT '',
    raw_payload TEXT,
    deadline TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_live INTEGER NOT NULL DEFAULT 1,
    is_excluded INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,
    user_status TEXT NOT NULL DEFAULT 'new',
    UNIQUE(source_id, source_url)
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT PRIMARY KEY REFERENCES sources(id),
    platform TEXT NOT NULL,
    parser_type TEXT NOT NULL,
    last_checked_at TEXT,
    last_successful_at TEXT,
    jobs_found INTEGER NOT NULL DEFAULT 0,
    new_jobs_found INTEGER NOT NULL DEFAULT 0,
    error_status TEXT,
    manual_review_needed INTEGER NOT NULL DEFAULT 0,
    likely_broken_url INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS source_runs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    jobs_found INTEGER NOT NULL DEFAULT 0,
    new_jobs_found INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS user_profile (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scoring_rubric (
    id TEXT PRIMARY KEY,
    profile_id TEXT REFERENCES user_profile(id),
    rubric_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_scores (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    rubric_id TEXT REFERENCES scoring_rubric(id),
    score REAL NOT NULL,
    explanation_json TEXT NOT NULL,
    scored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    status TEXT NOT NULL DEFAULT 'new',
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
