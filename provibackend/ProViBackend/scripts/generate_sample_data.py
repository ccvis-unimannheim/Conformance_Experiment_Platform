#!/usr/bin/env python3
"""Prepare the sample dataset for the 2-step preview feature.

Copies the BPIC12_A event log and process model from new_input/ into
scripts/sample_data/input/ so the idiom preview uses real data:

    scripts/sample_data/input/EventLog.csv   ← BPIC12_Log_onlyA.csv
    scripts/sample_data/input/Guideline.bpmn ← Model_A.bpmn

Called automatically at startup (main.py lifespan) when the files are absent.
"""
import logging
import pathlib
import shutil

logger = logging.getLogger(__name__)

_SCRIPT_DIR      = pathlib.Path(__file__).parent
_NEW_INPUT_DIR   = _SCRIPT_DIR.parent / "new_input"

SAMPLE_INPUT_DIR = _SCRIPT_DIR / "sample_data" / "input"
CSV_PATH         = SAMPLE_INPUT_DIR / "EventLog.csv"
BPMN_PATH        = SAMPLE_INPUT_DIR / "Guideline.bpmn"

_SRC_CSV  = _NEW_INPUT_DIR / "BPIC12_Log_onlyA.csv"
_SRC_BPMN = _NEW_INPUT_DIR / "Model_A.bpmn"


def generate() -> bool:
    """Copy BPIC12_A files into sample_data/input/ if absent. Returns True on success."""
    if CSV_PATH.exists() and BPMN_PATH.exists():
        logger.info("[sample_data] Sample dataset already present — skipping generation.")
        return True

    if not _SRC_CSV.exists() or not _SRC_BPMN.exists():
        logger.error(
            "[sample_data] Source files not found in new_input/. "
            "Expected: %s and %s", _SRC_CSV, _SRC_BPMN
        )
        return False

    try:
        SAMPLE_INPUT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_SRC_CSV,  CSV_PATH)
        shutil.copy2(_SRC_BPMN, BPMN_PATH)
        logger.info("[sample_data] Copied %s → %s", _SRC_CSV.name,  CSV_PATH)
        logger.info("[sample_data] Copied %s → %s", _SRC_BPMN.name, BPMN_PATH)
        return True
    except Exception:
        logger.exception("[sample_data] Failed to copy sample dataset.")
        return False


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    generate()
