from typing import List

from pydantic import BaseModel

from NHIOTSub.models.dtos import WorkflowRun


class WorkflowRunsResponse(BaseModel):
    workflow_runs: List[WorkflowRun]
