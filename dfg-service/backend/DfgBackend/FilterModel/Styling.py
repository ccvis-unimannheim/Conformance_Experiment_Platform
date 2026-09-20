import DfgBackend.MentalMapModel.FixGraphvizIds as FixGraphvizIds
import subprocess
import re
from pm4py.visualization.dfg import visualizer as dfg_visualization
import os
import pm4py
from pathlib import Path
import DfgBackend.utils.utils as utils
import DfgBackend.FilterModel.helper as helper

def extract_paths(target_path, base_xes_filepath):
    """ Extract paths for further handling """
    assert os.path.isdir(target_path)
    assert os.path.isfile(base_xes_filepath)
    base_xes_filepath = Path(base_xes_filepath)
    filename = utils.extract_filename_from_path(str(base_xes_filepath.absolute()))
    base_path = Path(target_path) / filename
    normal_map_path = Path(base_path / "normal")
    normal_map_path.mkdir(parents=True, exist_ok=True)
    target_directory = normal_map_path
    return normal_map_path, target_directory

def extract_nodes_edges(node_mapping, node_map, edge_mapping, edge_map):
    """ Creates dictionaries containing the label and the respective attributes of the nodes and labels """
    # Store edges
    for (tail_id, head_id), attrs in edge_map.items():
        edge_mapping[(tail_id, head_id)] = attrs
    # Store nodes
    for node_id, attrs in node_map.items():
        node_mapping[node_id] = attrs
    return node_mapping, edge_mapping

def adjust_label_styling(node_map, node_mapping):
    """ Adjusts node labels according to full map labels """
    for node_id, attrs in node_map.items():
        if node_id not in ['"@@startnode"', '"@@endnode"', 'left_bottom_anchor', 'top_right_anchor']:
            attrs['style'] = 'filled'
            attrs['shape'] = 'box'
        new_label = node_mapping[node_id]['label']
        attrs['label'] = new_label
    return node_map

def adjust_edge_styling(edge_map, edge_mapping):
    """ 
    - Currently not needed -
    Adjusts edge labels according to full map labels
    """
    for (tail_id, head_id), attrs in edge_map.items():
        if (tail_id, head_id) in edge_mapping:
            attrs['label'] = edge_mapping[((tail_id, head_id))]['label']
    return edge_map

def update_maps(node_map, edge_map, full_label_mapping):
    """ Update the node_map and edge_map for consistent naming and identification of nodes and labels """
    node_map_keys_to_delete = []
    node_map_elements_to_add = {}
    for item in full_label_mapping.items():
        edge_map_keys_to_delete = []
        edge_map_elements_to_add = {}
        for k, v in node_map.items():
            if item[0] in k:
                k_update = re.sub(item[0], item[1], k)
                node_map_elements_to_add[k_update] = node_map[k]
                node_map_keys_to_delete.append(k)
        for k, v in edge_map.items():
            a, b = k
            a_update = None
            b_update = None
            k_update = None
            if item[0] in a:
                a_update = re.sub(item[0], item[1], a)
            if item [0] in b:
                b_update = re.sub(item[0], item[1], b)
            if a_update or b_update:
                if a_update and b_update:
                    k_update = (a_update, b_update)
                elif a_update:
                    k_update = (a_update, b)
                elif b_update:
                    k_update = (a, b_update)
            if k_update:
                edge_map_elements_to_add[k_update] = edge_map[k]
                edge_map_keys_to_delete.append(k)
        for k in edge_map_keys_to_delete:
            del edge_map[k]
        edge_map = {**edge_map, **edge_map_elements_to_add}

    for k in node_map_keys_to_delete:
        del node_map[k]
    node_map = {**node_map, **node_map_elements_to_add}
    return node_map, edge_map

def map_event_labels(base_xes_filepath: Path, target_path: Path):
    """ Extracts dictionaries with name:label from input file containing nodes and edges """
    # Get the paths
    normal_map_path, target_directory = extract_paths(target_path, base_xes_filepath)
    # Import the file and transform into DOT file
    log = helper.load_event_log_as_pickle_or_xes(str(base_xes_filepath.absolute()))
    gviz = helper.process_file(log)
    gviz.render(target_directory / 'FullDot', format='dot', view=False)
    dot_file_path = target_directory / 'FullDot.dot'
    with open(dot_file_path, 'r') as dot_file:
        content = dot_file.read()
    statements = content.split('];')
    # Initialize dictionaries to store components
    graph_attrs = {}
    node_map = {}
    edge_map = {}
    # Iterate over individual lines from file and extract components
    for statement in statements:
        line = statement.strip() + ']'  # Add closing bracket back for consistency
        if not line or line == ']':
            continue
        # Identify attributes
        if line.startswith('digraph'):
            graph_attrs = helper.identify_attributes(line)
            continue
        if line.startswith('node ['):
            continue
        # Identify nodes
        if '[' in line and '->' not in line:  # It's a node if there's no '->'
            node_map = helper.identify_nodes(line, node_map)
            continue
        # Identify edges
        if '->' in line:
            edge_map = helper.identify_edges(line, edge_map)
    # Store result in DOT file
    helper.write_dot_file(dot_file_path, graph_attrs, node_map, edge_map)
    # Fix labels for consistent naming / identification and update
    full_label_mapping = FixGraphvizIds.node_id_label_mapping(dot_file_path)
    node_map, edge_map = update_maps(node_map, edge_map, full_label_mapping)
    # Generate images
    svg_directory = normal_map_path
    svg_output_path = svg_directory / "FullGraph.svg"
    # Generate SVG images from DOT file
    _ = subprocess.run(['neato', '-Tsvg', '-n2', dot_file_path, '-o', svg_output_path], check=True)
    # Store components to re-use when styling other SVGs
    node_mapping = {}
    edge_mapping = {}
    node_mapping, edge_mapping = extract_nodes_edges(node_mapping, node_map, edge_mapping, edge_map)
    return node_mapping, edge_mapping


def adjust_xes_labels(target_path: Path, base_xes_filepath: Path, node_mapping, edge_mapping):
    """ Adjusts the 'label' attribute and exports the SVG """
    # Get the paths
    normal_map_path, target_directory = extract_paths(target_path, base_xes_filepath)
    # Iterate over list of files
    base_filenames = {os.path.splitext(file_name)[0] for file_name in os.listdir(normal_map_path) if file_name.endswith('.pickle')}
    for file_name in base_filenames:
        file_path = helper.create_path(file_name, target_directory)
        log = helper.load_event_log_as_pickle_or_xes(file_path)
        gviz = helper.process_file(log)
        gviz.render(target_directory / 'HalfDot', format='dot', view=False)
        # Clean the file and save as dot-file
        dot_file_path = target_directory / 'HalfDot.dot'
        with open(dot_file_path, 'r') as dot_file:
            content = dot_file.read()
        statements = content.split('];')
        graph_attrs = {}
        node_map = {}
        edge_map = {}
        # Iterate over individual lines from file and extract components
        for statement in statements:
            line = statement.strip() + ']'  # Add closing bracket back for consistency
            if not line or line == ']':
                continue
            # Identify attributes
            if line.startswith('digraph'):
                graph_attrs = helper.identify_attributes(line)
                continue
            if line.startswith('node ['):
                continue
            # Identify nodes
            if '[' in line and '->' not in line:  # It's a node if there's no '->'
                node_map = helper.identify_nodes(line, node_map)
                continue
            # Identify edges
            if '->' in line:
                edge_map = helper.identify_edges(line, edge_map)
        # Store result in DOT file
        helper.write_dot_file(dot_file_path, graph_attrs, node_map, edge_map)
        # Fix labels for consistent naming / identification and update
        full_label_mapping = FixGraphvizIds.node_id_label_mapping(dot_file_path)
        node_map, edge_map = helper.replace_node_labels(full_label_mapping, node_map, edge_map)
        # edge_map = adjust_edge_styling(edge_map, edge_mapping)
        node_map = adjust_label_styling(node_map, node_mapping)
        # Store result in DOT file
        helper.write_dot_file(dot_file_path, graph_attrs, node_map, edge_map)
        svg_directory = normal_map_path
        # Return file ending from file_name
        file_name = file_name.split(".")[0]
        # Generate Images
        svg_output_path = f"{file_name}.svg"
        svg_output_path = svg_directory / svg_output_path
        # Generate SVG images from DOT file
        full_svg = subprocess.run(['neato', '-Tsvg', '-n2', dot_file_path, '-o', svg_output_path], check=True)
    return full_svg
