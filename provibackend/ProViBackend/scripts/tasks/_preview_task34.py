"""Generate Task 34 SVGs locally with synthetic data.
Run with: python _preview_task34.py  (from scripts/tasks/ directory)
SVGs are written to /tmp/task34_preview/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUTPUT_DIR = "/tmp/task34_preview"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Synthetic alignments — mix of violation types across several traces
ALIGNMENTS = [
    {   # Trace 1: worst (5 violations)
        "fitness": 0.3,
        "alignment": [
            ["A_SUBMITTED",   "A_SUBMITTED"],
            ["A_APPROVED",    ">>"],
            [">>",            "A_DECLINED"],
            ["A_CANCELLED",   "A_ACTIVATED"],
            ["A_APPROVED",    ">>"],
            [">>",            "A_REGISTERED"],
        ],
    },
    {   # Trace 2: 3 violations
        "fitness": 0.6,
        "alignment": [
            ["A_SUBMITTED",   "A_SUBMITTED"],
            ["A_APPROVED",    ">>"],
            [">>",            "A_DECLINED"],
            ["A_ACTIVATED",   "A_ACTIVATED"],
            [">>",            "A_REGISTERED"],
        ],
    },
    {   # Trace 3: 2 violations
        "fitness": 0.75,
        "alignment": [
            ["A_SUBMITTED",   "A_SUBMITTED"],
            ["A_ACTIVATED",   "A_ACTIVATED"],
            ["A_APPROVED",    ">>"],
            [">>",            "A_DECLINED"],
        ],
    },
    {   # Trace 4: 1 violation
        "fitness": 0.9,
        "alignment": [
            ["A_SUBMITTED",   "A_SUBMITTED"],
            ["A_ACTIVATED",   "A_ACTIVATED"],
            [">>",            "A_REGISTERED"],
        ],
    },
    {   # Trace 5: conformant
        "fitness": 1.0,
        "alignment": [
            ["A_SUBMITTED",   "A_SUBMITTED"],
            ["A_ACTIVATED",   "A_ACTIVATED"],
            ["A_REGISTERED",  "A_REGISTERED"],
        ],
    },
]

from task34 import generate

MODEL_PATH = (
    "/Users/tayyabazafar/Desktop/Conformance_Experiment_Platform"
    "/provibackend/ProViBackend/data"
    "/a67dfb01-d640-4516-8e71-f5466d30e944/input/Guideline.bpmn"
)

generate(log=None, alignments=ALIGNMENTS, output_dir=OUTPUT_DIR, model_path=MODEL_PATH)

print(f"\nSVGs written to: {OUTPUT_DIR}")
print("Files:")
for f in sorted(os.listdir(OUTPUT_DIR)):
    path = os.path.join(OUTPUT_DIR, f)
    size = os.path.getsize(path)
    print(f"  {f}  ({size:,} bytes)")

# Open all SVGs in the browser
import subprocess
for f in sorted(os.listdir(OUTPUT_DIR)):
    subprocess.Popen(["open", os.path.join(OUTPUT_DIR, f)])
