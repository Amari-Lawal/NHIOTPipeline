import time
import json
from typing import Dict
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics
from NHIOTSub.dependencies.create_logger import create_logger
from NHIOTSub.models.payloads import OTAStatusPayload, HeartbeatPayload

logger = create_logger("SERVER_FLEET_AUDIT")

# Fleet Registry: device_id -> {last_seen, branch, arch, binary, status}
fleet_registry: Dict[str, dict] = {}


def main():
    logger.info("Initializing Enterprise Server Fleet Audit Daemon...")
    client = NHIOTMQTT()
    client.connect()

    def on_heartbeat(topic, payload, **kwargs):
        try:
            raw_str = payload.decode("utf-8")
            hb = HeartbeatPayload.model_validate_json(raw_str)
            fleet_registry[hb.device_id] = {
                "last_seen": hb.timestamp,
                "branch": hb.active_branch,
                "arch": hb.architecture,
                "binary": hb.active_binary,
                "status": hb.status
            }
            logger.info(
                f"💓 [HEARTBEAT] Device '{hb.device_id}' | Status: {hb.status} | "
                f"Branch: '{hb.active_branch}' | Arch: '{hb.architecture}' | Active: '{hb.active_binary}' | "
                f"Active Devices in Fleet: {len(fleet_registry)}"
            )
        except Exception as e:
            logger.error(f"Failed to parse Heartbeat on '{topic}': {e}")

    def on_ota_status(topic, payload, **kwargs):
        try:
            raw_str = payload.decode("utf-8")
            ota_event = OTAStatusPayload.model_validate_json(raw_str)
            status_symbol = "✅" if ota_event.status == "SUCCESS" else "⚠️" if ota_event.status == "ROLLBACK" else "❌"
            
            logger.info(
                f"\n{status_symbol} [OTA EVENT] Device '{ota_event.device_id}' | "
                f"Status: {ota_event.status} | Branch: '{ota_event.branch}' | "
                f"SHA: {ota_event.commit_sha[:7]} | Detail: {ota_event.detail}\n"
            )
        except Exception as e:
            logger.error(f"Failed to parse OTA Status on '{topic}': {e}")

    logger.info(f"Subscribing to Heartbeat topic '{Topics.HEARTBEAT_TOPIC}'...")
    client.subscribe(on_heartbeat, topic=Topics.HEARTBEAT_TOPIC)

    logger.info(f"Subscribing to OTA Telemetry topic '{Topics.OTA_STATUS_TOPIC}'...")
    client.subscribe(on_ota_status, topic=Topics.OTA_STATUS_TOPIC)

    logger.info("Server Fleet Audit Daemon is running and tracking IoT fleet devices...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping Server Fleet Audit Daemon.")
        client.disconnect()


if __name__ == "__main__":
    main()
