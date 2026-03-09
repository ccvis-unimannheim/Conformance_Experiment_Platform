import pathlib as pl
from typing import Final

BASE_DIRECTORY: Final[pl.Path] = pl.Path.cwd() / "ProViBackend"  # under docker its /code/ProViBackend