
from logging import Logger
import time
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.clients.GithubClient import GitHubClient
from NHIOTSub.config import Envs
from NHIOTSub.executors.Executor import Executor
from NHIOTSub.handlers.MQTTHandler import MQTTHandler
from NHIOTSub.services.ArtifactService import ArtifactService


class NHIOTSubscriber:
    def __init__(
        self,
        github : GitHubClient,
        artifacts : ArtifactService,
        executor :Executor,
        mqtt_client : NHIOTMQTT,
        mqtt_handler :MQTTHandler,
        logger : Logger,
    ):
        self.github = github 
        self.artifacts = artifacts
        self.executor = executor
        self.client = mqtt_client
        self.mqtt = mqtt_handler
        self.logger = logger

        self.client.connect()

    def monitor_workflow(self) -> None:
        downloaded = False
        file_path = None

        while True:
            # 1. Get the local HEAD commit SHA
            try:
                import subprocess
                local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
            except Exception as git_err:
                local_sha = ""

            run = self.github.get_latest_run()

            if not run:
                self.logger.warning("No workflow run found")
                time.sleep(5)
                continue

            # 2. Check if the run matches the local SHA, or if this is the initial boot setup
            is_matching_sha = local_sha and (run.head_sha == local_sha or run.head_sha.startswith(local_sha) or local_sha.startswith(run.head_sha))
            is_initial_boot = (file_path is None)

            if run.status == "completed" and not downloaded:
                # We only download if it matches our pushed commit hash OR it is the initial boot
                if is_matching_sha or is_initial_boot:
                    artifacts = self.github.get_artifacts(run)
                    target = f"{Envs.ARTIFACT_NAME}_{Envs.SUBSCRIBER_ARCHITECTURE}"
                    artifact = self.artifacts.choose(artifacts, target)

                    if artifact:
                        try:
                            file_path = self.artifacts.download(artifact)
                        except Exception as download_error:
                            self.logger.warning(f"Could not overwrite remote artifact: {download_error}. Falling back to cached executable.")
                            file_path = f"./Executables/{target}/{target}"

                        self.client.subscribe(
                            self.mqtt.handle(file_path),
                            topic="machineB/recv"
                        )

                        downloaded = True
                        if is_matching_sha:
                            self.logger.info(f"OTA HOT-SWAP SUCCESS: Swapped to new binary for commit {local_sha[:7]}!")
                        else:
                            self.logger.info(f"Daemon initialized with latest GitHub Action artifact run #{run.id}")

            elif run.status == "in_progress":
                # Only reset download flag if this progress run matches our active local commit!
                if is_matching_sha:
                    downloaded = False

            time.sleep(int(Envs.POLL_INTERVAL))