from NHIOTSub.container import Container
from NHIOTSub.subscriber import NHIOTSubscriber


def main():
    container = Container()

    subscriber = NHIOTSubscriber(
        github=container.github_client(),
        artifacts=container.artifact_service(),
        executor=container.executor(),
        mqtt_client=container.mqtt_client(),
        mqtt_handler=container.mqtt_handler(),
        logger=container.logger.getChild("subscriber"),
    )

    subscriber.monitor_workflow()


if __name__ == "__main__":
    main()
