from datetime import datetime, timezone

from pydantic import BaseModel, Field


class HeartbeatPayload(BaseModel):
    device_id: str
    architecture: str
    active_branch: str
    active_binary: str
    status: str = "HEALTHY"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
