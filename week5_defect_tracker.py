"""
Week 5 companion utility: lightweight defect tracker and debugging log.

This command-line program stores defect records in a local SQLite database.
It demonstrates practical defect documentation, status tracking, and a
structured debugging workflow using only the Python standard library.

Examples:
    python week5_defect_tracker.py add \
      --title "Checkout total is incorrect" \
      --component checkout \
      --severity High \
      --priority High \
      --steps "Add item; apply discount; open checkout" \
      --expected "Total follows approved rounding rule" \
      --actual "Displayed total differs"

    python week5_defect_tracker.py list
    python week5_defect_tracker.py list --status "In Progress"
    python week5_defect_tracker.py update --id 1 --status "Ready for QA" \
      --owner "QA Team" --resolution "Calculation rule standardized"
    python week5_defect_tracker.py show --id 1

Database file: defects.db (created in the current working directory).
Do not store passwords, access tokens, or sensitive personal information
in defect descriptions, command arguments, or diagnostic logs.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).with_name("defects.db")

VALID_STATUSES = {
    "New",
    "Triaged",
    "In Progress",
    "Fixed",
    "Ready for QA",
    "Verified",
    "Reopened",
    "Closed",
}
VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}
VALID_PRIORITIES = {"Urgent", "High", "Medium", "Low"}


def now_utc() -> str:
    """Return a consistent UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """Open the database and ensure the defects table exists."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS defects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            component TEXT NOT NULL,
            severity TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            steps TEXT NOT NULL,
            expected TEXT NOT NULL,
            actual TEXT NOT NULL,
            environment TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            evidence TEXT DEFAULT '',
            root_cause TEXT DEFAULT '',
            resolution TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def add_defect(args: argparse.Namespace) -> None:
    """Create a defect record."""
    with connect() as db:
        cursor = db.execute(
            """
            INSERT INTO defects (
                title, component, severity, priority, status, steps,
                expected, actual, environment, owner, evidence,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'New', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.title,
                args.component,
                args.severity,
                args.priority,
                args.steps,
                args.expected,
                args.actual,
                args.environment,
                args.owner,
                args.evidence,
                now_utc(),
                now_utc(),
            ),
        )
        defect_id = cursor.lastrowid
    print(f"Created defect BUG-{defect_id:04d} (database ID: {defect_id}).")


def list_defects(args: argparse.Namespace) -> None:
    """List defects, optionally filtered by status."""
    with connect() as db:
        if args.status:
            rows = db.execute(
                "SELECT id, title, component, severity, priority, status, owner "
                "FROM defects WHERE status = ? ORDER BY updated_at DESC",
                (args.status,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, title, component, severity, priority, status, owner "
                "FROM defects ORDER BY updated_at DESC"
            ).fetchall()

    if not rows:
        print("No defects found.")
        return

    print(
        f"{'ID':<10} {'STATUS':<15} {'SEVERITY':<9} "
        f"{'PRIORITY':<9} {'COMPONENT':<15} TITLE"
    )
    print("-" * 95)
    for row in rows:
        print(
            f"BUG-{row['id']:04d}  {row['status']:<15} "
            f"{row['severity']:<9} {row['priority']:<9} "
            f"{row['component'][:14]:<15} {row['title']}"
        )


def show_defect(args: argparse.Namespace) -> None:
    """Display the complete details of one defect."""
    with connect() as db:
        row = db.execute(
            "SELECT * FROM defects WHERE id = ?", (args.id,)
        ).fetchone()

    if row is None:
        raise SystemExit(f"No defect found with ID {args.id}.")

    for key in row.keys():
        print(f"{key.replace('_', ' ').title()}: {row[key]}")


def update_defect(args: argparse.Namespace) -> None:
    """Update status and optional ownership/root-cause/resolution fields."""
    updates = {}
    for field in ("status", "owner", "root_cause", "resolution", "evidence"):
        value = getattr(args, field)
        if value is not None:
            updates[field] = value

    if not updates:
        raise SystemExit("No updates supplied. Provide at least one update field.")

    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise SystemExit(
            "Invalid status. Choose one of: " + ", ".join(sorted(VALID_STATUSES))
        )

    updates["updated_at"] = now_utc()
    assignments = ", ".join(f"{column} = ?" for column in updates)
    values = list(updates.values()) + [args.id]

    with connect() as db:
        cursor = db.execute(
            f"UPDATE defects SET {assignments} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            raise SystemExit(f"No defect found with ID {args.id}.")

    print(f"Updated BUG-{args.id:04d}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track software defects during code review and debugging."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a defect record.")
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--component", required=True)
    add_parser.add_argument("--severity", choices=sorted(VALID_SEVERITIES), required=True)
    add_parser.add_argument("--priority", choices=sorted(VALID_PRIORITIES), required=True)
    add_parser.add_argument("--steps", required=True, help="Steps to reproduce.")
    add_parser.add_argument("--expected", required=True)
    add_parser.add_argument("--actual", required=True)
    add_parser.add_argument("--environment", default="")
    add_parser.add_argument("--owner", default="")
    add_parser.add_argument("--evidence", default="")
    add_parser.set_defaults(func=add_defect)

    list_parser = subparsers.add_parser("list", help="List defect records.")
    list_parser.add_argument("--status", choices=sorted(VALID_STATUSES))
    list_parser.set_defaults(func=list_defects)

    show_parser = subparsers.add_parser("show", help="Show one defect.")
    show_parser.add_argument("--id", type=int, required=True)
    show_parser.set_defaults(func=show_defect)

    update_parser = subparsers.add_parser("update", help="Update a defect.")
    update_parser.add_argument("--id", type=int, required=True)
    update_parser.add_argument("--status", choices=sorted(VALID_STATUSES))
    update_parser.add_argument("--owner")
    update_parser.add_argument("--root-cause")
    update_parser.add_argument("--resolution")
    update_parser.add_argument("--evidence")
    update_parser.set_defaults(func=update_defect)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
