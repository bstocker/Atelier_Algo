-- Journal classique, et non WAL. Le mode WAL est plus rapide, mais il
-- exige de la memoire partagee entre les processus qui ouvrent la base :
-- SQLite le documente comme inutilisable sur un systeme de fichiers
-- reseau, et l'hebergement monte precisement /home par le reseau. Le
-- gain ne vaut pas le risque de corrompre des copies d'eleves.
-- `outils/diag_base.py` dit sous quel mode tourne la base deployee.
PRAGMA journal_mode = DELETE;

-- Comptes enseignants crees par l'administrateur. Le compte administrateur
-- lui-meme n'est pas ici : il vient des variables d'environnement, et il est
-- le seul a pouvoir creer, reinitialiser ou supprimer les comptes ci-dessous.
CREATE TABLE IF NOT EXISTS teacher (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    created_by    TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS session (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,
    title       TEXT    NOT NULL,
    patterns    TEXT    NOT NULL,              -- JSON : liste de cles de motifs
    status      TEXT    NOT NULL DEFAULT 'draft',  -- draft | open | closed
    exam_mode   INTEGER NOT NULL DEFAULT 0,       -- 1 : l'eleve ne voit pas sa reussite
    created_by  TEXT    NOT NULL DEFAULT '',      -- compte qui a cree la session
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

-- Chapitre QCM : les modules importes au format Excel. Les modules livres
-- avec l'application, eux, restent decrits en Python dans atelier/modules/.
CREATE TABLE IF NOT EXISTS qcm_module (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,     -- cle de module, derivee du titre
    title       TEXT    NOT NULL,
    summary     TEXT    NOT NULL DEFAULT '',
    level       INTEGER NOT NULL DEFAULT 2,
    source      TEXT    NOT NULL DEFAULT '', -- nom du fichier importe
    imported_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS qcm_question (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id   INTEGER NOT NULL REFERENCES qcm_module(id) ON DELETE CASCADE,
    key         TEXT    NOT NULL UNIQUE,     -- cle de motif, unique au registre
    position    INTEGER NOT NULL,
    question    TEXT    NOT NULL,
    choices     TEXT    NOT NULL,            -- JSON : les quatre propositions
    answer      INTEGER NOT NULL,            -- indice de la bonne, de 0 a 3
    level       INTEGER NOT NULL DEFAULT 2,
    explanation TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_qcm_question_module
    ON qcm_question(module_id, position);

CREATE INDEX IF NOT EXISTS idx_task_student ON task(student_id);
CREATE INDEX IF NOT EXISTS idx_incident_student ON incident(student_id);
CREATE INDEX IF NOT EXISTS idx_student_session ON student(session_id);
