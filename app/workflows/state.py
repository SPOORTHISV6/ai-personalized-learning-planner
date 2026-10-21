
from typing import TypedDict, List, Dict, Any


class LearningState(TypedDict, total=False):

    # STUDENT
    student_id: int
    student_profile: Dict[str, Any]
    student_memory: Dict[str, Any]

    # ACADEMIC DATA
    subjects: List[Dict[str, Any]]
    topics: List[Dict[str, Any]]

    # LEARNING ANALYSIS
    learning_gaps: List[Dict[str, Any]]

    # RESOURCES
    resources: List[Dict[str, Any]]

    # STUDY PLAN
    study_plan: Dict[str, Any]
    persisted_plan: Dict[str, Any]
    persistence_action: str

    # QUIZ / EVALUATION
    quiz_result_id: int
    evaluation: Dict[str, Any]

    # VALIDATION
    validation: Dict[str, Any]
    validation_retry_count: int

    # WORKFLOW CONTROL
    next_action: str
    user_feedback: str

    
    # SESSION LIFECYCLE
    workflow_mode: str
    session_action: str
    session_item_id: int
    session_lifecycle_result: Dict[str, Any]


    # ERRORS
    errors: List[str]
