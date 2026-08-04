from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class IsolationProtectionPayload(BaseModel):
    device_id: str
    branch: str
    active_binary: str
    function_called: str
    parameters: List[str]
    error_message: str
    status: str = "PROTECTED"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
