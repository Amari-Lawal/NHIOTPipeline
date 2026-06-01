from typing import List, Optional
import logging

import requests

from NHIOTSub.config import Envs
from NHIOTSub.models.dtos import Artifact, WorkflowRun
from NHIOTSub.models.responses import ArtifactsResponse, WorkflowRunsResponse
from NHIOTSub.config import Config

logger = logging.getLogger("NHIOT")


class GitHubClient:
    def __init__(self):
        self.workflow_url = (
            f"{Config.BASE_URL}"
            f"{Envs.OWNER}/{Envs.REPO}"
            f"/actions/workflows/{Envs.WORKFLOW_ID}/runs"
        )

    def _safe_get(self, url: str, params: dict = None) -> Optional[requests.Response]:
        """Make a GET request, returning None gracefully on rate-limit or auth errors."""
        response = requests.get(url, headers=Config.GITHUB_HEADERS, params=params or {})
        if response.status_code in (403, 429):
            # Check if this is a rate limit (not a permissions issue)
            body = response.json()
            msg = body.get("message", "")
            if "rate limit" in msg.lower():
                reset_ts = response.headers.get("X-RateLimit-Reset", "unknown")
                logger.warning(f"GitHub API rate limit hit — backing off. Reset at epoch: {reset_ts}")
            else:
                logger.warning(f"GitHub API returned {response.status_code}: {msg}")
            return None
        response.raise_for_status()
        return response

    def get_latest_run(self) -> Optional[WorkflowRun]:
        response = self._safe_get(self.workflow_url, params={"per_page": 1})
        if response is None:
            return None
        data = WorkflowRunsResponse(**response.json())
        return data.workflow_runs[0] if data.workflow_runs else None

    def get_artifacts(self, run: WorkflowRun) -> List[Artifact]:
        artifact_url = (
            f"{Config.BASE_URL}"
            f"{Envs.OWNER}/{Envs.REPO}"
            f"/actions/runs/{run.id}/artifacts"
        )
        response = self._safe_get(artifact_url)
        if response is None:
            return []
        return ArtifactsResponse(**response.json()).artifacts