from datetime import datetime, timezone

from pydantic import BaseModel, Field


class UnitTestStatusPayload(BaseModel):
    suite_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    status: str  # "PASSED", "FAILED"
    detail: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
