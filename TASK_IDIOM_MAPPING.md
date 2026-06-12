# Task–Idiom Mapping Reference

Source: *Conformance Checking Tasks Working Table.xlsx* + *Task_Idiom_Complete_Mapping_副本.xlsx*

> `flow_chart_elaborate` covers all Flow Chart+ variants (BPMN, Petri Net, DFG). See per-idiom canonical keys below.

## task01

**Goal · Means · Characteristics:** Confirm · Compare · Process conformance

**Description:** How does the conformance of traces with a certain condition (i.e., process outcome positive (bug fixed)) differ from those who not meet this condition? To answer this, we compare the behavior of different sub-logs with the desired behavior and pinpoint violations.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Line Graph | `line_graph` | Medium/Reviewed |
| Horizon Chart | `horizon_chart` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task02

**Goal · Means · Characteristics:** Confirm · Present · Process conformance

**Description:** Does the behavior predominantly follow the desired executions in the process model? Assuming that this is the case, we compute the fitness of a (sub-) log and only investigate the behavior any further if we incur violations. The fitness is typically represented as a simple number.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Tile Metric | `tile_metric` | High |
| Table | `table` | Medium/Reviewed |

## task03

**Goal · Means · Characteristics:** Describe · Compare · Conformant and non-conformant traces

**Description:** How does the overall behavior of conformant traces differ from that of non-conformant traces? This allows us to inspect differences or behavioral patterns between conforming and non-conforming traces, hinting at potential correlating factors between them.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Gantt Chart | `gantt_chart` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task04

**Goal · Means · Characteristics:** Describe · Compare · Process conformance

**Description:** How does the overall degree of conformance with a set of guidelines differ between multiple logs or traces? To answer this, we first need to derive the process conformance for these entities. At the log level, this provides a more generic overview between different process executions. At the trace level, this is specific to the execution patterns found in the trace.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Line Graph | `line_graph` | Medium/Reviewed |
| Horizon Chart | `horizon_chart` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | Medium/Reviewed |
| Table & Bar Chart | `table_bar_chart` | Medium/Reviewed |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |

## task05

**Goal · Means · Characteristics:** Describe · Compare · Violation patterns

**Description:** How often does a set of violations occur in different logs? This is particularly interesting for predefined sets of violations that describe a certain undesired process behavior. It allows us to track the occurrence of this behavior in different process executions.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task06

**Goal · Means · Characteristics:** Describe · Derive · Process conformance

**Description:** What is the overall degree of conformance between a (single) log and a set of guidelines? This is typically expressed as an automatically computed fitness value, set between 0 (no conformance at all) and 1 (perfect conformance). The value often serves as a first step in conformance checking, providing a first orientation on which steps to take next.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Tile Metric | `tile_metric` | High |
| Table | `table` | Medium/Reviewed |

## task07

**Goal · Means · Characteristics:** Describe · Derive · Process conformance over time

**Description:** How does the degree of process conformance change over time? To answer this, we first need to derive the process conformance for a (partial) log at multiple points in time.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Line Graph | `line_graph` | High |
| Horizon Chart | `horizon_chart` | High |
| Gantt Chart | `gantt_chart` | High |

## task08

**Goal · Means · Characteristics:** Describe · Derive · Violation patterns

**Description:** Which guideline violations frequently co-occur in a trace? If there are correlations between guideline violations, they might hint to an underlying common cause or a dependencies in the process.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task09

**Goal · Means · Characteristics:** Describe · Identify · Guideline violations

**Description:** How exactly does the process execution differ from the guidelines? What behavior was prescribed by the guidelines and what behavior was executed instead? This can relate to different control-flow relations, but also resource and data constraints. 
This task is similar to ``Present: Present Guideline violations'', but rather than analyzing the control-flow of a complete trace, ``Describe: Identify Guideline violations'' provides detailed context about specific constraints of interest and their potential violations.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart (Chevron Diagram) | `flow_chart_basic` | Medium/Reviewed |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task10

**Goal · Means · Characteristics:** Describe · Present · Conformance distribution

**Description:** Which percentage of traces in the log fall into which conformance category? In this context, the conformance range is typically separated into intervals, into which the traces are distributed. It allows for a more detailed insight into the overall log conformance, which is an average value.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Stacked Bar Graph | `stacked_bar` | High |
| Line Graph | `line_graph` | High |
| Horizon Chart | `horizon_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Box and Whisker Plot | `boxplot` | High |
| Table | `table` | Medium/Reviewed |
| Table & Bar Chart | `table_bar_chart` | Medium/Reviewed |
| Heatmap | `heatmap` | High |
| Calendar | `calendar` | High |
| Pie / Donut Chart | `pie_chart` | Medium/Reviewed |

## task11

**Goal · Means · Characteristics:** Describe · Summarize · Guideline violations

**Description:** How often did a specific guideline violation occur? To answer this, we first need to determine the guideline violations that occur. Those might relate to any process perspective on event, trace, or log level.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | High |
| Sunburst Diagram | `sunburst` | High |
| Tree Map | `tree_map` | High |
| Parallel Sets | `parallel_sets` | High |

## task12

**Goal · Means · Characteristics:** Describe · Summarize · Process conformance

**Description:** In what percentage of traces do violations occur? To answer this, we first need to identify these guideline violations. The task is similar "derive process conformance", with the difference that this one quantifies the percentage of conformant / deviating traces.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Tile Metric | `tile_metric` | High |
| Table | `table` | Medium/Reviewed |
| Table & Bar Chart | `table_bar_chart` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | Medium/Reviewed |

## task13

**Goal · Means · Characteristics:** Explain · (not known) · Reasons for guideline violations

**Description:** What are the underlying reasons for guideline violations?

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | Medium/Reviewed |
| Sunburst Diagram | `sunburst` | Medium/Reviewed |
| Tree Map | `tree_map` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task14

**Goal · Means · Characteristics:** Explain · Annotate · Guideline violations

**Description:** What kind of violation occurs in a given trace? This requires a classification of violations, and a textual description of them.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Parallel Sets | `parallel_sets` | High |

## task15

**Goal · Means · Characteristics:** Explain · Annotate · Reasons for process conformance

**Description:** How can the overall process conformance be explained? Requires prior knowledge of potential explanations.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Parallel Sets | `parallel_sets` | High |

## task16

**Goal · Means · Characteristics:** Explain · Annotate · Reasons for guideline violations

**Description:** What is the reason for guideline violations? Similar to (Explain: Indentify ''Reasons for guideline violations'') tasks, although here, preexisting knowledge about the reason is taken into account

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Parallel Sets | `parallel_sets` | High |

## task17

**Goal · Means · Characteristics:** Explain · Annotate · Severity of guideline violations

**Description:** How often in a log is a guideline violated? How severe / problematic is a frequent violation? Is it feasible that the rule is too strict and frequent violations are not concerning? This includes deviations of a log presented in a model, and textual explanations. Pre-existing knowledge of explanations is required.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Flow Chart & Table | `flow_chart_table` | Medium/Reviewed |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | High |
| Sunburst Diagram | `sunburst` | High |
| Tree Map | `tree_map` | High |
| Parallel Sets | `parallel_sets` | High |

## task18

**Goal · Means · Characteristics:** Explain · Derive · Reasons for guideline violations

**Description:** Which events are responsible for guideline violations in one or more traces? Reasons are not known previously, but deduced by the analyst.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task19

**Goal · Means · Characteristics:** Explain · Discover · Effects of goal deviations

**Description:** What is the effect of a guideline violation on overall process goals? We first need to formally define the process goal.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Parallel Sets | `parallel_sets` | High |

## task20

**Goal · Means · Characteristics:** Explain · Discover · Reasons for guideline violations

**Description:** What control-flow, data, resource, or time attribtues of  events, traces, or logs lead to guideline violations?

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Parallel Sets | `parallel_sets` | High |

## task21

**Goal · Means · Characteristics:** Explain · Identify · Reasons for guideline violations

**Description:** What are the underlying reasons for guideline violations of traces? In contrast to (Explain: Identify "Reasons for guideline violations"), this task focusses on finding potential reasons through the visualization

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | Medium/Reviewed |
| Sunburst Diagram | `sunburst` | Medium/Reviewed |
| Tree Map | `tree_map` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task22

**Goal · Means · Characteristics:** Explain · Summarize · Reasons for process conformance

**Description:** How can the overall process conformance be explained for different traces? This requires knowledge from the analyst about potential reasons, which are then presented in one or more models.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Parallel Sets | `parallel_sets` | High |

## task23

**Goal · Means · Characteristics:** Explore · Compare · Guideline violations

**Description:** How are the guideline violations different to each other? This needs first a summarizing of the violations.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task24

**Goal · Means · Characteristics:** Explore · Discover · Guideline violations in model

**Description:** Where is the discovered model different to the process model with the desired behavior? Multiple traces are taken and the model is discovered to see the differences between the desired behavior and the observed behavior in reality

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | High |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |

## task25

**Goal · Means · Characteristics:** Explore · Discover · Process conformance

**Description:** What is the overall degree of conformance between a (single) log and a set of guidelines? Here the degree of conformance is discovered by the process analysts based on visualized results from a conformance checking technique. The task is similar to "Describe-Derive-Process conformance", but here the analyst discovers the conformance degree themself.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Tile Metric | `tile_metric` | High |
| Table | `table` | Medium/Reviewed |

## task26

**Goal · Means · Characteristics:** Present · Present · Severity of guideline violations

**Description:** How impactful/serious is a guideline violation from a process execution? The types of violations and their severity are defined beforehand and then are presented to the analysts.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | High |
| Sunburst Diagram | `sunburst` | High |
| Tree Map | `tree_map` | High |
| Parallel Sets | `parallel_sets` | High |

## task27

**Goal · Means · Characteristics:** Explore · Identify · Conformant and non-conformant traces

**Description:** What are conformant and what are non-conformant trace(s) (variants)? How are they different from each other? Trace or trace variants s are visualized, such that the compliant and the non-copliant cases can be identified and explored by the analyst.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Flow Chart & Table | `flow_chart_table` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Gantt Chart | `gantt_chart` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task28

**Goal · Means · Characteristics:** Explore · Identify · Guideline violations

**Description:** Where exactly does the process execution differ from the guideline? What does alternative behavior look like? This can relate to different control-flow relations, but also resource and data constraints. Although most frequently relating to traces, it can also occur on an event or log level. The task is similar to ``Present: Present Guideline violations''. The difference is that in this task, the violations are not immediately shown to the analysts. Instead, the means are provided for the analysts to explore the data and identify the violations on their own.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Flow Chart (Chevron Diagram) | `flow_chart_basic` | Medium/Reviewed |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Gantt Chart | `gantt_chart` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |
| Sunburst Diagram | `sunburst` | Medium/Reviewed |
| Tree Map | `tree_map` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task29

**Goal · Means · Characteristics:** Explore · Summarize · Guideline violations

**Description:** What type of guideline violation happened in different traces? How often do they happen? The task is similar to ``Describe: Summarize Guideline violation'', with the difference that ``Explore'' requires the process analyst to summarize the violations on their own.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Pie / Donut Chart | `pie_chart` | High |
| Sunburst Diagram | `sunburst` | High |
| Tree Map | `tree_map` | High |
| Parallel Sets | `parallel_sets` | High |

## task30

**Goal · Means · Characteristics:** Present · Compare · Guideline violations

**Description:** How do different sub-logs with certain data attribute values (i.e., students with better or worse grades) deviate from the prescribed process models? We aim to uncover significant differences in process conformance and deviating behavior in between the sub-logs. This task is similar to "Present - Present - Guideline violation", with the different that multiple sub-processes are investigated simultaneously.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task31

**Goal · Means · Characteristics:** Present · Compare · Impact of conformance on process outcome

**Description:** Do cases with a higher degree of conformance lead to a higher probability of a positive process outcome? To answer this, we compare sub-logs with different degrees of conformance w.r.t. to their corresponding probability of a positive outcome (e.g., survival probability) over time.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Table | `table` | Medium/Reviewed |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | High |

## task32

**Goal · Means · Characteristics:** Present · Compare · Most frequent guideline violations

**Description:** What are the main violations in my process and do they differ in between different sub-processes? To answer this, we first have to detect all occurring guideline violations and determines their frequency. At (sub-)log level, this pinpoints the main conformance issues and allows to compare these issues between the sub-processes.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Stacked Bar Graph | `stacked_bar` | High |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | High |
| Heatmap | `heatmap` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task33

**Goal · Means · Characteristics:** Present · Compare · Process conformance

**Description:** How does the overall degree of conformance with a set of guidelines differ between traces with a certain data attribute value? To answer this, we first need to derive the process conformance for these sub-logs. At the log level, this provides a more generic overview between different process executions. In addition to a mere description, a range of fitness values within the sub-logs is provided.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Stacked Bar Graph | `stacked_bar` | Medium/Reviewed |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Box and Whisker Plot | `boxplot` | Medium/Reviewed |
| Table | `table` | Medium/Reviewed |
| Table & Bar Chart | `table_bar_chart` | Medium/Reviewed |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Calendar | `calendar` | Medium/Reviewed |

## task34

**Goal · Means · Characteristics:** Present · Present · Guideline violations

**Description:** Where does the recorded behavior violate which guidelines? This is typically answered for one trace or few traces simultaneously. Concretely, we are interested in how the activities in the trace(s) align with the process model and whether there are incorrect executions of activities or missing activities. That way, it is clear which violations can be attributed to which activities in the trace(s).

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | High |
| Flow Chart (Chevron Diagram) | `flow_chart_basic` | Medium/Reviewed |
| Flow Chart & Table | `flow_chart_table` | High |
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |
| Network Diagram | `network_diagram` | Medium/Reviewed |
| Tree | `tree` | Medium/Reviewed |
| Table | `table` | High |
| Table & Bar Chart | `table_bar_chart` | High |
| Matrix | `matrix` | Medium/Reviewed |
| Heatmap | `heatmap` | Medium/Reviewed |
| Parallel Sets | `parallel_sets` | High |

## task35

**Goal · Means · Characteristics:** Present · Present · Guideline violations in model

**Description:** Where does the recorded behvaior violate which guidelines? In addition to answering this on a trace basis in the task "Present - Present - Guideline violations", a second typical form of analyzing this questions is based on the process model. Concretely, the desired state in this model is annotated with frequently skipped/inserted activites. In that manner, major conformance issues are presented within the well-known process model diagram.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | High |
| Flow Chart+ & Table | `flow_chart_elaborate_table` | High |

## task36

**Goal · Means · Characteristics:** Present · Present · Process conformance per rule

**Description:** Which concrete violations of guidelines are predominant in my process? Based on concrete guidelines (e.g., LTL-formulas), we first have to calculate the average grade of conformance to each of these guidelines. These averages are presented in cunjuction (e.g., as a colored declarative process model).

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Flow Chart+ (BPMN / Petri Net / DFG) | `flow_chart_elaborate` | Medium/Reviewed |

## task37

**Goal · Means · Characteristics:** Present · Summarize · Process conformance

**Description:** How do fitness values of traces differ when applying two different techniques to compute them? Further, what is the overall trend of trace fitness in my log? To answer this, we first need to calculate the fitness values of different comutations. Based on that, we visually infer hotspots of trace fitness and also inspect differences in the trace fitness values.

| Idiom (Excel label) | Canonical key | Priority |
|---|---|---|
| Bar Chart | `bar_chart` | Medium/Reviewed |
| Stacked Bar Graph | `stacked_bar` | High |
| Line Graph | `line_graph` | High |
| Horizon Chart | `horizon_chart` | High |
| Scatter Plot (Dotted Chart) | `scatter_plot` | Medium/Reviewed |
| Box and Whisker Plot | `boxplot` | High |
| Table | `table` | Medium/Reviewed |
| Table & Bar Chart | `table_bar_chart` | Medium/Reviewed |
| Heatmap | `heatmap` | High |
| Calendar | `calendar` | High |
