import pathlib as pl

def clean_directory_from_xes_and_pickle(directory_path: pl.Path) -> None:
    for file in directory_path.iterdir():
        if file.suffix == '.xes' or file.suffix == '.pickle':
            file.unlink()