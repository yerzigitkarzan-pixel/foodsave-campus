"""SQLite storage, explicit transactions and durable integrity constraints."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS organizations(
 id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,short_name TEXT NOT NULL,
 type TEXT NOT NULL,address TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,full_name TEXT NOT NULL,
 password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('operator','reviewer')),
 organization_id INTEGER REFERENCES organizations(id),active INTEGER NOT NULL DEFAULT 1,
 CHECK(role='reviewer' OR organization_id IS NOT NULL));
CREATE TABLE IF NOT EXISTS methods(
 id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,factor TEXT,
 priority INTEGER NOT NULL DEFAULT 5,note TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS waste_types(
 id INTEGER PRIMARY KEY,name TEXT NOT NULL,unit TEXT NOT NULL CHECK(unit IN ('kg','l')),
 category TEXT NOT NULL,recyclability TEXT NOT NULL CHECK(recyclability IN ('yes','partial','no')),
 default_method_id INTEGER REFERENCES methods(id),organization_id INTEGER REFERENCES organizations(id),
 density_kg_per_l TEXT,factor_tbo TEXT,source_note TEXT NOT NULL DEFAULT '',
 coefficient_source TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS org_waste_types(
 organization_id INTEGER NOT NULL REFERENCES organizations(id),
 waste_type_id INTEGER NOT NULL REFERENCES waste_types(id),PRIMARY KEY(organization_id,waste_type_id));
CREATE TABLE IF NOT EXISTS reports(
 id INTEGER PRIMARY KEY,organization_id INTEGER NOT NULL REFERENCES organizations(id),period TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','submitted','in_review','returned','accepted')),
 revision INTEGER NOT NULL DEFAULT 1,created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
 submitted_at TEXT,reviewer_id INTEGER REFERENCES users(id),decided_at TEXT,last_comment TEXT,
 UNIQUE(organization_id,period));
CREATE TABLE IF NOT EXISTS entries(
 id INTEGER PRIMARY KEY,report_id INTEGER NOT NULL REFERENCES reports(id),date TEXT NOT NULL,
 waste_type_id INTEGER NOT NULL REFERENCES waste_types(id),quantity TEXT NOT NULL,
 method_id INTEGER NOT NULL REFERENCES methods(id),responsible_user_id INTEGER NOT NULL REFERENCES users(id),
 snapshot TEXT NOT NULL,client_request_id TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 reason_code TEXT NOT NULL DEFAULT 'unspecified',note TEXT NOT NULL DEFAULT '',
 UNIQUE(report_id,client_request_id));
CREATE TABLE IF NOT EXISTS service_days(
 report_id INTEGER NOT NULL REFERENCES reports(id),date TEXT NOT NULL,
 portions INTEGER NOT NULL CHECK(typeof(portions)='integer' AND portions>=0 AND portions<=100000),
 updated_by INTEGER NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL,
 PRIMARY KEY(report_id,date));
CREATE TABLE IF NOT EXISTS report_history(
 id INTEGER PRIMARY KEY,report_id INTEGER NOT NULL REFERENCES reports(id),action TEXT NOT NULL,
 from_status TEXT,to_status TEXT,actor_id INTEGER NOT NULL REFERENCES users(id),comment TEXT NOT NULL DEFAULT '',
 timestamp TEXT NOT NULL,details TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS sessions(
 id_hash TEXT PRIMARY KEY,csrf_token TEXT NOT NULL,user_id INTEGER REFERENCES users(id),
 created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_entries_report_date ON entries(report_id,date);
CREATE INDEX IF NOT EXISTS idx_reports_org_status ON reports(organization_id,status,period);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_service_days_date ON service_days(date);
"""

@contextmanager
def connection(db_path, write=False):
    conn=sqlite3.connect(str(db_path),timeout=15,isolation_level=None)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    try:
        if write: conn.execute('BEGIN IMMEDIATE')
        yield conn
        if write: conn.commit()
    except Exception:
        if write: conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with connection(db_path) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(SCHEMA)
    # Additive migration: existing measurements retain "unspecified" and an
    # empty note. No reasons or service counts are inferred from old records.
    with connection(db_path,write=True) as conn:
        columns={row['name'] for row in conn.execute('PRAGMA table_info(entries)')}
        if 'reason_code' not in columns:
            conn.execute("ALTER TABLE entries ADD COLUMN reason_code TEXT NOT NULL DEFAULT 'unspecified'")
        if 'note' not in columns:
            conn.execute("ALTER TABLE entries ADD COLUMN note TEXT NOT NULL DEFAULT ''")

def setting(conn,key,default=None):
    row=conn.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return row['value'] if row else default
