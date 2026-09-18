import pathlib as pl
from typing import Final

BASE_DIRECTORY: Final[pl.Path] = pl.Path.cwd() / "ProViBackend"  # under docker its /code/ProViBackend

# Fixed, admin-uploaded idiom assets (static images/SVGs, not per-dataset generated).
CUSTOM_IDIOM_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "app" / "static" / "custom_idioms"

# Admin-uploaded process model images shown on the participant intro pages, one
# per experiment. Lives under data/ so it sits on the persisted docker volume.
PROCESS_MODEL_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "data" / "_process_models"