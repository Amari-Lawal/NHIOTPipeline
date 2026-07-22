class Topics:
    COMMAND_TOPIC = "nhiot/fleet/command"
    RESPONSE_TOPIC = "nhiot/fleet/response"
    OTA_STATUS_TOPIC = "nhiot/ota/status"
    
    # Legacy topic aliases for backward compatibility
    LEGACY_COMMAND_TOPIC = "machineB/recv"
    LEGACY_RESPONSE_TOPIC = "machineA/recv"
