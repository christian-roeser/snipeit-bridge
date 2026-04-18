import sqlite3
from datetime import datetime, timezone
from config import config


def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    # Row enables column-name access (row["id"]) instead of index-based (row[0]).
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                items_processed INTEGER DEFAULT 0,
                error_msg TEXT
            );
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES sync_runs(id)
            );
            CREATE TABLE IF NOT EXISTS asset_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                snipeit_id INTEGER NOT NULL,
                last_synced TEXT NOT NULL,
                UNIQUE(source, source_id)
            );
        """)
        # Syncs run synchronously in the request thread — any "running" row at
        # startup is an orphan from a crashed/killed process and will never finish.
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE sync_runs SET status='error', finished_at=?, error_msg='Interrupted (process restart)' WHERE status='running'",
            (now,),
        )


def begin_run(source):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO sync_runs (source, started_at, status) VALUES (?, ?, 'running')",
            (source, now),
        )
        return cur.lastrowid


def end_run(run_id, status, items=0, error=None):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE sync_runs SET finished_at=?, status=?, items_processed=?, error_msg=? WHERE id=?",
            (now, status, items, error, run_id),
        )


def has_errors(run_id):
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM sync_log WHERE run_id=? AND level='ERROR'",
            (run_id,),
        ).fetchone()
        return (row[0] if row else 0) > 0


def log(run_id, level, message):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sync_log (run_id, level, message, timestamp) VALUES (?, ?, ?, ?)",
            (run_id, level, message, now),
        )


def get_mapping(source, source_id):
    with _conn() as conn:
        row = conn.execute(
            "SELECT snipeit_id FROM asset_mapping WHERE source=? AND source_id=?",
            (source, source_id),
        ).fetchone()
        return row["snipeit_id"] if row else None


def set_mapping(source, source_id, snipeit_id):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        # SQLite upsert: insert or overwrite on the unique (source, source_id) constraint.
        conn.execute(
            """INSERT INTO asset_mapping (source, source_id, snipeit_id, last_synced)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(source, source_id) DO UPDATE SET snipeit_id=excluded.snipeit_id, last_synced=excluded.last_synced""",
            (source, source_id, snipeit_id, now),
        )


def get_runs():
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 200"
        ).fetchall()


def get_last_run(source):
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM sync_runs WHERE source=? ORDER BY started_at DESC LIMIT 1",
            (source,),
        ).fetchone()


def get_last_successful_run(source):
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM sync_runs WHERE source=? AND status='success' ORDER BY started_at DESC LIMIT 1",
            (source,),
        ).fetchone()


def get_logs(run_id):
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM sync_log WHERE run_id=? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
