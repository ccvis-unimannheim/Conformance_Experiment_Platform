"""
Canonical Task and Idiom catalogs.

Inserted into MongoDB on application startup if the corresponding
collections are empty (see main.py lifespan).
"""

CANONICAL_TASKS = [
    {
        "task_key": "task06",
        "label": "What is the overall degree of conformance between an event log and a set of guidelines?",
        "description": "Assess the overall conformance rate of the entire event log against the process model.",
        "answer_type": "numeric",
    },
    {
        "task_key": "task28",
        "label": "Where exactly does the process execution differ from the guideline? What does the violating behavior look like?",
        "description": "Pinpoint specific violations in traces against the expected model.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task29",
        "label": "What type of guideline violations happen in different traces? How often do they happen?",
        "description": "Classify violation types and quantify their occurrences across traces.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task20",
        "label": "What control-flow, data, resource, or time attributes of events, traces, or event logs lead to guideline violations?",
        "description": "Identify potential root causes of non-conformance.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task10",
        "label": "Which percentage of traces in the event log fall into which conformance category?",
        "description": "Group traces by conformance ranges and determine their distribution.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task31",
        "label": "Do cases with a higher degree of conformance lead to a higher probability of a positive process outcome?",
        "description": "Explore the relationship between conformance and process outcomes.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task07",
        "label": "How does the degree of process conformance change over time?",
        "description": "Derive and visualize conformance trends over time using trace timestamps.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task08",
        "label": "What violation co-occurrence patterns exist in the event log? Which violations tend to happen together?",
        "description": "Identify pairs of violations that frequently co-occur across traces and quantify their co-occurrence strength.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task09",
        "label": "How exactly does the process execution differ from the guidelines? Which activities are responsible, and what violation type occurs?",
        "description": "Identify guideline violations per activity and violation type across the entire event log.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task11",
        "label": "How often did a specific guideline violation occur?",
        "description": "Summarize guideline violation frequency per activity and type across the entire event log.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task12",
        "label": "In what percentage of traces do violations occur?",
        "description": "Summarize the proportion of conformant vs deviating traces across the entire event log.",
        "answer_type": "numeric",
    },
    {
        "task_key": "task37",
        "label": "How do fitness values of traces differ when applying two different techniques to compute them? What is the overall trend?",
        "description": "Compare alignment-based and token-based replay fitness per trace; visualize distribution, agreement, and trend.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task36",
        "label": "What is the conformance of each individual guideline rule in a Declare model?",
        "description": "Assess per-rule conformance rates across the event log for a Declare constraint model.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task35",
        "label": "Where does the recorded behavior violate which guidelines, as annotated on the process model?",
        "description": "Present guideline violations (skipped/inserted activities) overlaid on the BPMN process model.",
        "answer_type": "single_choice",
    },
]

CANONICAL_IDIOMS = [
    {"idiom_key": "bar_chart",            "label": "Bar Chart",                            "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "donut_chart",          "label": "Donut Chart",                          "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "tile_metric",          "label": "Tile Metric",                          "granularity": "log",   "renderer_type": "html",    "active": True},
    {"idiom_key": "scatterplot",          "label": "Scatterplot",                          "granularity": "trace", "renderer_type": "echarts", "active": True},
    {"idiom_key": "table",                "label": "Table",                                "granularity": "log",   "renderer_type": "html",    "active": True},
    {"idiom_key": "heatmap",              "label": "Heatmap",                              "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "boxplot",              "label": "Boxplot",                              "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "flow_chart_basic",     "label": "Flow Chart basic (Chevron Diagram)",   "granularity": "trace", "renderer_type": "svg",     "active": True},
    {"idiom_key": "flow_chart_elaborate", "label": "Flow Chart elaborate (BPMN Diagram)",  "granularity": "trace", "renderer_type": "bpmn",    "active": True},
    {"idiom_key": "pie_chart",            "label": "Pie Chart",                            "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "decision_tree",        "label": "Tree (Decision Tree)",                 "granularity": "log",   "renderer_type": "d3",      "active": True},
    {"idiom_key": "flow_chart_table",     "label": "Flow Chart & Table",                   "granularity": "trace", "renderer_type": "html",    "active": True},
    {"idiom_key": "table_bar_chart",      "label": "Table & Bar Chart",                    "granularity": "log",   "renderer_type": "html",    "active": True},
    {"idiom_key": "line_graph",           "label": "Line Graph",                           "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "horizon_chart",        "label": "Horizon Chart",                        "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "gantt_chart",          "label": "Gantt Chart",                          "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "matrix",              "label": "Co-occurrence Matrix",                  "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "network_diagram",     "label": "Network Diagram",                       "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "scatter_plot",        "label": "Scatter Plot",                          "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "tree",                    "label": "Hierarchical Clustering Tree",          "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "stacked_bar",             "label": "Stacked Bar Chart",                     "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "flow_chart_elaborate_table", "label": "Flow Chart+ & Table",                "granularity": "log",   "renderer_type": "svg",     "active": True},
]
