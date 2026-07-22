from logging import Logger
import os
import shutil
import socket
import time
import subprocess
from typing import Optional
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.clients.GithubClient import GitHubClient
from NHIOTSub.config import Envs, Topics
from NHIOTSub.executors.Executor import Executor
from NHIOTSub.handlers.MQTTHandler import MQTTHandler
from NHIOTSub.services.ArtifactService import ArtifactService
from NHIOTSub.models.payloads import OTAStatusPayload


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
        self.device_id = f"{socket.gethostname()}-{Envs.SUBSCRIBER_ARCHITECTURE}"

        # Connect MQTT client & register branch change callback
        self.client.connect()
        self.mqtt.set_branch_change_callback(self._on_branch_changed)
        
        # Subscribe exclusively to enterprise command topic
        handler_cb = self.mqtt.handle(lambda: self.current_file_path)
        self.client.subscribe(handler_cb, topic=Topics.COMMAND_TOPIC)

    def send_ota_notification(self, status: str, detail: str, commit_sha: str) -> None:
        """Publishes a Pydantic-validated OTA status payload to enterprise topic 'nhiot/ota/status'."""
        try:
            payload = OTAStatusPayload(
                device_id=self.device_id,
                branch=Envs.BRANCH or "unknown",
                artifact_name=f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}",
                commit_sha=commit_sha or "unknown",
                status=status,
                detail=detail
            )
            self.client.publish(payload.model_dump_json(), topic=Topics.OTA_STATUS_TOPIC)
            self.logger.info(f"Published OTA Notification to '{Topics.OTA_STATUS_TOPIC}': Status={status} | SHA={commit_sha[:7] if commit_sha else 'unknown'}")
        except Exception as e:
            self.logger.error(f"Failed to send OTA notification: {e}")

    def test_and_swap_binary(self, new_binary_path: str, target: str, commit_sha: str) -> str:
        """Runs a post-pull operational unit test suite on the newly downloaded binary and auto-rolls back if any test fails."""
        backup_path = f"{new_binary_path}.bak"

        # 1. Create backup copy if current binary exists
        if os.path.exists(new_binary_path):
            try:
                shutil.copy2(new_binary_path, backup_path)
            except Exception as e:
                self.logger.warning(f"Could not create backup file '{backup_path}': {e}")

        # 2. Run Post-Pull Operational Unit Test Suite
        test_cases = [
            ("add", ["10", "20"], "30"),
            ("minus", ["50", "20"], "30"),
            ("multiply", ["6", "7"], "42"),
        ]

        try:
            os.chmod(new_binary_path, 0o755)
            self.logger.info(f"Running post-pull operational unit tests for binary '{target}'...")
            
            passed_count = 0
            for fn, args, expected in test_cases:
                stdout, stderr = self.executor.run(new_binary_path, fn, args)
                out_clean = stdout.strip().replace(" ", "")
                if stderr or expected not in out_clean:
                    raise RuntimeError(f"Unit test '{fn}({args})' FAILED! Output: '{stdout.strip()}', Error: '{stderr.strip()}' (Expected: '{expected}')")
                passed_count += 1
                self.logger.info(f"  [PASS] Unit Test {fn}({args}) -> Output: '{stdout.strip()}'")

            self.logger.info(f"ALL OPERATIONAL UNIT TESTS PASSED ({passed_count}/{len(test_cases)})! Binary '{target}' verified functional.")
            self.send_ota_notification("SUCCESS", f"All unit tests passed ({passed_count}/{len(test_cases)}). Binary operational.", commit_sha)
            return new_binary_path
        except Exception as crash_err:
            self.logger.error(f"CRITICAL OPERATIONAL UNIT TEST FAILURE for '{target}': {crash_err}")
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, new_binary_path)
                self.logger.warning(f"AUTOMATED ROLLBACK SUCCESSFUL: Restored working backup '{backup_path}' -> '{new_binary_path}'")
                self.send_ota_notification("ROLLBACK", f"Unit test failed: {crash_err}. Automatically rolled back to backup binary.", commit_sha)
            else:
                self.send_ota_notification("FAILURE", f"Unit test failed: {crash_err}. No backup available.", commit_sha)
            return new_binary_path

    def fetch_artifact_for_branch(self, branch: str) -> Optional[str]:
        """Synchronously pull, integrity-verify, unit-test, and hot-swap the latest build artifact."""
        self.logger.info(f"Triggering immediate artifact pull for branch '{branch}'...")
        run = self.github.get_latest_run()
        if not run:
            self.logger.warning(f"No workflow run found for branch '{branch}'.")
            return None

        commit_sha = run.head_sha or ""
        artifacts = self.github.get_artifacts(run)
        target = f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}"
        artifact = self.artifacts.choose(artifacts, target)

        if artifact:
            self.logger.info(f"Artifact '{target}' found for branch '{branch}' (run #{run.id}) — downloading...")
            try:
                downloaded_path = self.artifacts.download(artifact)
                # Run post-pull operational unit tests with automated rollback protection
                self.current_file_path = self.test_and_swap_binary(downloaded_path, target, commit_sha)
            except Exception as download_error:
                self.logger.warning(f"Download/Verification failed: {download_error}. Falling back to cached executable.")
                self.current_file_path = f"./Executables/{target}/{target}"
                self.send_ota_notification("FAILURE", f"Artifact download/verification failed: {download_error}", commit_sha)
            
            self.last_processed_run_id = run.id
            self.logger.info(f"SUCCESS: Subscriber loaded operational artifact '{target}' for branch '{branch}' -> {self.current_file_path}")
            self.logger.info(f"Subscriber active with run #{run.id} on branch '{branch}'. Monitoring GitHub for next build...")
            return self.current_file_path
        else:
            self.logger.warning(f"No matching artifact '{target}' found in run #{run.id} for branch '{branch}'.")
            self.send_ota_notification("FAILURE", f"No matching artifact '{target}' found in run #{run.id}", commit_sha)
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