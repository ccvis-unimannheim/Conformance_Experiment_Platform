#!/usr/bin/env python3
"""Generate a minimal synthetic sample dataset for the 2-step preview feature.

Creates:
    scripts/sample_data/input/EventLog.xes
    scripts/sample_data/input/Guideline.bpmn

Called automatically at startup (main.py lifespan) when the files are absent.
The synthetic log models a simplified loan-application process: 5 activities,
35 traces (25 conformant, 10 non-conformant), timestamps over ~35 days.
"""
import datetime
import logging
import pathlib
import random

logger = logging.getLogger(__name__)

# XES trace-level case ID key — NOT the DataFrame column name ('case:concept:name').
# pm4py adds the 'case:' prefix when converting XES → DataFrame, so the raw
# trace attribute must stay as 'concept:name'.
_XES_CASE_KEY = "concept:name"

_SCRIPT_DIR = pathlib.Path(__file__).parent
SAMPLE_INPUT_DIR = _SCRIPT_DIR / "sample_data" / "input"
XES_PATH  = SAMPLE_INPUT_DIR / "EventLog.xes"
BPMN_PATH = SAMPLE_INPUT_DIR / "Guideline.bpmn"

_HAPPY       = ["A_SUBMITTED", "A_PARTLY_SUBMITTED", "A_PREACCEPTED", "A_ACCEPTED"]
_ALT         = ["A_SUBMITTED", "A_PARTLY_SUBMITTED", "A_PREACCEPTED", "A_DECLINED"]
_NON_CONFORM = [
    ["A_SUBMITTED", "A_PREACCEPTED", "A_ACCEPTED"],
    ["A_SUBMITTED", "A_ACCEPTED"],
    ["A_SUBMITTED", "A_PARTLY_SUBMITTED", "A_DECLINED"],
]


def _build_event_log():
    from pm4py.objects.log.obj import EventLog, Trace, Event

    rng  = random.Random(42)
    base = datetime.datetime(2024, 1, 1, 8, 0, 0, tzinfo=datetime.timezone.utc)
    log  = EventLog()

    def add_trace(case_id, activities, start):
        trace = Trace()
        trace.attributes[_XES_CASE_KEY] = case_id
        t = start
        for act in activities:
            ev = Event()
            ev["concept:name"]   = act
            ev["time:timestamp"] = t
            t += datetime.timedelta(hours=rng.randint(1, 12))
            trace.append(ev)
        log.append(trace)

    for i in range(25):
        path = _HAPPY if rng.random() > 0.3 else _ALT
        add_trace(f"C{i+1:03d}", path, base + datetime.timedelta(days=i))

    for i in range(10):
        path = rng.choice(_NON_CONFORM)
        add_trace(f"NC{i+1:03d}", path, base + datetime.timedelta(days=25 + i))

    return log


def generate() -> bool:
    """Generate sample XES + BPMN if absent. Returns True on success."""
    if XES_PATH.exists() and BPMN_PATH.exists():
        logger.info("[sample_data] Sample dataset already present — skipping generation.")
        return True

    try:
        from pm4py.objects.log.obj import EventLog
        from pm4py.objects.log.exporter.xes import exporter as xes_exporter
        from pm4py.algo.discovery.inductive import algorithm as inductive_miner
        import pm4py

        SAMPLE_INPUT_DIR.mkdir(parents=True, exist_ok=True)

        log = _build_event_log()
        xes_exporter.apply(log, str(XES_PATH))
        logger.info("[sample_data] XES written → %s", XES_PATH)

        conformant_log = EventLog(log[:25])
        process_tree   = inductive_miner.apply(conformant_log)
        net, im, fm    = pm4py.convert_to_petri_net(process_tree)
        bpmn_graph     = pm4py.convert_to_bpmn(net, im, fm)
        pm4py.write_bpmn(bpmn_graph, str(BPMN_PATH))
        logger.info("[sample_data] BPMN written → %s", BPMN_PATH)

        return True

    except Exception:
        logger.exception("[sample_data] Failed to generate sample dataset.")
        return False


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    generate()
