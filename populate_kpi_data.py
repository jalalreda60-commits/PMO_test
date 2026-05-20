"""
populate_kpi_data.py
Run once to seed the database with all real data extracted from KPI_s_Mar_202611.xlsb.

Usage:  python populate_kpi_data.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database.db_manager import get_connection, initialize_database, initialize_kpi_tables

# ── Month mapping ─────────────────────────────────────────────────────────────
# The Excel uses Jan'25..Dec'25 + Jan'26..Feb'26
# We map each to (year, month_int)
MONTH_MAP = {
    "Jan'25": (2025, 1),  "Feb'25": (2025, 2),  "Mar'25": (2025, 3),
    "Apr'25": (2025, 4),  "Apr '25": (2025, 4), "May'25": (2025, 5),
    "June'25":(2025, 6),  "July'25": (2025, 7), "Aug'25": (2025, 8),
    "Sep'25": (2025, 9),  "Sep'25 / Oct WK40": (2025, 9),
    "Oct'25": (2025,10),  "Nov'25": (2025,11),  "Dec'25": (2025,12),
    "Jan'26": (2026, 1),  "Feb'26": (2026, 2),
    # Short form used in some sheets
    "Jan":    (2025, 1),  "February":(2025, 2), "March":  (2025, 3),
    "April":  (2025, 4),  "May":     (2025, 5), "June":   (2025, 6),
    "July":   (2025, 7),  "August":  (2025, 8), "September":(2025,9),
    "October":(2025,10),  "November":(2025,11), "December": (2025,12),
}

def upsert_kpi(conn, name, category, unit, target, description="", sort_order=0):
    cur = conn.execute(
        "SELECT id FROM kpis WHERE name=?", (name,)
    )
    row = cur.fetchone()
    if row:
        conn.execute(
            "UPDATE kpis SET category=?,unit=?,target=?,description=?,sort_order=? WHERE id=?",
            (category, unit, target, description, sort_order, row[0])
        )
        return row[0]
    else:
        cur = conn.execute(
            "INSERT INTO kpis(name,category,unit,target,description,sort_order,active)"
            " VALUES(?,?,?,?,?,?,1)",
            (name, category, unit, target, description, sort_order)
        )
        return cur.lastrowid


def upsert_score(conn, kpi_id, year, month, score, target=None, comment=""):
    conn.execute("""
        INSERT INTO kpi_monthly_scores(kpi_id,year,month,score,target,comment)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(kpi_id,year,month) DO UPDATE SET
            score=excluded.score,
            target=excluded.target,
            comment=excluded.comment
    """, (kpi_id, year, month, score, target, comment or ""))


def populate():
    initialize_database()
    initialize_kpi_tables()
    conn = get_connection()

    print("Seeding KPI definitions and monthly scores…\n")

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 1 — % Programs With No Past Due Gates
    # Sheet 1: R16 = % values, R17 = targets, R18 = avg days late
    # Months (cols 2-13): Jan'25 → Dec'25
    # Forecast (R14): 21,23,23,23,23,23,23,23,23,23,23,23
    # Real     (R15): 15,23,20,20,19
    # ══════════════════════════════════════════════════════════════════════════
    kid = upsert_kpi(conn,
        "% Programs With No Past Due Gates",
        "Gate Management", "%", 90,
        "Percentage of active programs that have no overdue gate milestones. "
        "Target: ≥90%. Source: Gate Walk Follow-up tracker.",
        sort_order=1
    )
    # (year, month): (score_pct*100, target_pct*100)
    gate_data = {
        (2025, 1): (71.43, 90),
        (2025, 2): (96.0,  90),
        (2025, 3): (86.96, 90),
        (2025, 4): (84.0,  90),
        (2025, 5): (96.0,  90),
        (2025, 6): (95.0,  90),
        (2025, 7): (95.0,  90),
        (2025, 8): (95.0,  90),
        (2025, 9): (86.0,  90),
        (2025,10): (78.0,  90),
        (2025,11): (82.0,  90),
        (2025,12): (0.0,   90),
    }
    for (y,m),(sc,tgt) in gate_data.items():
        upsert_score(conn, kid, y, m, sc, tgt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 2 — Average Days Late (Gate Management)
    # Sheet 1 R18
    # ══════════════════════════════════════════════════════════════════════════
    kid2 = upsert_kpi(conn,
        "Average Days Late (Gates)",
        "Gate Management", "days", 0,
        "Average number of days gates are overdue across all active programs. "
        "Target: 0 days late. Lower is better.",
        sort_order=2
    )
    avg_late = {
        (2025,1): 29, (2025,2): 7, (2025,3): 35, (2025,4): 53,
    }
    for (y,m),sc in avg_late.items():
        upsert_score(conn, kid2, y, m, float(sc), 0)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 3 — N° of Projects
    # Sheet 2: Total=25, Quotation=15, Launch=10
    # ══════════════════════════════════════════════════════════════════════════
    kid3 = upsert_kpi(conn,
        "N° of Active Projects",
        "Portfolio", "count", 25,
        "Total number of active engineering projects in portfolio. "
        "Breakdown: 15 in Quotation phase, 10 in Launch phase.",
        sort_order=3
    )
    # Only March 2025 data available (current month)
    upsert_score(conn, kid3, 2025, 3, 25.0, 25.0,
                 "Total: 25 (Quotation: 15, Launch: 10)")

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 4 — Programs With Successful Launch
    # Sheet 3: Forecast vs Released vs Result by month
    # ══════════════════════════════════════════════════════════════════════════
    kid4 = upsert_kpi(conn,
        "Programs With Successful Launch",
        "Launch", "count", 1,
        "Number of programs successfully launched per month vs. forecast. "
        "Target: ≥1 per month. Programs: P22094B/C/L, P22258C/D, P23134C/D/E, P24199A, P24211A, P25020A, P25021A.",
        sort_order=4
    )
    # Forecast | Released | Result
    launch_data = {
        # (year,month): (result, forecast, comment)
        (2025,1):  (1, 1,  "1 forecast / 1 released"),
        (2025,2):  (4, 4,  "4 forecast / 4 released"),
        (2025,3):  (0, 0,  "0 forecast"),
        (2025,4):  (0, 0,  "0 forecast"),
        (2025,5):  (0, 2,  "2 forecast / 0 released"),
        (2025,6):  (0, 0,  ""),
        (2025,7):  (0, 1,  "1 forecast / 0 released"),
        (2025,8):  (0, 1,  "1 forecast / 0 released"),
        (2025,9):  (0, 1,  "1 forecast / 0 released"),
        (2025,10): (0, 0,  ""),
        (2025,11): (0, 1,  "1 forecast / 0 released"),
        (2025,12): (0, 1,  "1 forecast / 0 released"),
    }
    for (y,m),(result, forecast, cmt) in launch_data.items():
        upsert_score(conn, kid4, y, m, float(result), float(forecast), cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 5 — R&R 1st Score Result
    # Sheet 4: 5 project responsibles, monthly scores
    # Target = 0.9 (90%)
    # ══════════════════════════════════════════════════════════════════════════
    kid5 = upsert_kpi(conn,
        "R&R 1st Score Result",
        "R&R", "score", 90,
        "Run & Rate first score achieved at launch. Target ≥ 90%. "
        "Tracked per responsible: Zouhir, Abdelhadi, Halima, Reda, Abdelghafour.",
        sort_order=5
    )
    # All responsibles have 0 score (no R&R released yet this period)
    # Result per month from R27 = 0, target = 0.9
    for m in range(1, 13):
        upsert_score(conn, kid5, 2025, m, 0.0, 90.0,
                     "No R&R released this month")

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 6 — R&R Released vs Planned
    # Sheet 5: Summary rows R38-R42
    # ══════════════════════════════════════════════════════════════════════════
    kid6 = upsert_kpi(conn,
        "R&R Released vs Planned",
        "R&R", "%", 100,
        "Ratio of R&R documents released vs planned per month. "
        "Planned includes: Zouhir, Yasser, Halima, Reda, Abdelghafour. "
        "Target: 100% (all planned released on time).",
        sort_order=6
    )
    # Result row: Jan=1.0 (100%), Feb=0.0909 (9.1%), Mar=0, Apr=0
    rrp_data = {
        (2025,1): (100.0, 100.0, "Planned:2, Released:2"),
        (2025,2): (9.1,   100.0, "Planned:22, Released:2 — Yasser backlog"),
        (2025,3): (0.0,   100.0, "Planned:31, Released:0"),
        (2025,4): (0.0,   100.0, "Planned:7, Released:0"),
        (2025,5): (0.0,   100.0, "Planned:0"),
        (2025,6): (0.0,   100.0, "Planned:3, Released:0"),
        (2025,7): (0.0,   100.0, "Planned:0"),
        (2025,8): (0.0,   100.0, "Planned:4, Released:0"),
        (2025,9): (0.0,   100.0, "Planned:3, Released:0"),
        (2025,10):(0.0,   100.0, "Planned:3, Released:0"),
        (2025,11):(0.0,   100.0, "Planned:0"),
        (2025,12):(0.0,   100.0, "Planned:3, Released:0"),
    }
    for (y,m),(sc,tgt,cmt) in rrp_data.items():
        upsert_score(conn, kid6, y, m, sc, tgt, cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 7 — Engineering Scrap Vs Sales %
    # Sheet 9 (Eng_Scrap2): R18 = Engineering Scrap Vs Sales %
    # Jan=0.0906%, Feb=0.2554%, Mar=0.1988%
    # ══════════════════════════════════════════════════════════════════════════
    kid7 = upsert_kpi(conn,
        "Engineering Scrap Vs Sales %",
        "Scrap", "%", 0.2,
        "Engineering scrap cost as % of total sales. "
        "Lower is better. Target ≤ 0.2%. "
        "Includes Process + Method scrap. Sales tracked monthly in DH.",
        sort_order=7
    )
    scrap_pct = {
        # From Sheet 9 R18 (Engineering Scrap Vs Sales col by col)
        (2025,1): (0.09057 * 100, 0.2, "Sales: 36.04M DH, Process+Method scrap"),
        (2025,2): (0.2554  * 100, 0.2, "Sales: 35.14M DH"),
        (2025,3): (0.1988  * 100, 0.2, "Sales: 37.59M DH"),
        (2025,4): (0.0,           0.2, ""),
        (2025,5): (0.0,           0.2, ""),
        (2025,6): (0.0,           0.2, ""),
        (2025,7): (0.0,           0.2, ""),
        (2025,8): (0.0,           0.2, ""),
        (2025,9): (0.0,           0.2, ""),
        (2025,10):(0.0,           0.2, ""),
        (2025,11):(0.24,          0.2, ""),  # from Sheet9 R41
        (2025,12):(0.0,           0.2, ""),
    }
    for (y,m),(sc,tgt,cmt) in scrap_pct.items():
        upsert_score(conn, kid7, y, m, round(sc,4), tgt, cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 8 — Engineering Obsolete (MAD)
    # Sheet 7: monthly values row R06
    # Jan=9000 MAD, Feb=9000, Mar=9000, Apr=0...
    # Total Obsolete = 35,000 MAD (P23134: 9k, P22094: 8.6k, Others: 17.4k)
    # ══════════════════════════════════════════════════════════════════════════
    kid8 = upsert_kpi(conn,
        "Engineering Obsolete (MAD)",
        "Scrap", "kMAD", 0,
        "Value of obsolete engineering parts in MAD. "
        "Lower is better. Target: 0. "
        "Main contributors: P23134 (9k), P22094 (8.6k), Others (17.4k). Total: 35k MAD.",
        sort_order=8
    )
    # Sheet 7 R06: col4=Jan(9), col5=Feb(9), col6=Mar(9), col7-15=0
    obs_data = {
        (2025,1): (9000,   0, "P23134 + P22094 obsolete parts"),
        (2025,2): (9000,   0, ""),
        (2025,3): (9000,   0, ""),
        (2025,4): (0,      0, ""),
        (2025,5): (0,      0, ""),
        (2025,6): (0,      0, ""),
        (2025,7): (0,      0, ""),
        (2025,8): (0,      0, ""),
        (2025,9): (0,      0, ""),
        (2025,10):(0,      0, ""),
        (2025,11):(0,      0, ""),
        (2025,12):(0,      0, ""),
    }
    for (y,m),(sc,tgt,cmt) in obs_data.items():
        upsert_score(conn, kid8, y, m, float(sc), float(tgt), cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 9 — Non-Productive Freight Cost (€)
    # Sheet 10: actual shipment costs per month
    # Jan 2025: 280+660+4800+95+3859+970+545+350+420+470 = 12,449 €
    # Feb 2025: 260+850+970+850 = 2,930 €
    # Mar 2025: 560+170+150+180+550 = 1,610 €
    # ══════════════════════════════════════════════════════════════════════════
    kid9 = upsert_kpi(conn,
        "Non-Productive Freight Cost (€)",
        "Logistics", "€", 5000,
        "Total non-productive freight and transport cost in Euros. "
        "Lower is better. Target ≤ 5,000 €/month. "
        "Includes all air/road shipments for samples, validation parts, tools.",
        sort_order=9
    )
    freight_data = {
        (2025,1): (12449, 5000,
                   "10 shipments: P25252×3, P23134 SB Mold 4800€, P22094B 3859€, P22094L×3"),
        (2025,2): (2930,  5000,
                   "4 shipments: P25252 Air 260€, P23028×2, P22094L"),
        (2025,3): (1610,  5000,
                   "5 shipments: P24199&P24211×3, P22258C Air 180€, semi-finished parts"),
    }
    for (y,m),(sc,tgt,cmt) in freight_data.items():
        upsert_score(conn, kid9, y, m, float(sc), float(tgt), cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 10 — Total Transport Cost %
    # Sheet 10 / Transport_Data: Air=25% (1 shipment), Road=75% (3 shipments)
    # ══════════════════════════════════════════════════════════════════════════
    kid10 = upsert_kpi(conn,
        "Air Freight Usage %",
        "Logistics", "%", 10,
        "Percentage of shipments using Air freight vs total shipments. "
        "Target ≤ 10%. Air freight is significantly more expensive than road. "
        "March 2025: 1 Air (180€) out of 4 shipments = 25%.",
        sort_order=10
    )
    transport_data = {
        (2025,1): (10.0, 10.0, "1 Air out of 10 shipments (P25252 CMP verification)"),
        (2025,2): (50.0, 10.0, "1 Air out of 2 tracked — P25252 260€"),
        (2025,3): (25.0, 10.0, "1 Air (P22258C 180€) out of 4 shipments (Road×3)"),
    }
    for (y,m),(sc,tgt,cmt) in transport_data.items():
        upsert_score(conn, kid10, y, m, sc, tgt, cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 11 — Late Process Actions (OPMS)
    # Sheet 12: Result row R29, Target row R30 = 50
    # Jan=6, Feb=34, Mar-Dec=0
    # ══════════════════════════════════════════════════════════════════════════
    kid11 = upsert_kpi(conn,
        "Late Process Actions (OPMS)",
        "Process", "count", 50,
        "Number of late process actions linked to programs in OPMS. "
        "Lower is better. Target ≤ 50. "
        "Jan'25: 6 late (P23133A: 6). Feb'25: 34 late (P23133A: 34 — spike).",
        sort_order=11
    )
    # From Sheet 12 R29 (Result row by month)
    late_actions = {
        (2025,1):  (6,  50, "P23133A: 6 late actions"),
        (2025,2):  (34, 50, "P23133A: 34 late actions — spike"),
        (2025,3):  (0,  50, ""),
        (2025,4):  (0,  50, ""),
        (2025,5):  (0,  50, ""),
        (2025,6):  (0,  50, ""),
        (2025,7):  (0,  50, ""),
        (2025,8):  (0,  50, ""),
        (2025,9):  (0,  50, ""),
        (2025,10): (0,  50, ""),
        (2025,11): (0,  50, ""),
        (2025,12): (0,  50, ""),
    }
    for (y,m),(sc,tgt,cmt) in late_actions.items():
        upsert_score(conn, kid11, y, m, float(sc), float(tgt), cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # KPI 12 — GAP Analysis CCAR Closure
    # Sheet 1 R41 (GAP analysis) / Sheet 12 R49 (GAP analysis closure)
    # Sheet 8 R46-R50: Actual status 0.002, Slow moving 0, Samples 0, Parameters 0
    # ══════════════════════════════════════════════════════════════════════════
    kid12 = upsert_kpi(conn,
        "GAP Analysis CCAR Closure %",
        "Process", "%", 100,
        "Percentage of GAP analysis CCAR action items closed on time. "
        "Target: 100%. Categories: Actual status, Slow moving, Samples, Parameters Def. "
        "GAP closure rate Mar'25: 68% (from process tracking).",
        sort_order=12
    )
    gap_data = {
        (2025,1): (0.0,  100.0, "No data — tracking started Feb"),
        (2025,2): (0.0,  100.0, ""),
        (2025,3): (68.0, 100.0, "68% closure — categories: Actual status, Slow moving, Samples, Parameters"),
    }
    for (y,m),(sc,tgt,cmt) in gap_data.items():
        upsert_score(conn, kid12, y, m, sc, tgt, cmt)

    # ══════════════════════════════════════════════════════════════════════════
    # Remove default seeded KPIs that are now replaced by real ones
    # ══════════════════════════════════════════════════════════════════════════
    old_names = [
        "% Programs with No Past Due Gates",   # replaced by correct name
        "Gates Walk Follow up",
        "N° of Projects",
        "Programs With Successful Launch",
        "R&R 1st Score Result",
        "R&R Released vs Planned",
        "Engineering Scrap Vs Sales",
        "Engineering Obsolete",
        "No Productive Freight Cost",
        "Total Transport Cost %",
        "Late Process Actions - OPMS",
        "Gap Analysis CCAR Closure",
    ]
    for old in old_names:
        conn.execute("DELETE FROM kpis WHERE name=? AND sort_order=0", (old,))

    conn.commit()

    # Summary
    kpis = conn.execute("SELECT id, name, sort_order FROM kpis ORDER BY sort_order").fetchall()
    print(f"✅ {len(kpis)} KPIs in database:")
    for k in kpis:
        scores = conn.execute(
            "SELECT COUNT(*) FROM kpi_monthly_scores WHERE kpi_id=? AND score IS NOT NULL",
            (k[0],)
        ).fetchone()[0]
        print(f"   [{k[0]:2d}] {k[1][:55]:<55}  {scores} monthly scores")

    conn.close()
    print("\n✅ Done! All KPI data populated from Excel file.")

if __name__ == "__main__":
    populate()
