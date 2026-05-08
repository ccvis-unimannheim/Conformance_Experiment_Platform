"""
Canonical Task and Idiom catalogs.

Inserted into MongoDB on application startup if the corresponding
collections are empty (see main.py lifespan).
"""

CANONICAL_TASKS = [
    {
        "task_key": "task1",
        "label": "What is the overall degree of conformance between an event log and a set of guidelines?",
        "description": "Assess the overall conformance rate of the entire event log against the process model.",
        "answer_type": "numeric",
    },
    {
        "task_key": "task2",
        "label": "Where exactly does the process execution differ from the guideline? What does the violating behavior look like?",
        "description": "Pinpoint specific violations in traces against the expected model.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task3",
        "label": "What type of guideline violations happen in different traces? How often do they happen?",
        "description": "Classify violation types and quantify their occurrences across traces.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task4",
        "label": "What control-flow, data, resource, or time attributes of events, traces, or event logs lead to guideline violations?",
        "description": "Identify potential root causes of non-conformance.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task5",
        "label": "Which percentage of traces in the event log fall into which conformance category?",
        "description": "Group traces by conformance ranges and determine their distribution.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task6",
        "label": "Do cases with a higher degree of conformance lead to a higher probability of a positive process outcome?",
        "description": "Explore the relationship between conformance and process outcomes.",
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
]
