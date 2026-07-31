import sqlite3
from contextlib import contextmanager

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_basics (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    first_name TEXT,
    last_name TEXT,
    headline TEXT,
    industry TEXT,
    location TEXT,
    raw_json TEXT,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    company TEXT,
    location TEXT,
    description TEXT,
    started_on TEXT,
    ended_on TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS profile_education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name TEXT,
    degree_name TEXT,
    field_of_study TEXT,
    start_date TEXT,
    end_date TEXT,
    notes TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS profile_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    authority TEXT,
    started_on TEXT,
    finished_on TEXT,
    license_number TEXT,
    url TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS profile_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    url TEXT,
    started_on TEXT,
    finished_on TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS search_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    keywords TEXT,
    target_roles TEXT,
    industries TEXT,
    locations TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    url TEXT,
    description TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    linkedin_url TEXT,
    company TEXT,
    email TEXT,
    phone TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'not_contacted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_url TEXT,
    company TEXT,
    recruiter_name TEXT,
    recruiter_contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'not_contacted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_leads_status ON job_leads(status);

CREATE TABLE IF NOT EXISTS cv_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT,
    stored_filename TEXT,
    file_type TEXT,
    uploaded_at TEXT NOT NULL,
    raw_text TEXT,
    sections_json TEXT,
    layout_meta_json TEXT,
    parse_warnings_json TEXT,
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cv_ats_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cv_document_id INTEGER NOT NULL REFERENCES cv_documents(id) ON DELETE CASCADE,
    checked_at TEXT NOT NULL,
    overall_score INTEGER,
    checklist_json TEXT,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS target_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT,
    source_type TEXT NOT NULL,
    fetch_status TEXT NOT NULL,
    fetch_warning TEXT,
    company TEXT,
    title TEXT,
    location TEXT,
    jd_text TEXT,
    fetched_at TEXT NOT NULL,
    job_lead_id INTEGER REFERENCES job_leads(id) ON DELETE SET NULL,
    manual_listing_id INTEGER REFERENCES manual_listings(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS cv_tailoring_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cv_document_id INTEGER NOT NULL REFERENCES cv_documents(id) ON DELETE CASCADE,
    target_job_id INTEGER NOT NULL REFERENCES target_jobs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    matched_keywords_json TEXT,
    missing_keywords_json TEXT,
    match_score REAL,
    generated_files_json TEXT,
    key_skills_line TEXT
);

CREATE TABLE IF NOT EXISTS salary_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_job_id INTEGER REFERENCES target_jobs(id) ON DELETE SET NULL,
    role_query TEXT,
    location_query TEXT,
    created_at TEXT NOT NULL,
    histogram_json TEXT,
    history_json TEXT,
    ctc_low REAL,
    ctc_median REAL,
    ctc_high REAL,
    deduction_pct_low REAL,
    deduction_pct_high REAL,
    inhand_low REAL,
    inhand_high REAL,
    disclaimer TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    config.ensure_data_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
