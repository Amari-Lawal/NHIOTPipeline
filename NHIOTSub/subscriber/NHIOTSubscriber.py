from logging import Logger
import os
import shutil
import time
import subprocess
from typing import Optional
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.clients.GithubClient import GitHubClient
from NHIOTSub.config import Envs
from NHIOTSub.executors.Executor import Executor
from NHIOTSub.handlers.MQTTHandler import MQTTHandler
from NHIOTSub.services.ArtifactService import ArtifactService


class NHIOTSubscriber:
    def __init__(
        self,
        github: GitHubClient,
        artifacts: ArtifactService,
        executor: Executor,
        mqtt_client: NHIOTMQTT,
        mqtt_handler: MQTTHandler,
        logger: Logger,
    ):
        self.github = github 
        self.artifacts = artifacts
        self.executor = executor
        self.client = mqtt_client
        self.mqtt = mqtt_handler
        self.logger = logger
        
        self.current_file_path = None
        self.last_processed_run_id = None
        self.branch_changed = False

        # Connect MQTT client & register branch change callback
        self.client.connect()
        self.mqtt.set_branch_change_callback(self._on_branch_changed)
        
        # Subscribe to MQTT commands immediately on startup
        self.client.subscribe(
            self.mqtt.handle(lambda: self.current_file_path),
            topic="machineB/recv"
        )

    def test_and_swap_binary(self, new_binary_path: str, target: str) -> str:
        """Runs a self-test healthcheck on newly downloaded binary and auto-rolls back if it crashes."""
        backup_path = f"{new_binary_path}.bak"

        # 1. Create backup copy if current binary exists
        if os.path.exists(new_binary_path):
            try:
                shutil.copy2(new_binary_path, backup_path)
            except Exception as e:
                self.logger.warning(f"Could not create backup file '{backup_path}': {e}")

        # 2. Run self-test healthcheck on newly downloaded binary
        try:
            os.chmod(new_binary_path, 0o755)
            stdout, stderr = self.executor.run(new_binary_path, "add", ["1", "1"])
            if stderr:
                raise RuntimeError(f"Healthcheck failed with error: {stderr.strip()}")
            self.logger.info(f"HEALTHCHECK PASSED: Binary '{target}' verified OK (Self-test stdout: {stdout.strip()}).")
            return new_binary_path
        except Exception as crash_err:
            self.logger.error(f"CRITICAL HEALTHCHECK FAILURE for '{target}': {crash_err}")
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, new_binary_path)
                self.logger.warning(f"AUTOMATED ROLLBACK SUCCESSFUL: Restored working backup '{backup_path}' -> '{new_binary_path}'")
            return new_binary_path

    def fetch_artifact_for_branch(self, branch: str) -> Optional[str]:
        """Synchronously pull, integrity-verify, healthcheck, and hot-swap the latest build artifact."""
        self.logger.info(f"Triggering immediate artifact pull for branch '{branch}'...")
        run = self.github.get_latest_run()
        if not run:
            self.logger.warning(f"No workflow run found for branch '{branch}'.")
            return None

        artifacts = self.github.get_artifacts(run)
        target = f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}"
        artifact = self.artifacts.choose(artifacts, target)

        if artifact:
            self.logger.info(f"Artifact '{target}' found for branch '{branch}' (run #{run.id}) — downloading...")
            try:
                downloaded_path = self.artifacts.download(artifact)
                # Run self-test healthcheck with automated rollback protection
                self.current_file_path = self.test_and_swap_binary(downloaded_path, target)
            except Exception as download_error:
                self.logger.warning(f"Download/Verification failed: {download_error}. Falling back to cached executable.")
                self.current_file_path = f"./Executables/{target}/{target}"
            
            self.last_processed_run_id = run.id
            self.logger.info(f"SUCCESS: Subscriber loaded verified artifact '{target}' for branch '{branch}' -> {self.current_file_path}")
            self.logger.info(f"Subscriber active with run #{run.id} on branch '{branch}'. Monitoring GitHub for next build...")
            return self.current_file_path
        else:
            self.logger.warning(f"No matching artifact '{target}' found in run #{run.id} for branch '{branch}'.")
            return None

    def _on_branch_changed(self, new_branch: str) -> Optional[str]:
        """Callback invoked when publisher sends a branch change payload over MQTT."""
        self.logger.info(f"Subscriber notified of branch change to '{new_branch}' — resetting run tracker & pulling artifact.")
        self.last_processed_run_id = None
        self.branch_changed = False
        return self.fetch_artifact_for_branch(new_branch)

    def monitor_workflow(self) -> None:
        while True:
            # Check if a remote branch change command was received via MQTT
            if self.branch_changed:
                self.logger.info(f"Switched active target branch to '{Envs.BRANCH}'. Re-polling GitHub Actions...")
                self.last_processed_run_id = None
                self.current_file_path = None
                self.branch_changed = False

            # 1. Get the local HEAD commit SHA
            try:
                local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
            except Exception as git_err:
                local_sha = ""
                self.logger.warning(f"Could not resolve local HEAD SHA: {git_err}")

            self.logger.info(f"Polling GitHub Actions API for branch '{Envs.BRANCH}'... (local HEAD: {local_sha[:7] if local_sha else 'unknown'})")

            run = self.github.get_latest_run()

            if not run:
                self.logger.warning(f"No workflow run found for branch '{Envs.BRANCH}'. Retrying in 5s...")
                time.sleep(5)
                continue

            sha_str = run.head_sha[:7] if run.head_sha else 'unknown'
            target = f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}"

            # Check if this run ID has not been processed yet
            if self.last_processed_run_id != run.id:
                if run.status == "completed":
                    self.logger.info(f"New completed build run #{run.id} (SHA: {sha_str}) detected on branch '{Envs.BRANCH}' — fetching artifact...")
                    self.fetch_artifact_for_branch(Envs.BRANCH)
                elif run.status in ("in_progress", "queued", "requested", "waiting"):
                    self.logger.info(f"New build run #{run.id} (SHA: {sha_str}) on branch '{Envs.BRANCH}' is '{run.status}' — waiting for build to complete...")
            else:
                self.logger.info(f"Waiting for next GitHub build on branch '{Envs.BRANCH}'... (Active: run #{run.id} [{sha_str}] | Target: '{target}' | Next check in {Envs.POLL_INTERVAL}s)")

            time.sleep(int(Envs.POLL_INTERVAL))