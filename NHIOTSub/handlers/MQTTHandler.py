import json
import os
import socket
from logging import Logger
from typing import Callable, Union

from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Envs, Topics
from NHIOTSub.executors.Executor import Executor
from NHIOTSub.models.payloads import CommandPayload, IsolationProtectionPayload
from NHIOTSub.models.responses import CommandResponse


class MQTTHandler:
    def __init__(self, client: NHIOTMQTT, executor: Executor, logger: Logger):
        self.client = client
        self.executor = executor
        self.logger = logger
        self.branch_change_callback: Callable[[str], None] = None
        self.revert_callback: Callable[[], str] = None

    def set_branch_change_callback(self, callback: Callable[[str], None]) -> None:
        self.branch_change_callback = callback

    def set_revert_callback(self, callback: Callable[[], str]) -> None:
        self.revert_callback = callback

    def _publish_response(self, payload_str: str) -> None:
        """Publishes response exclusively to enterprise response topic."""
        self.client.publish(payload_str, topic=Topics.RESPONSE_TOPIC)

    def _publish_isolation_event(self, current_file_path: str, function_name: str, parameters: list, error_msg: str) -> None:
        """Publishes a Pydantic-validated isolation protection payload to 'nhiot/isolation/status'."""
        try:
            device_id = f"{socket.gethostname()}-{Envs.SUBSCRIBER_ARCHITECTURE}"
            event = IsolationProtectionPayload(
                device_id=device_id,
                branch=Envs.BRANCH or "unknown",
                active_binary=os.path.basename(current_file_path) if current_file_path else "unknown",
                function_called=function_name,
                parameters=parameters,
                error_message=error_msg.strip(),
                status="PROTECTED"
            )
            self.client.publish(event.model_dump_json(), topic=Topics.ISOLATION_STATUS_TOPIC)
            self.logger.info(f"Published Isolation Protection Event to '{Topics.ISOLATION_STATUS_TOPIC}': Device protected from '{function_name}' crash.")
        except Exception as e:
            self.logger.error(f"Failed to publish isolation protection event: {e}")

    def handle(self, get_file_path: Union[str, Callable[[], str]]) -> Callable:
        def on_message(topic, payload, **kwargs):
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to decode MQTT JSON payload on topic '{topic}': {e}")
                return

            # 1. Branch Switch Command
            if isinstance(data, dict) and data.get("command") == "SET_BRANCH":
                target_branch = data.get("branch")
                if target_branch:
                    self.logger.info(f"RECEIVED MQTT BRANCH SWITCH COMMAND -> Target Branch: '{target_branch}'")
                    Envs.BRANCH = target_branch

                    fetched_path = None
                    if callable(self.branch_change_callback):
                        fetched_path = self.branch_change_callback(target_branch)

                    res_data = {
                        "function": "set_branch",
                        "result": "READY",
                        "branch": Envs.BRANCH,
                        "file_path": fetched_path or "",
                        "error": ""
                    }
                    self._publish_response(json.dumps(res_data))
                    return

            # 2. Revert / Rollback Command over MQTT
            if isinstance(data, dict) and data.get("command") == "TRIGGER_REVERT":
                self.logger.info("RECEIVED MQTT REVERT COMMAND -> Triggering GitHub Actions Version History Revert...")
                reverted_path = None
                if callable(self.revert_callback):
                    reverted_path = self.revert_callback()

                res_data = {
                    "function": "trigger_revert",
                    "result": "REVERTED" if reverted_path else "FAILED",
                    "branch": Envs.BRANCH,
                    "file_path": reverted_path or "",
                    "error": "" if reverted_path else "No historical build could be reverted."
                }
                self._publish_response(json.dumps(res_data))
                return

            # 3. Target Binary Execution Command
            try:
                cmd = CommandPayload.model_validate(data)
            except Exception as e:
                self.logger.error(f"Invalid command payload format: {e}")
                return

            current_file_path = get_file_path() if callable(get_file_path) else get_file_path

            if not current_file_path:
                self.logger.warning(f"Received function command '{cmd.function}', but no target binary has been downloaded yet for branch '{Envs.BRANCH}'.")
                response = CommandResponse.from_stdout(stdout="", stderr=f"No binary available yet for branch '{Envs.BRANCH}'")
                self._publish_response(response.model_dump_json())
                return

            self.logger.info(f"Executing dynamic target binary: {cmd.function}({cmd.parameters})")

            stdout, stderr = self.executor.run(
                current_file_path,
                cmd.function,
                cmd.parameters
            )

            if stderr:
                self.logger.error(f"Isolated process exited with crash standard error:\n{stderr.strip()}")
                self._publish_isolation_event(current_file_path, cmd.function, cmd.parameters, stderr)
            else:
                self.logger.info(f"Isolated process execution completed successfully. stdout: {stdout.strip()}")

            response = CommandResponse.from_stdout(stdout=stdout, stderr=stderr)
            self._publish_response(response.model_dump_json())

        return on_message