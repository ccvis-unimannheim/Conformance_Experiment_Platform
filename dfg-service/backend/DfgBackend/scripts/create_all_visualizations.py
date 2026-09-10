import DfgBackend.FilterModel.NewFilter as NewFilter
import DfgBackend.MentalMapModel.MentalMap as MentalMap
import os
from pathlib import Path
import time
import DfgBackend.utils.utils as utils
import DfgBackend.FilterModel.Styling as Styling
from DfgBackend.scripts.cleaner import clean_directory_from_xes_and_pickle


def create_all_visualizations(base_xes_filepath: Path, target_path: Path) -> None:
    """
    # create a file structure
    # /visualisations
    #   - ./
    #   - ./normal
    #   - mapping.json
    """
    start_time = time.time()
    assert os.path.isdir(target_path)
    assert os.path.isfile(base_xes_filepath)
    base_xes_filepath = Path(base_xes_filepath)
    filename = utils.extract_filename_from_path(str(base_xes_filepath.absolute()))
    base_path = Path(target_path) / filename
    mental_map_path = Path(base_path / "mentalmap")
    mental_map_path.mkdir(parents=True, exist_ok=True)
    normal_map_path = Path(base_path / "normal")
    normal_map_path.mkdir(parents=True, exist_ok=True)
    base_xes_filepath_string = str(base_xes_filepath.absolute())

    #  Create all filtered eventlogs as pickle files
    NewFilter.create_all_subplots(base_xes_filepath, normal_map_path)

    # Compute all mental map visualizations
    print("Computing mental map")
    start_time_mental_map = time.time()
    MentalMap.mental_map(base_xes_filepath_string, normal_map_path, str(mental_map_path.absolute()))
    print(f"Time taken to compute mental map: {round(time.time() - start_time_mental_map) / 60} minutes")

    # Compute all normal map visualizations and apply styling changes
    print("Computing normal map")
    start_time_normal_map = time.time()
    node_mapping, edge_mapping = Styling.map_event_labels(base_xes_filepath, target_path)
    Styling.adjust_xes_labels(target_path, base_xes_filepath, node_mapping, edge_mapping)
    print(f"Time taken to compute normal map: {round(time.time() - start_time_normal_map) / 60} minutes")

    # free up memory
    clean_directory_from_xes_and_pickle(mental_map_path)
    clean_directory_from_xes_and_pickle(normal_map_path)
    print(f"Time taken to compute all svgs: {round(time.time() - start_time) / 60} minutes")
