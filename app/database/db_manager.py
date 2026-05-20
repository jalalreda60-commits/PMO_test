"""
Database Manager — persistent connection singleton + WAL mode for speed.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.path.expanduser("~")) / "pmo_app_data" / "pmo_database.db"

# ── Persistent connection singleton ──────────────────────────────────────────
# Re-using a single connection eliminates open/close overhead on every call.
# SQLite is single-process here so this is safe.
_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is not None:
        return _connection
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode: reads don't block writes; much faster for a desktop app.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous  = NORMAL")   # safe with WAL
    conn.execute("PRAGMA cache_size   = -8000")    # 8 MB page cache
    conn.execute("PRAGMA temp_store   = MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")
    _connection = conn
    return conn


def initialize_database():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    UNIQUE NOT NULL,
            name            TEXT    NOT NULL,
            status          TEXT    DEFAULT 'Active',
            phase           TEXT    DEFAULT 'Phase 1',
            priority        TEXT    DEFAULT 'Medium',
            manager         TEXT,
            department      TEXT,
            client          TEXT,
            start_date      TEXT,
            end_date        TEXT,
            progress        REAL    DEFAULT 0,
            description     TEXT,
            nbr_ref         INTEGER DEFAULT 1,
            ref_names       TEXT    DEFAULT '',
            lifetime_years  INTEGER DEFAULT 5,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        )
    """)
    for col, dfn in [("nbr_ref","INTEGER DEFAULT 1"),("lifetime_years","INTEGER DEFAULT 5"),("ref_names","TEXT DEFAULT ''")]:
        try: c.execute(f"ALTER TABLE projects ADD COLUMN {col} {dfn}")
        except: pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            budget_type     TEXT    NOT NULL DEFAULT 'CPT Cash',
            planned_budget  REAL    DEFAULT 0,
            actual_cost     REAL    DEFAULT 0,
            remaining       REAL    DEFAULT 0,
            cost_variance   REAL    DEFAULT 0,
            UNIQUE(project_id, budget_type),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS gate_dates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            phase           TEXT    NOT NULL,
            gate_date       TEXT,
            status          TEXT    DEFAULT 'Pending',
            UNIQUE(project_id, phase),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS phase_actions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            phase           TEXT    NOT NULL,
            action_name     TEXT    NOT NULL,
            lead_time_weeks REAL    DEFAULT 0,
            start_date      TEXT,
            end_date        TEXT,
            status          TEXT    DEFAULT 'Open',
            sort_order      INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS risks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            description     TEXT,
            impact          TEXT    DEFAULT 'Medium',
            probability     TEXT    DEFAULT 'Medium',
            mitigation      TEXT,
            owner           TEXT,
            status          TEXT    DEFAULT 'Open',
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            content         TEXT,
            author          TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS volumes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            year_label      TEXT    NOT NULL,
            volume          REAL    DEFAULT 0,
            UNIQUE(project_id, year_label),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS industrialisation_planning (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id        TEXT    NOT NULL,
            department        TEXT    NOT NULL,
            action            TEXT    NOT NULL,
            status            TEXT    DEFAULT 'Open',
            start_date        TEXT,
            lead_time_weeks   REAL    DEFAULT 2,
            end_date          TEXT,
            pct_complete      REAL    DEFAULT 0,
            sort_order        INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        )
    """)

    _migrate_industrialisation(c)

    c.execute("""
        CREATE TABLE IF NOT EXISTS rar_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            ref_name        TEXT    NOT NULL,
            planned_week    TEXT,
            shift           TEXT,
            score_1st       REAL,
            score_1st_month INTEGER,
            score_1st_year  INTEGER,
            score_1st_locked INTEGER DEFAULT 0,
            score_updated   REAL,
            comment         TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transport_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      TEXT    NOT NULL,
            item_desc       TEXT,
            quantity        INTEGER DEFAULT 1,
            dim_l           REAL,
            dim_w           REAL,
            dim_h           REAL,
            weight_kg       REAL,
            origin          TEXT,
            destination     TEXT,
            transport_mode  TEXT    DEFAULT 'Road',
            cost_eur        REAL    DEFAULT 0,
            pr_number       TEXT,
            entry_date      TEXT    DEFAULT (date('now')),
            entry_month     INTEGER,
            entry_year      INTEGER,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS prpo_entries (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id              TEXT    NOT NULL,
            item                    TEXT,
            rfq_submitted_date      TEXT,
            rfq_forecasted_date     TEXT,
            rfq_reception_date      TEXT,
            rfq_status              TEXT,
            cost                    REAL    DEFAULT 0,
            internal_order          TEXT,
            supplier                TEXT,
            contact                 TEXT,
            pr_number               TEXT,
            pr_approval_flow        TEXT,
            pr_status               TEXT    DEFAULT 'Pending',
            pr_validation_date      TEXT,
            po_forecasted_date      TEXT,
            po_submission_date      TEXT,
            po_number               TEXT,
            po_lead_time_weeks      REAL,
            reception_forecasted    TEXT,
            reception_date          TEXT,
            reception_status        TEXT,
            created_at              TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Indexes for common query patterns ─────────────────────────────────────
    _create_indexes(c)

    conn.commit()
    print(f"[DB] Database initialized at: {DB_PATH}")


def _create_indexes(c):
    """Create indexes to speed up common queries. Safe to call multiple times."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_projects_status   ON projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_projects_phase    ON projects(phase)",
        "CREATE INDEX IF NOT EXISTS idx_budget_project    ON budget(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_actions_project   ON phase_actions(project_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_risks_project     ON risks(project_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_gate_project      ON gate_dates(project_id, gate_date)",
        "CREATE INDEX IF NOT EXISTS idx_transport_project ON transport_entries(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_rar_project       ON rar_entries(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_kpi_scores        ON kpi_monthly_scores(kpi_id, year, month)",
    ]
    for sql in indexes:
        try:
            c.execute(sql)
        except Exception:
            pass


def _migrate_industrialisation(c):
    for col, dfn in [
        ("start_date",      "TEXT"),
        ("end_date",        "TEXT"),
        ("lead_time_weeks", "REAL DEFAULT 2"),
        ("pct_complete",    "REAL DEFAULT 0"),
    ]:
        try:
            c.execute(f"ALTER TABLE industrialisation_planning ADD COLUMN {col} {dfn}")
        except Exception:
            pass

    try:
        c.execute(
            "SELECT id, start_week, lead_time_weeks FROM industrialisation_planning "
            "WHERE start_date IS NULL"
        )
        rows = c.fetchall()
        if rows:
            from datetime import date, timedelta
            yr = date.today().year
            for row in rows:
                try:
                    sw = int(row["start_week"] or 1)
                except Exception:
                    sw = 1
                lt = float(row["lead_time_weeks"] or 2)
                try:
                    sd = date.fromisocalendar(yr, max(1, min(sw, 52)), 1)
                except Exception:
                    sd = date.today()
                ed = sd + timedelta(weeks=lt)
                c.execute(
                    "UPDATE industrialisation_planning SET start_date=?, end_date=? WHERE id=?",
                    (sd.isoformat(), ed.isoformat(), row["id"])
                )
    except Exception:
        pass


def initialize_kpi_tables():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS kpis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            category    TEXT    NOT NULL,
            unit        TEXT    DEFAULT '%',
            target      REAL    DEFAULT 100,
            description TEXT,
            sort_order  INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS kpi_monthly_scores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_id      INTEGER NOT NULL,
            year        INTEGER NOT NULL,
            month       INTEGER NOT NULL,
            score       REAL,
            target      REAL,
            comment     TEXT,
            UNIQUE(kpi_id, year, month),
            FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE
        )
    """)

    _create_indexes(c)

    conn.commit()


def _seed_kpi(c, name, category, unit, target, description, sort_order=0):
    """Insert a KPI row only if it doesn't already exist."""
    c.execute(
        "INSERT OR IGNORE INTO kpis "
        "(name, category, unit, target, description, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, category, unit, target, description, sort_order),
    )
