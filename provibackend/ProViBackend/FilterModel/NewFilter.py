import json
import os.path
import pathlib as pl
import pm4py
from collections import Counter
import copy
import os
import time
from ProViBackend.FilterModel import helper
from ProViBackend.FilterModel.ProViTrace import ProViTrace
from ProViBackend.FilterModel import edges


# Todo: Find additional activity level as in Celonis: Celonis looks always to increase the activity level by one. So if
#  there is a less common trace with one more activity than the core trace, it will be added to the core trace, instead of a more
#  frequent trace that has two new activities compared to the core trace.

# Todo: Find missing edges as in Celonis see issue Seems that Celonis creates them in an arbitrary order when the timestamp is identical
#  thereby creating new edges where actually there is none. So not really an issue in the code here.

def create_event_log_from_activity_tuples(activity_name_traces: list[tuple[str]], event_log: pm4py.objects.log.obj.EventLog) -> pm4py.objects.log.obj.EventLog:
    return pm4py.filtering.filter_variants(event_log, activity_name_traces)


def create_svg_from_event_traces(event_log: pm4py.objects.log.obj.EventLog, target_directory_path: str):
    dfg, start, end = pm4py.discover_dfg(event_log)
    pm4py.save_vis_dfg(dfg, start, end, target_directory_path)


def find_shortest_most_common_trace_with_start_and_end(log: pm4py.objects.log.obj.EventLog):
    """Celonis style core trace"""
    most_common_start_activity = Counter([trace[0]['concept:name'] for trace in log]).most_common(1)[0][0]
    most_common_end_activity = Counter([trace[-1]['concept:name'] for trace in log]).most_common(1)[0][0]

    shortest_trace = None
    for trace in log:
        if trace[0]['concept:name'] == most_common_start_activity and trace[-1]['concept:name'] == most_common_end_activity:
            if shortest_trace is None or len(trace) < len(shortest_trace):
                shortest_trace = trace
    return shortest_trace


def find_most_common_trace(log: pm4py.objects.log.obj.EventLog):
    """Disco style core trace"""
    most_common_trace = Counter([tuple([event['concept:name'] for event in trace]) for trace in log]).most_common(1)[0][0]
    for trace in log:
        if tuple([event['concept:name'] for event in trace]) == most_common_trace:
            return trace


def init_variables(base_xes_file_path: str):
    start_time = time.time()
    # event_log = xes_importer.apply(base_xes_file_path)
    event_log = helper.load_event_log_as_pickle_or_xes(base_xes_file_path)
    all_trace_occurrences = helper.get_all_traces_and_occurrences(event_log)
    # core_trace = find_shortest_most_common_trace_with_start_and_end(event_log)
    core_trace = find_most_common_trace(event_log)
    end_time = time.time()
    print(f"Initialization finished in: {round(end_time - start_time)} seconds")
    return event_log, core_trace, all_trace_occurrences


def find_core_traces_in_activity_name_form(core_trace, all_trace_occurrences) -> list[ProViTrace]:
    pro_vi_traces: list[ProViTrace] = []
    start_time = time.time()
    core_trace_activities = [helper.extract_activities_from_single_trace(core_trace)]
    pro_vi_traces.append(ProViTrace(copy.deepcopy(core_trace_activities)))

    previous_core_trace_activities = core_trace_activities
    finished = False
    while not finished:
        for trace in all_trace_occurrences:
            trace_activity_names = trace[0]
            if helper.are_additional_entries(previous_core_trace_activities, trace_activity_names):
                # trace with new activity found and add to previous_core_trace_activities
                previous_core_trace_activities.append(trace[0])
                pro_vi_traces.append(ProViTrace(copy.deepcopy(previous_core_trace_activities)))
                break
        else:
            finished = True
    end_time = time.time()
    print(f"Calculation of core traces finished in: {round(end_time - start_time)} seconds")
    return pro_vi_traces


def find_edge_traces_in_activity_name_form(pro_vi_traces: list[ProViTrace], all_traces_occurrences: list[tuple[tuple[str], int]]) -> list[ProViTrace]:
    start_time = time.time()
    for pro_vi_trace in pro_vi_traces:
        # deep copy of all_traces_occurrences to not change the original list
        all_traces_occurrences_current_run = copy.deepcopy(all_traces_occurrences)
        # Remove core traces from all traces to only get real edge traces
        print(f"len of core traces: {len(pro_vi_trace.core_trace_activities)}")
        print(f"len of all traces: {len(all_traces_occurrences_current_run)}")
        for core_trace_activity in pro_vi_trace.core_trace_activities:
            index_of_core_trace_activity = helper.get_index_of_trace_occurrence_combination_from_total_list(core_trace_activity, all_traces_occurrences_current_run)
            all_traces_occurrences_current_run.pop(index_of_core_trace_activity)
        print(f"len of all traces after removing core traces: {len(all_traces_occurrences_current_run)}")

        edge_traces = []
        for trace in all_traces_occurrences_current_run:
            if not helper.are_additional_entries(pro_vi_trace.core_trace_activities, trace[0]):
                edge_traces.append(trace[0])
        pro_vi_trace.edge_trace_activities = edge_traces
    print(f"finished finding edge_traces after {round(time.time() - start_time)} seconds")
    return pro_vi_traces


def group_edge_traces_on_new_edges(pro_vi_traces: list[ProViTrace]) -> list[ProViTrace]:
    """Split the edge traces list into sub lists where a new edge is introduced"""
    start_time = time.time()
    for pro_vi_trace in pro_vi_traces:
        # find all edges in core traces
        core_trace_edges = edges.find_all_edges_in_traces(pro_vi_trace.core_trace_activities)
        already_known_edges = copy.deepcopy(core_trace_edges)
        # iterate over all edge traces and make a split when a new edge is introduced
        current_edge_traces = []
        for edge_trace in pro_vi_trace.edge_trace_activities:
            edge_trace_edges = edges.find_all_edges_in_traces([edge_trace])
            if  not edges.are_new_edges_present(already_known_edges, edge_trace_edges):
                # no new edge is introduced therefore add  this trace to the current edge traces list
                current_edge_traces.extend([edge_trace])
            else:
                # trace with new edge is introduced: store current edge traces as a new collection
                all_edges_in_current_trace = list(set(core_trace_edges + edges.find_all_edges_in_traces(current_edge_traces)))
                pro_vi_trace.edge_trace_activities_split_on_new_edges[len(all_edges_in_current_trace)] = copy.deepcopy(current_edge_traces)
                # update already known edges with the new detected edges
                already_known_edges = edges.add_new_edges_to_list(already_known_edges, edge_trace_edges)
                # add trace with new edge to the current edge traces list
                current_edge_traces.extend([edge_trace])
        # add the last edge trace to the list
        all_edges_in_current_trace = list(set(core_trace_edges + edges.find_all_edges_in_traces(current_edge_traces)))
        pro_vi_trace.edge_trace_activities_split_on_new_edges[len(all_edges_in_current_trace)] = copy.deepcopy(current_edge_traces)

    print(f"finished finding new edges after {round(time.time() - start_time)} seconds")
    return pro_vi_traces


def compute_all_traces_from_activity_name_form_to_event_log(pro_vi_traces: list[ProViTrace], total_event_log: pm4py.objects.log.obj.EventLog) -> list[ProViTrace]:
    start_time = time.time()
    index = 0
    for pro_vi_trace in pro_vi_traces:
        for amount_edges, edge_trace in pro_vi_trace.edge_trace_activities_split_on_new_edges.items():
            # combine always the core trace with the edge trace
            trace = pro_vi_trace.core_trace_activities + edge_trace
            event_log = create_event_log_from_activity_tuples(trace, total_event_log)
            event_log_name = f"{pro_vi_trace.get_number_of_core_trace_activities()}_{amount_edges}"
            pro_vi_trace.event_log_traces[event_log_name] = event_log
        index += 1
        print(f"finished computing {index} of {len(pro_vi_traces)} traces")
    print(f"finished computing all event log based traces in {round(time.time() - start_time)} seconds")
    return pro_vi_traces


def save_all_event_logs_as_pickle(pro_vi_traces: list[ProViTrace], target_directory_path: str):
    start_time = time.time()
    index = 0
    print("Start exporting event logs as pickle files")
    for pro_vi_trace in pro_vi_traces:
        for event_log_name, event_log in pro_vi_trace.event_log_traces.items():
            helper.save_xes_log_as_pickle(event_log, target_directory_path + f"/{event_log_name}.pickle")
        index += 1
        print(f"finished exporting {index} of {len(pro_vi_traces)} traces")
    print(f"Finished exporting event logs as pickle files in {round(time.time() - start_time)} seconds")


def create_mapping(pro_vi_traces: list[ProViTrace], target_directory_path: str):
    mapping = {}
    for pro_vi_trace in pro_vi_traces:
        activity_number = pro_vi_trace.get_number_of_core_trace_activities()
        sub_traces = []
        for event_log_name, event_log in pro_vi_trace.event_log_traces.items():
            sub_traces.append(event_log_name)
        mapping[activity_number] = sub_traces
    with open(target_directory_path + "/normalmapping.json", "w") as file:
        json.dump(mapping, file)


def export_all_event_logs_as_svg(pro_vi_traces: list[ProViTrace], target_directory_path: str):
    for pro_vi_trace in pro_vi_traces:
        for event_log_name, event_log in pro_vi_trace.event_log_traces.items():
            create_svg_from_event_traces(event_log, target_directory_path + f"/{event_log_name}.svg")



def create_all_subplots(base_xes_file_path: pl.Path, target_directory_path: pl.Path):
    start_time = time.time()
    if not os.path.isdir(str(target_directory_path.absolute())):
        os.mkdir(str(target_directory_path.absolute()))
    event_log, core_trace, all_trace_occurrences = init_variables(str(base_xes_file_path.absolute()))

    # find core traces in activity name form
    pro_vi_traces: list[ProViTrace] = find_core_traces_in_activity_name_form(core_trace, all_trace_occurrences)

    # find edge traces in activity name form
    pro_vi_traces: list[ProViTrace] = find_edge_traces_in_activity_name_form(pro_vi_traces, all_trace_occurrences)

    # group edge traces till new edge is introduced
    pro_vi_traces: list[ProViTrace] = group_edge_traces_on_new_edges(pro_vi_traces)

    # compute all traces from activity name form to eventlog
    pro_vi_traces: list[ProViTrace] = compute_all_traces_from_activity_name_form_to_event_log(pro_vi_traces, event_log)

    # save all event logs as pickle files for further processing
    save_all_event_logs_as_pickle(pro_vi_traces, str(target_directory_path.absolute()))

    # create mapping table
    create_mapping(pro_vi_traces, str(target_directory_path.parent.absolute()))

    # for testing - test save all traces as svg
    # export_all_event_logs_as_svg(pro_vi_traces, target_directory_path)
    print(f"Finished filtering process in {round(time.time() - start_time)} seconds")


if __name__ == "__main__":
    cwd = pl.Path.cwd().parent.parent
    create_all_subplots(base_xes_file_path=cwd / "tests/testdata/NoNoise.xes",
                        target_directory_path=cwd / "tests/testdata/NoNoise/")