import time
import json
from typing import Dict
from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics
from NHIOTSub.dependencies.create_logger import create_logger
from NHIOTSub.models.payloads import OTAStatusPayload, HeartbeatPayload, IsolationProtectionPayload

logger = create_logger("SERVER_FLEET_AUDIT")

fleet_registry: Dict[str, dict] = {}


def main():
    logger.info("Initializing Server Fleet Audit Daemon...")
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
                f"[HEARTBEAT] Device: {hb.device_id} | Status: {hb.status} | "
                f"Branch: {hb.active_branch} | Arch: {hb.architecture} | Active: {hb.active_binary} | "
                f"Fleet Count: {len(fleet_registry)}"
            )
        except Exception as e:
            logger.error(f"Failed to parse Heartbeat on topic '{topic}': {e}")

    def on_ota_status(topic, payload, **kwargs):
        try:
            raw_str = payload.decode("utf-8")
            ota_event = OTAStatusPayload.model_validate_json(raw_str)
            
            logger.info(
                f"\n[OTA EVENT: {topic}]\n"
                f"   Device ID:  {ota_event.device_id}\n"
                f"   Status:     {ota_event.status}\n"
                f"   Branch:     {ota_event.branch}\n"
                f"   Artifact:   {ota_event.artifact_name}\n"
                f"   Commit SHA: {ota_event.commit_sha[:7]}\n"
                f"   Detail:     {ota_event.detail}\n"
                f"   Timestamp:  {ota_event.timestamp}\n"
            )
        except Exception as e:
            logger.error(f"Failed to parse OTA Status on topic '{topic}': {e}")

    def on_isolation_status(topic, payload, **kwargs):
        try:
            raw_str = payload.decode("utf-8")
            iso_evt = IsolationProtectionPayload.model_validate_json(raw_str)
            
            logger.info(
                f"\n[ISOLATION EVENT: {topic}]\n"
                f"   Device ID:        {iso_evt.device_id}\n"
                f"   Protection Status: {iso_evt.status}\n"
                f"   Function Called:  {iso_evt.function_called}({iso_evt.parameters})\n"
                f"   Active Binary:    {iso_evt.active_binary}\n"
                f"   Branch:           {iso_evt.branch}\n"
                f"   Trapped Error:    {iso_evt.error_message}\n"
                f"   Timestamp:        {iso_evt.timestamp}\n"
            )
        except Exception as e:
            logger.error(f"Failed to parse Isolation Event on topic '{topic}': {e}")

    logger.info(f"Subscribing to Heartbeat topic '{Topics.HEARTBEAT_TOPIC}'...")
    client.subscribe(on_heartbeat, topic=Topics.HEARTBEAT_TOPIC)

    logger.info(f"Subscribing to OTA Status topic '{Topics.OTA_STATUS_TOPIC}'...")
    client.subscribe(on_ota_status, topic=Topics.OTA_STATUS_TOPIC)

    logger.info(f"Subscribing to Isolation Status topic '{Topics.ISOLATION_STATUS_TOPIC}'...")
    client.subscribe(on_isolation_status, topic=Topics.ISOLATION_STATUS_TOPIC)

    logger.info("Server Fleet Audit Daemon active.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping Server Fleet Audit Daemon.")
        client.disconnect()


if __name__ == "__main__":
    main()
