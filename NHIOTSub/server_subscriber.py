import time
import json
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics
from NHIOTSub.dependencies.create_logger import create_logger
from NHIOTSub.models.payloads import OTAStatusPayload

logger = create_logger("SERVER_AUDIT")


def main():
    logger.info("Initializing Server OTA Audit Subscriber Daemon...")
    client = NHIOTMQTT()
    client.connect()

    def on_ota_status(topic, payload, **kwargs):
        try:
            raw_str = payload.decode("utf-8")
            ota_event = OTAStatusPayload.model_validate_json(raw_str)
            
            status_symbol = "✅" if ota_event.status == "SUCCESS" else "⚠️" if ota_event.status == "ROLLBACK" else "❌"
            
            logger.info(
                f"\n{status_symbol} [OTA STATUS AUDIT EVENT on '{topic}']\n"
                f"   Device ID:  {ota_event.device_id}\n"
                f"   Status:     {ota_event.status}\n"
                f"   Branch:     {ota_event.branch}\n"
                f"   Artifact:   {ota_event.artifact_name}\n"
                f"   Commit SHA: {ota_event.commit_sha[:7]}\n"
                f"   Detail:     {ota_event.detail}\n"
                f"   Timestamp:  {ota_event.timestamp}\n"
            )
        except Exception as e:
            logger.error(f"Failed to parse incoming OTA status payload on '{topic}': {e}")

    logger.info(f"Subscribing to telemetry topic '{Topics.OTA_STATUS_TOPIC}'...")
    client.subscribe(on_ota_status, topic=Topics.OTA_STATUS_TOPIC)

    logger.info("Server OTA Audit Subscriber is running and listening for device events...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping Server OTA Audit Subscriber.")
        client.disconnect()


if __name__ == "__main__":
    main()
