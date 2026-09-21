PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS session (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,
    title       TEXT    NOT NULL,
    patterns    TEXT    NOT NULL,              -- JSON : liste de cles de motifs
    status      TEXT    NOT NULL DEFAULT 'draft',  -- draft | open | closed
    created_at  TEXT    NOT NULL,
    opened_at   TEXT,
    closed_at   TEXT
);

CREATE TABLE IF NOT EXISTS student (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    first_name     TEXT    NOT NULL,
    last_name      TEXT    NOT NULL,
    token          TEXT    NOT NULL UNIQUE,
    joined_at      TEXT    NOT NULL,
    last_seen_at   TEXT,
    finished_at    TEXT,
    exit_count     INTEGER NOT NULL DEFAULT 0,
    penalty_points REAL    NOT NULL DEFAULT 0,
    final_score    REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_identity
    ON student(session_id, last_name, first_name);

CREATE TABLE IF NOT EXISTS task (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    pattern_key TEXT    NOT NULL,
    position    INTEGER NOT NULL,
    params      TEXT    NOT NULL,              -- JSON : {"n": 5}
    attempts    INTEGER NOT NULL DEFAULT 0,
    wrong_attempts INTEGER NOT NULL DEFAULT 0,  -- essais manques avant reussite
    solved      INTEGER NOT NULL DEFAULT 0,
    solved_at   TEXT,
    selection   TEXT    NOT NULL DEFAULT '{}', -- JSON : dernier choix
    UNIQUE(student_id, pattern_key)
);

CREATE TABLE IF NOT EXISTS incident (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    ordinal    INTEGER NOT NULL,               -- 1re, 2e, 3e sortie...
    kind       TEXT    NOT NULL,               -- blur | hidden | fullscreen
    penalty    REAL    NOT NULL,
    returned_ms INTEGER,                       -- delai de retour, si revenu
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_student ON task(student_id);
CREATE INDEX IF NOT EXISTS idx_incident_student ON incident(student_id);
CREATE INDEX IF NOT EXISTS idx_student_session ON student(session_id);
