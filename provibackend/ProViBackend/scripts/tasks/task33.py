"""
tasks/task33.py – Task ID 33: Present / Compare / Process conformance (attribute sub-logs).

How does the overall degree of conformance differ between traces with a certain
data attribute value? Each chosen attribute is cut into sub-logs by its own type
unless a split strategy is set (see trace_features). Every idiom shows the mean
fitness per bucket, through task20's renderers. Every reported number comes from
fitness; alignments are only used to discover the default attribute set.

Public API:
    generate(log, fitness_df, output_dir, alignments=None,
             attribute_set=None, split_strategy=None, group_cap=None)
        alignments     – optional; only used to discover the default attributes
        attribute_set  – attributes to compare; empty = the discovered default
                         set. Every idiom covers all of them.
        split_strategy – "binary" | "nominal_n" | "ordered_bins"; None picks
                         by each attribute's type
        group_cap      – most groups named before the rest become "Other"
"""

import logging

logger = logging.getLogger(__name__)

#: All four are task20's renderers, handed fitness instead of a violation rate.
#: The box plot, scatter plot, stacked bar and table & bar chart are gone: the
#: first three were the only ones reading a per-trace distribution, which is
#: more than a mean per bucket, and the table & bar chart drew the table and the
#: bar chart of this same list in one frame.
IDIOMS = [
    "bar_chart",
    "table",
    "matrix",
    "heatmap",
]


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see docs/TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "fitness"
SPLIT_STRATEGY = None  # admin chooses

#: One title over all four, in the same words as the value they carry. "Candidate
#: Attribute" is task20's vocabulary, where the attributes are candidate root
#: causes; here the admin has chosen the attribute, so there is nothing candidate
#: about it.
_SPLIT_SUPTITLE = "Mean Fitness by Attribute"

import trace_features

def validate_params(log, params) -> list:
    return trace_features.validate_attribute_class(params, multi=True)


PARAM_SPEC = [*trace_features.grouping_params()]
import os
import matplotlib
matplotlib.use("Agg")

# Nothing is drawn here any more: every idiom is one of task20's renderers,
# imported inside generate() because task20 pulls in task13, which imports
# task20 back.

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir, alignments=None,
             attribute_set=None, split_strategy=None, group_cap=None):
    """Render Task ID 33 into output_dir.

    Every idiom draws mean fitness per bucket of every chosen attribute, through
    the renderers task20 also uses.

    The distribution idioms that used to sit beside them — box plot, scatter plot
    and stacked bar — are gone. They read a per-trace distribution, which is more
    than a mean per bucket, and they could only ever do it for the *first*
    attribute selected, so a two-attribute selection gave four figures about both
    and three about one.
    """
    import trace_response
    import tasks.task20 as task20

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 33 visualizations ---")

    # Alignments are used only to discover the default attribute set; every
    # number this task reports comes from fitness.
    feat = task20.task20_trace_feature_dataframe(log, alignments) if alignments is not None else None
    attrs = list(attribute_set) if attribute_set else task20._default_attributes(log, feat)
    panels = trace_response.attribute_panels(
        log, attrs, "fitness", fitness_per_trace=fitness_df["fitness"],
        strategy=split_strategy, cap=group_cap,
    )
    logger.info(f"      -> attributes: {attrs}  ({len(panels)} panel(s))")

    # One spelling of the measure across the four. value_label feeds the axis
    # labels, value_label_header the column headers and tick labels; task20
    # title-cases the first into the second, which gave a participant "Mean
    # fitness" on the bar chart and "Mean Fitness" on the matrix beside it.
    #
    # attribute_on_axis puts each attribute's name on the axis its buckets sit
    # on, instead of floating over the panel as a title. Only task33 asks for
    # it, and only task33 asks the matrix to drop its meaningless panel wash:
    # task15, task16, task20 and task22 share these renderers and have tuned
    # screenshots in the running experiment.
    fmt = dict(suptitle=_SPLIT_SUPTITLE, value_label="Mean Fitness",
               value_label_header="Mean Fitness",
               value_fmt="{:.3f}", value_max=1.0, attribute_on_axis=True)
    task20.task20_bar_chart(panels, output_dir, filename="task33_bar_chart.svg", **fmt)
    task20.task20_table(panels, output_dir, filename="task33_table.svg", **fmt)
    task20.task20_matrix(panels, output_dir, filename="task33_matrix.svg",
                         colorless=True, **fmt)
    task20.task20_heatmap(panels, output_dir, filename="task33_heatmap.svg", **fmt)

