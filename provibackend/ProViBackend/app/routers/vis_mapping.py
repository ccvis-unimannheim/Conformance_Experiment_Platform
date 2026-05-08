# Maps DB Task.task_key to the SVG subdirectory name under new_output/
TASK_KEY_TO_DIR = {
    "T-01": "task1",
    "T-02": "task2",
    "T-03": "task3",
    "T-04": "task4",
    "T-05": "task5",
    "T-06": "task6",
}

# Maps DB Idiom.idiom_key to the SVG filename suffix (without task prefix or .svg extension)
IDIOM_KEY_TO_SVG_SUFFIX = {
    "bar_chart":            "bar_chart",
    "donut_chart":          "donut_chart",
    "tile_metric":          "tile_metric",
    "table":                "table",
    "heatmap":              "heatmap",
    "pie_chart":            "pie_chart",
    "decision_tree":        "decision_tree",
    "flow_chart_basic":     "flow_chart_basic",
    "boxplot":              "box_plot",
    "scatterplot":          "scatter_plot",
    "flow_chart_elaborate": "flow_chart_elaborate_bpmn",
    "flow_chart_table":     "flow_chart_and_table",
    "table_bar_chart":      "table_and_bar_chart",
}
