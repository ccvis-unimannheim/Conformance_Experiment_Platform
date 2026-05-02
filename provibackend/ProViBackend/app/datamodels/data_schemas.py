from pydantic import BaseModel
from typing import List, Optional

class Experiment(BaseModel):
    experiment_id: str
    experiment_name: str
    experiment_description: Optional[str] = None
    experiment_type: Optional[str] = None
    experiment_status: Optional[str] = None
    experiment_design_type: Optional[str] = None
    experiment_between_factors: List[str] = []
    experiment_within_factors: List[str] = []
    experiment_stratification_fields: List[str] = []
    experiment_between_balance_mode: Optional[str] = None
    experiment_within_sequence_mode: Optional[str] = None
    experiment_dataset_ids: List[str] = []
    experiment_task_configs: List[str] = []
    experiment_created_at: str

class ExperimentCreate(BaseModel):
    experiment_name: str
    experiment_description: Optional[str] = None
    experiment_dataset_ids: List[str]

class ExperimentPatch(BaseModel):
    experiment_name: Optional[str] = None
    experiment_description: Optional[str] = None
    experiment_type: Optional[str] = None
    experiment_status: Optional[str] = None
    experiment_design_type: Optional[str] = None
    experiment_between_factors: Optional[List[str]] = None
    experiment_within_factors: Optional[List[str]] = None
    experiment_stratification_fields: Optional[List[str]] = None
    experiment_between_balance_mode: Optional[str] = None
    experiment_within_sequence_mode: Optional[str] = None
    experiment_dataset_ids: Optional[List[str]] = None
    experiment_task_configs: Optional[List[str]] = None

class PreEliminaryAnswers(BaseModel):
    gender: str
    age: int
    professional_background: str
    experience_time_process_mining: str
    frequency_process_mining: str
    expertise_level_process_mining: str

class KnowledgeAnswers(BaseModel):
    what_is_process_mining: str
    spaghetti_process: str
    what_is_process_variant: str
    what_are_bpm_for: str
    which_is_not_bpmn: str
    what_is_dfg: str
    worked_with_dfg: str

class User(BaseModel):
    user_id: str
    dataset_id: str
    pre_eliminary_answers: PreEliminaryAnswers

class Dataset(BaseModel):
    dataset_id: str
    dataset_title: str
    dataset_checksum: str
    dataset_is_active: bool
    dataset_location: str
    insert_datetime: str

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
    dataset_is_active: bool

class ListDatasetsFromFrontend(BaseModel):
    datasets: List[DatasetFromFrontend]

class AnswerFromFrontend(BaseModel):
    question_id: str
    answer: str

class AnswerForDatabase(BaseModel):
    user_id: str
    answer: AnswerFromFrontend
    insert_datetime: str

class UILogging(BaseModel):
    activity: str
    uiElement: str
    uiGroup: str
    value: str
    insert_datetime: str

class UILogDataFrontend(BaseModel):
    question_id: str
    ui_logs: List[UILogging]

class UILogDataDatabase(BaseModel):
    user_id: str
    ui_log_data: UILogDataFrontend
