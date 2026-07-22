from datetime import datetime, timezone
from pydantic import BaseModel, Field


class OTAStatusPayload(BaseModel):
    device_id: str
    branch: str
    artifact_name: str
    commit_sha: str
    status: str  # "SUCCESS", "ROLLBACK", "FAILURE"
    detail: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
