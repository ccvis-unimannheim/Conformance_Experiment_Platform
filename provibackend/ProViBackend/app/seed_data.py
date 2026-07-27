"""
Canonical Task and Idiom catalogs.

Inserted into MongoDB on application startup if the corresponding
collections are empty (see main.py lifespan).
"""

CANONICAL_TASKS = [
    {
        "task_key": "task06",
        "label": "What is the overall degree of conformance between the given event log and the guideline?",
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
        "label": "What attributes of events, traces, or event logs lead to guideline violations?",
        "description": "Identify potential root causes of non-conformance.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task13",
        "label": "What are the underlying reasons for guideline violations, in terms of case and event attributes?",
        "description": "Show which case/event attributes (data, resource, time) are associated with guideline violations, ranked by association strength — the attribute-evidence companion to the root-cause analysis.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task18",
        "label": "Which events are responsible for guideline violations in one or more traces?",
        "description": "Deduce which activities/events are responsible for guideline violations from the alignment data, with each responsible activity's responsibility share and dominant attribute context.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task21",
        "label": "What are the underlying reasons for guideline violations, as identified by the analyst through the visualization?",
        "description": "Surface candidate reasons of both kinds (attributes and responsible events) side by side, neutrally ranked, so the analyst can identify the underlying reasons themselves.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task10",
        "label": "How are the traces distributed across the different conformance categories?",
        "description": "Group traces by conformance ranges and determine their distribution.",
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
        "label": "Which guideline violations frequently co-occur in a trace?",
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
        "label": "How often did predefined guideline violation(s) occur?",
        "description": "Summarize trace-level frequency of predefined guideline violations across the entire event log.",
        "answer_type": "pct-set",
    },
    {
        "task_key": "task12",
        "label": "In what percentage of traces do violations occur?",
        "description": "Summarize the proportion of conformant vs deviating traces across the entire event log.",
        "answer_type": "numeric",
    },
    {
        "task_key": "task14",
        "label": "What kind of violation occurs in a given trace?",
        "description": "Classify the violations present in a representative trace and provide a description of each violation type.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task15",
        "label": "How can the overall process conformance be explained?",
        "description": "Relate per-trace conformance to case-level attribute groups and summarise the conformance distribution across groups.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task16",
        "label": "What is the reason for guideline violations?",
        "description": "Identify and annotate the activities and move types responsible for violations across the event log.",
        "answer_type": "single_choice",
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
    {
        "task_key": "task01",
        "label": "How does the conformance of traces differ between those meeting a condition and those that do not?",
        "description": "Compare conformance of sub-logs split by a process outcome condition; pinpoint violations in each group.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task02",
        "label": "Does the event log predominantly follow the desired executions in the process model?",
        "description": "Compute fitness of a log and determine whether the behavior predominantly conforms to the guidelines.",
        "answer_type": "numeric",
    },
    {
        "task_key": "task03",
        "label": "How does the Throughput-time of conformant traces differ from that of non-conformant traces?",
        "description": "Compare the throughput-time distribution of conforming vs non-conforming traces and determine which group is slower.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task04",
        "label": "How does the degree of conformance differ between the given 2 traces?",
        "description": "Compare the trace-level conformance patterns of two traces — where each conforms to or deviates from the guideline.",
        "answer_type": "free_text",
    },
    {
        "task_key": "task05",
        "label": "How often does a set of violations occur across different logs?",
        "description": "Track the occurrence frequency of predefined violation patterns across multiple process executions.",
        "answer_type": "multiple_choice",
    },
    {
        "task_key": "task23",
        "label": "How do guideline violations differ from each other?",
        "description": "Summarize and compare violations to understand their variety and relative prevalence.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task24",
        "label": "Where does the discovered process model differ from the prescribed guidelines?",
        "description": "Discover a process model from the log and compare it against the normative BPMN model to locate deviations.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task25",
        "label": "What is the overall degree of conformance between a log and guidelines, as discovered through visualization?",
        "description": "Allow the analyst to discover the conformance degree by exploring visualized conformance checking results.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task26",
        "label": "How impactful or serious is each guideline violation in the process execution?",
        "description": "Present predefined violation types and their severity so analysts can assess the impact of non-conformance.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task27",
        "label": "Which traces are conformant and which are non-conformant, and how do they differ?",
        "description": "Identify and explore conformant versus non-conformant trace variants to understand their behavioral differences.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task30",
        "label": "How do different sub-logs with certain data attribute values deviate from the prescribed process model?",
        "description": "Compare guideline violations across sub-logs split by a data attribute to uncover conformance differences between groups.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task17",
        "label": "How often is a guideline violated, and how severe or problematic is a frequent violation?",
        "description": "Present the frequency of each guideline violation and where it occurs on the model (by deviation type), so the analyst can judge severity and whether a rule is too strict using their own domain knowledge.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task22",
        "label": "How can the overall process conformance be explained for different traces?",
        "description": "Relate per-trace conformance to analyst-supplied candidate reasons (case data attributes); summarise the explanation per sub-log and present it on the process model.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task19",
        "label": "What is the effect of a guideline violation on overall process goals?",
        "description": "Formally define a process goal (positive outcome activity, else throughput), then relate each guideline violation and the activity it occurs at to whether the trace meets that goal.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task32",
        "label": "What are the main violations in my process, and do they differ between sub-processes?",
        "description": "Detect all guideline violations and rank them by total frequency (Pareto), then break each violation down across sub-logs to compare the main conformance issues between sub-processes.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task33",
        "label": "How does the overall degree of conformance differ between traces with a certain data attribute value?",
        "description": "Compare process conformance across sub-logs defined by a case-level data attribute; show fitness distributions, ranges, and summaries per group.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task34",
        "label": "In which part of the process does a guideline violation occur at the trace level?",
        "description": "Locate guideline violations within individual traces, showing exactly where each trace deviates from the expected process model.",
        "answer_type": "single_choice",
    },
    {
        "task_key": "task31",
        "label": "Do cases with a higher degree of conformance lead to a higher probability of a positive process outcome?",
        "description": "Compare sub-logs with different degrees of conformance w.r.t. their corresponding probability of a positive outcome (e.g., survival probability) over time.",
        "answer_type": "single_choice",
    },
]

CANONICAL_KNOWLEDGE_QUESTIONS = [
    # ── Domain 1: Basic Process Mining Concepts ──────────────────────────────
    {
        "kq_key": "kq01",
        "section_title": "Domain 1: Basic Process Mining Concepts",
        "text": "1. What is the primary purpose of conformance checking in process mining?",
        "options": [
            "To predict future process behavior",
            "To compare observed process behavior with a process model",
            "To improve process execution speed automatically",
            "To design a new process model",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 1,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq02",
        "section_title": "Domain 1: Basic Process Mining Concepts",
        "text": "2. In an event log, what does one trace represent?",
        "options": [
            "One event at a single point in time",
            "All activities in the event log",
            "The sequence of activities belonging to one process case",
            "A statistical summary of process performance",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 2,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq03",
        "section_title": "Domain 1: Basic Process Mining Concepts",
        "text": (
            "3. An event log contains the following 5 traces:\n"
            "Trace 1: A → B → C → D\n"
            "Trace 2: A → B → D\n"
            "Trace 3: A → B → C → D\n"
            "Trace 4: A → C → B → D\n"
            "Trace 5: A → B → D\n"
            "How many distinct variants does this log contain?"
        ),
        "options": [
            "2",
            "3",
            "4",
            "5",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 1,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    # ── Domain 2: Conformance Checking Core Concepts ─────────────────────────
    {
        "kq_key": "kq04",
        "section_title": "Domain 2: Conformance Checking Core Concepts",
        "text": "4. What does fitness describe in conformance checking?",
        "options": [
            "How quickly the process is completed",
            "The degree to which observed process behavior conforms to the process model",
            "The number of violation types in the event log",
            "The level of detail in the process model",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 1,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq05",
        "section_title": "Domain 2: Conformance Checking Core Concepts",
        "text": "5. A process model has very high fitness (0.98) but very low precision (0.35). What does this combination indicate?",
        "options": [
            "The model accurately captures most observed behavior but also allows many behaviors that never occur in practice",
            "The model is too restrictive and rejects most of the observed behavior",
            "The event log contains almost no deviations from the model",
            "The model and the log are completely unrelated",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 0,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq06",
        "section_title": "Domain 2: Conformance Checking Core Concepts",
        "text": "6. When does a trace perfectly conform to a process model?",
        "options": [
            "When every activity of the trace appears somewhere in the model",
            "When the trace contains the same number of events as the model has activities",
            "When the trace can be executed by the model from start to end without any deviation",
            "When the trace is the most frequent variant in the event log",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 2,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    # ── Domain 3: Alignments and Deviation Types ─────────────────────────────
    {
        "kq_key": "kq07",
        "section_title": "Domain 3: Alignments and Deviation Types",
        "text": "7. The process model requires an activity, but it is missing from the recorded trace. Which alignment move represents this?",
        "options": [
            "Synchronous Move",
            "Log Move",
            "Model Move",
            "Trace Variant",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 2,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq08",
        "section_title": "Domain 3: Alignments and Deviation Types",
        "text": "8. The recorded trace contains an activity that the process model does not expect at that point. Which alignment move represents this?",
        "options": [
            "Synchronous Move",
            "Log Move",
            "Model Move",
            "Trace Variant",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 1,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq09",
        "section_title": "Domain 3: Alignments and Deviation Types",
        "text": (
            "9. Consider a process model that prescribes the sequence: "
            "Register → Examine → Decide → Notify. "
            "A recorded trace shows: Register → Examine → Pay → Decide → Notify. "
            "In an optimal alignment, the activity \"Pay\" would be classified as:"
        ),
        "options": [
            "A synchronous move, because it was successfully executed",
            "A model move, because the model expected it but it was missing",
            "A log move, because it was recorded in the log but not expected by the model at that point",
            "A silent transition, because it does not appear in either the log or the model",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 2,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    # ── Domain 4: Quantitative Reasoning and Analysis ────────────────────────
    {
        "kq_key": "kq10",
        "section_title": "Domain 4: Quantitative Reasoning and Analysis",
        "text": "10. When comparing two process models for the same event log, Model A replays 95% of traces without violations, while Model B replays only 60%. Which statement is most accurate?",
        "options": [
            "Model B is preferable because it is more flexible",
            "Model A has a higher fitness with respect to the event log",
            "Both models are equally valid since they describe the same process",
            "Model A must also have higher precision than Model B",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 1,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq11",
        "section_title": "Domain 4: Quantitative Reasoning and Analysis",
        "text": "11. Which of the following is NOT typically considered a root cause analysis task in conformance checking?",
        "options": [
            "Identifying which data attributes correlate with guideline violations",
            "Detecting which resources or time patterns are associated with non-conformant traces",
            "Designing a new process model from scratch based on user preferences",
            "Investigating whether specific organizational units show higher deviation rates",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 2,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "kq_key": "kq12",
        "section_title": "Domain 4: Quantitative Reasoning and Analysis",
        "text": (
            "12. An alignment analysis of an event log produces the following results for a single activity \"Approve Payment\":\n"
            "Move on Model (MoM): 120 occurrences\n"
            "Move on Log (MoL): 45 occurrences\n"
            "Synchronous Moves: 835 occurrences\n"
            "Which interpretation is most accurate?"
        ),
        "options": [
            "\"Approve Payment\" is never executed correctly in any trace",
            "\"Approve Payment\" is mostly executed as expected, but is sometimes skipped (120 times) and sometimes occurs unexpectedly (45 times)",
            "The process model does not include \"Approve Payment\" as a valid activity",
            "There are 165 traces in total that contain \"Approve Payment\"",
            "I don't know",
        ],
        "include_idk": True,
        "correct_option_index": 1,
        "is_system": True,
        "created_at": "2025-01-01T00:00:00Z",
    },
]

CANONICAL_IDIOMS = [
    {"idiom_key": "bar_chart",            "label": "Bar Chart",                            "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "tile_metric",          "label": "Tile Metric",                          "granularity": "log",   "renderer_type": "html",    "active": True},
    {"idiom_key": "gauge_chart",          "label": "Gauge Chart",                          "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "scatterplot",          "label": "Scatterplot (Dotted Chart)",           "granularity": "trace", "renderer_type": "echarts", "active": True},
    {"idiom_key": "table",                "label": "Table",                                "granularity": "log",   "renderer_type": "html",    "active": True},
    {"idiom_key": "heatmap",              "label": "Heatmap",                              "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "boxplot",              "label": "Box and Whisker Plot",                 "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "flow_chart_basic",     "label": "Flow Chart (Chevron Diagram)",         "granularity": "trace", "renderer_type": "svg",     "active": True},
    {"idiom_key": "flow_chart_elaborate", "label": "Flow Chart+ (BPMN Diagram)",           "granularity": "trace", "renderer_type": "bpmn",    "active": True},
    {"idiom_key": "pie_chart",            "label": "Pie Chart",                            "granularity": "log",   "renderer_type": "echarts", "active": True},
    {"idiom_key": "tree",                  "label": "Decision Tree",                        "granularity": "log",   "renderer_type": "d3",      "active": True},
    {"idiom_key": "flow_chart_table",     "label": "Flow Chart & Table",                   "granularity": "trace", "renderer_type": "html",    "active": True},
    {"idiom_key": "table_bar_chart",      "label": "Table & Bar Chart",                    "granularity": "log",   "renderer_type": "html",    "active": True},
    {"idiom_key": "line_graph",           "label": "Line Graph",                           "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "horizon_chart",        "label": "Horizon Chart",                        "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "gantt_chart",          "label": "Gantt Chart",                          "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "matrix",              "label": "Matrix",                                "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "network_diagram",     "label": "Network Diagram",                       "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "scatter_plot",        "label": "Scatter Plot",                          "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "stacked_bar",             "label": "Stacked Bar Graph",                     "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "flow_chart_elaborate_table", "label": "Flow Chart+ & Table",                "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "petri_net",                  "label": "Petri Net",                           "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "flow_chart_elaborate_dfg",   "label": "Flow Chart+ DFG",                     "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "parallel_sets",              "label": "Parallel Sets",                        "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "calendar",                   "label": "Calendar",                             "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "sunburst",                   "label": "Sunburst Diagram",                     "granularity": "log",   "renderer_type": "svg",     "active": True},
    {"idiom_key": "tree_map",                   "label": "Tree Map",                             "granularity": "log",   "renderer_type": "svg",     "active": True},
]
