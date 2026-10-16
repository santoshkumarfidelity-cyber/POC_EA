"""SQLite schema for the POC. One row per artifact version; history is
never overwritten."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact_families (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    segment TEXT NOT NULL,
    domain TEXT NOT NULL,
    content_type TEXT NOT NULL,
    audience TEXT NOT NULL,
    owner TEXT NOT NULL,
    contributor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    current_version_id TEXT
);

CREATE TABLE IF NOT EXISTS artifact_versions (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL REFERENCES artifact_families(id),
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    review_date TEXT,
    uploaded_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_text TEXT NOT NULL,
    extraction_status TEXT NOT NULL DEFAULT 'TEXT',
    is_current_approved INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_versions_family
    ON artifact_versions(family_id);
CREATE INDEX IF NOT EXISTS ix_versions_status
    ON artifact_versions(lifecycle_status);

CREATE TABLE IF NOT EXISTS artifact_tags (
    version_id TEXT NOT NULL REFERENCES artifact_versions(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (version_id, tag)
);

CREATE TABLE IF NOT EXISTS artifact_acl_groups (
    version_id TEXT NOT NULL REFERENCES artifact_versions(id),
    grp TEXT NOT NULL,
    PRIMARY KEY (version_id, grp)
);

CREATE TABLE IF NOT EXISTS lifecycle_events (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES artifact_versions(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_persona TEXT NOT NULL,
    note TEXT,
    at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registered_links (
    id TEXT PRIMARY KEY,
    family_id TEXT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    link_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registered_link_acl_groups (
    link_id TEXT NOT NULL REFERENCES registered_links(id),
    grp TEXT NOT NULL,
    PRIMARY KEY (link_id, grp)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    persona TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_id TEXT,
    details_json TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_at ON audit_events(at);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    persona TEXT NOT NULL,
    last_question TEXT,
    last_status TEXT,
    cited_ids_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
    version_id UNINDEXED, title, description, content_text, tags_text);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            "SELECT * FROM artifact_fts LIMIT 0")
        return True
    except sqlite3.Error:
        return False


def initialize(conn: sqlite3.Connection) -> bool:
    """Create schema. Returns True if FTS5 is usable."""
    conn.executescript(SCHEMA)
    try:
        conn.executescript(FTS_SCHEMA)
        ok = True
    except sqlite3.Error:
        ok = False
    conn.commit()
    return ok
