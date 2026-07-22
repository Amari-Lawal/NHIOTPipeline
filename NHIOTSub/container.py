from NHIOTMQTT import NHIOTMQTT
from NHIOTSub.clients.GithubClient import GitHubClient
from NHIOTSub.dependencies import create_logger
from NHIOTSub.executors import Executor
from NHIOTSub.handlers import MQTTHandler
from NHIOTSub.services.ArtifactService import ArtifactService


class Container:
    def __init__(self):
        self.logger = create_logger("NHIOT")
        self._mqtt_client = None

    def mqtt_client(self):
        if self._mqtt_client is None:
            self._mqtt_client = NHIOTMQTT(self.logger)
        return self._mqtt_client

    def mqtt_handler(self):
        return MQTTHandler(self.mqtt_client(), self.executor(), self.logger)

    def github_client(self):
        return GitHubClient()

    def executor(self):
        return Executor()

    def artifact_service(self):
        return ArtifactService(self.logger)
