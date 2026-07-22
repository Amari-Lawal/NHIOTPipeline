from typing import Any, List

from pydantic import BaseModel


class CommandPayload(BaseModel):
    function: str
    parameters: List[Any] = []
