import datetime
import os
import pathlib as pl
import hashlib


def extract_filename_from_path(file_path: str) -> str:
    assert os.path.isfile(file_path)
    file_path = pl.Path(file_path)
    file_name_with_ending = file_path.name
    file_name, ending = file_name_with_ending.split(".")
    return file_name


def convert_path_to_str(path: pl.Path) -> str:
    return str(path.absolute())


def get_file_checksum(file_path: pl.Path) -> str:
    with open(file_path, "rb") as file:
        md5_checksum = hashlib.file_digest(file, "md5")
        return str(md5_checksum)


def get_current_datetime():
    # get current datetime
    return str(datetime.datetime.now())