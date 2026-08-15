from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import time
from ..ops.json_ui import TASK_STATUS


class TaskStatus(str, Enum):
    """Status of a task in the image operation"""
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAIL = "fail"


class ReportType(str, Enum):
    """Type of report being sent"""
    TASK_PROGRESS = "task_progress"
    TASK_SUCCESS = "task_success"
    TASK_ERROR = "task_error"


class TaskRunDetails(BaseModel):
    """Details of a running task"""
    taskCategory: str  # Description of the task
    taskEstimate: float  # Estimated time to complete
    taskElapse: float  # Time elapsed so far
    taskMessage: str  # Current message from the task
    taskExplain: str  # Detailed explanation of the task
    taskVerdict: Optional[str] = None  # Final verdict if task is complete


class TaskRunStatus(BaseModel):
    """Represents a single task in the image operation"""
    name: str
    status: TaskStatus
    progress: Optional[float] = None  # Progress percentage (0-100)
    details: TaskRunDetails


class RunnerMessage(BaseModel):
    """Base message structure for both save and load operations"""
    step: int  # Current step in the process
    task: Optional[TaskRunStatus] = None  # Current task information
    tasks: Optional[List[TaskRunStatus]] = None  # List of all tasks
    device: str  # Target device name
    runState: TaskStatus  # Current state of the operation
    report: ReportType  # Type of report being sent
    operation: Literal["save", "load"]  # Type of operation
    operation_id: str  # Unique identifier for the operation
    timestamp: float = Field(default_factory=time.time)  # Unix timestamp of the message


class ImageOperationPayload(BaseModel):
    """Top-level payload structure for image operations"""
    message: RunnerMessage 