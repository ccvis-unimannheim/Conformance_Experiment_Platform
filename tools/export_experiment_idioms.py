#!/usr/bin/env python3
"""Export every generated idiom (SVG) of an experiment, by experiment name.

Talks only to the public HTTP API (no DB creds / SSH needed):

    GET  /api/admin/experiments                          -> find experiment by name
    GET  /api/admin/tasks, /api/admin/idioms             -> map ids -> readable keys
    GET  /api/participant/vis/{dataset}/{task}/{idiom}?experiment_id=...  -> the SVG

For each (task, idiom, dataset) entry in the experiment's task_configs it writes
    <out>/<experiment_name>/<task_key>__<idiom_key>.svg

Stdlib only — runs with any Python 3 (no pip install).

Examples
--------
    python tools/export_experiment_idioms.py "My Experiment"
    python tools/export_experiment_idioms.py "My Experiment" \
        --base-url http://127.0.0.1:1234 --out ./exported
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "https://cc-vis.rz.uni-mannheim.de/api"


def _get(url: str):
    """GET a URL; return (content_bytes, content_type)."""
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def _get_json(url: str):
    body, _ = _get(url)
    return json.loads(body.decode("utf-8"))


def _safe(name: str) -> str:
    """Filesystem-safe slug for folder/file names."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "unnamed"


def main() -> int:
    ap = argparse.ArgumentParser(description="Export an experiment's idiom SVGs by name.")
    ap.add_argument("experiment_name", help="Exact experiment name (use --contains for substring).")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help=f"API base URL (default: {DEFAULT_BASE_URL})")
    ap.add_argument("--out", default="./exported_idioms", help="Output directory.")
    ap.add_argument("--contains", action="store_true",
                    help="Match experiments whose name CONTAINS the argument (case-insensitive).")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")

    # 1. Locate the experiment by name.
    try:
        experiments = _get_json(f"{base}/admin/experiments")
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach {base}/admin/experiments — {e}", file=sys.stderr)
        return 2

    if args.contains:
        needle = args.experiment_name.lower()
        matches = [e for e in experiments if needle in (e.get("name") or "").lower()]
    else:
        matches = [e for e in experiments if (e.get("name") or "") == args.experiment_name]

    if not matches:
        names = ", ".join(repr(e.get("name")) for e in experiments) or "(none)"
        print(f"ERROR: no experiment matched {args.experiment_name!r}.\nAvailable: {names}",
              file=sys.stderr)
        return 1
    if len(matches) > 1:
        names = ", ".join(repr(e.get("name")) for e in matches)
        print(f"ERROR: {len(matches)} experiments matched: {names}\n"
              f"Refine the name (exact match) to disambiguate.", file=sys.stderr)
        return 1

    exp = matches[0]
    exp_id = str(exp.get("_id", ""))
    exp_name = exp.get("name", exp_id)
    print(f"Experiment: {exp_name!r}  (_id={exp_id}, status={exp.get('status')})")

    # 2. Build id -> readable-key maps.
    tasks = _get_json(f"{base}/admin/tasks")
    idioms = _get_json(f"{base}/admin/idioms")
    task_key_by_id = {t["_id"]: t.get("task_key", t["_id"]) for t in tasks}
    idiom_key_by_id = {i["_id"]: i.get("idiom_key", i["_id"]) for i in idioms}

    # 3. Flatten the experiment's (task, idiom, dataset) triples.
    #    Prefer task_configs (flat, one per idiom); fall back to task_instances.
    triples = []
    seen = set()
    for tc in exp.get("task_configs", []):
        key = (tc.get("task_id"), tc.get("idiom_id"), tc.get("dataset_id"))
        if all(key) and key not in seen:
            seen.add(key)
            triples.append(key)
    if not triples:
        for ti in exp.get("task_instances", []):
            for idiom_id in ti.get("idiom_ids", []):
                key = (ti.get("task_id"), idiom_id, ti.get("dataset_id"))
                if all(key) and key not in seen:
                    seen.add(key)
                    triples.append(key)

    if not triples:
        print("ERROR: experiment has no (task, idiom, dataset) entries to export.", file=sys.stderr)
        return 1

    out_dir = os.path.join(args.out, _safe(exp_name))
    os.makedirs(out_dir, exist_ok=True)
    print(f"Exporting {len(triples)} idiom(s) -> {out_dir}\n")

    ok, failed = 0, 0
    for task_id, idiom_id, dataset_id in triples:
        task_key = task_key_by_id.get(task_id, task_id)
        idiom_key = idiom_key_by_id.get(idiom_id, idiom_id)
        qs = urllib.parse.urlencode({"experiment_id": exp_id})
        url = f"{base}/participant/vis/{dataset_id}/{task_id}/{idiom_id}?{qs}"
        fname = f"{_safe(task_key)}__{_safe(idiom_key)}.svg"
        dest = os.path.join(out_dir, fname)
        try:
            body, ctype = _get(url)
            with open(dest, "wb") as f:
                f.write(body)
            print(f"  ok    {fname}  ({len(body)} bytes)")
            ok += 1
        except urllib.error.HTTPError as e:
            print(f"  FAIL  {fname}  (HTTP {e.code} — not generated yet?)", file=sys.stderr)
            failed += 1
        except urllib.error.URLError as e:
            print(f"  FAIL  {fname}  ({e})", file=sys.stderr)
            failed += 1

    print(f"\nDone: {ok} exported, {failed} failed -> {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
