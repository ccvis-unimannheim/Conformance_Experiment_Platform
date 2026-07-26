from pydantic import BaseModel,Field, ConfigDict
from typing import List, Optional, Dict, Any

class PreliminaryAnswersRequest(BaseModel):
    """Request body from frontend — no _id, generated server-side."""
    gender: str
    age_range: str                   # e.g. "18–24"
    education: str
    role: str
    field_of_study: str
    rating_business_process_management: int # 1–5
    rating_process_mining: int       # 1–5
    rating_conformance_checking: int # 1–5
    years_experience: int            # 0–15
    tools: List[str] = []            # PM tools used (moved from knowledge survey)

class PreliminaryAnswers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    gender: str
    age: int
    professional_background: str
    experience_time_pm: str
    frequency_pm: str
    expertise_level_pm: str

class KnowledgeAnswers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    notes: str
    score: int
    level: int

class KnowledgeAnswersRequest(BaseModel):
    answers: Dict[str, int]   # {question_id: option_index}
    tools: List[str] = []

class KnowledgeQuestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    section_title: str
    text: str
    options: List[str]
    include_idk: bool
    correct_option_index: Optional[int]
    is_system: bool
    created_at: str

class KnowledgeQuestionCreate(BaseModel):
    section_title: str
    text: str
    options: List[str]          # does NOT include "I don't know" (added automatically if include_idk=True)
    include_idk: bool = False
    correct_option_index: Optional[int] = None

class KnowledgeQuestionIds(BaseModel):
    knowledge_question_ids: List[str]

class PrequestionnaireSections(BaseModel):
    sections: List[str]  # e.g. ["personal_info", "academic_profile", "technical_expertise", "tool_experience"]

class FeedbackAnswersRequest(BaseModel):
    ratings:  dict        # {mentalDemand, physicalDemand, temporalDemand, performance, effort, frustration}
    feedback: str | None = None

class User(BaseModel):
    user_id: str
    preliminary_id: str
    knowledge_id: str
    insert_datetime: str

class Dataset(BaseModel):
    dataset_id: str
    dataset_title: str
    checksum: str
    is_active: bool
    location: str

class DatasetFile(BaseModel):
    filename: str
    location: str
    checksum: str

class DatasetPair(BaseModel):
    dataset_id: str
    dataset_title: str
    dataset_is_active: bool
    insert_datetime: str
    log: DatasetFile
    guideline: DatasetFile

class DatasetFromFrontend(BaseModel):
    dataset_id: str
    dataset_title: str
    is_active: bool

class ListDatasetsFromFrontend(BaseModel):
    datasets: List[DatasetFromFrontend]

class AnswerFromFrontend(BaseModel):
    experiment_id: Optional[str] = None
    question_id: str
    task_id: str
    idiom_id: str
    dataset_id: str
    ground_truth_id: Optional[str] = None
    trial_index: int
    presentation_order: int
    answer: str
    response_time_ms: int
    capabilities_meet_requirements: Optional[int] = None
    easy_to_use: Optional[int] = None

class AnswerForDatabase(BaseModel):
    user_id: str
    group_id: Optional[str] = None
    experiment_id: Optional[str] = None
    question_id: str
    task_id: str
    idiom_id: str
    dataset_id: str
    ground_truth_id: Optional[str] = None
    trial_index: int
    presentation_order: int
    answer: str
    is_correct: Optional[bool] = None
    response_time_ms: int
    capabilities_meet_requirements: Optional[int] = None
    easy_to_use: Optional[int] = None
    insert_datetime: str

class UILogging(BaseModel):
    user_id: str
    group_id: str
    experiment_id: str
    question_id: str
    task_id: str
    idiom_id: str
    dataset_id: str
    trial_index: int
    presentation_order: int
    activity: str
    uiElement: str
    uiGroup: str
    value: str
    insert_datetime: str

class UILogDataFrontend(BaseModel):
    ui_logs: List[UILogging]

class UILogBatch(BaseModel):
    """Frontend sends a batch of UI logs"""
    ui_logs: List[UILogging]

class UILogDataDatabase(BaseModel):
    ui_log_data: UILogDataFrontend


class FitnessHelpEvent(BaseModel):
    """One open→close interaction with the fitness help popup."""
    experiment_id: Optional[str] = None
    open_index: int             # which open this was (1-based cumulative counter)
    open_datetime: Optional[str] = None  # ISO timestamp when the user clicked to open
    dwell_ms: int               # ms the popup was visible
    insert_datetime: str        # ISO timestamp when the popup was closed / event was posted


class TermHelpEvent(BaseModel):
    """One open→close interaction with a per-task term explanation chip."""
    experiment_id: Optional[str] = None
    task_key: str               # e.g. "task06"
    term_key: str               # e.g. "degree_of_conformance"
    open_index: int             # cumulative open count for this term in this session
    open_datetime: Optional[str] = None
    dwell_ms: int
    insert_datetime: str


class Administrator(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    username: str
    password_hash: str
    email: str
    role: str
    last_login: Optional[str] = None
    created_at: str

class TaskConfig(BaseModel):
    task_id: str
    idiom_id: str
    dataset_id: str
    question_ids: List[str]

class OptionItem(BaseModel):
    """One option in a multiple-choice ground-truth set (correct answer or distractor)."""
    label: str
    value: str = ""
    correct: bool = False

class GroundTruthBlock(BaseModel):
    """Format-tagged ground truth for one task instance (see ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §3)."""
    tier: str = "MANUAL"               # AUTO | SEMI | MANUAL
    format: Optional[str] = None       # the answer_format this GT is shaped for
    decisive: bool = False             # derived from format, admin-overridable
    value: Optional[Any] = None        # scalar / set / rank / matrix per format
    options: List[OptionItem] = []     # MC: full closed set incl. distractors
    reference: Optional[str] = None    # optional reference text from compute_ground_truth; the grading rubric is task-level (served by /tasks/{task_key}/rubric), not stored here
    artefact_path: Optional[str] = None

class TaskInstance(BaseModel):
    """One task in an experiment, grouping its idioms + shared params/format/GT."""
    task_id: str
    dataset_id: str = ""
    idiom_ids: List[str] = []
    parameters: Dict[str, Any] = {}
    answer_format: Optional[str] = None
    generation_status: str = "pending"   # pending | running | ready | failed
    generation_error: Optional[str] = None
    ground_truth: Optional[GroundTruthBlock] = None
    question_ids: List[str] = []

class Experiment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    name: str
    type: str
    status: str
    design_type: str
    between_factors: List[str]
    within_factors: List[str]
    stratification_fields: List[str]
    between_balance_mode: str
    within_sequence_mode: str
    dataset_ids: List[str]
    task_configs: List[TaskConfig] = []      # legacy flat view (mirror of task_instances)
    task_instances: List[TaskInstance] = []  # canonical: one entry per task
    knowledge_question_ids: List[str] = []   # empty = use all system questions
    prequestionnaire_sections: List[str] = ["personal_info", "academic_profile", "technical_expertise", "tool_experience"]  # enabled sections
    created_by: str             # FK → Administrator
    created_at: str

class UserAssignment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    experiment_id: str
    user_id: str
    group_id: str
    assigned_between: Dict[str, str]
    trial_sequence: List[str]
    current_trial_index: int
    insert_datetime: str

class Task(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    task_key: str
    label: str
    description: str
    answer_type: str

class TaskUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    answer_type: str | None = None

class Question(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    task_id: str
    question_text: str
    answer_options: List[str]
    scoring_rule: Dict[str, int]
    metadata: Dict[str, str]

class GroundTruth(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    question_id: str
    dataset_id: str
    correct_answer: str

class Idiom(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")
    idiom_key: str
    label: str
    granularity: str
    renderer_type: str
    active: bool

class ExperimentUpdate(BaseModel):
    task_configs: Optional[List[TaskConfig]] = None
    task_instances: Optional[List[TaskInstance]] = None
    status: Optional[str] = None

# Aliases for backward compatibility with older router code
PreEliminaryAnswers = PreliminaryAnswers
