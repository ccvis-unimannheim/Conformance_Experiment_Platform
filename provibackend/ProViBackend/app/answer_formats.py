"""Answer formats — the single source of truth for how a participant answers.

Formats are global: every task may use every format (there is no per-task
whitelist). A task module declares what it *draws* (IDIOMS), what it needs
configured (PARAM_SPEC) and how a human grades free text (RUBRIC); the answer
shape is an experiment-design choice made by the admin on /answer-format.

    needs_options  the format renders a closed set the admin authors on
                   /answer-format (either imported from an event-log source or
                   typed by hand). Formats without it take free input.
    numeric        the widget is a number field configured by `number_kind`.
"""

ANSWER_FORMATS: list[dict] = [
    {"key": "mc-single",  "label": "Single choice",    "widget": "single_choice",   "needs_options": True},
    {"key": "mc-multi",   "label": "Multiple choice",  "widget": "multiple_choice", "needs_options": True},
    {"key": "rank",       "label": "Ranking",          "widget": "rank",            "needs_options": True},
    {"key": "matrix",     "label": "Matrix",           "widget": "matrix",          "needs_options": True},
    {"key": "number-set", "label": "Number set",       "widget": "numeric_set",     "needs_options": True,  "numeric": True},
    {"key": "number",     "label": "Number",           "widget": "numeric",         "needs_options": False, "numeric": True},
    {"key": "free-text",  "label": "Free text",        "widget": "free_text",       "needs_options": False},
]

# Numeric presets — what used to be the separate `pct` / `count` / `decimal`
# formats, demoted to a setting on the two numeric formats. The frontend's
# numericMeta() maps these to suffix / step / min / max / hint.
NUMBER_KINDS: list[str] = ["percentage", "integer", "decimal"]
DEFAULT_NUMBER_KIND = "decimal"

# Used when a task instance has no answer_format yet (participant-side safety
# net; the admin overview gates publishing on the format actually being set).
FALLBACK_ANSWER_FORMAT = "free-text"

_BY_KEY = {f["key"]: f for f in ANSWER_FORMATS}

# key -> widget, consumed by participant.py and mirrored by AnswerWidgets.js.
FORMAT_TO_WIDGET: dict[str, str] = {f["key"]: f["widget"] for f in ANSWER_FORMATS}

# Formats whose stored `answer_options` are sent to the participant as a set.
OPTION_FORMATS: set[str] = {f["key"] for f in ANSWER_FORMATS if f.get("needs_options")}

# Ranking is shuffled before it reaches the participant so the stored option
# order cannot bias the response (no longer a ground-truth concern — the order
# carries no answer — but presentation order still would).
RANK_FORMATS: set[str] = {"rank"}


def is_known(format_key: str) -> bool:
    return format_key in _BY_KEY


def needs_options(format_key: str) -> bool:
    return format_key in OPTION_FORMATS


def widget_for(format_key: str) -> str:
    """The participant widget for this format, or free_text for unknown keys."""
    return FORMAT_TO_WIDGET.get(format_key, FORMAT_TO_WIDGET[FALLBACK_ANSWER_FORMAT])
