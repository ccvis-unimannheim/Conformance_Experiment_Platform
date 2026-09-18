import pathlib as pl
from typing import Final

BASE_DIRECTORY: Final[pl.Path] = pl.Path.cwd() / "ProViBackend"  # under docker its /code/ProViBackend

# Fixed, admin-uploaded idiom assets (static images/SVGs, not per-dataset generated).
# Under data/ so they sit on the persisted docker volume; they used to live in
# app/static/custom_idioms, which every redeploy wiped (see
# utils/idiom_files.migrate_legacy_custom_idioms).
CUSTOM_IDIOM_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "data" / "_custom_idioms"
LEGACY_CUSTOM_IDIOM_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "app" / "static" / "custom_idioms"

# Per-experiment images that replace generated idioms: imported from an idiom
# bundle or uploaded one by one. Laid out as {experiment_id}/{task_key}/{idiom_key}.{ext}.
IDIOM_OVERRIDE_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "data" / "_idiom_overrides"

# Admin-uploaded process model images shown on the participant intro pages, one
# per experiment. Lives under data/ so it sits on the persisted docker volume.
PROCESS_MODEL_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "data" / "_process_models"