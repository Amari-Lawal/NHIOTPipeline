from logging import Logger
import os
import socket
import threading
import time
import subprocess
from typing import Optional
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.clients.GithubClient import GitHubClient
from NHIOTSub.config import Envs, Topics
from NHIOTSub.executors.Executor import Executor
from NHIOTSub.handlers.MQTTHandler import MQTTHandler
from NHIOTSub.services.ArtifactService import ArtifactService
from NHIOTSub.models.payloads import OTAStatusPayload, HeartbeatPayload


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
        
        target = f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}"
        local_exec = f"./Executables/{target}/{target}"
        self.current_file_path = local_exec if os.path.exists(local_exec) else None
        self.last_processed_run_id = None
        self.branch_changed = False
        self.device_id = f"{socket.gethostname()}-{Envs.SUBSCRIBER_ARCHITECTURE}"

        # Connect MQTT client & register branch change & revert callbacks
        self.client.connect()
        self.mqtt.set_branch_change_callback(self._on_branch_changed)
        self.mqtt.set_revert_callback(self.trigger_revert_from_mqtt)
        
        # Subscribe exclusively to enterprise command topic
        handler_cb = self.mqtt.handle(lambda: self.current_file_path)
        self.client.subscribe(handler_cb, topic=Topics.COMMAND_TOPIC)

        # Start periodic background heartbeat daemon
        self._start_heartbeat_loop()

    def _start_heartbeat_loop(self) -> None:
        """Launches a background thread publishing Pydantic HeartbeatPayload every 15 seconds."""
        def heartbeat_worker():
            while True:
                try:
                    payload = HeartbeatPayload(
                        device_id=self.device_id,
                        architecture=Envs.SUBSCRIBER_ARCHITECTURE or "unknown",
                        active_branch=Envs.BRANCH or "unknown",
                        active_binary=os.path.basename(self.current_file_path) if self.current_file_path else "none",
                        status="HEALTHY"
                    )
                    self.client.publish(payload.model_dump_json(), topic=Topics.HEARTBEAT_TOPIC)
                except Exception as e:
                    self.logger.debug(f"Heartbeat emission failed: {e}")
                time.sleep(15)

        thread = threading.Thread(target=heartbeat_worker, daemon=True, name="IoT-Heartbeat")
        thread.start()
        self.logger.info(f"Started IoT Device Heartbeat thread (Device: '{self.device_id}', Topic: '{Topics.HEARTBEAT_TOPIC}', Interval: 15s)")

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

    def run_unit_tests(self, binary_path: str, target: str) -> bool:
        """Executes post-pull operational unit tests on the downloaded binary. Returns True if all pass."""
        test_cases = [
            ("add", ["10", "20"], "30"),
            ("minus", ["50", "20"], "30"),
            ("multiply", ["6", "7"], "42"),
        ]

        os.chmod(binary_path, 0o755)
        self.logger.info(f"Running post-pull operational unit tests for binary '{target}'...")
        
        passed_count = 0
        for fn, args, expected in test_cases:
            stdout, stderr = self.executor.run(binary_path, fn, args)
            out_clean = stdout.strip().replace(" ", "")
            if stderr or expected not in out_clean:
                self.logger.warning(f"  [FAIL] Unit Test {fn}({args}) failed! Output: '{stdout.strip()}', Error: '{stderr.strip()}' (Expected: '{expected}')")
                return False
            passed_count += 1
            self.logger.info(f"  [PASS] Unit Test {fn}({args}) -> Output: '{stdout.strip()}'")

        self.logger.info(f"ALL OPERATIONAL UNIT TESTS PASSED ({passed_count}/{len(test_cases)})! Binary '{target}' verified functional.")
        return True

    def trigger_revert_from_mqtt(self) -> Optional[str]:
        """Callback invoked when publisher sends TRIGGER_REVERT MQTT command."""
        self.logger.info("Publisher requested manual GitHub Actions version rollback over MQTT...")
        return self.revert_to_previous_github_build(self.last_processed_run_id or 0, Envs.BRANCH)

    def revert_to_previous_github_build(self, failed_run_id: int, branch: str) -> Optional[str]:
        """Queries GitHub Actions API for previous successful build runs and reverts to the latest working one."""
        self.logger.warning(f"Searching GitHub Actions build history for previous successful build run on branch '{branch}'...")
        recent_runs = self.github.get_recent_successful_runs(limit=5)
        
        target = f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}"

        for prev_run in recent_runs:
            if prev_run.id == failed_run_id:
                continue

            prev_sha = prev_run.head_sha or ""
            self.logger.info(f"Attempting GitHub Version Revert -> Build Run #{prev_run.id} (SHA: {prev_sha[:7] if prev_sha else 'unknown'})...")
            
            artifacts = self.github.get_artifacts(prev_run)
            artifact = self.artifacts.choose(artifacts, target)

            if not artifact:
                continue

            try:
                downloaded_path = self.artifacts.download(artifact)
                if self.run_unit_tests(downloaded_path, target):
                    self.current_file_path = downloaded_path
                    self.last_processed_run_id = prev_run.id
                    self.logger.info(f"AUTOMATED GITHUB REVERT SUCCESSFUL: Reverted to verified GitHub build run #{prev_run.id} (SHA: {prev_sha[:7]})!")
                    self.send_ota_notification(
                        "ROLLBACK",
                        f"Manual/Post-pull revert triggered. Reverted via GitHub Actions build history to previous working build #{prev_run.id} (SHA: {prev_sha[:7]}).",
                        prev_sha
                    )
                    return self.current_file_path
            except Exception as e:
                self.logger.warning(f"Revert attempt on run #{prev_run.id} failed: {e}. Trying next historical build...")

        self.logger.error("CRITICAL: No operational historical build run found in GitHub Actions history.")
        return None

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
                
                # 1. Run post-pull operational unit tests on new binary
                if self.run_unit_tests(downloaded_path, target):
                    self.current_file_path = downloaded_path
                    self.last_processed_run_id = run.id
                    self.send_ota_notification("SUCCESS", f"All unit tests passed for build #{run.id}. Binary operational.", commit_sha)
                    self.logger.info(f"SUCCESS: Subscriber loaded operational artifact '{target}' for branch '{branch}' -> {self.current_file_path}")
                    self.logger.info(f"Subscriber active with run #{run.id} on branch '{branch}'. Monitoring GitHub for next build...")
                    return self.current_file_path
                else:
                    # 2. Unit tests failed -> Revert using GitHub Actions Build History!
                    self.logger.warning(f"Build run #{run.id} failed post-pull unit tests! Triggering GitHub version revert...")
                    reverted_path = self.revert_to_previous_github_build(run.id, branch)
                    if reverted_path:
                        return reverted_path
                    else:
                        self.send_ota_notification("FAILURE", f"Unit tests failed on run #{run.id} and no historical build could be restored.", commit_sha)
                        return self.current_file_path

            except Exception as download_error:
                self.logger.warning(f"Download/Verification failed: {download_error}. Triggering GitHub version revert...")
                reverted_path = self.revert_to_previous_github_build(run.id, branch)
                if reverted_path:
                    return reverted_path
                else:
                    self.send_ota_notification("FAILURE", f"Artifact download/verification failed: {download_error}", commit_sha)
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
        # Check and download initial artifact on startup if not already loaded
        if not self.current_file_path:
            self.logger.info(f"No local binary found on startup. Attempting initial artifact pull for branch '{Envs.BRANCH}'...")
            self.fetch_artifact_for_branch(Envs.BRANCH)

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