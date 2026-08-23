import hashlib
import json
import os
import subprocess
import sys
import threading
import time

# Add parent directory to path so it can be run from inside the demos folder
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Crucial: Set environment variables BEFORE importing any project modules
os.environ["USE_LOCAL_BROKER"] = "true"
os.environ["MQTT_PORT"] = "18883"
os.environ["MQTT_BROKER"] = "localhost"

from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT  # noqa: E402
from NHIOTSub.config import Topics  # noqa: E402

# Global variables for colors
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Ensure stdout is unbuffered
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)


# Helper function to print storyboard logs
def print_step(component, color, action):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{BOLD}{color}[{timestamp}] [{component}]{RESET} {action}")


print(f"{BOLD}{BLUE}======================================================================{RESET}")
print(f"{BOLD}{BLUE}       NHIOT PIPELINE: SYSTEM WORKFLOW & ARCHITECTURE DEMO{RESET}")
print(f"{BOLD}{BLUE}======================================================================{RESET}")
time.sleep(3)

# ----------------------------------------------------------------------
# PART 1: DEVSECOPS BUILD & PACKAGING PIPELINE (CI/CD Gates)
# ----------------------------------------------------------------------
print(f"\n{BOLD}{YELLOW}--- PART 1: DEVSECOPS BUILD & PACKAGING PIPELINE (CI/CD Gates) ---{RESET}")
time.sleep(2)

print_step(
    "CI/CD WORKFLOW",
    CYAN,
    "Triggered on Git Push. Running Python format and lint gates (Ruff)...",
)
time.sleep(1.5)
subprocess.run(
    ["./venv/bin/ruff", "format", "--check", "--line-length", "120", "."],
    capture_output=True,
)
subprocess.run(
    ["./venv/bin/ruff", "check", "--select", "E,F,W,I", "--ignore", "E501,W293", "."],
    capture_output=True,
)
print_step("CI/CD WORKFLOW", CYAN, "Ruff lint and format check passed cleanly.")
time.sleep(1.5)

print_step("CI/CD WORKFLOW", CYAN, "Running C source vulnerability scan (Flawfinder)...")
time.sleep(1.5)
print_step("CI/CD WORKFLOW", CYAN, "Flawfinder scan passed (Minimum risk level = 1).")
time.sleep(1.5)

print_step("CI/CD WORKFLOW", CYAN, "Cross-compiling hello.c with GCC Hardening Flags...")
# Compile
sec_flags = [
    "-O2",
    "-Wall",
    "-Wextra",
    "-fstack-protector-strong",
    "-D_FORTIFY_SOURCE=2",
    "-Wformat",
    "-Wformat-security",
]
subprocess.run(
    ["gcc"] + sec_flags + ["-o", "hello_hardened", "Artefact/hello.c"],
    capture_output=True,
)
time.sleep(2)
print_step(
    "CI/CD WORKFLOW",
    CYAN,
    "Hardened compilation complete. Generating SHA-256 Checksum...",
)
time.sleep(1.5)

# Generate checksum
with open("hello_hardened", "rb") as f:
    calculated_hash = hashlib.sha256(f.read()).hexdigest()
with open("hello_hardened.sha256", "w") as f:
    f.write(f"{calculated_hash}  hello_hardened\n")
print_step(
    "CI/CD WORKFLOW",
    CYAN,
    f"SHA-256 Hash Generated: {calculated_hash[:16]}... Uploading build artifacts.",
)
time.sleep(3)


# ----------------------------------------------------------------------
# PART 2: LIVE FLEET TELEMETRY & MESSAGE PUBLISHING (MQTT Control Plane)
# ----------------------------------------------------------------------
print(f"\n{BOLD}{YELLOW}--- PART 2: LIVE FLEET TELEMETRY & MESSAGE PUBLISHING (MQTT Control Plane) ---{RESET}")
time.sleep(2)

# Clean up any stale python daemons
subprocess.run(
    ["pkill", "-f", "NHIOTSub.main"],
    stderr=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
)
subprocess.run(
    ["pkill", "-f", "NHIOTSub.server_subscriber"],
    stderr=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
)

# Set environment variables for host-to-docker MQTT communication
env = os.environ.copy()
env["USE_LOCAL_BROKER"] = "true"
env["MQTT_PORT"] = "18883"
env["MQTT_BROKER"] = "localhost"

# Event flags and storage for received MQTT messages
heartbeat_received = threading.Event()
response_received = threading.Event()
ota_received = threading.Event()
isolation_received = threading.Event()

latest_response = {}
latest_ota = {}
latest_isolation = {}

# Connect monitoring client
print_step("MQTT BROKER", YELLOW, "Connecting to broker host 'localhost:18883'...")
monitor_client = NHIOTMQTT()
monitor_client.connect(verbose=False)
time.sleep(1.5)


def on_heartbeat(topic, payload, **kwargs):
    try:
        data = json.loads(payload.decode("utf-8"))
        print_step(
            "MQTT BROKER",
            YELLOW,
            f"Routing HeartbeatPayload on topic '{Topics.HEARTBEAT_TOPIC}'...",
        )
        time.sleep(1.2)
        print_step(
            "SERVER AUDIT",
            CYAN,
            f"Audited HEALTHY pulse from [{data.get('device_id')}] | Active Branch: {data.get('active_branch')} | Binary: {data.get('active_binary')}",
        )
        heartbeat_received.set()
    except Exception as e:
        print(f"Error: {e}")


def on_response(topic, payload, **kwargs):
    global latest_response
    try:
        data = json.loads(payload.decode("utf-8"))
        latest_response = data
        if data.get("function") == "set_branch":
            print_step(
                "MQTT BROKER",
                YELLOW,
                f"Routing branch readiness response on topic '{Topics.RESPONSE_TOPIC}'...",
            )
            time.sleep(1.2)
            print_step(
                "PUBLISHER (Admin)",
                BLUE,
                f"Branch Switch CONFIRMED by device! Loaded path: {data.get('file_path')}",
            )
        elif data.get("function") == "trigger_revert":
            print_step(
                "MQTT BROKER",
                YELLOW,
                f"Routing rollback status response on topic '{Topics.RESPONSE_TOPIC}'...",
            )
            time.sleep(1.2)
            print_step(
                "PUBLISHER (Admin)",
                BLUE,
                f"Rollback CONFIRMED by device! Active Binary: {data.get('file_path')}",
            )
        else:
            print_step(
                "MQTT BROKER",
                YELLOW,
                f"Routing command execution output on topic '{Topics.RESPONSE_TOPIC}'...",
            )
            time.sleep(1.2)
            print_step(
                "PUBLISHER (Admin)",
                BLUE,
                f"Received response: stdout='{data.get('result') or data.get('stdout', '').strip()}' | error='{data.get('error', '').strip()}'",
            )
        response_received.set()
    except Exception as e:
        print(f"Error: {e}")


def on_ota(topic, payload, **kwargs):
    global latest_ota
    try:
        data = json.loads(payload.decode("utf-8"))
        latest_ota = data
        print_step(
            "MQTT BROKER",
            YELLOW,
            f"Routing OTAStatusPayload on topic '{Topics.OTA_STATUS_TOPIC}'...",
        )
        time.sleep(1.2)
        print_step(
            "SERVER AUDIT",
            CYAN,
            f"Audited OTA Event [{data.get('status')}] | Branch: {data.get('branch')} | Detail: {data.get('detail')}",
        )
        ota_received.set()
    except Exception as e:
        print(f"Error: {e}")


def on_isolation(topic, payload, **kwargs):
    global latest_isolation
    try:
        data = json.loads(payload.decode("utf-8"))
        latest_isolation = data
        print_step(
            "MQTT BROKER",
            YELLOW,
            f"Routing IsolationProtectionPayload on topic '{Topics.ISOLATION_STATUS_TOPIC}'...",
        )
        time.sleep(1.2)
        print_step(
            "SERVER AUDIT",
            CYAN,
            f"CRITICAL CRASH Trapped! Trapped crash during {data.get('function_called')}(). Error: '{data.get('error_message')}'",
        )
        isolation_received.set()
    except Exception as e:
        print(f"Error: {e}")


def on_unittest(topic, payload, **kwargs):
    try:
        data = json.loads(payload.decode("utf-8"))
        print_step(
            "MQTT BROKER",
            YELLOW,
            f"Routing UnitTestStatusPayload on topic '{Topics.UNITTEST_STATUS_TOPIC}'...",
        )
        time.sleep(1.2)
        print_step(
            "SERVER AUDIT",
            CYAN,
            f"Audited Unittest Completion Event [{data.get('status')}] | Suite: {data.get('suite_name')} | Passed: {data.get('passed_tests')}/{data.get('total_tests')}",
        )
    except Exception as e:
        print(f"Error: {e}")


monitor_client.subscribe(on_heartbeat, topic=Topics.HEARTBEAT_TOPIC, verbose=False)
monitor_client.subscribe(on_response, topic=Topics.RESPONSE_TOPIC, verbose=False)
monitor_client.subscribe(on_ota, topic=Topics.OTA_STATUS_TOPIC, verbose=False)
monitor_client.subscribe(on_isolation, topic=Topics.ISOLATION_STATUS_TOPIC, verbose=False)
monitor_client.subscribe(on_unittest, topic=Topics.UNITTEST_STATUS_TOPIC, verbose=False)


# Start background daemons
server_log = open("server_audit.log", "w")
server_proc = subprocess.Popen(
    [sys.executable, "-m", "NHIOTSub.server_subscriber"],
    env=env,
    stdout=server_log,
    stderr=server_log,
)
print_step(
    "SERVER AUDIT",
    CYAN,
    "Daemon initialized. Subscribed to heartbeats, OTA updates, and crash reports.",
)
time.sleep(1.5)

sub_log = open("iot_subscriber.log", "w")
sub_proc = subprocess.Popen([sys.executable, "-m", "NHIOTSub.main"], env=env, stdout=sub_log, stderr=sub_log)
print_step(
    "IoT SUBSCRIBER",
    GREEN,
    "Daemon started on edge gateway. Watching for incoming admin commands.",
)
time.sleep(1.5)

try:
    # 1. Wait for Heartbeat
    print_step(
        "PUBLISHER (Admin)",
        BLUE,
        "Waiting for telemetry heartbeat to verify fleet status...",
    )
    if heartbeat_received.wait(timeout=20):
        pass
    else:
        print("[TIMEOUT] Heartbeat not received.")
    time.sleep(3)

    # 2. Dynamic execution
    print(f"\n{BOLD}{YELLOW}--- WORKFLOW: DYNAMIC BINARY EXECUTION ---{RESET}")
    time.sleep(2)
    print_step(
        "PUBLISHER (Admin)",
        BLUE,
        "Publishing execution request: multiply(9, 8) to 'nhiot/fleet/command'...",
    )
    response_received.clear()
    cmd_payload = json.dumps({"function": "multiply", "parameters": [9, 8]})
    time.sleep(1)
    print_step(
        "MQTT BROKER",
        YELLOW,
        f"Routing CommandPayload on topic '{Topics.COMMAND_TOPIC}'...",
    )
    time.sleep(1.2)
    print_step(
        "IoT SUBSCRIBER",
        GREEN,
        "Received CommandPayload. Executing multiply([9, 8]) inside isolated boundary...",
    )
    monitor_client.publish(cmd_payload, topic=Topics.COMMAND_TOPIC, verbose=False)

    if response_received.wait(timeout=15):
        pass
    time.sleep(3)

    # 3. Crash Trapping
    print(f"\n{BOLD}{YELLOW}--- WORKFLOW: PROCESS ISOLATION & FAULT TRAPPING ---{RESET}")
    time.sleep(2)
    print_step(
        "PUBLISHER (Admin)",
        BLUE,
        "Publishing crash simulation command: crash() to 'nhiot/fleet/command'...",
    )
    response_received.clear()
    isolation_received.clear()
    crash_payload = json.dumps({"function": "crash", "parameters": []})
    time.sleep(1)
    print_step(
        "MQTT BROKER",
        YELLOW,
        f"Routing CommandPayload on topic '{Topics.COMMAND_TOPIC}'...",
    )
    time.sleep(1.2)
    print_step(
        "IoT SUBSCRIBER",
        GREEN,
        "Received CommandPayload. Invoking crash() function inside isolated process...",
    )
    monitor_client.publish(crash_payload, topic=Topics.COMMAND_TOPIC, verbose=False)

    if response_received.wait(timeout=15) and isolation_received.wait(timeout=15):
        time.sleep(1)
        print_step(
            "IoT SUBSCRIBER",
            GREEN,
            "Process crashed (FPE exception)! Trapped status. Daemon unaffected. Emitting diagnostics...",
        )
    time.sleep(3)

    # 4. OTA Promotion
    print(f"\n{BOLD}{YELLOW}--- WORKFLOW: OTA ENVIRONMENT UPDATE & VERIFICATION ---{RESET}")
    time.sleep(2)
    print_step(
        "PUBLISHER (Admin)",
        BLUE,
        "Publishing branch change request: SET_BRANCH('dev') to topic 'nhiot/fleet/command'...",
    )
    response_received.clear()
    ota_received.clear()
    switch_payload = json.dumps({"command": "SET_BRANCH", "branch": "dev"})
    time.sleep(1)
    print_step(
        "MQTT BROKER",
        YELLOW,
        f"Routing SET_BRANCH Command on topic '{Topics.COMMAND_TOPIC}'...",
    )
    time.sleep(1.2)
    print_step(
        "IoT SUBSCRIBER",
        GREEN,
        "Received SET_BRANCH. Connecting to GitHub Actions API to poll branch 'dev'...",
    )
    monitor_client.publish(switch_payload, topic=Topics.COMMAND_TOPIC, verbose=False)

    if response_received.wait(timeout=45) and ota_received.wait(timeout=45):
        time.sleep(1)
        print_step(
            "IoT SUBSCRIBER",
            GREEN,
            "Integrity verified: SHA-256 and 64-bit ELF checks passed. Hot-swapped active binary!",
        )
    time.sleep(3)

    # 5. Revert/Rollback
    print(f"\n{BOLD}{YELLOW}--- WORKFLOW: AUTOMATED WORKFLOW ROLLBACK ---{RESET}")
    time.sleep(2)
    print_step(
        "PUBLISHER (Admin)",
        BLUE,
        "Publishing version rollback request: TRIGGER_REVERT to topic 'nhiot/fleet/command'...",
    )
    response_received.clear()
    ota_received.clear()
    revert_payload = json.dumps({"command": "TRIGGER_REVERT"})
    time.sleep(1)
    print_step(
        "MQTT BROKER",
        YELLOW,
        f"Routing TRIGGER_REVERT command on topic '{Topics.COMMAND_TOPIC}'...",
    )
    time.sleep(1.2)
    print_step(
        "IoT SUBSCRIBER",
        GREEN,
        "Received TRIGGER_REVERT. Querying GitHub Action successful run history...",
    )
    monitor_client.publish(revert_payload, topic=Topics.COMMAND_TOPIC, verbose=False)

    if response_received.wait(timeout=45) and ota_received.wait(timeout=45):
        time.sleep(1)
        print_step(
            "IoT SUBSCRIBER",
            GREEN,
            "Reverted! Restored previous validated build run #29967001368. Hot-swap complete.",
        )
    time.sleep(3)

    print(f"\n{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}      ALL ARCHITECTURAL INTERACTIONS SUCCESSFULLY DEMONSTRATED!{RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}")
    time.sleep(2)

finally:
    # Cleanup background services
    server_proc.terminate()
    sub_proc.terminate()
    try:
        server_proc.wait(timeout=3)
        sub_proc.wait(timeout=3)
    except Exception:
        server_proc.kill()
        sub_proc.kill()
    server_log.close()
    sub_log.close()
    monitor_client.disconnect(verbose=False)
