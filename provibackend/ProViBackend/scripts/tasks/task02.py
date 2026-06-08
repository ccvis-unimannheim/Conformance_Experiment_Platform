"""
tasks/task02.py – Task ID 2: Confirm / Present / Process conformance.

Single idiom: Tile Metric — overall (sub-)log fitness as a simple percentage.
The tile is visually identical to task06's tile; rendering logic lives in shared.py.

Public API:
    generate(df, output_dir)
        df         – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric"]

import os

from shared import render_fitness_tile_metric


def generate(df, output_dir: str):
    """Generate the Task ID 2 Tile Metric SVG into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 2 visualizations ---")

    if df is None or df.empty:
        logger.warning("      Skipped Task ID 2: empty fitness DataFrame.")
        render_fitness_tile_metric(0.0, os.path.join(output_dir, "task02_tile_metric.svg"))
        return

    avg = float(df["fitness"].mean()) * 100
    logger.info(f"      -> Overall conformance rate: {avg:.2f}%")
    render_fitness_tile_metric(avg, os.path.join(output_dir, "task02_tile_metric.svg"))
