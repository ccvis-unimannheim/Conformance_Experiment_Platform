# Participant Answer Widgets

The answer-input controls on `/taskexecution`, one per `answer_type` returned by
the trial contract (`PARTICIPANT_TRIAL_CONTRACT.md`). This describes the widgets
as built; it replaces the implementation plan that preceded them.

## Wiring

```
GET .../trials  ──▶ taskexecution/page.js  groupTrialsByTask()
                        carries answer_format, answer_type, number_kind, options
                    └▶ TaskAnswerPanel      answerType, numberKind, options
                        └▶ AnswerInput      dispatches on answerType
```

`answer_format`, `number_kind` and `options` are properties of the
`task_instance`, so they are shared by every idiom of that task — the panel is
keyed on the trial position and re-mounts per trial.

## Widget set

`components/Task/AnswerWidgets.js` — one component per `answer_type`, plus the
`AnswerInput` dispatcher.

| `answer_type` | `answer_format` | Widget |
|---|---|---|
| `single_choice` | `mc-single` | radio list |
| `multiple_choice` | `mc-multi` | checkbox list |
| `numeric` | `number` | one number input, masked per `number_kind` |
| `numeric_set` | `number-set` | one number input per option row, same mask |
| `rank` | `rank` | reorderable list (drag or arrow buttons) |
| `matrix` | `matrix` | toggle grid over the `a__b` option cells |
| `free_text` | `free-text` | textarea |

### Numeric masking

`numericMeta(numberKind)` is the single source of the numeric input rules,
shared by `numeric` and `numeric_set`:

| `number_kind` | suffix | step | range | hint |
|---|---|---|---|---|
| `percentage` | `%` | 0.1 | 0–100 | "Enter a number between 0 and 100…" |
| `integer` | — | 1 | ≥ 0 | "Enter a whole number (≥ 0)." |
| `decimal` | — | any | — | "Enter a decimal value." |

### Matrix

Option values are `"a__b"` pair tokens. `parsePairs()` recovers both axes from
the token set — order-independently, so the stored token survives whichever cell
the participant clicks. A non-pair-shaped option set falls back to a checkbox
list rather than failing.

### Rank

The backend shuffles `options` before sending them, so the admin's authoring
order cannot bias responses. The submitted order is the participant's.

## Submit gating

`isAnswered(answerType, value)` decides whether the trial can be submitted:

- `multiple_choice`, `rank` — a non-empty selection
- `numeric_set` — at least one row filled
- `matrix` — **any** selection, including none: "no cells" is a real answer
- everything else — a non-empty string

## Answer encoding

`serializeAnswer(answerType, value)` flattens each widget's value into the
single `answer: string` field:

| `answer_type` | value shape | serialized |
|---|---|---|
| `single_choice` | string token | the token |
| `multiple_choice` | string[] | JSON array |
| `numeric` | string | the string |
| `numeric_set` | `{[label]: string}` | JSON object |
| `rank` | string[] (ordered) | JSON array, top → bottom |
| `matrix` | string[] (pair tokens) | JSON array, sorted |
| `free_text` | string | the string |

Answers are stored exactly as submitted. Nothing is scored — see
`ADMIN_EXPERIMENT_SETUP.md`.
