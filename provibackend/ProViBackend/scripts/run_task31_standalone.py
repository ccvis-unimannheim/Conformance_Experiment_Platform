"""
Standalone runner for task31 new idioms.

Builds synthetic trace data from the BPIC12 CSV (no pm4py needed),
then runs task31.generate() to produce all 7 SVGs.
"""
import sys, os, warnings
warnings.filterwarnings("ignore")

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "tasks"))

import numpy as np
import pandas as pd

# ── Load BPIC12 CSV and derive synthetic fitness & outcome ───────────────────
CSV_PATH   = os.path.join(SCRIPT_DIR, "..", "new_input", "BPIC12_Log_onlyA.csv")
OUT_DIR    = os.path.join(SCRIPT_DIR, "..", "new_output", "task31")
os.makedirs(OUT_DIR, exist_ok=True)

print("Loading CSV...")
df_raw = pd.read_csv(CSV_PATH)
print(f"  Columns: {list(df_raw.columns)}")
print(f"  Rows: {len(df_raw)}")

# Detect column names
case_col = next((c for c in df_raw.columns if c.lower() in ("case:concept:name","case_id","caseid")), df_raw.columns[0])
act_col  = next((c for c in df_raw.columns if c.lower() in ("concept:name","activity","activityname")), df_raw.columns[1])
ts_col   = next((c for c in df_raw.columns if "time" in c.lower() or "timestamp" in c.lower()), None)

print(f"  Case col: {case_col}, Activity col: {act_col}, Timestamp col: {ts_col}")

# Group by case to get per-trace activity sequences
grp = df_raw.groupby(case_col)
case_ids = list(grp.groups.keys())
print(f"  Total traces: {len(case_ids)}")

# ── Build a synthetic EventLog-like list of traces ───────────────────────────
# Each "trace" is a list of event dicts (concept:name, time:timestamp)
rng = np.random.default_rng(42)

class FakeTrace(list):
    """Minimal PM4Py-like trace: list of event dicts with .attributes."""
    def __init__(self, events, attrs=None):
        super().__init__(events)
        self.attributes = attrs or {}

log = []
for cid in case_ids:
    sub = grp.get_group(cid)
    if ts_col:
        sub = sub.sort_values(ts_col)
    events = []
    for _, row in sub.iterrows():
        ev = {"concept:name": str(row[act_col])}
        if ts_col and pd.notna(row[ts_col]):
            try:
                ev["time:timestamp"] = pd.Timestamp(row[ts_col])
            except Exception:
                pass
        events.append(ev)
    attrs = {}
    for col in df_raw.columns:
        if col not in (case_col, act_col, ts_col or ""):
            val = sub[col].iloc[0] if len(sub) > 0 else None
            attrs[col] = val
    log.append(FakeTrace(events, attrs))

print(f"  Built {len(log)} fake traces")

# ── Build synthetic alignment results ────────────────────────────────────────
# Derive fitness from activity patterns: A_ACTIVATED → higher fitness
OUTCOME_ACT = "A_ACTIVATED"
REJECT_ACTS = {"A_DECLINED", "A_CANCELLED"}

alignments = []
for trace in log:
    acts = {str(e.get("concept:name","")) for e in trace}
    has_outcome = OUTCOME_ACT in acts
    has_reject  = bool(acts & REJECT_ACTS)

    # Fitness: conformant traces tend to follow A_PREACCEPTED→A_ACCEPTED→A_ACTIVATED
    # Use a heuristic: fraction of "expected" activities present
    expected = {"A_PREACCEPTED","A_ACCEPTED","A_ACTIVATED","A_REGISTERED","A_APPROVED"}
    n_expected = len(expected & acts)
    base_fitness = n_expected / len(expected)
    # Add noise
    noise = rng.normal(0, 0.08)
    fitness = float(np.clip(base_fitness + noise, 0.0, 1.0))
    # Rejected traces typically have lower fitness
    if has_reject and not has_outcome:
        fitness = float(np.clip(fitness * 0.6 + rng.normal(0, 0.05), 0.0, 0.95))

    # Build fake alignment steps (not used by new idioms but needed by task20)
    alignment = []
    for e in trace:
        act = str(e.get("concept:name",""))
        if rng.random() < fitness:
            alignment.append(((act, act), (act, act)))   # sync move
        else:
            alignment.append(((act, act), (">>", ">>"))) # log move

    alignments.append({
        "fitness": fitness,
        "cost": int((1.0 - fitness) * len(trace) * 2),
        "alignment": alignment,
    })

fitnesses = [a["fitness"] for a in alignments]
print(f"  Fitness: min={min(fitnesses):.3f} max={max(fitnesses):.3f} mean={np.mean(fitnesses):.3f}")

# ── Monkey-patch task31 helpers to use our outcome activity ─────────────────
import tasks.task31 as t31
t31._OUTCOME_ACTIVITY = OUTCOME_ACT
t31._REJECTED_FINAL_ACTIVITIES = REJECT_ACTS

# ── Run generate() ───────────────────────────────────────────────────────────
print("\nRunning task31.generate()...")
t31.generate(log, alignments, OUT_DIR, outcome_activity=OUTCOME_ACT)

print(f"\nDone! SVGs written to: {os.path.abspath(OUT_DIR)}")
for f in sorted(os.listdir(OUT_DIR)):
    size = os.path.getsize(os.path.join(OUT_DIR, f))
    print(f"  {f:50s}  {size:>8,} bytes")
