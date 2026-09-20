import pathlib as pl
from typing import Final

BASE_DIRECTORY: Final[pl.Path] = pl.Path.cwd() / "DfgBackend"  # under docker its /code/DfgBackend

# Fixed, admin-uploaded idiom assets (static images/SVGs, not per-dataset generated).
CUSTOM_IDIOM_DIRECTORY: Final[pl.Path] = BASE_DIRECTORY / "app" / "static" / "custom_idioms"