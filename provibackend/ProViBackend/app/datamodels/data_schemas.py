from cgitb import text
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict

class PreliminaryAnswersRequest(BaseModel):
    """Request body from frontend — no _id, generated server-side."""
    gender: str
    age: int
    professional_background: str
    experience_time_pm: str
    frequency_pm: str
    expertise_level_pm: str

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

class DatasetFromFrontend(BaseModel):
    dataset_id: str
    dataset_title: str
    is_active: bool

class ListDatasetsFromFrontend(BaseModel):
    datasets: List[DatasetFromFrontend]

class AnswerFromFrontend(BaseModel):
    question_id: str
    task_id: str
    idiom_id: str
    dataset_id: str
    ground_truth_id: str
    trial_index: int
    presentation_order: int
    answer: str
    response_time_ms: int

class AnswerForDatabase(BaseModel):
    user_id: str
    group_id: str
    experiment_id: str
    question_id: str
    task_id: str
    idiom_id: str
    dataset_id: str
    ground_truth_id: str
    trial_index: int
    presentation_order: int
    answer: str              
    is_correct: bool
    response_time_ms: int
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
    task_configs: List[TaskConfig]
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
