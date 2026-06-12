"""Standalone runner for task29 new idioms — no pm4py needed."""
import sys, os, warnings
warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "tasks"))

import numpy as np
import pandas as pd
import tasks.task29 as t29

CSV_PATH = os.path.join(SCRIPT_DIR, "..", "new_input", "BPIC12_Log_onlyA.csv")
OUT_DIR  = os.path.join(SCRIPT_DIR, "..", "new_output", "task29")
os.makedirs(OUT_DIR, exist_ok=True)

print("Loading CSV...")
df_raw = pd.read_csv(CSV_PATH)
case_col = "case:concept:name"; act_col = "concept:name"; ts_col = "time:timestamp"
grp = df_raw.groupby(case_col)
case_ids = list(grp.groups.keys())
print(f"  {len(case_ids)} traces")

# Build a synthetic alignments list with realistic violation patterns
rng = np.random.default_rng(42)
ACTIVITIES = list(df_raw[act_col].unique())
VTYPES = ["Model Move", "Log Move", "Mismatch Move"]
expected_activities = {"A_PREACCEPTED", "A_ACCEPTED", "A_ACTIVATED", "A_REGISTERED", "A_APPROVED", "A_FINALIZED"}

alignments = []
for cid in case_ids:
    sub = grp.get_group(cid).sort_values(ts_col)
    acts = list(sub[act_col])
    steps = []
    for i, act in enumerate(acts):
        if act in expected_activities and rng.random() < 0.85:
            steps.append(((act, act), (act, act)))          # sync
        elif rng.random() < 0.35:
            exp_act = rng.choice(list(expected_activities))
            steps.append(((">>", ">>"), (exp_act, exp_act)))  # model move
        elif rng.random() < 0.25:
            steps.append(((act, act), (">>", ">>")))          # log move
        else:
            steps.append(((act, act), (act, act)))            # sync
    n_viol = sum(1 for s in steps if s[0][0] == ">>" or s[1][0] == ">>")
    fitness = max(0.0, 1.0 - n_viol / max(len(steps), 1))
    alignments.append({"fitness": fitness, "cost": n_viol, "alignment": steps})

print(f"  Built {len(alignments)} alignments")

print("\nRunning task29.generate()...")
t29.generate(alignments, OUT_DIR)

print("\nSVGs:")
for f in sorted(os.listdir(OUT_DIR)):
    if f.endswith(".svg"):
        sz = os.path.getsize(os.path.join(OUT_DIR, f))
        print(f"  {f:55s}  {sz:>9,} bytes")
