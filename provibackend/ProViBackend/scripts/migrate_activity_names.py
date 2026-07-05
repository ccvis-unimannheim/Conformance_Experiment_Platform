#!/usr/bin/env python3
"""Migrate activity names in uploaded datasets from constant-style to verb-noun BPMN convention.

Run this once on the server after the verb-noun rename to update all existing uploaded
Guideline.bpmn and EventLog.csv files under the data/ directory.

Usage:
    python scripts/migrate_activity_names.py [--dry-run] [--data-dir /path/to/data]
"""
import argparse
import pathlib
import re
import shutil
import sys

# Mapping from old constant-style names → new verb-noun BPMN names
ACTIVITY_RENAME = {
    "CASE_OPENED":        "Open Case",
    "INTAKE_PARTIAL":     "Submit Partial Intake",
    "TRIAGE_COMPLETE":    "Complete Triage",
    "ASSESSMENT_DONE":    "Complete Assessment",
    "CASE_CLOSED":        "Close Case",
    "TREATMENT_APPROVED": "Approve Treatment",
    "PATIENT_REGISTERED": "Register Patient",
    "CARE_ACTIVATED":     "Activate Care",
    "CASE_REJECTED":      "Reject Case",
    "CASE_WITHDRAWN":     "Withdraw Case",
}


def _patch_bpmn(path: pathlib.Path, dry_run: bool) -> bool:
    """Replace old activity names inside a BPMN file. Returns True if changed."""
    text = path.read_text(encoding="utf-8")
    patched = text
    for old, new in ACTIVITY_RENAME.items():
        patched = patched.replace(f'name="{old}"', f'name="{new}"')
    if patched == text:
        return False
    if not dry_run:
        shutil.copy2(path, path.with_suffix(".bpmn.bak"))
        path.write_text(patched, encoding="utf-8")
    return True


def _patch_csv(path: pathlib.Path, dry_run: bool) -> bool:
    """Replace old activity names in the concept:name column of an event log CSV. Returns True if changed."""
    text = path.read_text(encoding="utf-8")
    patched = text
    for old, new in ACTIVITY_RENAME.items():
        # Match the value as a CSV field (comma-delimited, not a substring of another word)
        patched = re.sub(
            r'(?<=[,\n\r])' + re.escape(old) + r'(?=[,\n\r])',
            new,
            patched,
        )
    if patched == text:
        return False
    if not dry_run:
        shutil.copy2(path, path.with_suffix(".csv.bak"))
        path.write_text(patched, encoding="utf-8")
    return True


def migrate(data_dir: pathlib.Path, dry_run: bool):
    prefix = "[DRY RUN] " if dry_run else ""

    bpmn_files = list(data_dir.rglob("Guideline.bpmn"))
    csv_files  = list(data_dir.rglob("EventLog*.csv"))

    if not bpmn_files and not csv_files:
        print(f"No dataset files found under {data_dir}")
        return

    print(f"Found {len(bpmn_files)} BPMN file(s) and {len(csv_files)} CSV file(s)\n")

    for bpmn in bpmn_files:
        changed = _patch_bpmn(bpmn, dry_run)
        status = "UPDATED" if changed else "no change"
        print(f"  {prefix}{status}: {bpmn}")

    for csv in csv_files:
        changed = _patch_csv(csv, dry_run)
        status = "UPDATED" if changed else "no change"
        print(f"  {prefix}{status}: {csv}")

    print("\nDone. Backups written as *.bak alongside any changed files.")
    print("After running without --dry-run, restart the backend so alignment caches are invalidated.")


def _default_data_dir() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve().parent.parent  # ProViBackend/
    return here / "data"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate activity names to verb-noun convention.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    parser.add_argument("--data-dir", default=None, help="Path to the data/ directory (default: auto-detected).")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data_dir) if args.data_dir else _default_data_dir()
    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Migrating datasets in: {data_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}\n")
    migrate(data_dir, dry_run=args.dry_run)
