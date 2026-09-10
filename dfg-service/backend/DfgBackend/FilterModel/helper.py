from collections import Counter
import pickle
import re
import pm4py
import os
from pm4py.visualization.dfg import visualizer as dfg_visualization
from pm4py.objects.log.importer.xes import importer as xes_importer


def save_xes_log_as_pickle(xes_log, file_path:str):
    """ Saves a XES file as a pickle for performance improvement """
    with open(file_path, "wb") as file:
        pickle.dump(xes_log, file)


def read_xes_from_pickle(file_path:str):
    """ Read a pickle file and load for further handling """
    with open(file_path, "rb") as file:
        return pickle.load(file)


def get_all_traces_and_occurrences(log: pm4py.objects.log.obj.EventLog):
    """
    Returns a list with tuples that contains end-2-end traces and their occurrences in the log
    """
    traces = [tuple(event['concept:name'] for event in trace) for trace in log]
    trace_counts = Counter(traces)
    return trace_counts.most_common()


def extract_activities_from_single_trace(trace) -> tuple:
    """
    Extracts the activities from a trace and returns them as a list in the correct order.

    Args:
        trace: A trace, which is a list of events.

    Returns:
        A list of activities in the order they occurred.
    """
    activities = [event['concept:name'] for event in trace]
    return tuple(activities)


def get_index_of_trace_in_list(target_trace: pm4py.objects.log.obj.Trace, all_traces:list):
    index = 0
    activities_in_core_trace = extract_activities_from_single_trace(target_trace)
    for trace in all_traces:
        if trace[0] == tuple(activities_in_core_trace):
            return index
        index += 1


def are_additional_entries(list_a: list[tuple], list_b: tuple):
    """Check if there are additional new entries in list_b that are not present in list_a."""
    list_a = get_unique_elements_of_a_list_with_tuples(list_a)
    for item in list_b:
        if item not in list_a:
            return True
    return False


def get_unique_elements_of_a_list_with_tuples(list_a: list[tuple]) ->tuple:
    unique_elements = set()
    for tup in list_a:
        unique_elements.update(tup)
    return tuple(unique_elements)


def get_index_of_trace_occurrence_combination_from_total_list(trace_occurrence: tuple, total_list: list[tuple[tuple[str], int]]):
    index = 0
    for item in total_list:
        if item[0] == trace_occurrence:
            return index
        index += 1
    return -1


def create_path(file_name, output_dir):
    """ Create file path as pickle or xes, depending on availability """
    pickle_path = os.path.join(output_dir, f"{file_name}.pickle")
    xes_path = os.path.join(output_dir, f"{file_name}.xes")
    if os.path.exists(pickle_path):  # Prefer the pickle file
        file_path = pickle_path
    elif os.path.exists(xes_path):  # Fallback to the XES file
        file_path = xes_path
    return file_path

def load_event_log_as_pickle_or_xes(file_path: str):
    """
    Checks if the provided file path exists as a pickle file.
    If it does, reads and returns the pickle file.
    Otherwise, loads the file as an xes file using xes_importer.apply.
    Args:
        file_path (str): Path to the file.

    Returns:
        The loaded file.
    """
    if file_path.endswith('.pickle'):
        try:
            return read_xes_from_pickle(file_path)
        except Exception as e:
            raise ValueError(f"Failed to load pickle file: {e}")
    elif file_path.endswith('.xes'):
        try:
            return xes_importer.apply(file_path)
        except Exception as e:
            raise ValueError(f"Failed to load xes file using xes_importer: {e}")

def parse_attributes(attributes_str):
    """ Format the nodes and edge attributes """
    attrs = {}
    # Adjust quotation marks
    quoted_attrs = re.findall(r'(\w+)\s*=\s*"([^"]*?)"', attributes_str)
    for key, value in quoted_attrs:
        attrs[key] = f'"{value.strip()}"'
    unquoted_attrs = re.findall(r'(\w+)\s*=\s*([^,\s]+(?:\s*[^,]*)?)', attributes_str)
    # Convert edge labels to integers (= frequencies)
    for key, value in unquoted_attrs:
        if key == 'label' and value.isdigit():
            attrs[key] = int(value)
        elif key not in ['label', 'pos', 'bb', 'lp']:
            attrs[key] = value.strip()
    html_labels = re.findall(r'(\w+)\s*=\s*<([^>]*?)>', attributes_str)
    for key, value in html_labels:
        attrs[key] = f'<{value.strip()}>'
    return attrs

def format_graph_attributes(graph_attrs):
    """ Format graph attributes """
    formatted_attrs = []
    # Add quotation marks
    for key, value in graph_attrs.items():
        formatted_attrs.append(f'{key}={value}')
    return ',\n\t'.join(formatted_attrs)


def write_dot_file(output_dot_path, graph_attrs, node_map, edge_map):
    """
    Write a DOT file with predefined nodes and edges.
    Args:
        output_dot_path: name to store DOT file under
        graph_attrs, node_map, edge_map: dictionaries of graph information, nodes, edges and their respective attributes
    Result:
        Produces a DOT-File
    """
    with open(output_dot_path, 'w') as f:
        # Add attributes and styling definitions
        f.write("digraph {\n")
        f.write("graph [\n")
        formatted_attrs = format_graph_attributes(graph_attrs)
        f.write(f"\t{formatted_attrs},\n")
        f.write("];\n\n")
        # Default node and edge styles
        f.write('  node [label="\\N", shape="box"];\n')
        # Add nodes
        for node_id, node_attrs in node_map.items():
            # Set label to an empty string if it’s missing or empty
            if 'label' not in node_attrs or not node_attrs['label']:
                node_attrs['label'] = '""'
            # Define color of nodes
            # node_attrs.pop('fillcolor', None)
            node_attrs['fillcolor'] = '"lightblue"'
            formatted_node_attrs = [f'{key}={value}' for key, value in node_attrs.items()]
            f.write(f'{node_id} [{", ".join(formatted_node_attrs)}];\n')
        # Add edges
        for (tail_id, head_id), attrs in edge_map.items():
            # Define penwidth of edges (disable if automatic generation according to frequency desired)
            attrs.pop('penwidth', None)
            f.write(f'  {tail_id} -> {head_id} [')
            f.write(", ".join(f'{k}={v}' for k, v in attrs.items()))
            f.write("];\n")
        f.write("}\n")

def identify_nodes(line, node_map):
    """
    Read a line and extract nodes.
    Args:
        line: line read from DOT file
        node_map: dictionary to store nodes in
    Returns:
        node_map: dictionary including all nodes detected and their respective information
    """
    # Identify nodes
    node_id, attrs_str = line.split('[')
    node_id = node_id.strip()
    attrs_str = attrs_str.strip()
    if attrs_str.endswith(']'):
        attrs_str = attrs_str[:-1].strip()
    attrs = parse_attributes(attrs_str)
    # attrs.pop('fillcolor', None)
    # Ensure styling
    if 'style' in attrs and 'shape' in attrs:
            attrs['style'] = 'filled'
            attrs['shape'] = 'box'
    # Store node attributes by node_id
    node_map[node_id] = attrs
    return node_map

def identify_edges(line, edge_map):
    """
    Read a line and extract edges.
    Args:
        line: line read from DOT file
        edge_map: dictionary to store edges in
    Returns:
        edge_map: dictionary including all edges detected and their respective information
    """
    edge_definition = line.split('->')
    tail_id = edge_definition[0].strip()
    head_and_attrs = edge_definition[1].strip()
    head_id, attrs_str = head_and_attrs.split('[', 1)
    head_id = head_id.strip()
    attrs_str = attrs_str.strip(' []')
    attrs = parse_attributes(attrs_str)
    # attrs.pop('penwidth', None)
    attrs.pop('label')
    # Store edge attributes by tuple of (tail, head)
    edge_map[(tail_id, head_id)] = attrs
    return edge_map

def identify_attributes(line):
    """
    Read a line and extract attributes of a graph.
    Args:
        line: line read from DOT file
    Returns:
        graph_attrs_str: string of graph information in right format
    """
    graph_attrs_str = line[len('digraph { graph ['):].strip()
    if graph_attrs_str.startswith('['):
        graph_attrs_str = graph_attrs_str[1:]
    if graph_attrs_str.endswith(']'):
        graph_attrs_str = graph_attrs_str[:-1]
    return parse_attributes(graph_attrs_str)

def replace_node_labels(full_label_mapping, node_map, edge_map):
    """ Adjust labels for unambiguous identification """
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

def process_file(xes_file):
    """ Read XES file and prepare for further handling """
    dfg, start_activities, end_activities = pm4py.discover_dfg(xes_file)
    start_activities = pm4py.get_start_activities(xes_file)
    end_activities = pm4py.get_end_activities(xes_file)

    gviz = dfg_visualization.apply(
        dfg,
        parameters={
            "start_activities": start_activities,
            "end_activities": end_activities
        }
    )
    gviz.attr(rankdir='TB')
    return gviz