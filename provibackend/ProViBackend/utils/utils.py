import datetime
import os
import pathlib as pl
import hashlib

from ProViBackend.utils import config


def extract_filename_from_path(file_path: str) -> str:
    assert os.path.isfile(file_path)
    file_path = pl.Path(file_path)
    file_name_with_ending = file_path.name
    file_name, ending = file_name_with_ending.split(".")
    return file_name


def convert_path_to_str(path: pl.Path) -> str:
    return str(path.absolute())


def get_file_checksum(file_path: pl.Path) -> str:
    """MD5 hex digest of the file. (Datasets uploaded before this returned the
    digest itself carry "<md5 _hashlib.HASH object @ …>" instead.)"""
    with open(file_path, "rb") as file:
        return hashlib.file_digest(file, "md5").hexdigest()


def get_current_datetime():
    # get current datetime
    return str(datetime.datetime.now())


def process_model_path(exp: dict) -> pl.Path | None:
    """Path of the experiment's uploaded process model image, or None when it
    uses the bundled order-to-cash diagram (or the file has gone missing)."""
    ext = exp.get("process_model_ext")
    if not ext:
        return None
    path = config.PROCESS_MODEL_DIRECTORY / f"{exp['_id']}{ext}"
    return path if path.exists() else None


def image_media_type(ext: str) -> str:
    return {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext.lower(), "application/octet-stream")