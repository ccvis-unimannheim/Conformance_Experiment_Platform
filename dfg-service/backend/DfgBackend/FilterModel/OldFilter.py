import os.path
import json
import pm4py
from pm4py.objects.log.importer.xes import importer as xes_importer
from collections import Counter
import os
from DfgBackend.FilterModel import helper


# ToDo: Make the code more readable and put them more concise together. its hard to read so far
# Todo: mapping table and created svgs/xes are not aligned
# Todo: There are missing svgs/xes files that are not generated due to the loop logic
# Todo: The core trace needs to be created separately

# Todo: There is a Problem with the logic. Since the most common trace is not create fine, payment but the longer one,
#  the logic is off. Therefore need to look into how to change the problems at hand in order to make them function


class FilterableTrace:
    core_traces: list
    edge_traces: list

    def __init__(self, core_traces, edge_traces):
        self.core_traces = core_traces
        self.edge_traces = edge_traces

    def filter_trace_on_edges_by_percentage(self, percentage):
        filtered_traces = []
        filtered_traces.extend(self.core_traces)
        for index in range(0, round(len(self.edge_traces) * percentage)):
            filtered_traces.append(self.edge_traces[index])
        print(filtered_traces)
        return filtered_traces

    def filter_trace_by_edge_level(self, edge_level):
        filtered_traces = []
        filtered_traces.extend(self.core_traces)
        filtered_traces.extend(self.edge_traces[:edge_level])
        # for index in range(0, edge_level):
        #     filtered_traces.append(self.edge_traces[index])
        return filtered_traces

    def get_core_trace(self):
        return self.core_traces

    # def count_distinct_activities_in_trace(self):
    #     """Returns the number of distinct activities in the log"""
    #     activities = set()
    #     for trace in self.core_traces:
    #         for event in trace:
    #             activities.add(event['concept:name'])
    #     return len(activities)


def get_all_traces_and_occurrences(log):
    """
    Returns a list with tuples that contains end-2-end traces and their occurrences in the log
    """
    traces = [tuple(event['concept:name'] for event in trace) for trace in log]
    trace_counts = Counter(traces)
    return trace_counts.most_common()

def get_all_edges_and_occurrences(log):
    """
    Returns a Counter Object that contains all edges from the dfg and their occurrence

    Return: {(A, B): number_of_occurrence,...}
    """
    return pm4py.algo.discovery.dfg.algorithm.apply(log)

def find_additional_entries(tuple1, tuple2):
    """Finds the entries that are in tuple1 but not in tuple2.

    Args:
        tuple1: The first tuple.
        tuple2: The second tuple.

    Returns:
        A list of entries that are in tuple1 but not in tuple2.
    """
    additional_entries = []
    for item in tuple1:
        if item not in tuple2:
            additional_entries.append(item)
    return additional_entries


def find_shortest_common_trace_with_start_and_end(log):
    most_common_start_activity = Counter([trace[0]['concept:name'] for trace in log]).most_common(1)[0][0]
    most_common_end_activity = Counter([trace[-1]['concept:name'] for trace in log]).most_common(1)[0][0]

    shortest_trace = None
    for trace in log:
        if trace[0]['concept:name'] == most_common_start_activity and trace[-1]['concept:name'] == most_common_end_activity:
            if shortest_trace is None or len(trace) < len(shortest_trace):
                shortest_trace = trace
    return shortest_trace


def translate_indices_to_trace(log, trace:FilterableTrace, edge_level , all_traces):
    indexes_for_trace = trace.filter_trace_by_edge_level(edge_level)
    all_variants = []
    for index in indexes_for_trace:
        all_variants.append(all_traces[index][0])
    # translate trace indices into a real event-log based trace
    trace = pm4py.filtering.filter_variants(log, all_variants)
    return trace


def find_all_edge_variants(index_list: list) -> list[FilterableTrace]:
    all_edge = []
    for index in range(0, len(index_list)):

        # select first and last element of index_list[:index+1] as borders for the iterator
        indexes_for_activity_traces = index_list[:index + 2]
        # print(f"for node {index_list[index]} there are the following {indexes_for_activity_traces}")

        first = indexes_for_activity_traces[0]
        last = indexes_for_activity_traces[-1]
        # print(first, last)

        # construct full list based on these borders
        full_list = []
        for i in range(first, last + 1):
            full_list.append(i)
        # print(full_list)

        # subtract index_list[:index+1] from full list to just have the rest of the edge traces
        for i in indexes_for_activity_traces:
            if i in full_list:
                full_list.remove(i)
        # print(f"core traces {[trace for trace in indexes_for_activity_traces if indexes_for_activity_traces[index] >= trace]}")
        # print(f"edge traces {full_list}")

        trace = FilterableTrace(
            core_traces=[trace for trace in indexes_for_activity_traces if indexes_for_activity_traces[index] >= trace],
            edge_traces=full_list)

        all_edge.append(trace)

    return all_edge

def create_mapping_table(all_filterable_traces, file_path) -> None:
    mapping = {}
    for filterable_trace in all_filterable_traces:
        full_identifier = []
        activity_identifier = str(all_filterable_traces.index(filterable_trace))
        for edge_trace in filterable_trace.edge_traces:
            edge_identifier = str(filterable_trace.edge_traces.index(edge_trace))
            full_identifier.append(activity_identifier+"_"+edge_identifier)
        mapping[activity_identifier] = full_identifier
    with open(file_path + "mapping.json", "w") as file:
        json.dump(mapping, file)



def create_all_subplots(base_xes, target_directory):
    log = xes_importer.apply(base_xes)
    if not os.path.isdir(target_directory):
        os.mkdir(target_directory)
    # find core trace
    all_traces = get_all_traces_and_occurrences(log)
    core_trace = all_traces[0]
    # current_trace = core_trace
    # current_trace = list(current_trace[0])
    print(f"core trace {core_trace}")
    print(f"all traces {all_traces}")

    # determine number of total activities to not search through all traces

    index = 0
    additional_activities_index_list = {}

    current_trace = []

    for trace in all_traces:
        additional_activities = find_additional_entries(trace[0], current_trace)
        if additional_activities:
            # print(f"trace with new activity: {trace}")
            # print(f"current activity: {current_trace}")
            # print(f"additional activity {additional_activities}")
            additional_activities_index_list[tuple(additional_activities)] = index

            # append activity to current_trace
            current_trace.extend(additional_activities)
            # print(current_trace)
        index += 1
    print(f"additional activities_index_list: {additional_activities_index_list}")

    list_index_new_activity_added = list(additional_activities_index_list.values())

    all_filterable_traces = find_all_edge_variants(list_index_new_activity_added)
    print(f"all_filterable_traces: {[filterable_trace.core_traces for filterable_trace in all_filterable_traces]}")

    create_mapping_table(all_filterable_traces, target_directory)

    # plot all edge traces
    for filterable_trace in all_filterable_traces:
        list_index = all_filterable_traces.index(filterable_trace)
        for edge_level in range(0, len(filterable_trace.edge_traces)):
            trace = translate_indices_to_trace(log, filterable_trace, edge_level, all_traces=all_traces)
            dfg, start, end = pm4py.discover_dfg(trace)

            # pm4py.save_vis_dfg(dfg, start, end,
            #                    target_directory + "/" + str(list_index) + "_" + str(
            #     edge_level) + ".svg")
            # pm4py.objects.log.exporter.xes.exporter.apply(trace, target_directory + "/" + str(
            #     list_index) + "_" + str(edge_level) + ".xes")
            helper.save_xes_log_as_pickle(trace, target_directory + "/" + str(list_index) + "_" + str(edge_level) + ".pickle")
            # pm4py.objects.log.exporter.xes.exporter.apply(trace, target_directory + "/" + str(
            #     list_index) + "_" + str(edge_level) + ".xes")



    print("Filtering done")

if __name__ == "__main__":
    create_all_subplots(base_xes=r'../../tests/testdata/Road_Traffic_Fine_Management_Process.xes',
                        target_directory=r"../../tests/testdata/RoadTraffic/")
