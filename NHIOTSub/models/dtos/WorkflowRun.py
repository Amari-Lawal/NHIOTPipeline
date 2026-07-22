from typing import Optional

from pydantic import BaseModel


class WorkflowRun(BaseModel):
    id: int
    name: str
    head_branch: str
    status: str
    conclusion: Optional[str] = None
    head_sha: str
