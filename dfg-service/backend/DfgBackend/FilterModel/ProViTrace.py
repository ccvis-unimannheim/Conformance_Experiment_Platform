import pm4py

from DfgBackend.FilterModel import helper


class ProViTrace:
    core_trace_activities: list[tuple[str]]
    edge_trace_activities: list[tuple[str]]
    edge_trace_activities_split_on_new_edges: dict[int, list[tuple[str]]]
    event_log_traces: dict[str, pm4py.objects.log.obj.EventLog]

    def __init__(self, core_trace_activities: list[tuple[str]]):
        self.core_trace_activities = core_trace_activities
        self.edge_trace_activities = []
        self.edge_trace_activities_split_on_new_edges = {}
        self.event_log_traces = {}

    def get_number_of_core_trace_activities(self):
        return len(helper.get_unique_elements_of_a_list_with_tuples(self.core_trace_activities))
