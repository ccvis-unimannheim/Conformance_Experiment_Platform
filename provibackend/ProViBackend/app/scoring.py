"""Answer scoring — turns a participant's raw ``answer`` string into is_correct.

Graded at submit time (questionnaire.post_answer). The frontend serialises every
answer into the single ``answer: str`` field; the shape depends on answer_format
(see AnswerWidgets.js ``serializeAnswer``). This module reverses that and compares
against the stored GroundTruthBlock.

    answer_format        raw answer string          ground truth source
    ------------------   ------------------------   ----------------------------
    mc-single            token                      options[].correct (one set)
    mc-multi             JSON array of tokens        options[].correct (set ==)
    matrix               JSON array of pair tokens   options[].correct (set ==)
    pct / count / decimal   number string           ground_truth.value (scalar)
    pct-set / count-set  JSON {label: number}        options[].value (per label)
    rank                 JSON array (ordered)        options[] order (list ==)
    free-text            free text                   None (manual grading)

Returns Optional[bool]:
    True / False — graded automatically.
    None         — not auto-gradable (free-text/reference) or GT/answer missing
                   or malformed, so it stays ungraded rather than fabricated.
"""

import json
import logging

logger = logging.getLogger(__name__)

# Per-format numeric comparison precision (decimal places to round both sides to).
_NUM_NDIGITS = {"pct": 0, "count": 0, "decimal": 3, "pct-set": 0, "count-set": 0}

_CHOICE_SINGLE = {"mc-single"}
_CHOICE_MULTI = {"mc-multi", "matrix"}
_SCALAR = {"pct", "count", "decimal"}
_LABELLED_SET = {"pct-set", "count-set"}
_RANK = {"rank"}
_MANUAL = {"free-text"}

# Formats whose ground truth lives in options[]; with no options the task isn't
# gradable (e.g. GT not authored, or empty log) so it must stay ungraded (None)
# rather than mc-multi's empty-vs-empty falsely scoring correct.
_NEEDS_OPTIONS = _CHOICE_SINGLE | _CHOICE_MULTI | _LABELLED_SET | _RANK


def _token(opt: dict) -> str:
    """Submit token for an option — mirrors participant._participant_options."""
    return opt.get("value") or opt.get("label", "")


def _parse_num(raw):
    """Parse a possibly-formatted number ('96%', '1,024', ' 0.82 ') to float."""
    if raw is None:
        return None
    s = str(raw).strip().replace("%", "").replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _nums_equal(a, b, ndigits: int) -> bool:
    if a is None or b is None:
        return False
    return round(a, ndigits) == round(b, ndigits)


def _correct_tokens(options: list) -> set:
    return {_token(o) for o in options if o.get("correct")}


def score_answer(answer_format: str, ground_truth: dict, raw_answer: str):
    """Grade one answer. See module docstring for the contract.

    ``ground_truth`` is the stored GroundTruthBlock as a plain dict
    (keys: value, options, ...). ``raw_answer`` is the submitted ``answer`` string.
    """
    if not answer_format or answer_format in _MANUAL:
        return None
    if ground_truth is None:
        return None

    options = ground_truth.get("options") or []
    if answer_format in _NEEDS_OPTIONS and not options:
        return None

    try:
        if answer_format in _CHOICE_SINGLE:
            return raw_answer in _correct_tokens(options)

        if answer_format in _CHOICE_MULTI:
            selected = set(json.loads(raw_answer)) if raw_answer else set()
            return selected == _correct_tokens(options)

        if answer_format in _SCALAR:
            gt = _parse_num(ground_truth.get("value"))
            ans = _parse_num(raw_answer)
            if gt is None or ans is None:
                return None
            return _nums_equal(ans, gt, _NUM_NDIGITS.get(answer_format, 3))

        if answer_format in _LABELLED_SET:
            ans_map = json.loads(raw_answer) if raw_answer else {}
            if not isinstance(ans_map, dict):
                return None
            ndigits = _NUM_NDIGITS.get(answer_format, 0)
            for opt in options:
                label = opt.get("label", "")
                gt = _parse_num(opt.get("value"))
                ans = _parse_num(ans_map.get(label))
                if not _nums_equal(ans, gt, ndigits):
                    return False
            return True

        if answer_format in _RANK:
            gt_order = [_token(o) for o in options]
            ans_order = json.loads(raw_answer) if raw_answer else []
            if not isinstance(ans_order, list):
                return None
            return ans_order == gt_order

    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("score_answer: could not grade %s answer %r: %s",
                       answer_format, raw_answer, exc)
        return None

    # Unknown format → leave ungraded.
    return None
