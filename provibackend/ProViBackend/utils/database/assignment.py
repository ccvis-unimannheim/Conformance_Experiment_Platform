"""
Participant assignment logic: balanced random idiom allocation.

Between-subjects: for each task the idiom with the fewest prior assignments is
chosen (random tiebreak), keeping the distribution across idioms equal over time.

Within-subjects: every participant receives all idioms for every task; the full
trial list is shuffled when within_sequence_mode == "random".

Note on concurrency: if two participants call this simultaneously in between
mode, both may read the same counts and land on the same idiom. For typical
research experiment sizes (<200 participants) this slight skew is acceptable.
If strict balance is required, wrap the read-count + insert in a MongoDB
transaction.
"""

import random
import uuid
from collections import defaultdict

import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.utils as utils


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _group_configs_by_task(task_configs: list[dict]) -> dict[str, list[dict]]:
    """Return {task_id: [task_config, ...]} preserving insertion order."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for tc in task_configs:
        grouped[tc["task_id"]].append(tc)
    return dict(grouped)


def _count_idiom_assignments(
    experiment_id: str,
    task_id: str,
    candidate_idiom_ids: list[str],
) -> dict[str, int]:
    """
    Count how many existing UserAssignments used each candidate idiom for this
    task in this experiment.

    Returns {idiom_id: count}, with 0 for idioms not yet assigned.
    """
    counts = {iid: 0 for iid in candidate_idiom_ids}
    existing = dbc.get_query_db(
        "UserAssignment",
        query={"experiment_id": experiment_id},
        projection={"assigned_between": 1, "_id": 0},
    )
    for assignment in existing:
        # assigned_between: {task_id: idiom_id}
        idiom_id = assignment.get("assigned_between", {}).get(task_id)
        if idiom_id and idiom_id in counts:
            counts[idiom_id] += 1
    return counts


def _pick_least_assigned(options: list[dict], counts: dict[str, int]) -> dict:
    """
    Return the task_config dict whose idiom_id has the lowest assignment count.
    Ties are broken randomly to avoid systematic ordering bias.
    """
    min_count = min(counts[opt["idiom_id"]] for opt in options)
    candidates = [opt for opt in options if counts[opt["idiom_id"]] == min_count]
    return random.choice(candidates)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assign_participant_to_experiment(user_id: str, experiment_id: str) -> dict:
    """
    Create and persist a balanced idiom assignment for a participant.

    - Idempotent: returns the existing assignment unchanged on repeat calls.
    - Between-subjects: one idiom per task chosen via least-assigned balancing
      (random tiebreak). group_id is set to the sorted assigned idiom_ids.
    - Within-subjects: all idioms for every task are included; every participant
      sees the full set. group_id is set to "within".
    - Trial order is shuffled when within_sequence_mode == "random".

    Returns the UserAssignment document dict (including '_id').
    Raises ValueError when the experiment is missing or has no task_configs.
    """
    existing = dbc.get_user_assignment(user_id, experiment_id)
    if existing:
        return existing

    experiment = dbc.get_document("Experiment", {"_id": experiment_id})
    if not experiment:
        raise ValueError(f"Experiment not found: {experiment_id}")

    task_configs: list[dict] = experiment.get("task_configs", [])
    if not task_configs:
        raise ValueError(f"Experiment '{experiment_id}' has no task_configs.")

    design_type = experiment.get("design_type", "between")
    grouped = _group_configs_by_task(task_configs)

    assigned_between: dict[str, str] = {}
    trial_sequence: list[str] = []
    group_id: str = ""

    if design_type == "within":
        # Within-subjects: participant sees ALL idioms for every task
        for task_id, options in grouped.items():
            for opt in options:
                trial_sequence.append(
                    f"{task_id}::{opt['idiom_id']}::{opt['dataset_id']}"
                )
        if experiment.get("within_sequence_mode", "fixed") == "random":
            random.shuffle(trial_sequence)
        group_id = "within"
    else:
        # Between-subjects: one idiom per task, least-assigned balancing
        for task_id, options in grouped.items():
            candidate_ids = [opt["idiom_id"] for opt in options]
            counts = _count_idiom_assignments(experiment_id, task_id, candidate_ids)
            chosen = _pick_least_assigned(options, counts)

            assigned_between[task_id] = chosen["idiom_id"]
            trial_sequence.append(
                f"{task_id}::{chosen['idiom_id']}::{chosen['dataset_id']}"
            )
        if experiment.get("within_sequence_mode", "fixed") == "random":
            random.shuffle(trial_sequence)
        # group_id encodes which idiom was assigned per task (sorted by task_id)
        group_id = ",".join(iid for _, iid in sorted(assigned_between.items()))

    assignment_doc = {
        "_id": str(uuid.uuid4()),
        "experiment_id": experiment_id,
        "user_id": user_id,
        "group_id": group_id,
        "assigned_between": assigned_between,
        "trial_sequence": trial_sequence,
        "current_trial_index": 0,
        "insert_datetime": utils.get_current_datetime(),
    }

    dbc.create_document("UserAssignment", assignment_doc)
    return assignment_doc


def get_assignment(user_id: str, experiment_id: str) -> dict | None:
    """Return the existing UserAssignment, or None if not yet created."""
    return dbc.get_user_assignment(user_id, experiment_id)


def parse_trial_token(token: str) -> tuple[str, str, str]:
    """
    Parse a trial_sequence token back to (task_id, idiom_id, dataset_id).

    Tokens are written as 'task_id::idiom_id::dataset_id'.
    """
    parts = token.split("::")
    if len(parts) != 3:
        raise ValueError(f"Malformed trial token: {token!r}")
    return parts[0], parts[1], parts[2]
