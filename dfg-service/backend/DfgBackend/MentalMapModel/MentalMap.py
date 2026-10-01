import os.path
import re
import subprocess
import DfgBackend.MentalMapModel.FixGraphvizIds as FixGraphvizIds
from DfgBackend.FilterModel import helper

def set_anchors(node_map, edge_map):
    """ Calculates and adds anchor points to ensure consistent image sizing """
    # Extract x- and y-coordinates from pos attributes of the filtered nodes
    x_values = []
    y_values = []
    # Iterate over nodes to get positions
    for attrs in node_map.values():
        pos = attrs.get('pos')
        if pos:
            # Ensure pos is a string and clean it 
            pos_cleaned = str(pos).strip('"')
            pos_cleaned = re.sub(r'\\+', '', pos_cleaned)  
            pos_cleaned = re.sub(r',\s+', ',', pos_cleaned)
            pos_cleaned = pos_cleaned.split(',')
            try:
                    x_coord, y_coord = map(float, pos_cleaned)
                    x_values.append(x_coord)
                    y_values.append(y_coord)
            except ValueError as e:
                print(f"Skipping invalid node position: {pos_cleaned}. Error: {e}")
    # Iterate over edges to get positions
    for edge_attrs in edge_map.values():  
        pos = edge_attrs.get('pos')
        if pos:
            # Ensure pos is a string and clean it
            pos_cleaned = str(pos).strip('"')
            pos_cleaned = re.sub(r'\\+', '', pos_cleaned)  # Remove all instances of '\\' or single '\'
            pos_cleaned = re.sub(r',\s+', ',', pos_cleaned) # Remove all instances where a blank follows a comma
            pos_cleaned = re.sub(r'e,', '', pos_cleaned) # Remove all 'e,'
            # Split the string and ignore the first 'e,' part if present
            edge_coords = pos_cleaned.split()[1:] if pos_cleaned.startswith('e,') else pos_cleaned.split()
            for coord in edge_coords:
                try:
                    x_coord, y_coord = map(float, coord.split(','))
                    x_values.append(x_coord)
                    y_values.append(y_coord)
                except ValueError as e:
                    print(f"Skipping invalid edge position: {coord}. Error: {e}") # Needs to be adjusted if not needed
    # Calculate x_min, x_max, y_min, and y_max if coordinates are available
    if x_values and y_values:
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        # Add invisible anchor nodes for consistent x and y alignment
        node_map['left_bottom_anchor'] = {'pos': f'"{x_min},{y_min}"', 'style': 'invis'}
        node_map['right_top_anchor'] = {'pos': f'"{x_max},{y_max}"', 'style': 'invis'}
    else:
        raise ValueError("No position data found for the anchors") # Needs to be adjusted if not needed
    return node_map, edge_map

def identify_node_labels(line, node_labels):
    """ Extract a list of node labels from a dictionary of nodes and their attributes """
    node_id, attrs_str = line.split('[')
    node_id = node_id.strip()
    attrs_str = attrs_str.strip()
    if attrs_str.endswith(']'):
        attrs_str = attrs_str[:-1].strip()
    attrs = dot_to_dictionary(attrs_str)
    # Only store the 'label' attribute
    if 'label' in attrs:
        node_labels.append(attrs['label'])
    return node_labels

def identify_edge_labels(line, edge_labels):
    """ Extract a dictionary of edge labels using the head and tail id from a dictionary of edges and their attributes """
    edge_definition = line.split('->')
    tail_id = edge_definition[0].strip()
    head_and_attrs = edge_definition[1].strip()
    head_id, _ = head_and_attrs.split('[', 1)
    head_id = head_id.strip()
    # Store the edge label as a tuple of (tail_id, head_id)
    edge_labels[(tail_id, head_id)] = re.findall("label=?(\d*)", head_and_attrs)[0]
    return edge_labels

def parse_dot_file(dot_file_path):
    """ 
    Extract graph information, nodes and edges from FullDot file.
    Args:
        dot_file_path: path of DOT file to analyze
    Returns:
        Dictionaries of graph information, nodes and edges with their respective attributes
    """
    # Open file
    with open(dot_file_path, 'r') as dot_file:
        content = dot_file.read()
    statements = content.split('];')
    # Initialize dictionaries to store components in
    graph_attrs = {}
    node_map = {}
    edge_map = {}
    # Iterate over file to identify components
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
    # Add anchors
    node_map, edge_map = set_anchors(node_map, edge_map)
    return graph_attrs, node_map, edge_map

def filter_nodes_by_fixed_id(node_map, ids_to_include):
    """ 
    Filter node dictionary based on the provided list of nodes from filter. 
    Args:
        node_map: dictionary of nodes and their respective attributes
        ids_to_include: list of node labels 
    Returns: 
        Dictionary of filtered nodes and their attributes.
    """
    filtered_node_map = {node_id: attrs for node_id, attrs in node_map.items() if any(ids in node_id for ids in ids_to_include)}
    # Include place holders for right frame
    for node_id, attrs in node_map.items():
        # Ensure the 'style' attribute is set to 'filled' and 'shape' to 'box'
        if node_id not in ['"@@startnode"', '"@@endnode"', 'left_bottom_anchor', 'right_top_anchor']:
            attrs['style'] = 'filled'
            attrs['shape'] = 'box'
        if node_id in ['right_top_anchor', 'left_bottom_anchor']:
            filtered_node_map[node_id] = attrs
    return filtered_node_map

def filter_edges(edge_map, edges_to_filter):
    """
    Filters the edge dictionary based on the provided list of edges from filter.
    Args:
        edge_map: dictionary of edges and their respective attributes
        edges_to_filter: dictionary of edge labels 
    Returns: 
        Dictionary of filtered edges and their attributes.
    """
    filtered_edges = {}
    for tail_id, head_id in edges_to_filter:
        if (tail_id, head_id) in edge_map:
            filtered_edges[(tail_id, head_id)] = edge_map[(tail_id, head_id)]
    return filtered_edges

def calculate_node_label_sums(filtered_node_map, filtered_edge_map):
    """ 
    - Currently not needed - 
    Calculate the new label sums with regard to the filtered map. 
    """    
    incoming_label_sums = {node_id: 0 for node_id in filtered_node_map}
    for (tail_id, head_id), attrs in filtered_edge_map.items():
        label = attrs.get('label', 0)
        incoming_label_sums[head_id] += int(label)
    return incoming_label_sums

def update_node_labels(node_map, incoming_label_sums):
    """
    - Currently not needed - 
    Update the label sums with regard to the filtered map.
    """
    updated_node_map = {}
    for node_id, attrs in node_map.items():
        # Get the current label and strip surrounding quotes
        label = attrs.get('label', '').strip('"')
        # Check if the label initially contains a frequency pattern (e.g., "(1234)")
        if re.search(r'\(\d+\)', label):
            # If a frequency count is found, strip it and update with the new sum
            base_label = re.sub(r'\(\d+\)', '', label).strip()
            new_label = f'{base_label} ({incoming_label_sums.get(node_id, 0)})'
            attrs['label'] = f'"{new_label}"'  # Add quotation marks back for DOT format
        else:
            # If no frequency count, keep the label unchanged
            attrs['label'] = f'{label}'
        updated_node_map[node_id] = attrs
    return updated_node_map

def get_filtered_maps(file_path, target_directory):
    """ 
    Extracts a list of node labels and a dictionary of edge labels included in the file.
    Args:
        file_path: path of file to use
        target_directory: path of directory to store output in
    Returns:
        Dictionaries of graph information, nodes and edges with their respective attributes
    """
    # Read file and prepare for handling as DOT file
    xes_file = helper.load_event_log_as_pickle_or_xes(file_path)
    middle = helper.process_file(xes_file)
    middle_file_path = target_directory + '/' + 'MiddleDot'
    middle.render(middle_file_path, format='dot', view=False)
    sub_label_mapping = FixGraphvizIds.node_id_label_mapping(middle_file_path + '.dot')
    with open(middle_file_path + '.dot', 'r') as dot_file2:
        content = dot_file2.read()
    statements = content.split('];')
    # Initialize list & dictionary to store components in
    node_labels = []
    edge_labels = {}
    # Iterate over file to identify components
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
        # Identify node labels
        if '[' in line and '->' not in line:  # It's a node if there's no '->'
            node_labels = identify_node_labels(line, node_labels)
            continue
        # Identify edge labels
        if '->' in line:
            edge_labels = identify_edge_labels(line, edge_labels)
    edges_updated = {}
    for k, v in edge_labels.items():
        edges_updated[(sub_label_mapping.get(k[0], k[0]), sub_label_mapping.get(k[1],k[1]))] = v
    # Replace node_labels and edges with fixed labels
    node_labels = list(sub_label_mapping.values())
    node_labels.extend(["@@startnode", "@@endnode"])
    edges = edges_updated
    return graph_attrs, node_labels, edges

def dot_to_dictionary(attrs_str):
    """ 
    Parse attributes from DOT format into a dictionary. 
    Args: 
        attrs_str: attributes as present in DOT file
    Returns:
        attrs: dictionary of attributes
    """
    attrs = {}
    for attr in attrs_str.split(','):
        if '=' in attr:
            key, value = attr.split('=')
            attrs[key.strip()] = value.strip('"')
    return attrs

def full_graph(file_path, target_directory):
    """ 
    Transforms the full xes-file into an SVG as well as dictionaries of nodes, edges and attributes 
    Args:
        file_path: path of file to use
        target_directory: path of directory to store output in
    Returns:
        Dictionaries of the graph attributes, nodes, edges and an SVG    
    """
    # Read file and prepare for further handling as DOT file
    log = helper.load_event_log_as_pickle_or_xes(file_path)
    gviz = helper.process_file(log)
    gviz.render( target_directory + '/' + 'FullDot', format='dot', view=False)
    dot_file_path = target_directory + '/' + 'FullDot.dot'
    # Extract components from DOT file
    graph_attrs, node_map, edge_map = parse_dot_file(dot_file_path)
    # Store components in DOT file
    helper.write_dot_file(dot_file_path, graph_attrs, node_map, edge_map)
    # Fix labels for unambiguous identification
    full_label_mapping = FixGraphvizIds.node_id_label_mapping(dot_file_path)
    node_map, edge_map = helper.replace_node_labels(full_label_mapping, node_map, edge_map)
    # Generate images
    svg_output_path = target_directory + '/' + "FullGraph.svg"
    # Generate SVG images from DOT file
    full_svg = subprocess.run(['neato', '-Tsvg', '-n2', dot_file_path, '-o', svg_output_path], check=True)
    return graph_attrs, node_map, edge_map, full_svg

def get_graphs(graph_attrs, node_map, edge_map, full_svg, xes_filtered, file_name, target_directory):
    """ 
    Transform filtered xes-files into SVGs 
    Args:
        Dictionaries of the graph attributes, nodes, edges
        xes_filtered: file to visualize as SVG
        file_name: name of the SVG created
        target_directory: path of directory to store SVG in
    Returns:
        SVGs of the files
    """
    # Get filtered xes-file
    graph_info, labels_to_include, edges_to_include = get_filtered_maps(xes_filtered, target_directory)
    # Create new dot-file
    filtered_node_map = filter_nodes_by_fixed_id(node_map, labels_to_include)
    filtered_edge_map = filter_edges(edge_map, edges_to_include)
    # Activate the Following Two Lines plus the input to write_dot_file to Adjust Node Labels According to Actual Frequency: 
    # incoming_label_sums = calculate_node_label_sums(filtered_node_map, filtered_edge_map)
    # updated_node_map = update_node_labels(filtered_node_map, incoming_label_sums)
    # Generate DOT-file
    output_dot_path = target_directory + '/' + 'HalfDot.dot'
    helper.write_dot_file(output_dot_path, graph_attrs, filtered_node_map, filtered_edge_map)
    # Generate SVGs
    svg_output_path = f"{file_name}.svg"
    svg_output_path = target_directory + "/" + svg_output_path
    # Generate SVG images from DOT file
    filtered_svg = subprocess.run(['neato', '-Tsvg', '-n2', output_dot_path, '-o', svg_output_path], check=True)
    return full_svg, filtered_svg

def mental_map(base_xes_file, filtered_xes_files, target_directory):
    """ Transform the full + filtered xes-files into SVGs """
    # Transform the full xes-file into an SVG as well as extracting the individual components
    graph_attrs, node_map, edge_map, full_svg = full_graph(base_xes_file, target_directory)
    # Transform all filtered xes-files into SVGs
    base_filenames = {os.path.splitext(file_name)[0] for file_name in os.listdir(filtered_xes_files) if
                      file_name.endswith('.pickle')}
    for file_name in base_filenames:
        file = helper.create_path(file_name, filtered_xes_files)
        get_graphs(graph_attrs, node_map, edge_map, full_svg, file, file_name, target_directory)

#------------------------------------------------

if __name__ == "__main__":
    xes_test_file = r"..\..\tests\testdata\NoNoise.xes"
    new_test_xes = [r"..\..\tests\testdata\NoNoise"]
    mental_map(xes_test_file, new_test_xes, os.getcwd())
