from pydantic import BaseModel
from typing import List

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
