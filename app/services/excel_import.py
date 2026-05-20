"""
Excel Import Service - Reads Excel files and maps columns to project data.
Handles single files, multiple files, and multi-sheet workbooks.
"""
import pandas as pd
from pathlib import Path
from app.models.project_model import (
    upsert_project, upsert_budget, upsert_milestone,
    upsert_risk, upsert_action, insert_default_milestones
)


# ── Column aliases for flexible import ───────────────────────────────────────
COL_MAP = {
    "project_id":       ["project id", "id", "proj id", "project_id", "code"],
    "name":             ["project name", "name", "title", "project title"],
    "status":           ["status", "state", "project status"],
    "phase":            ["phase", "project phase", "current phase"],
    "priority":         ["priority", "prio"],
    "manager":          ["manager", "project manager", "pm", "owner"],
    "department":       ["department", "dept", "division", "bu"],
    "client":           ["client", "customer", "account"],
    "start_date":       ["start date", "start", "begin date", "startdate"],
    "end_date":         ["end date", "end", "finish date", "enddate", "target date"],
    "progress":         ["progress", "completion", "% complete", "percent complete"],
    "description":      ["description", "details", "scope", "summary"],
    # Budget
    "planned_budget":   ["planned budget", "budget", "planned", "total budget"],
    "actual_cost":      ["actual cost", "actual", "spent", "cost"],
    "budget_type":      ["budget type", "type"],
    # Milestones
    "milestone_name":   ["milestone", "milestone name", "name"],
    "due_date":         ["due date", "date", "target date"],
    # Risks
    "description":      ["description", "risk", "issue"],
    "impact":           ["impact", "severity"],
    "mitigation":       ["mitigation", "action", "response"],
    "owner":            ["owner", "responsible", "assignee"],
}


def _normalize_col(col: str) -> str:
    return col.strip().lower().replace("_", " ")


def _map_columns(df: pd.DataFrame, field_aliases: dict) -> dict:
    """Return a mapping {field: actual_column_name} for what's found in df."""
    normalized = {_normalize_col(c): c for c in df.columns}
    result = {}
    for field, aliases in field_aliases.items():
        for alias in aliases:
            if alias in normalized:
                result[field] = normalized[alias]
                break
    return result


def _safe_str(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def _safe_float(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _safe_date(val) -> str:
    if pd.isna(val):
        return ""
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return str(val).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Main import entry point
# ─────────────────────────────────────────────────────────────────────────────

def preview_excel(filepath: str) -> dict:
    """
    Returns a preview dict with sheets found and sample rows.
    Does NOT write to DB.
    """
    xl = pd.ExcelFile(filepath)
    sheets = xl.sheet_names
    preview = {"filepath": filepath, "sheets": {}}
    for sheet in sheets:
        try:
            df = pd.read_excel(filepath, sheet_name=sheet, nrows=5)
            preview["sheets"][sheet] = {
                "columns": list(df.columns),
                "rows": df.fillna("").to_dict(orient="records"),
                "total_rows": len(pd.read_excel(filepath, sheet_name=sheet)),
            }
        except Exception as e:
            preview["sheets"][sheet] = {"error": str(e)}
    return preview


def import_excel(filepath: str, callback=None) -> dict:
    """
    Full import: reads file, maps columns, writes to SQLite.
    Returns summary dict: {imported, updated, skipped, errors}
    """
    result = {"imported": 0, "updated": 0, "skipped": 0, "errors": []}
    xl = pd.ExcelFile(filepath)
    sheets_lower = {s.lower(): s for s in xl.sheet_names}

    # ── Detect sheets ────────────────────────────────────────────────────────
    project_sheet = _find_sheet(sheets_lower, ["projects", "project", "data", "main", "portfolio"])
    milestone_sheet = _find_sheet(sheets_lower, ["milestones", "milestone", "gates"])
    budget_sheet = _find_sheet(sheets_lower, ["budget", "financials", "finance", "cost"])
    risk_sheet = _find_sheet(sheets_lower, ["risks", "risk", "issues"])
    action_sheet = _find_sheet(sheets_lower, ["actions", "tasks", "action", "task"])

    if callback:
        callback(f"Detected sheets: {[s for s in [project_sheet, milestone_sheet, budget_sheet] if s]}")

    # ── Import Projects ───────────────────────────────────────────────────────
    if project_sheet:
        df = pd.read_excel(filepath, sheet_name=project_sheet)
        df.columns = [str(c) for c in df.columns]
        field_map = _map_columns(df, {k: v for k, v in COL_MAP.items()})
        for _, row in df.iterrows():
            try:
                pid = _safe_str(row.get(field_map.get("project_id", ""), ""))
                name = _safe_str(row.get(field_map.get("name", ""), ""))
                if not pid and not name:
                    continue
                if not pid:
                    pid = f"PRJ-{name[:8].upper().replace(' ', '')}-{result['imported']:04d}"
                data = {
                    "project_id": pid,
                    "name": name or pid,
                    "status": _safe_str(row.get(field_map.get("status", ""), "Active")) or "Active",
                    "phase": _safe_str(row.get(field_map.get("phase", ""), "Phase 1")) or "Phase 1",
                    "priority": _safe_str(row.get(field_map.get("priority", ""), "Medium")) or "Medium",
                    "manager": _safe_str(row.get(field_map.get("manager", ""), "")),
                    "department": _safe_str(row.get(field_map.get("department", ""), "")),
                    "client": _safe_str(row.get(field_map.get("client", ""), "")),
                    "start_date": _safe_date(row.get(field_map.get("start_date", ""), "")),
                    "end_date": _safe_date(row.get(field_map.get("end_date", ""), "")),
                    "progress": _safe_float(row.get(field_map.get("progress", ""), 0)),
                    "description": _safe_str(row.get(field_map.get("description", ""), "")),
                }
                upsert_project(data)
                # Auto-insert milestones if phase is set and no custom milestone sheet
                if not milestone_sheet and data["phase"]:
                    insert_default_milestones(pid, data["phase"])
                result["imported"] += 1
            except Exception as e:
                result["errors"].append(str(e))
        if callback:
            callback(f"Projects imported: {result['imported']}")

    # ── Import Milestones ─────────────────────────────────────────────────────
    if milestone_sheet:
        df = pd.read_excel(filepath, sheet_name=milestone_sheet)
        df.columns = [str(c) for c in df.columns]
        for _, row in df.iterrows():
            try:
                pid = _safe_str(row.get("project_id", row.get("Project ID", "")))
                name = _safe_str(row.get("name", row.get("milestone", row.get("Milestone", ""))))
                if not pid or not name:
                    continue
                upsert_milestone({
                    "project_id": pid,
                    "name": name,
                    "due_date": _safe_date(row.get("due_date", row.get("Due Date", ""))),
                    "status": _safe_str(row.get("status", "Pending")) or "Pending",
                    "comments": _safe_str(row.get("comments", "")),
                    "phase": _safe_str(row.get("phase", "")),
                })
            except Exception as e:
                result["errors"].append(f"Milestone: {e}")

    # ── Import Budget ─────────────────────────────────────────────────────────
    if budget_sheet:
        df = pd.read_excel(filepath, sheet_name=budget_sheet)
        df.columns = [str(c) for c in df.columns]
        for _, row in df.iterrows():
            try:
                pid = _safe_str(row.get("project_id", row.get("Project ID", "")))
                if not pid:
                    continue
                upsert_budget({
                    "project_id": pid,
                    "budget_type": _safe_str(row.get("budget_type", row.get("Budget Type", "CPT Cash"))) or "CPT Cash",
                    "planned_budget": _safe_float(row.get("planned_budget", row.get("Planned Budget", 0))),
                    "actual_cost": _safe_float(row.get("actual_cost", row.get("Actual Cost", 0))),
                })
            except Exception as e:
                result["errors"].append(f"Budget: {e}")

    # ── Import Risks ──────────────────────────────────────────────────────────
    if risk_sheet:
        df = pd.read_excel(filepath, sheet_name=risk_sheet)
        df.columns = [str(c) for c in df.columns]
        for _, row in df.iterrows():
            try:
                pid = _safe_str(row.get("project_id", row.get("Project ID", "")))
                if not pid:
                    continue
                upsert_risk({
                    "project_id": pid,
                    "description": _safe_str(row.get("description", row.get("Risk", ""))),
                    "impact": _safe_str(row.get("impact", "Medium")) or "Medium",
                    "mitigation": _safe_str(row.get("mitigation", "")),
                    "owner": _safe_str(row.get("owner", "")),
                    "status": _safe_str(row.get("status", "Open")) or "Open",
                })
            except Exception as e:
                result["errors"].append(f"Risk: {e}")

    # ── Import Actions ────────────────────────────────────────────────────────
    if action_sheet:
        df = pd.read_excel(filepath, sheet_name=action_sheet)
        df.columns = [str(c) for c in df.columns]
        for _, row in df.iterrows():
            try:
                pid = _safe_str(row.get("project_id", row.get("Project ID", "")))
                if not pid:
                    continue
                upsert_action({
                    "project_id": pid,
                    "task_name": _safe_str(row.get("task_name", row.get("Task", ""))),
                    "owner": _safe_str(row.get("owner", "")),
                    "due_date": _safe_date(row.get("due_date", "")),
                    "status": _safe_str(row.get("status", "Open")) or "Open",
                    "comments": _safe_str(row.get("comments", "")),
                })
            except Exception as e:
                result["errors"].append(f"Action: {e}")

    return result


def import_multiple_excel(filepaths: list[str], callback=None) -> dict:
    """Import multiple Excel files sequentially."""
    total = {"imported": 0, "updated": 0, "skipped": 0, "errors": []}
    for fp in filepaths:
        if callback:
            callback(f"Processing: {Path(fp).name}")
        r = import_excel(fp, callback)
        total["imported"] += r["imported"]
        total["updated"] += r["updated"]
        total["skipped"] += r["skipped"]
        total["errors"].extend(r["errors"])
    return total


def _find_sheet(sheets_lower: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in sheets_lower:
            return sheets_lower[c]
    return None
