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
from collections.abc import Callable

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


def _rename_in_bpmn(text: str) -> str:
    """Replace old activity names inside BPMN name="..." attributes."""
    for old, new in ACTIVITY_RENAME.items():
        text = text.replace(f'name="{old}"', f'name="{new}"')
    return text


def _rename_in_csv(text: str) -> str:
    """Replace old activity names that appear as standalone CSV fields."""
    for old, new in ACTIVITY_RENAME.items():
        # Match the value as a CSV field (comma/newline-delimited, not a substring of another word)
        text = re.sub(
            r'(?<=[,\n\r])' + re.escape(old) + r'(?=[,\n\r])',
            new,
            text,
        )
    return text


def _patch_file(path: pathlib.Path, rename: Callable[[str], str], dry_run: bool) -> bool:
    """Apply a rename function to a file's text. Returns True if the content changed."""
    text = path.read_text(encoding="utf-8")
    patched = rename(text)
    if patched == text:
        return False
    if not dry_run:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text(patched, encoding="utf-8")
    return True


def migrate(data_dir: pathlib.Path, dry_run: bool) -> None:
    prefix = "[DRY RUN] " if dry_run else ""

    bpmn_files = list(data_dir.rglob("Guideline.bpmn"))
    csv_files  = list(data_dir.rglob("EventLog*.csv"))

    if not bpmn_files and not csv_files:
        print(f"No dataset files found under {data_dir}")
        return

    print(f"Found {len(bpmn_files)} BPMN file(s) and {len(csv_files)} CSV file(s)\n")

    targets = [(path, _rename_in_bpmn) for path in bpmn_files]
    targets += [(path, _rename_in_csv) for path in csv_files]
    for path, rename in targets:
        changed = _patch_file(path, rename, dry_run)
        status = "UPDATED" if changed else "no change"
        print(f"  {prefix}{status}: {path}")

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
