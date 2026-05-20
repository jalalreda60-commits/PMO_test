"""
Project Model - Full CRUD for all entities (updated schema).
"""
from __future__ import annotations
from app.database.db_manager import get_connection

PHASES = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]

PHASE_ACTIONS = {
    "Phase 1": [
        "Product/Technical Feasibility (Specification analysis)",
        "Process Feasibility & Capacity & Environment Rules",
        "Cost Consolidation (eBOM + Manufacturing + Logistic + Validation)",
        "Quotation Approval (RFQa Sign off)",
        "Gate 1 Exit Review",
    ],
    "Phase 2": [
        "Program Kick-off Meeting",
        "Prototype Build Feasibility Review & QC Point Defined",
        "DFMEA Conducted",
        "Design Freeze (3D & 2D Agreed)",
        "eBOM Released",
        "2D Drawings (Sub-Assy & Components)",
        "Process Validation Plan Definition",
        "DVP&R Completion for DV",
        "Specification Tooling and Equipment",
        "Nominate Component Suppliers (SOQ Signed)",
        "Nominate Equipment, Tooling & Gage Suppliers",
        "Capex Kick off / Submission / Approval",
        "Create RFQn & Confirm Profitability Baseline",
        "Gate 2 Exit Review",
    ],
    "Phase 3": [
        "Investment Kick-Off / Submission and Approval",
        "Kick Off Tooling Meeting & Issue Product Launch Auth.",
        "Issue SNL & Raise Order Components (PO&TO)",
        "Order Tooling, Equipment & Gages (PO&TO)",
        "PFMEA Update (Final)",
        "Manufacturing BOM (mBOM)",
        "Internal Run at Rate",
        "Process Validation (PV) Testing & Report",
        "Customer PPAP Preparation & Submission",
        "Production Purchase Order (PO) Received",
        "Update Commercial Follow Up & Confirm Cost Target",
        "Gate 3 Exit Review",
    ],
    "Phase 4": [
        "Complete Plant Program Readiness",
        "PSW Signed by Customer",
        "Run at Rate Actions Closure",
        "Safe Launch Management Review",
        "Update Commercial Follow Up at SOP",
        "Gate 4 Exit Review",
    ],
    "Phase 5": [
        "Long Run Production Results",
        "Long Run Quality Results",
        "Confirm Profitability Alignment",
        "Gate 5 Exit Review",
    ],
}

BUDGET_TYPES = ["CPT Cash", "CAPEX", "ED&T Amortization"]

# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

def get_all_projects(filters=None):
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT * FROM projects"
    params = []
    conditions = []
    if filters:
        if filters.get("status"):
            conditions.append("status = ?"); params.append(filters["status"])
        if filters.get("priority"):
            conditions.append("priority = ?"); params.append(filters["priority"])
        if filters.get("phase"):
            conditions.append("phase = ?"); params.append(filters["phase"])
        if filters.get("search"):
            conditions.append("(name LIKE ? OR project_id LIKE ? OR client LIKE ?)")
            s = f"%{filters['search']}%"; params.extend([s, s, s])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    return rows


def get_project(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    row = c.fetchone()
    return dict(row) if row else None


def upsert_project(data):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM projects WHERE project_id = ?", (data["project_id"],))
    if c.fetchone():
        c.execute("""UPDATE projects SET name=?,status=?,phase=?,priority=?,manager=?,
            department=?,client=?,start_date=?,end_date=?,progress=?,description=?,
            nbr_ref=?,lifetime_years=?,ref_names=?,updated_at=datetime('now') WHERE project_id=?""",
            (data.get("name"), data.get("status","Active"), data.get("phase","Phase 1"),
             data.get("priority","Medium"), data.get("manager"), data.get("department"),
             data.get("client"), data.get("start_date"), data.get("end_date"),
             data.get("progress",0), data.get("description"),
             data.get("nbr_ref",1), data.get("lifetime_years",5), data.get("ref_names",""), data["project_id"]))
    else:
        c.execute("""INSERT INTO projects
            (project_id,name,status,phase,priority,manager,department,client,
             start_date,end_date,progress,description,nbr_ref,lifetime_years,ref_names)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["project_id"], data.get("name"), data.get("status","Active"),
             data.get("phase","Phase 1"), data.get("priority","Medium"),
             data.get("manager"), data.get("department"), data.get("client"),
             data.get("start_date"), data.get("end_date"), data.get("progress",0),
             data.get("description"), data.get("nbr_ref",1), data.get("lifetime_years",5), data.get("ref_names","")))
    conn.commit()
    return data["project_id"]


def delete_project(project_id):
    conn = get_connection()
    conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
    conn.commit()


def get_dashboard_stats(project_filter=None):
    conn = get_connection()
    c = conn.cursor()
    if project_filter:
        c.execute("SELECT COUNT(*) as total FROM projects WHERE project_id=?", (project_filter,))
    else:
        c.execute("SELECT COUNT(*) as total FROM projects")
    total = c.fetchone()["total"]
    if project_filter:
        c.execute("SELECT status, COUNT(*) as cnt FROM projects WHERE project_id=? GROUP BY status", (project_filter,))
    else:
        c.execute("SELECT status, COUNT(*) as cnt FROM projects GROUP BY status")
    status_counts = {r["status"]: r["cnt"] for r in c.fetchall()}

    pid_clause = "AND b.project_id=?" if project_filter else ""
    params = (project_filter,) if project_filter else ()
    c.execute(f"""SELECT SUM(b.planned_budget) as pb, SUM(b.actual_cost) as ac
                  FROM budget b WHERE 1=1 {pid_clause}""", params)
    brow = c.fetchone()
    planned = brow["pb"] or 0
    actual  = brow["ac"] or 0

    pid_r = "AND r.project_id=?" if project_filter else ""
    c.execute(f"SELECT COUNT(*) as cnt FROM risks r WHERE r.status='Open' {pid_r}", params)
    open_risks = c.fetchone()["cnt"]

    # Open actions — only count actions in the project's current phase
    if project_filter:
        c.execute("""
            SELECT COUNT(*) as cnt
            FROM phase_actions a
            JOIN projects p ON a.project_id = p.project_id
            WHERE a.status = 'Open'
              AND a.phase  = p.phase
              AND a.project_id = ?
        """, (project_filter,))
    else:
        c.execute("""
            SELECT COUNT(*) as cnt
            FROM phase_actions a
            JOIN projects p ON a.project_id = p.project_id
            WHERE a.status = 'Open'
              AND a.phase  = p.phase
        """)
    open_actions = c.fetchone()["cnt"]

    # Next gate date
    pid_g = "AND g.project_id=?" if project_filter else ""
    c.execute(f"""SELECT g.gate_date, g.phase, p.name as project_name
                  FROM gate_dates g JOIN projects p ON g.project_id=p.project_id
                  WHERE g.gate_date >= date('now') AND g.status != 'Completed' {pid_g}
                  ORDER BY g.gate_date ASC LIMIT 5""", params)
    next_gates = [dict(r) for r in c.fetchall()]

    if project_filter:
        c.execute("""
            SELECT a.action_name, a.end_date, a.status, p.name as project_name
            FROM phase_actions a
            JOIN projects p ON a.project_id = p.project_id
            WHERE a.end_date >= date('now')
              AND a.status   = 'Open'
              AND a.phase    = p.phase
              AND a.project_id = ?
            ORDER BY a.end_date ASC LIMIT 8
        """, (project_filter,))
    else:
        c.execute("""
            SELECT a.action_name, a.end_date, a.status, p.name as project_name
            FROM phase_actions a
            JOIN projects p ON a.project_id = p.project_id
            WHERE a.end_date >= date('now')
              AND a.status   = 'Open'
              AND a.phase    = p.phase
            ORDER BY a.end_date ASC LIMIT 8
        """)
    upcoming = [dict(r) for r in c.fetchall()]

    # Next gate in current month
    import datetime
    now = datetime.date.today()
    cur_month_start = now.strftime("%Y-%m-01")
    cur_month_end   = (now.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    cur_month_end   = cur_month_end.strftime("%Y-%m-%d")

    pid_gm = "AND g.project_id=?" if project_filter else ""
    c.execute(f"""SELECT g.gate_date, g.phase, p.name as project_name
                  FROM gate_dates g JOIN projects p ON g.project_id=p.project_id
                  WHERE g.gate_date BETWEEN ? AND ?
                  AND g.status != 'Completed' {pid_gm}
                  ORDER BY g.gate_date ASC LIMIT 1""",
              (cur_month_start, cur_month_end) + params)
    _ngrow = c.fetchone()
    next_gate_this_month = dict(_ngrow) if _ngrow else None

    # Planned R@R current month — parse "WKxx-YYYY" → ISO week → check month
    import datetime as _dt
    now = _dt.date.today()
    try:
        pid_rar = "AND project_id=?" if project_filter else ""
        c.execute(f"SELECT planned_week FROM rar_entries WHERE planned_week IS NOT NULL AND planned_week!='' {pid_rar}", params)
        rar_rows = c.fetchall()
        planned_rar = 0
        for rrow in rar_rows:
            pw = (rrow["planned_week"] or "").strip()   # e.g. "WK14-2026"
            try:
                parts = pw.upper().replace("WK", "").split("-")
                if len(parts) == 2:
                    wk_num = int(parts[0])
                    yr     = int(parts[1])
                    # ISO week to date: Monday of that week
                    week_date = _dt.datetime.strptime(f"{yr}-W{wk_num:02d}-1", "%Y-W%W-%w").date()
                    if week_date.month == now.month and week_date.year == now.year:
                        planned_rar += 1
            except (ValueError, TypeError):
                pass
    except Exception:
        planned_rar = 0

    return {
        "total": total,
        "active": status_counts.get("Active", 0),
        "completed": status_counts.get("Completed", 0),
        "delayed": status_counts.get("Delayed", 0),
        "at_risk": status_counts.get("At Risk", 0),
        "on_hold": status_counts.get("On Hold", 0),
        "planned_budget": planned,
        "actual_cost": actual,
        "open_risks": open_risks,
        "open_actions": open_actions,
        "status_counts": status_counts,
        "next_gates": next_gates,
        "next_gate_this_month": next_gate_this_month,
        "planned_rar_this_month": planned_rar,
        "upcoming_deadlines": upcoming,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Budget (per type)
# ─────────────────────────────────────────────────────────────────────────────

def get_all_budgets(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM budget WHERE project_id=?", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    return rows

def get_all_budgets_bulk(project_ids=None):
    """Fetch all budgets in a single query. Much faster than N calls to get_all_budgets."""
    conn = get_connection()
    c = conn.cursor()
    if project_ids:
        placeholders = ",".join("?" * len(project_ids))
        c.execute(f"SELECT * FROM budget WHERE project_id IN ({placeholders})", project_ids)
    else:
        c.execute("SELECT * FROM budget")
    rows = [dict(r) for r in c.fetchall()]
    # Group by project_id for easy lookup
    result = {}
    for r in rows:
        result.setdefault(r["project_id"], []).append(r)
    return result


def upsert_budget(data):
    conn = get_connection()
    c = conn.cursor()
    planned = float(data.get("planned_budget") or 0)
    actual  = float(data.get("actual_cost") or 0)
    remaining = planned - actual
    variance  = planned - actual
    c.execute("SELECT id FROM budget WHERE project_id=? AND budget_type=?",
              (data["project_id"], data["budget_type"]))
    if c.fetchone():
        c.execute("""UPDATE budget SET planned_budget=?,actual_cost=?,remaining=?,cost_variance=?
                     WHERE project_id=? AND budget_type=?""",
                  (planned, actual, remaining, variance, data["project_id"], data["budget_type"]))
    else:
        c.execute("""INSERT INTO budget (project_id,budget_type,planned_budget,actual_cost,remaining,cost_variance)
                     VALUES (?,?,?,?,?,?)""",
                  (data["project_id"], data["budget_type"], planned, actual, remaining, variance))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Gate Dates
# ─────────────────────────────────────────────────────────────────────────────

def get_gate_dates(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM gate_dates WHERE project_id=? ORDER BY phase", (project_id,))
    rows = {r["phase"]: dict(r) for r in c.fetchall()}
    return rows

def upsert_gate_date(project_id, phase, gate_date, status="Pending"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM gate_dates WHERE project_id=? AND phase=?", (project_id, phase))
    if c.fetchone():
        c.execute("UPDATE gate_dates SET gate_date=?,status=? WHERE project_id=? AND phase=?",
                  (gate_date, status, project_id, phase))
    else:
        c.execute("INSERT INTO gate_dates (project_id,phase,gate_date,status) VALUES (?,?,?,?)",
                  (project_id, phase, gate_date, status))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Phase Actions
# ─────────────────────────────────────────────────────────────────────────────

def get_phase_actions(project_id, phase=None):
    conn = get_connection()
    c = conn.cursor()
    if phase:
        c.execute("SELECT * FROM phase_actions WHERE project_id=? AND phase=? ORDER BY sort_order",
                  (project_id, phase))
    else:
        c.execute("SELECT * FROM phase_actions WHERE project_id=? ORDER BY phase, sort_order",
                  (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    return rows

def upsert_phase_action(data):
    conn = get_connection()
    c = conn.cursor()
    if data.get("id"):
        c.execute("""UPDATE phase_actions SET action_name=?,lead_time_weeks=?,start_date=?,
                     end_date=?,status=?,sort_order=? WHERE id=?""",
                  (data.get("action_name"), data.get("lead_time_weeks",0),
                   data.get("start_date"), data.get("end_date"),
                   data.get("status","Open"), data.get("sort_order",0), data["id"]))
    else:
        c.execute("""INSERT INTO phase_actions
                     (project_id,phase,action_name,lead_time_weeks,start_date,end_date,status,sort_order)
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (data["project_id"], data["phase"], data.get("action_name"),
                   data.get("lead_time_weeks",0), data.get("start_date"), data.get("end_date"),
                   data.get("status","Open"), data.get("sort_order",0)))
    conn.commit()

def update_action_status(action_id, status):
    conn = get_connection()
    conn.execute("UPDATE phase_actions SET status=? WHERE id=?", (status, action_id))
    conn.commit()

def delete_phase_action(action_id):
    conn = get_connection()
    conn.execute("DELETE FROM phase_actions WHERE id=?", (action_id,))
    conn.commit()

def insert_default_phase_actions(project_id):
    """Insert all standard actions for all 5 phases."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM phase_actions WHERE project_id=?", (project_id,))
    if c.fetchone()["cnt"] > 0:
        return
    for phase, actions in PHASE_ACTIONS.items():
        for i, name in enumerate(actions):
            c.execute("""INSERT INTO phase_actions (project_id,phase,action_name,status,sort_order)
                         VALUES (?,?,?,?,?)""", (project_id, phase, name, "Open", i))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Risks
# ─────────────────────────────────────────────────────────────────────────────

def get_risks(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM risks WHERE project_id=?", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    return rows

def upsert_risk(data):
    conn = get_connection()
    c = conn.cursor()
    if data.get("id"):
        c.execute("""UPDATE risks SET description=?,impact=?,probability=?,mitigation=?,owner=?,status=?
                     WHERE id=?""",
                  (data.get("description"), data.get("impact","Medium"), data.get("probability","Medium"),
                   data.get("mitigation"), data.get("owner"), data.get("status","Open"), data["id"]))
    else:
        c.execute("""INSERT INTO risks (project_id,description,impact,probability,mitigation,owner,status)
                     VALUES (?,?,?,?,?,?,?)""",
                  (data["project_id"], data.get("description"), data.get("impact","Medium"),
                   data.get("probability","Medium"), data.get("mitigation"),
                   data.get("owner"), data.get("status","Open")))
    conn.commit()

def delete_risk(risk_id):
    conn = get_connection()
    conn.execute("DELETE FROM risks WHERE id=?", (risk_id,))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Notes
# ─────────────────────────────────────────────────────────────────────────────

def get_notes(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM notes WHERE project_id=? ORDER BY created_at DESC", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    return rows

def add_note(project_id, content, author="User"):
    conn = get_connection()
    conn.execute("INSERT INTO notes (project_id,content,author) VALUES (?,?,?)",
                 (project_id, content, author))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Annual Volumes
# ─────────────────────────────────────────────────────────────────────────────

def get_volumes(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM volumes WHERE project_id=? ORDER BY year_label", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    return rows

def upsert_volume(project_id, year_label, volume):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM volumes WHERE project_id=? AND year_label=?", (project_id, year_label))
    if c.fetchone():
        c.execute("UPDATE volumes SET volume=? WHERE project_id=? AND year_label=?",
                  (volume, project_id, year_label))
    else:
        c.execute("INSERT INTO volumes (project_id,year_label,volume) VALUES (?,?,?)",
                  (project_id, year_label, volume))
    conn.commit()

def delete_volume(project_id, year_label):
    conn = get_connection()
    conn.execute("DELETE FROM volumes WHERE project_id=? AND year_label=?", (project_id, year_label))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Compatibility aliases used by excel_import and export_service
# ─────────────────────────────────────────────────────────────────────────────

def upsert_milestone(data: dict):
    """
    Upsert a milestone.  Milestones map to gate_dates (one gate per phase).
    Falls back to inserting a phase_action when the milestone is not a named
    Phase gate (e.g. free-text milestone names from an imported sheet).
    """
    project_id = data.get("project_id", "")
    name       = data.get("name", "")
    due_date   = data.get("due_date", "")
    status     = data.get("status", "Pending") or "Pending"
    phase      = data.get("phase", "")

    # If the name looks like a phase gate, store it in gate_dates
    if phase in PHASES or any(name.lower().startswith(p.lower()) for p in PHASES):
        target_phase = phase or next(
            (p for p in PHASES if name.lower().startswith(p.lower())), "Phase 1"
        )
        upsert_gate_date(project_id, target_phase, due_date, status)
    else:
        # Store as a phase_action with the milestone name
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id FROM phase_actions WHERE project_id=? AND action_name=?",
            (project_id, name),
        )
        existing = c.fetchone()
        if existing:
            c.execute(
                "UPDATE phase_actions SET end_date=?,status=? WHERE id=?",
                (due_date, status, existing["id"]),
            )
        else:
            c.execute(
                """INSERT INTO phase_actions
                   (project_id, phase, action_name, end_date, status, sort_order)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (project_id, phase or "Phase 1", name, due_date, status),
            )
        conn.commit()


def upsert_action(data: dict):
    """Map imported action rows to phase_actions table."""
    conn = get_connection()
    c = conn.cursor()
    project_id = data.get("project_id", "")
    task_name  = data.get("task_name", "")
    phase      = data.get("phase", "Phase 1") or "Phase 1"
    c.execute(
        "SELECT id FROM phase_actions WHERE project_id=? AND action_name=?",
        (project_id, task_name),
    )
    existing = c.fetchone()
    if existing:
        c.execute(
            "UPDATE phase_actions SET end_date=?,status=?,sort_order=? WHERE id=?",
            (data.get("due_date"), data.get("status", "Open"), data.get("sort_order", 0), existing["id"]),
        )
    else:
        c.execute(
            """INSERT INTO phase_actions
               (project_id, phase, action_name, end_date, status, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, phase, task_name,
             data.get("due_date"), data.get("status", "Open"), data.get("sort_order", 0)),
        )
    conn.commit()


def insert_default_milestones(project_id: str, phase: str = None):
    """Insert default phase actions (called insert_default_milestones for compatibility)."""
    insert_default_phase_actions(project_id)


def get_milestones(project_id: str) -> list:
    """Return gate_dates as a list of dicts (export_service compatibility)."""
    gates = get_gate_dates(project_id)
    return list(gates.values())


def get_budget(project_id: str) -> dict | None:
    """Return the first budget row for a project (export_service compatibility)."""
    rows = get_all_budgets(project_id)
    return rows[0] if rows else None


def get_actions(project_id: str) -> list:
    """Alias for get_phase_actions (export_service compatibility)."""
    return get_phase_actions(project_id)


def sync_volumes_for_project(project_id, lifetime_years):
    """Ensure volume rows exist for Y1..YN, remove extras."""
    conn = get_connection()
    c = conn.cursor()
    expected = [f"Y{i+1}" for i in range(lifetime_years)]
    c.execute("SELECT year_label FROM volumes WHERE project_id=?", (project_id,))
    existing = {r["year_label"] for r in c.fetchall()}
    for yr in expected:
        if yr not in existing:
            c.execute("INSERT INTO volumes (project_id,year_label,volume) VALUES (?,?,0)",
                      (project_id, yr))
    for yr in existing:
        if yr not in expected:
            c.execute("DELETE FROM volumes WHERE project_id=? AND year_label=?", (project_id, yr))
    conn.commit()


# =============================================================================
# Industrialisation Planning — Date-based CRUD
# =============================================================================
# ARCHITECTURE:
#   - start_date (ISO YYYY-MM-DD)  ← user input, stored in DB
#   - lead_time_weeks (REAL)       ← user input, stored in DB
#   - end_date (ISO YYYY-MM-DD)    ← COMPUTED = start_date + lead_time_weeks*7
#   - pct_complete (REAL 0-100)    ← user input
#
# WEEK NUMBERS: computed on read, NEVER stored.
#   week_number = date.isocalendar()[1]
#
# ROLLING WINDOW: Gantt displays W(current-2) to W(current+2) = 5 weeks
# =============================================================================

from datetime import date as _date, timedelta as _timedelta


DEFAULT_INDUSTRIALISATION_ACTIONS = [
    ("Purchasing",           "Quotation"),
    ("PM",                   "Budget on Zpbm"),
    ("Process Engineering",  "PR Creation & validation"),
    ("Purchasing",           "PO Submission"),
    ("Global Buyer",         "Rubber availability in Dolny plant"),
    ("Global Buyer",         "Clamp availability in Dolny plant"),
    ("Global Buyer",         "Sleeve availability in Dolny plant"),
    ("DK team",              "Machines & LT Dev"),
    ("Process Engineering",  "Validation"),
]


# ── Date / Week helpers ───────────────────────────────────────────────────────

def compute_end_date(start_date_iso: str, lead_time_weeks: float) -> str:
    """
    Returns ISO end date = start_date + lead_time_weeks * 7 days.
    Never stored by the user — always auto-computed.
    """
    try:
        sd = _date.fromisoformat(start_date_iso)
    except Exception:
        sd = _date.today()
    ed = sd + _timedelta(weeks=float(lead_time_weeks or 2))
    return ed.isoformat()


def iso_to_display(iso_str: str) -> str:
    """Convert stored ISO date (YYYY-MM-DD) to display format (DD/MM/YYYY)."""
    try:
        d = _date.fromisoformat(iso_str)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return iso_str or ""


def display_to_iso(display_str: str) -> str:
    """
    Convert user-entered date (DD/MM/YYYY or YYYY-MM-DD) to ISO YYYY-MM-DD.
    Raises ValueError on bad input.
    """
    s = (display_str or "").strip()
    if not s:
        return _date.today().isoformat()
    # Already ISO?
    if len(s) == 10 and s[4] == "-":
        _date.fromisoformat(s)  # validate
        return s
    # DD/MM/YYYY
    if len(s) == 10 and s[2] == "/" and s[5] == "/":
        d, m, y = s.split("/")
        return _date(int(y), int(m), int(d)).isoformat()
    raise ValueError(f"Unrecognised date format: {s!r}")


def date_to_week(iso_str: str) -> int:
    """Return ISO week number (1-52) for a stored date string."""
    try:
        return _date.fromisoformat(iso_str).isocalendar()[1]
    except Exception:
        return _date.today().isocalendar()[1]


def current_week() -> int:
    """Current ISO week number."""
    return _date.today().isocalendar()[1]


def current_year() -> int:
    return _date.today().year


def week_to_monday_iso(week: int, year: int = None) -> str:
    """Return ISO date of Monday for a given ISO week number."""
    if year is None:
        year = current_year()
    try:
        return _date.fromisocalendar(year, max(1, min(week, 52)), 1).isoformat()
    except Exception:
        return _date.today().isoformat()


# ── Normalise a raw DB row into a clean dict ──────────────────────────────────

def _normalise_indus_row(row: dict) -> dict:
    """
    Normalise a raw DB row:
      - Ensure start_date and end_date are valid ISO strings
      - Compute end_date from start_date + lead_time_weeks (authoritative)
      - Compute start_week and end_week from dates (read-only, not stored)
    """
    lt = float(row.get("lead_time_weeks") or 2)

    # Resolve start_date
    sd_raw = row.get("start_date")
    if sd_raw:
        try:
            sd = _date.fromisoformat(sd_raw).isoformat()
        except Exception:
            sd = _date.today().isoformat()
    else:
        sd = _date.today().isoformat()

    # end_date is ALWAYS recomputed — never trust the cached value
    ed = compute_end_date(sd, lt)

    return {
        **row,
        "start_date":       sd,
        "end_date":         ed,          # authoritative computed value
        "lead_time_weeks":  lt,
        "pct_complete":     float(row.get("pct_complete") or 0),
        # Convenience: week numbers derived from dates
        "start_week":       date_to_week(sd),
        "end_week":         date_to_week(ed),
        # Display helpers
        "start_date_disp":  iso_to_display(sd),
        "end_date_disp":    iso_to_display(ed),
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get_industrialisation_actions(project_id: str) -> list:
    """Return all industrialisation actions, normalised, ordered by sort_order."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM industrialisation_planning "
        "WHERE project_id=? ORDER BY sort_order, id",
        (project_id,)
    )
    rows = [_normalise_indus_row(dict(r)) for r in c.fetchall()]
    return rows


def insert_default_industrialisation_actions(project_id: str):
    """
    Seed the 9 default actions if none exist yet.
    Start dates are staggered from today (Monday + i*2 weeks).
    Lead time defaults to 2 weeks.  End date auto-computed.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) as cnt FROM industrialisation_planning WHERE project_id=?",
        (project_id,)
    )
    if c.fetchone()["cnt"] == 0:
        # Monday of current week as base
        today = _date.today()
        base = today - _timedelta(days=today.weekday())   # Monday this week
        for i, (dept, action) in enumerate(DEFAULT_INDUSTRIALISATION_ACTIONS):
            sd = (base + _timedelta(weeks=i * 2)).isoformat()
            lt = 2.0
            ed = compute_end_date(sd, lt)
            c.execute(
                """INSERT INTO industrialisation_planning
                   (project_id, department, action, status,
                    start_date, lead_time_weeks, end_date, pct_complete, sort_order)
                   VALUES (?, ?, ?, 'Open', ?, ?, ?, 0, ?)""",
                (project_id, dept, action, sd, lt, ed, i)
            )
    conn.commit()


def add_industrialisation_action(
    project_id:     str,
    department:     str,
    action:         str,
    status:         str   = "Open",
    start_date:     str   = None,
    lead_time:      float = 2.0,
    pct_complete:   float = 0.0,
) -> int:
    """
    Insert a new action.
    start_date must be ISO YYYY-MM-DD (caller uses display_to_iso() to convert).
    end_date is computed here — never passed in.
    """
    if not start_date:
        start_date = _date.today().isoformat()
    end_date = compute_end_date(start_date, lead_time)

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COALESCE(MAX(sort_order),0)+1 FROM industrialisation_planning "
        "WHERE project_id=?",
        (project_id,)
    )
    sort_order = c.fetchone()[0]
    c.execute(
        """INSERT INTO industrialisation_planning
           (project_id, department, action, status,
            start_date, lead_time_weeks, end_date, pct_complete, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, department, action, status,
         start_date, lead_time, end_date, pct_complete, sort_order)
    )
    new_id = c.lastrowid
    conn.commit()
    return new_id


def update_industrialisation_action(
    action_id:    int,
    department:   str,
    action:       str,
    status:       str,
    start_date:   str   = None,
    lead_time:    float = 2.0,
    pct_complete: float = 0.0,
):
    """
    Update an action.
    end_date is recomputed here — never passed in.
    """
    if not start_date:
        start_date = _date.today().isoformat()
    end_date = compute_end_date(start_date, lead_time)

    conn = get_connection()
    conn.execute(
        """UPDATE industrialisation_planning
           SET department=?, action=?, status=?,
               start_date=?, lead_time_weeks=?, end_date=?,
               pct_complete=?
           WHERE id=?""",
        (department, action, status,
         start_date, lead_time, end_date,
         pct_complete, action_id)
    )
    conn.commit()


def delete_industrialisation_action(action_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM industrialisation_planning WHERE id=?", (action_id,))
    conn.commit()


def reorder_industrialisation_actions(project_id: str, ordered_ids: list) -> None:
    """
    Persist a new sort_order for industrialisation actions.
    ordered_ids: list of action IDs in the new display order (top → bottom).
    """
    conn = get_connection()
    c = conn.cursor()
    for new_pos, action_id in enumerate(ordered_ids):
        c.execute(
            "UPDATE industrialisation_planning SET sort_order=? WHERE id=? AND project_id=?",
            (new_pos, action_id, project_id)
        )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# KPI Model Functions
# ══════════════════════════════════════════════════════════════════════════════

def get_all_kpis():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM kpis WHERE active=1 ORDER BY sort_order, name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_kpi(kpi_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM kpis WHERE id=?", (kpi_id,)).fetchone()
    return dict(row) if row else None


def upsert_kpi(data):
    with get_connection() as conn:
        if data.get("id"):
            conn.execute("""
                UPDATE kpis SET name=?,category=?,unit=?,target=?,description=?,sort_order=?
                WHERE id=?
            """, (data["name"], data["category"], data["unit"], data["target"],
                  data.get("description",""), data.get("sort_order",0), data["id"]))
        else:
            conn.execute("""
                INSERT INTO kpis (name,category,unit,target,description,sort_order)
                VALUES (?,?,?,?,?,?)
            """, (data["name"], data["category"], data.get("unit","%"),
                  data.get("target",100), data.get("description",""), data.get("sort_order",0)))
        conn.commit()


def delete_kpi(kpi_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM kpis WHERE id=?", (kpi_id,))
        conn.commit()


def get_kpi_scores(kpi_id, year=None):
    with get_connection() as conn:
        if year:
            rows = conn.execute(
                "SELECT * FROM kpi_monthly_scores WHERE kpi_id=? AND year=? ORDER BY month",
                (kpi_id, year)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM kpi_monthly_scores WHERE kpi_id=? ORDER BY year,month",
                (kpi_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def upsert_kpi_score(kpi_id, year, month, score, target=None, comment=""):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO kpi_monthly_scores (kpi_id,year,month,score,target,comment)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(kpi_id,year,month) DO UPDATE SET
                score=excluded.score, target=excluded.target, comment=excluded.comment
        """, (kpi_id, year, month, score, target, comment))
        conn.commit()


def get_all_kpi_scores_for_year(year):
    """Returns all KPI scores for a given year joined with KPI metadata."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT k.id, k.name, k.category, k.unit, k.target as kpi_target,
                   s.month, s.score, s.target as month_target, s.comment
            FROM kpis k
            LEFT JOIN kpi_monthly_scores s ON k.id=s.kpi_id AND s.year=?
            WHERE k.active=1
            ORDER BY k.sort_order, k.name, s.month
        """, (year,)).fetchall()
    return [dict(r) for r in rows]


def get_kpi_dashboard_summary(year):
    """Returns latest-month score for each KPI for dashboard cards."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT k.id, k.name, k.category, k.unit, k.target,
                   s.month, s.score, s.comment
            FROM kpis k
            LEFT JOIN kpi_monthly_scores s ON k.id=s.kpi_id
                AND s.year=? AND s.month=(
                    SELECT MAX(month) FROM kpi_monthly_scores
                    WHERE kpi_id=k.id AND year=?
                )
            WHERE k.active=1
            ORDER BY k.category, k.sort_order
        """, (year, year)).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# R@R Model Functions
# ══════════════════════════════════════════════════════════════════════════════

def get_rar_entries(project_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM rar_entries WHERE project_id=? ORDER BY id",
            (project_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def _parse_rar_week_to_month_year(planned_week: str):
    """Parse 'WKxx-YYYY' → (month, year) or None on failure."""
    import datetime as _dt
    try:
        parts = planned_week.upper().replace("WK", "").split("-")
        if len(parts) != 2:
            return None
        wk_num, yr = int(parts[0]), int(parts[1])
        week_date = _dt.datetime.strptime(f"{yr}-W{wk_num:02d}-1", "%Y-W%W-%w").date()
        return week_date.month, week_date.year
    except Exception:
        return None


def _count_planned_rar_for_month(conn, month: int, year: int) -> int:
    """Count all R@R entries whose planned_week falls in the given month/year."""
    rows = conn.execute(
        "SELECT planned_week FROM rar_entries "
        "WHERE planned_week IS NOT NULL AND planned_week != ''"
    ).fetchall()
    count = 0
    for rrow in rows:
        result = _parse_rar_week_to_month_year(rrow[0] or "")
        if result and result == (month, year):
            count += 1
    return count


def _sync_rar_planned_kpi(conn, planned_week: str):
    """Update 'R@R Released vs Planned' KPI for the month implied by planned_week.

    • target  = total number of R@R events *planned* in that month
    • score   = number of R@R entries whose *first score was locked* in that month
    Both values are raw counts (not percentages).
    """
    if not planned_week:
        return
    result = _parse_rar_week_to_month_year(planned_week)
    if result is None:
        return
    month, year = result

    planned_count = _count_planned_rar_for_month(conn, month, year)

    # Released = entries that have a first score registered in that month
    # (locked OR unlocked — a score is "released" as soon as it is entered)
    locked_row = conn.execute("""
        SELECT COUNT(*) as cnt FROM rar_entries
        WHERE score_1st IS NOT NULL
          AND score_1st_year=? AND score_1st_month=?
    """, (year, month)).fetchone()
    released = locked_row["cnt"] if locked_row else 0

    kpi_row = conn.execute(
        "SELECT id FROM kpis WHERE name='R@R Released vs Planned' "
        "   OR name LIKE '%Released vs Planned%' LIMIT 1"
    ).fetchone()
    if kpi_row:
        conn.execute("""
            INSERT INTO kpi_monthly_scores(kpi_id, year, month, score, target, comment)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(kpi_id, year, month) DO UPDATE SET
                score=excluded.score,
                target=excluded.target,
                comment=excluded.comment
        """, (
            kpi_row[0], year, month,
            released,          # actual = count of 1st scores registered
            planned_count,     # target = count of planned R@R events
            f"Released: {released} / Planned: {planned_count}",
        ))
        conn.commit()


def _sync_rar_1st_score_kpi(conn, year: int, month: int):
    """Recalculate the average 1st score for year/month and push it to the
    'R@R 1st Score' KPI monthly entry.

    Rule: ANY entry that has a non-null score_1st and whose score_1st_month /
    score_1st_year match the given month/year contributes to the average —
    regardless of whether the score is locked or not.  This means the KPI
    updates as soon as a first score is entered, not only after locking.
    """
    row = conn.execute(
        "SELECT AVG(score_1st) FROM rar_entries "
        "WHERE score_1st IS NOT NULL "
        "  AND score_1st_year=? AND score_1st_month=?",
        (year, month),
    ).fetchone()
    avg_score = row[0] if row and row[0] is not None else None
    if avg_score is None:
        return

    kpi_row = conn.execute(
        "SELECT id FROM kpis WHERE name='R@R 1st Score' "
        "   OR name LIKE '%R@R 1st Score%' OR name LIKE '%R&R 1st Score%' LIMIT 1"
    ).fetchone()
    if kpi_row:
        conn.execute("""
            INSERT INTO kpi_monthly_scores(kpi_id, year, month, score, target, comment)
            VALUES(?, ?, ?, ?, 90, 'Auto-updated from R@R entries')
            ON CONFLICT(kpi_id, year, month) DO UPDATE SET
                score=excluded.score,
                comment=excluded.comment
        """, (kpi_row[0], year, month, round(avg_score, 2)))
        conn.commit()

    # Also refresh Released vs Planned for every month that has planned entries
    planned_weeks = conn.execute(
        "SELECT DISTINCT planned_week FROM rar_entries "
        "WHERE planned_week IS NOT NULL AND planned_week != ''"
    ).fetchall()
    seen = set()
    for pw_row in planned_weeks:
        result = _parse_rar_week_to_month_year(pw_row[0] or "")
        if result and result not in seen:
            seen.add(result)
            _sync_rar_planned_kpi(conn, pw_row[0])


def upsert_rar_entry(data):
    """Insert or update a R@R entry.

    Business rules
    ──────────────
    • A **new** entry is always saved *unlocked* regardless of whether a
      1st score is supplied.  The score is only locked via the explicit
      🔒 Lock button (``lock_rar_1st_score``).
    • On **edit** of an *already-locked* entry only non-score fields can
      change (planned_week, shift, updated_score, comment).
    • On **edit** of an *unlocked* entry the 1st score may still be
      updated.  The entry remains unlocked until explicitly locked.

    After every save both KPIs are re-synchronised for the affected month:
      – R@R 1st Score (average of locked scores)
      – R@R Released vs Planned (count-based: target=planned, score=released)
    """
    import datetime
    now = datetime.date.today()
    with get_connection() as conn:
        if data.get("id"):
            existing = conn.execute(
                "SELECT score_1st_locked, score_1st_month, score_1st_year, planned_week "
                "FROM rar_entries WHERE id=?",
                (data["id"],),
            ).fetchone()
            locked = existing and existing["score_1st_locked"]
            old_planned_week = existing["planned_week"] if existing else ""

            if locked:
                # Score is frozen – only update non-score fields
                conn.execute("""
                    UPDATE rar_entries
                    SET ref_name=?, planned_week=?, shift=?,
                        score_updated=?, comment=?, updated_at=datetime('now')
                    WHERE id=?
                """, (
                    data["ref_name"], data.get("planned_week", ""),
                    data.get("shift", ""), data.get("score_updated"),
                    data.get("comment", ""), data["id"],
                ))
            else:
                # Entry is still unlocked – update 1st score but keep unlocked.
                # Stamp score_1st_month/year only when a score is being set for
                # the first time (existing month/year is NULL).  Once a month is
                # stamped it must not change on subsequent edits (only locking can
                # update it, and even then only the lock-time month matters).
                new_score = data.get("score_1st")
                had_score = existing and existing["score_1st_month"] is not None

                if new_score is not None and not had_score:
                    # First time a score is registered — stamp current month/year
                    conn.execute("""
                        UPDATE rar_entries
                        SET ref_name=?, planned_week=?, shift=?,
                            score_1st=?,
                            score_1st_month=?, score_1st_year=?,
                            score_updated=?, comment=?, updated_at=datetime('now')
                        WHERE id=?
                    """, (
                        data["ref_name"], data.get("planned_week", ""),
                        data.get("shift", ""),
                        new_score, now.month, now.year,
                        data.get("score_updated"),
                        data.get("comment", ""), data["id"],
                    ))
                elif new_score is None and had_score:
                    # Score cleared — also clear the month stamp
                    conn.execute("""
                        UPDATE rar_entries
                        SET ref_name=?, planned_week=?, shift=?,
                            score_1st=NULL,
                            score_1st_month=NULL, score_1st_year=NULL,
                            score_updated=?, comment=?, updated_at=datetime('now')
                        WHERE id=?
                    """, (
                        data["ref_name"], data.get("planned_week", ""),
                        data.get("shift", ""),
                        data.get("score_updated"),
                        data.get("comment", ""), data["id"],
                    ))
                else:
                    # Score value updated but month stamp already set — preserve it
                    conn.execute("""
                        UPDATE rar_entries
                        SET ref_name=?, planned_week=?, shift=?,
                            score_1st=?,
                            score_updated=?, comment=?, updated_at=datetime('now')
                        WHERE id=?
                    """, (
                        data["ref_name"], data.get("planned_week", ""),
                        data.get("shift", ""),
                        new_score,
                        data.get("score_updated"),
                        data.get("comment", ""), data["id"],
                    ))

            conn.commit()

            # Re-sync KPIs for the old planned week too (in case week changed)
            if old_planned_week and old_planned_week != data.get("planned_week", ""):
                _sync_rar_planned_kpi(conn, old_planned_week)

        else:
            # New entry – always inserted as unlocked.
            # Only stamp score_1st_month/year when a score is actually provided;
            # leave them NULL otherwise so a future edit stamps the right month.
            s1 = data.get("score_1st")
            s1_month = now.month if s1 is not None else None
            s1_year  = now.year  if s1 is not None else None
            conn.execute("""
                INSERT INTO rar_entries
                    (project_id, ref_name, planned_week, shift,
                     score_1st, score_1st_month, score_1st_year, score_1st_locked,
                     score_updated, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                data["project_id"], data["ref_name"],
                data.get("planned_week", ""), data.get("shift", ""),
                s1, s1_month, s1_year,
                data.get("score_updated"), data.get("comment", ""),
            ))
            conn.commit()

        # Always re-sync Released vs Planned for the current planned week
        _sync_rar_planned_kpi(conn, data.get("planned_week", ""))

        # Re-sync the 1st Score KPI.
        # Read the stored score_1st_month/year back from the DB — this is the
        # authoritative "registered month" regardless of which code path ran.
        # For new entries it equals today; for edits it equals when the score
        # was first set (or None if still unset / just cleared).
        entry_id = data.get("id")
        if entry_id:
            refreshed = conn.execute(
                "SELECT score_1st_month, score_1st_year FROM rar_entries WHERE id=?",
                (entry_id,),
            ).fetchone()
            if refreshed and refreshed["score_1st_month"] and refreshed["score_1st_year"]:
                _sync_rar_1st_score_kpi(conn, refreshed["score_1st_year"], refreshed["score_1st_month"])
            # Also re-sync the OLD month in case the score was cleared or
            # the entry previously had a score in a different month
            try:
                if existing and existing["score_1st_month"]:
                    old_m = existing["score_1st_month"]
                    old_y = existing["score_1st_year"]
                    if old_m and old_y:
                        _sync_rar_1st_score_kpi(conn, old_y, old_m)
            except (NameError, TypeError):
                pass
        else:
            # New entry — month was stamped as today if score was provided
            if data.get("score_1st") is not None:
                _sync_rar_1st_score_kpi(conn, now.year, now.month)


def lock_rar_1st_score(rar_id):
    """Lock the 1st score permanently and re-sync both R@R KPIs.

    • Sets score_1st_locked=1 and stamps the current month/year.
    • Recalculates the 'R@R 1st Score' KPI (average of all locked scores
      for the same month) via _sync_rar_1st_score_kpi.
    • Recalculates the 'R@R Released vs Planned' KPI (count-based) via
      _sync_rar_planned_kpi so the Released column increments immediately.
    """
    import datetime
    now = datetime.date.today()
    with get_connection() as conn:
        # Preserve the existing month stamp if a score was already registered
        # (month/year should reflect when the score was *entered*, not when it
        # was locked).  Only fall back to now if the stamp is missing.
        existing_stamp = conn.execute(
            "SELECT score_1st_month, score_1st_year FROM rar_entries WHERE id=?",
            (rar_id,),
        ).fetchone()
        lock_month = (existing_stamp["score_1st_month"] or now.month) if existing_stamp else now.month
        lock_year  = (existing_stamp["score_1st_year"]  or now.year)  if existing_stamp else now.year

        conn.execute("""
            UPDATE rar_entries
            SET score_1st_locked=1, score_1st_month=?, score_1st_year=?
            WHERE id=? AND score_1st_locked=0
        """, (lock_month, lock_year, rar_id))
        conn.commit()

        # Re-read the entry to get the actual locked month/year and planned_week
        entry_row = conn.execute(
            "SELECT score_1st_month, score_1st_year, planned_week "
            "FROM rar_entries WHERE id=?",
            (rar_id,),
        ).fetchone()
        if entry_row:
            _sync_rar_1st_score_kpi(conn, entry_row["score_1st_year"], entry_row["score_1st_month"])
            if entry_row["planned_week"]:
                _sync_rar_planned_kpi(conn, entry_row["planned_week"])


def delete_rar_entry(rar_id):
    """Delete a R@R entry and re-sync both KPIs for the affected month."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT planned_week, score_1st_locked, score_1st_month, score_1st_year "
            "FROM rar_entries WHERE id=?",
            (rar_id,),
        ).fetchone()
        planned_week = row["planned_week"] if row else ""
        was_locked   = bool(row["score_1st_locked"]) if row else False
        locked_month = row["score_1st_month"] if row else None
        locked_year  = row["score_1st_year"]  if row else None

        conn.execute("DELETE FROM rar_entries WHERE id=?", (rar_id,))
        conn.commit()

        if planned_week:
            _sync_rar_planned_kpi(conn, planned_week)
        # Re-sync 1st Score KPI whenever the deleted entry had any score
        # (locked or not — both contribute to the monthly average)
        if locked_month and locked_year:
            _sync_rar_1st_score_kpi(conn, locked_year, locked_month)


def get_rar_scores_for_kpi(year):
    """Return monthly average 1st scores for the KPI dashboard.

    Includes ALL entries that have a non-null score_1st for the given year —
    locked or not — so the KPI reflects scores as soon as they are entered.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT score_1st_month as month,
                   AVG(score_1st)  as avg_score,
                   COUNT(*)        as count
            FROM rar_entries
            WHERE score_1st IS NOT NULL
              AND score_1st_year=?
            GROUP BY score_1st_month
        """, (year,)).fetchall()
    return [dict(r) for r in rows]


def get_rar_entry_counts_for_kpi(year):
    """Return per-month count of entries that have a 1st score for annotations."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT score_1st_month as month, COUNT(*) as count
            FROM rar_entries
            WHERE score_1st IS NOT NULL AND score_1st_year=?
            GROUP BY score_1st_month
        """, (year,)).fetchall()
    return {r["month"]: r["count"] for r in rows}


# ══════════════════════════════════════════════════════════════════════════════
# Transport Model Functions
# ══════════════════════════════════════════════════════════════════════════════

def get_transport_entries(project_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM transport_entries WHERE project_id=? ORDER BY entry_date DESC, id DESC",
            (project_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_transport_entry(data):
    """Insert or update a transport entry and auto-update KPI."""
    import datetime
    now = datetime.date.today()
    month = data.get("entry_month") or now.month
    year  = data.get("entry_year")  or now.year

    with get_connection() as conn:
        if data.get("id"):
            conn.execute("""
                UPDATE transport_entries
                SET item_desc=?, quantity=?, dim_l=?, dim_w=?, dim_h=?,
                    weight_kg=?, origin=?, destination=?, transport_mode=?,
                    cost_eur=?, pr_number=?, entry_date=?, entry_month=?, entry_year=?
                WHERE id=?
            """, (data.get("item_desc",""), data.get("quantity",1),
                  data.get("dim_l"), data.get("dim_w"), data.get("dim_h"),
                  data.get("weight_kg"), data.get("origin",""), data.get("destination",""),
                  data.get("transport_mode","Road"), data.get("cost_eur",0),
                  data.get("pr_number",""), data.get("entry_date", now.isoformat()),
                  month, year, data["id"]))
        else:
            conn.execute("""
                INSERT INTO transport_entries
                    (project_id, item_desc, quantity, dim_l, dim_w, dim_h,
                     weight_kg, origin, destination, transport_mode, cost_eur,
                     pr_number, entry_date, entry_month, entry_year)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (data["project_id"], data.get("item_desc",""),
                  data.get("quantity",1), data.get("dim_l"), data.get("dim_w"),
                  data.get("dim_h"), data.get("weight_kg"),
                  data.get("origin",""), data.get("destination",""),
                  data.get("transport_mode","Road"), data.get("cost_eur",0),
                  data.get("pr_number",""),
                  data.get("entry_date", now.isoformat()), month, year))
        conn.commit()

        # Auto-update "Non-Productive Freight Cost" KPI for this month
        _sync_transport_kpi(conn, year, month)


def delete_transport_entry(entry_id, year, month):
    with get_connection() as conn:
        conn.execute("DELETE FROM transport_entries WHERE id=?", (entry_id,))
        conn.commit()
        _sync_transport_kpi(conn, year, month)


def _sync_transport_kpi(conn, year, month):
    """Recalculate total transport cost for year/month and update KPI score."""
    row = conn.execute("""
        SELECT COALESCE(SUM(cost_eur),0) as total
        FROM transport_entries
        WHERE entry_year=? AND entry_month=?
    """, (year, month)).fetchone()
    total = float(row["total"]) if row else 0.0

    kpi_row = conn.execute(
        "SELECT id FROM kpis WHERE name LIKE '%Freight%' OR name LIKE '%Transport%' LIMIT 1"
    ).fetchone()
    if kpi_row:
        conn.execute("""
            INSERT INTO kpi_monthly_scores(kpi_id,year,month,score,target,comment)
            VALUES(?,?,?,?,5000,'Auto-synced from transport entries')
            ON CONFLICT(kpi_id,year,month) DO UPDATE SET
                score=excluded.score, comment=excluded.comment
        """, (kpi_row[0], year, month, total))
        conn.commit()


# ── PR/PO Functions ────────────────────────────────────────────────────────────

def get_prpo_entries(project_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM prpo_entries WHERE project_id=? ORDER BY id DESC",
            (project_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_prpo_entry(data):
    with get_connection() as conn:
        if data.get("id"):
            conn.execute("""
                UPDATE prpo_entries SET
                    item=?, rfq_submitted_date=?, rfq_forecasted_date=?,
                    rfq_reception_date=?, rfq_status=?, cost=?,
                    internal_order=?, supplier=?, contact=?,
                    pr_number=?, pr_approval_flow=?, pr_status=?,
                    pr_validation_date=?, po_forecasted_date=?, po_submission_date=?,
                    po_number=?, po_lead_time_weeks=?, reception_forecasted=?,
                    reception_date=?, reception_status=?
                WHERE id=?
            """, (
                data.get("item"), data.get("rfq_submitted_date"), data.get("rfq_forecasted_date"),
                data.get("rfq_reception_date"), data.get("rfq_status"), data.get("cost", 0),
                data.get("internal_order"), data.get("supplier"), data.get("contact"),
                data.get("pr_number"), data.get("pr_approval_flow"), data.get("pr_status", "Pending"),
                data.get("pr_validation_date"), data.get("po_forecasted_date"), data.get("po_submission_date"),
                data.get("po_number"), data.get("po_lead_time_weeks"), data.get("reception_forecasted"),
                data.get("reception_date"), data.get("reception_status"),
                data["id"]
            ))
        else:
            conn.execute("""
                INSERT INTO prpo_entries (
                    project_id, item, rfq_submitted_date, rfq_forecasted_date,
                    rfq_reception_date, rfq_status, cost, internal_order,
                    supplier, contact, pr_number, pr_approval_flow, pr_status,
                    pr_validation_date, po_forecasted_date, po_submission_date,
                    po_number, po_lead_time_weeks, reception_forecasted,
                    reception_date, reception_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data.get("project_id"), data.get("item"),
                data.get("rfq_submitted_date"), data.get("rfq_forecasted_date"),
                data.get("rfq_reception_date"), data.get("rfq_status"), data.get("cost", 0),
                data.get("internal_order"), data.get("supplier"), data.get("contact"),
                data.get("pr_number"), data.get("pr_approval_flow"), data.get("pr_status", "Pending"),
                data.get("pr_validation_date"), data.get("po_forecasted_date"), data.get("po_submission_date"),
                data.get("po_number"), data.get("po_lead_time_weeks"), data.get("reception_forecasted"),
                data.get("reception_date"), data.get("reception_status")
            ))
        conn.commit()


def delete_prpo_entry(entry_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM prpo_entries WHERE id=?", (entry_id,))
        conn.commit()
