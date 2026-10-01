START_EDGE_ACTIVITY_NOTATION = "START"
END_EDGE_ACTIVITY_NOTATION = "END"

def are_new_edges_present(already_known_edges: list[tuple], new_edges: list[tuple]):
    """Detects new edges that are not in the already known edges."""
    new_edges_list = []
    for edge in new_edges:
        if edge not in already_known_edges:
            return True
    return False


def find_start_edges(activity_list: tuple[str]) -> list[tuple]:
    return [(START_EDGE_ACTIVITY_NOTATION, activity_list[0])]


def find_end_edges(activity_list: tuple[str]) ->list[tuple]:
    return [(activity_list[-1], END_EDGE_ACTIVITY_NOTATION)]


def find_edges_between_activities(activity_list: tuple[str]) -> list[tuple]:
    edges = []
    for i in range(len(activity_list) - 1):
        edges.append((activity_list[i], activity_list[i+1]))
    return edges

def find_all_edges_in_traces(traces: list[tuple[str]]) -> list[tuple]:
    all_edges = []
    for trace in traces:
        all_edges.extend(find_start_edges(trace))
        all_edges.extend(find_edges_between_activities(trace))
        all_edges.extend(find_end_edges(trace))
    # remove duplicates
    all_edges = list(set(all_edges))
    return all_edges


def add_new_edges_to_list(edge_list: list[tuple], new_edges: list[tuple]) -> list[tuple]:
    for edge in new_edges:
        if edge not in edge_list:
            edge_list.append(edge)
    return edge_list