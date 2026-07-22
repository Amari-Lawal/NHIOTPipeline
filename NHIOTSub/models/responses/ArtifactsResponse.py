from typing import List

from pydantic import BaseModel

from NHIOTSub.models.dtos import Artifact


class ArtifactsResponse(BaseModel):
    artifacts: List[Artifact]
