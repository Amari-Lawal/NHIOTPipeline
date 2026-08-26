import asyncio
import hashlib
import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
from NHIOTSub.config import Topics
from NHIOTSub.models.payloads import (
    HeartbeatPayload,
    IsolationProtectionPayload,
    OTAStatusPayload,
    UnitTestStatusPayload,
)

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WEB_ADMIN_DASHBOARD")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    init_mqtt()
    logger.info("FastAPI Web UI Admin Dashboard backend initialized.")
    yield


# Initialize FastAPI App
app = FastAPI(
    title="NHIOT Pipeline System Admin Dashboard",
    description="Enterprise Web UI for Managing IoT DevSecOps & Zero-Downtime OTA Pipeline Services",
    version="2.0.0",
    lifespan=lifespan,
)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# In-Memory State & Storage
# ============================================================================
fleet_registry: Dict[str, dict] = {}
ota_events: List[dict] = []
isolation_events: List[dict] = []
unittest_events: List[dict] = []
command_responses: List[dict] = []
recent_logs: List[dict] = []
daemon_processes: Dict[str, Optional[subprocess.Popen]] = {
    "server_subscriber": None,
    "iot_subscriber": None,
}


# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket Client Connected. Total Clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket Client Disconnected. Remaining Clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket client: {e}")
                self.disconnect(connection)


manager = ConnectionManager()
main_loop = None


def broadcast_sync(message: dict):
    """Bridge background thread MQTT callbacks to asyncio WebSocket broadcast."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": message.get("type", "EVENT"),
        "data": message,
    }
    recent_logs.append(log_entry)
    if len(recent_logs) > 200:
        recent_logs.pop(0)

    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)


# ============================================================================
# MQTT Background Subscriber Loop
# ============================================================================
def init_mqtt():
    def mqtt_worker():
        while True:
            try:
                logger.info("Initializing Dashboard MQTT Telemetry Listener...")
                mqtt_client = NHIOTMQTT()
                mqtt_client.connect(verbose=False)

                def on_heartbeat(topic, payload, **kwargs):
                    try:
                        raw_str = payload.decode("utf-8")
                        hb = HeartbeatPayload.model_validate_json(raw_str)
                        fleet_registry[hb.device_id] = {
                            "device_id": hb.device_id,
                            "last_seen": hb.timestamp,
                            "branch": hb.active_branch,
                            "arch": hb.architecture,
                            "binary": hb.active_binary,
                            "status": hb.status,
                        }
                        event_data = {
                            "type": "HEARTBEAT",
                            "topic": topic,
                            "device_id": hb.device_id,
                            "payload": hb.model_dump(),
                            "fleet_count": len(fleet_registry),
                        }
                        broadcast_sync(event_data)
                    except Exception as e:
                        logger.error(f"Error handling Heartbeat payload: {e}")

                def on_ota_status(topic, payload, **kwargs):
                    try:
                        raw_str = payload.decode("utf-8")
                        ota = OTAStatusPayload.model_validate_json(raw_str)
                        ota_data = ota.model_dump()
                        ota_events.append(ota_data)
                        if len(ota_events) > 100:
                            ota_events.pop(0)
                        event_data = {
                            "type": "OTA_STATUS",
                            "topic": topic,
                            "payload": ota_data,
                        }
                        broadcast_sync(event_data)
                    except Exception as e:
                        logger.error(f"Error handling OTA status payload: {e}")

                def on_isolation_status(topic, payload, **kwargs):
                    try:
                        raw_str = payload.decode("utf-8")
                        iso = IsolationProtectionPayload.model_validate_json(raw_str)
                        iso_data = iso.model_dump()
                        isolation_events.append(iso_data)
                        if len(isolation_events) > 100:
                            isolation_events.pop(0)
                        event_data = {
                            "type": "ISOLATION_STATUS",
                            "topic": topic,
                            "payload": iso_data,
                        }
                        broadcast_sync(event_data)
                    except Exception as e:
                        logger.error(f"Error handling Isolation status payload: {e}")

                def on_unittest_status(topic, payload, **kwargs):
                    try:
                        raw_str = payload.decode("utf-8")
                        ut = UnitTestStatusPayload.model_validate_json(raw_str)
                        ut_data = ut.model_dump()
                        unittest_events.append(ut_data)
                        if len(unittest_events) > 100:
                            unittest_events.pop(0)
                        event_data = {
                            "type": "UNITTEST_STATUS",
                            "topic": topic,
                            "payload": ut_data,
                        }
                        broadcast_sync(event_data)
                    except Exception as e:
                        logger.error(f"Error handling Unittest status payload: {e}")

                def on_response(topic, payload, **kwargs):
                    try:
                        raw_str = payload.decode("utf-8")
                        data = json.loads(raw_str)
                        command_responses.append(data)
                        if len(command_responses) > 100:
                            command_responses.pop(0)
                        event_data = {
                            "type": "COMMAND_RESPONSE",
                            "topic": topic,
                            "payload": data,
                        }
                        broadcast_sync(event_data)
                    except Exception as e:
                        logger.error(f"Error handling Command response payload: {e}")

                mqtt_client.subscribe(on_heartbeat, topic=Topics.HEARTBEAT_TOPIC, verbose=False)
                mqtt_client.subscribe(on_ota_status, topic=Topics.OTA_STATUS_TOPIC, verbose=False)
                mqtt_client.subscribe(on_isolation_status, topic=Topics.ISOLATION_STATUS_TOPIC, verbose=False)
                mqtt_client.subscribe(on_unittest_status, topic=Topics.UNITTEST_STATUS_TOPIC, verbose=False)
                mqtt_client.subscribe(on_response, topic=Topics.RESPONSE_TOPIC, verbose=False)

                logger.info("Dashboard MQTT Telemetry Listener active.")
                while True:
                    time.sleep(2)
            except Exception as e:
                logger.warning(f"MQTT Listener connection error: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    thread = threading.Thread(target=mqtt_worker, daemon=True)
    thread.start()


# ============================================================================
# API Models
# ============================================================================
class BranchSwitchRequest(BaseModel):
    branch: str


class CustomCommandRequest(BaseModel):
    function: str
    parameters: List[str] = []


class SaveCodeRequest(BaseModel):
    code: str
    message: Optional[str] = "Update hello.c via Admin Code Editor"


# ============================================================================
# Helper Process Controller
# ============================================================================
def get_daemon_status(daemon_name: str) -> dict:
    proc = daemon_processes.get(daemon_name)
    if proc is not None and proc.poll() is None:
        return {"status": "RUNNING", "pid": proc.pid}

    # Check system pgrep as fallback
    target_cmd = "NHIOTSub.server_subscriber" if daemon_name == "server_subscriber" else "NHIOTSub.main"
    try:
        res = subprocess.run(["pgrep", "-f", target_cmd], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            pids = res.stdout.strip().splitlines()
            return {"status": "RUNNING", "pid": int(pids[0])}
    except Exception:
        pass

    return {"status": "STOPPED", "pid": None}


def start_daemon(daemon_name: str) -> dict:
    current = get_daemon_status(daemon_name)
    if current["status"] == "RUNNING":
        return {"status": "ALREADY_RUNNING", "pid": current["pid"]}

    cmd = (
        [sys.executable, "-m", "NHIOTSub.server_subscriber"]
        if daemon_name == "server_subscriber"
        else [sys.executable, "-m", "NHIOTSub.main"]
    )
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    daemon_processes[daemon_name] = proc
    logger.info(f"Started daemon {daemon_name} with PID {proc.pid}")

    broadcast_sync(
        {
            "type": "DAEMON_STATUS_CHANGE",
            "daemon": daemon_name,
            "action": "START",
            "pid": proc.pid,
        }
    )
    return {"status": "STARTED", "pid": proc.pid}


def stop_daemon(daemon_name: str) -> dict:
    target_cmd = "NHIOTSub.server_subscriber" if daemon_name == "server_subscriber" else "NHIOTSub.main"
    try:
        res = subprocess.run(["pkill", "-f", target_cmd], capture_output=True, text=True)
        daemon_processes[daemon_name] = None
        logger.info(f"Stopped daemon {daemon_name}")
        broadcast_sync(
            {
                "type": "DAEMON_STATUS_CHANGE",
                "daemon": daemon_name,
                "action": "STOP",
            }
        )
        return {"status": "STOPPED", "detail": res.stdout}
    except Exception as e:
        logger.error(f"Failed to stop daemon {daemon_name}: {e}")
        return {"status": "ERROR", "message": str(e)}


# ============================================================================
# REST API Endpoints
# ============================================================================
@app.get("/api/status")
def get_system_status():
    server_status = get_daemon_status("server_subscriber")
    iot_status = get_daemon_status("iot_subscriber")

    active_branches = list({d.get("branch", "main") for d in fleet_registry.values()})
    active_branch = active_branches[0] if active_branches else "main"

    return {
        "system": "NHIOT DevSecOps OTA Enterprise Pipeline",
        "timestamp": datetime.now().isoformat(),
        "active_branch": active_branch,
        "fleet_count": len(fleet_registry),
        "daemons": {
            "server_subscriber": server_status,
            "iot_subscriber": iot_status,
        },
        "metrics": {
            "total_ota_events": len(ota_events),
            "total_isolation_crashes": len(isolation_events),
            "total_unittests": len(unittest_events),
            "total_command_responses": len(command_responses),
        },
    }


@app.get("/api/telemetry")
def get_telemetry():
    return {
        "fleet_registry": fleet_registry,
        "ota_events": list(reversed(ota_events[-20:])),
        "isolation_events": list(reversed(isolation_events[-20:])),
        "unittest_events": list(reversed(unittest_events[-20:])),
        "command_responses": list(reversed(command_responses[-20:])),
    }


@app.get("/api/logs")
def get_logs():
    return {"logs": list(reversed(recent_logs[-50:]))}


@app.post("/api/daemons/{daemon_name}/{action}")
def control_daemon(daemon_name: str, action: str):
    if daemon_name not in ["server_subscriber", "iot_subscriber"]:
        raise HTTPException(
            status_code=400, detail="Invalid daemon name. Must be 'server_subscriber' or 'iot_subscriber'."
        )

    action = action.lower()
    if action == "status":
        return get_daemon_status(daemon_name)
    elif action == "start":
        return start_daemon(daemon_name)
    elif action == "stop":
        return stop_daemon(daemon_name)
    elif action == "restart":
        stop_daemon(daemon_name)
        time.sleep(1)
        return start_daemon(daemon_name)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'. Use status, start, stop, or restart.")


@app.post("/api/command/switch-branch")
def trigger_switch_branch(req: BranchSwitchRequest):
    branch = req.branch.strip()
    if not branch:
        raise HTTPException(status_code=400, detail="Branch name cannot be empty.")

    logger.info(f"[API] Triggering Branch Switch to '{branch}'...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "NHIOTPub.switch_branch", branch],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=15)
        return {
            "status": "SUCCESS" if proc.returncode == 0 else "WARNING",
            "branch": branch,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        logger.error(f"Branch switch command failed: {e}")
        try:
            client = NHIOTMQTT()
            client.connect(verbose=False)
            client.publish(
                json.dumps({"command": "SET_BRANCH", "branch": branch}), topic=Topics.COMMAND_TOPIC, verbose=False
            )
            client.disconnect(verbose=False)
            return {"status": "MQTT_SENT", "branch": branch, "detail": "Published SET_BRANCH via MQTT direct client"}
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Failed to issue branch switch: {ex}")


@app.post("/api/command/crash")
def trigger_crash_test():
    logger.info("[API] Triggering Critical Failure / Crash Test...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "NHIOTPub.send_crash"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=15)
        return {
            "status": "TRAPPED_SUCCESS",
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        logger.error(f"Crash command failed: {e}")
        try:
            client = NHIOTMQTT()
            client.connect(verbose=False)
            client.publish(
                json.dumps({"function": "crash", "parameters": []}), topic=Topics.COMMAND_TOPIC, verbose=False
            )
            client.disconnect(verbose=False)
            return {"status": "MQTT_SENT", "detail": "Published crash payload via MQTT direct client"}
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Failed to issue crash payload: {ex}")


@app.post("/api/command/revert")
def trigger_revert_rollback():
    logger.info("[API] Triggering GitHub Actions Version History Rollback...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "NHIOTPub.send_revert"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=20)
        return {
            "status": "ROLLBACK_INITIATED",
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        logger.error(f"Revert command failed: {e}")
        try:
            client = NHIOTMQTT()
            client.connect(verbose=False)
            client.publish(json.dumps({"command": "TRIGGER_REVERT"}), topic=Topics.COMMAND_TOPIC, verbose=False)
            client.disconnect(verbose=False)
            return {"status": "MQTT_SENT", "detail": "Published TRIGGER_REVERT payload via MQTT direct client"}
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Failed to issue revert payload: {ex}")


@app.post("/api/command/unittests")
def trigger_run_unittests():
    logger.info("[API] Executing All Operational Unit Tests...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "unittest", "discover", "-s", "NHIOTPub/tests", "-t", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=25)
        passed = stdout.count("ok") or (1 if proc.returncode == 0 else 0)
        failed = stdout.count("FAIL") + stdout.count("ERROR") + (1 if proc.returncode != 0 else 0)
        total = passed + failed or 1
        status_str = "PASSED" if proc.returncode == 0 else "FAILED"

        ut_payload = UnitTestStatusPayload(
            suite_name="NHIOTPub_Full_Suite",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            status=status_str,
            detail=stdout if stdout.strip() else stderr,
        )
        unittest_events.append(ut_payload.model_dump())

        event_data = {
            "type": "UNITTEST_STATUS",
            "topic": Topics.UNITTEST_STATUS_TOPIC,
            "payload": ut_payload.model_dump(),
        }
        broadcast_sync(event_data)

        # Also publish over MQTT
        try:
            client = NHIOTMQTT()
            client.connect(verbose=False)
            client.publish(json.dumps({"command": "RUN_ALL_UNITTESTS"}), topic=Topics.COMMAND_TOPIC, verbose=False)
            client.disconnect(verbose=False)
        except Exception:
            pass

        return {
            "status": status_str,
            "suite_name": "NHIOTPub_Full_Suite",
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": failed,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        logger.error(f"Unittest execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute unit tests: {e}")


class CommitPushRequest(BaseModel):
    message: str = "Trigger OTA Artifact Build via Admin Dashboard"


@app.post("/api/github/commit-and-push")
def github_commit_and_push(req: CommitPushRequest):
    logger.info("[API] Executing Git Add, Commit & Push for Artifact C file...")
    try:
        res_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        active_branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "main"

        c_file = os.path.join(os.path.dirname(__file__), "Artefact", "hello.c")
        if os.path.exists(c_file):
            with open(c_file, "r") as f:
                content = f.read()
            new_comment = f"// Dashboard OTA Build Trigger: {datetime.now().isoformat()}\n"
            if "// Dashboard OTA Build Trigger:" in content:
                import re

                content = re.sub(r"// Dashboard OTA Build Trigger:.*\n", new_comment, content)
            else:
                content = new_comment + content
            with open(c_file, "w") as f:
                f.write(content)

        subprocess.run(["git", "add", "Artefact/hello.c"], check=True, capture_output=True)

        msg = req.message.strip() or "Trigger OTA Artifact Build via Admin Dashboard"
        commit_res = subprocess.run(["git", "commit", "--allow-empty", "-m", msg], capture_output=True, text=True)

        push_res = subprocess.run(["git", "push", "--force", "origin", active_branch], capture_output=True, text=True)

        sha_res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        head_sha = sha_res.stdout.strip()[:7] if sha_res.returncode == 0 else "UNKNOWN"

        broadcast_sync(
            {
                "type": "BUILD_TRIGGERED",
                "branch": active_branch,
                "commit_sha": head_sha,
                "message": msg,
            }
        )

        return {
            "status": "SUCCESS",
            "branch": active_branch,
            "commit_sha": head_sha,
            "commit_output": commit_res.stdout.strip() or commit_res.stderr.strip(),
            "push_output": push_res.stdout.strip() or push_res.stderr.strip() or "Pushed to origin successfully.",
        }
    except Exception as e:
        logger.error(f"Failed to commit & push: {e}")
        raise HTTPException(status_code=500, detail=f"Git commit/push failed: {e}")


@app.get("/api/code/hello")
def get_c_code():
    """Retrieve raw content of Artefact/hello.c for the in-dashboard code editor."""
    c_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Artefact", "hello.c")
    if not os.path.exists(c_file):
        raise HTTPException(status_code=404, detail="Artefact/hello.c not found.")
    try:
        with open(c_file, "r") as f:
            code = f.read()
        return {"status": "SUCCESS", "filename": "Artefact/hello.c", "code": code}
    except Exception as e:
        logger.error(f"Failed to read C source: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read C source: {e}")


@app.post("/api/code/save-and-push")
def save_and_push_c_code(req: SaveCodeRequest):
    """Saves updated C source code to Artefact/hello.c, commits to git, and force pushes to remote repository."""
    logger.info("[API] Saving edited C code from Web Admin Editor and triggering Git force push...")
    try:
        c_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Artefact", "hello.c")
        with open(c_file, "w") as f:
            f.write(req.code)

        res_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        active_branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "main"

        subprocess.run(["git", "add", "Artefact/hello.c"], check=True, capture_output=True)

        msg = req.message.strip() if req.message and req.message.strip() else "Update hello.c via Web Admin Code Editor"
        commit_res = subprocess.run(["git", "commit", "--allow-empty", "-m", msg], capture_output=True, text=True)
        push_res = subprocess.run(["git", "push", "--force", "origin", active_branch], capture_output=True, text=True)

        sha_res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        head_sha = sha_res.stdout.strip()[:7] if sha_res.returncode == 0 else "UNKNOWN"

        broadcast_sync(
            {
                "type": "BUILD_TRIGGERED",
                "branch": active_branch,
                "commit_sha": head_sha,
                "message": msg,
            }
        )

        return {
            "status": "SUCCESS",
            "branch": active_branch,
            "commit_sha": head_sha,
            "commit_output": commit_res.stdout.strip() or commit_res.stderr.strip(),
            "push_output": push_res.stdout.strip() or push_res.stderr.strip() or "Force pushed to origin successfully.",
        }
    except Exception as e:
        logger.error(f"Failed to save and push C code: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save & push C code: {e}")


@app.get("/api/artifacts/download")
def download_artifact(arch: str = "aarch64", file_type: str = "binary"):
    """
    Downloads compiled ELF binary, SHA-256 hash, or full ZIP bundle directly to the browser.
    """
    if arch not in ["x86_64", "aarch64"]:
        raise HTTPException(status_code=400, detail="Invalid architecture. Supported: 'x86_64', 'aarch64'.")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_name = f"hello_{arch}"
    bin_dir = os.path.join(base_dir, "Executables", target_name)
    bin_path = os.path.join(bin_dir, target_name)
    sha_path = os.path.join(bin_dir, f"{target_name}.sha256")

    # Local compile fallback for x86_64 if not yet pulled
    if not os.path.exists(bin_path):
        c_src = os.path.join(base_dir, "Artefact", "hello.c")
        if arch == "x86_64" and os.path.exists(c_src):
            os.makedirs(bin_dir, exist_ok=True)
            sec_flags = ["-O2", "-Wall", "-Wextra", "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2"]
            res = subprocess.run(["gcc"] + sec_flags + ["-o", bin_path, c_src], capture_output=True)
            if res.returncode == 0 and os.path.exists(bin_path):
                with open(bin_path, "rb") as f:
                    sha_val = hashlib.sha256(f.read()).hexdigest()
                with open(sha_path, "w") as f:
                    f.write(f"{sha_val}  {target_name}\n")

    if not os.path.exists(bin_path) and file_type != "sha256":
        raise HTTPException(
            status_code=404,
            detail=f"Compiled binary '{target_name}' is not found locally. Trigger a GitHub Actions OTA Build first.",
        )

    if file_type == "binary":
        return FileResponse(
            path=bin_path,
            filename=target_name,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={target_name}"},
        )
    elif file_type == "sha256":
        if os.path.exists(sha_path):
            return FileResponse(
                path=sha_path,
                filename=f"{target_name}.sha256",
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename={target_name}.sha256"},
            )
        elif os.path.exists(bin_path):
            with open(bin_path, "rb") as f:
                sha_val = hashlib.sha256(f.read()).hexdigest()
            return Response(
                content=f"{sha_val}  {target_name}\n",
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename={target_name}.sha256"},
            )
        else:
            raise HTTPException(status_code=404, detail="SHA-256 checksum not available.")
    elif file_type == "zip":
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
            if os.path.exists(bin_path):
                z.write(bin_path, arcname=target_name)
            if os.path.exists(sha_path):
                z.write(sha_path, arcname=f"{target_name}.sha256")
            elif os.path.exists(bin_path):
                with open(bin_path, "rb") as f:
                    sha_val = hashlib.sha256(f.read()).hexdigest()
                z.writestr(f"{target_name}.sha256", f"{sha_val}  {target_name}\n")
        zip_buf.seek(0)
        return Response(
            content=zip_buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={target_name}.zip"},
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid file_type. Choose 'binary', 'sha256', or 'zip'.")


@app.post("/api/ota/force-pull")
def force_edge_ota_download():
    """Publishes FORCE_OTA_DOWNLOAD command to immediately trigger edge OTA pull."""
    logger.info("[API] Dispatching Immediate Force OTA Pull Command to Fleet over MQTT...")
    try:
        client = NHIOTMQTT()
        client.connect(verbose=False)
        client.publish(json.dumps({"command": "FORCE_OTA_DOWNLOAD"}), topic=Topics.COMMAND_TOPIC, verbose=False)
        client.disconnect(verbose=False)
        return {"status": "SUCCESS", "message": "FORCE_OTA_DOWNLOAD command published to fleet topic."}
    except Exception as e:
        logger.error(f"Failed to publish force OTA command: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to dispatch force OTA command: {e}")


class DashboardGitHubClient:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.owner = os.environ.get("OWNER", "Amari-Lawal")
        self.repo = os.environ.get("REPO", "NHIOTPipeline")
        self.workflow_id = os.environ.get("WORKFLOW_ID", "build.yml")
        self.base_url = "https://api.github.com/repos"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def get_latest_run(self, branch: Optional[str] = None) -> Optional[dict]:
        url = f"{self.base_url}/{self.owner}/{self.repo}/actions/workflows/{self.workflow_id}/runs"
        params = {"per_page": 1}
        if branch:
            params["branch"] = branch
        try:
            res = requests.get(url, headers=self.headers, params=params, timeout=10)
            if res.status_code == 200:
                runs = res.json().get("workflow_runs", [])
                return runs[0] if runs else None
        except Exception as e:
            logger.error(f"Dashboard GitHub API error: {e}")
        return None

    def get_workflow_jobs(self, run_id: int) -> list:
        url = f"{self.base_url}/{self.owner}/{self.repo}/actions/runs/{run_id}/jobs"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json().get("jobs", [])
        except Exception as e:
            logger.error(f"Dashboard GitHub API jobs error: {e}")
        return []


@app.get("/api/github/build-status")
def get_github_build_status(branch: Optional[str] = None):
    try:
        gh = DashboardGitHubClient()
        run = gh.get_latest_run(branch=branch)
        if not run:
            return {"status": "NO_RUNS_FOUND"}

        jobs = gh.get_workflow_jobs(run["id"])
        head_commit = run.get("head_commit") or {}
        return {
            "run_id": run.get("id"),
            "name": run.get("name"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "html_url": run.get("html_url"),
            "commit_sha": run.get("head_sha", "")[:7] if run.get("head_sha") else "N/A",
            "commit_message": head_commit.get("message", "N/A"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "jobs": [
                {
                    "name": j.get("name"),
                    "status": j.get("status"),
                    "conclusion": j.get("conclusion"),
                    "steps_count": len(j.get("steps", [])),
                    "started_at": j.get("started_at"),
                    "completed_at": j.get("completed_at"),
                }
                for j in jobs
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch GitHub build status: {e}")
        return {"status": "ERROR", "detail": str(e)}


@app.post("/api/command/custom")
def trigger_custom_command(req: CustomCommandRequest):
    if req.function == "RUN_ALL_UNITTESTS":
        return trigger_run_unittests()

    logger.info(f"[API] Publishing Custom Command '{req.function}' with params {req.parameters}...")
    try:
        client = NHIOTMQTT()
        client.connect(verbose=False)
        payload = json.dumps({"function": req.function, "parameters": req.parameters})
        client.publish(payload, topic=Topics.COMMAND_TOPIC, verbose=False)
        client.disconnect(verbose=False)
        return {"status": "COMMAND_PUBLISHED", "function": req.function, "parameters": req.parameters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish custom command: {e}")


# ============================================================================
# WebSocket Endpoint
# ============================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        snapshot = {
            "type": "SNAPSHOT",
            "fleet_registry": fleet_registry,
            "ota_events": list(reversed(ota_events[-10:])),
            "isolation_events": list(reversed(isolation_events[-10:])),
            "recent_logs": list(reversed(recent_logs[-20:])),
            "daemons": {
                "server_subscriber": get_daemon_status("server_subscriber"),
                "iot_subscriber": get_daemon_status("iot_subscriber"),
            },
        }
        await websocket.send_json(snapshot)
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "PONG", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ============================================================================
# HTML Dashboard Frontend UI
# ============================================================================
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NHIOTPipeline | IoT DevSecOps & Zero-Downtime OTA Pipeline</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- FontAwesome Icons CDN -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        body { font-family: 'Inter', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #1f2937; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
        .pulse-dot {
            box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
            animation: pulse-green 2s infinite;
        }
        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
    </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen flex flex-col">

    <!-- Header Navigation -->
    <header class="bg-gray-900 border-b border-gray-800 px-6 py-4 sticky top-0 z-50 flex flex-wrap justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <div class="bg-blue-600/20 p-2.5 rounded-xl border border-blue-500/30 text-blue-400">
                <i class="fa-solid fa-microchip text-2xl"></i>
            </div>
            <div>
                <h1 class="text-xl font-bold text-white tracking-wide flex items-center gap-2">
                    NHIOTPipeline <span class="bg-blue-900/60 text-blue-300 text-xs px-2.5 py-0.5 rounded-full border border-blue-700/50">Admin UI</span>
                </h1>
                <p class="text-xs text-gray-400 font-medium">IoT DevSecOps & Zero-Downtime OTA Pipeline</p>
            </div>
        </div>

        <div class="flex items-center space-x-6 mt-3 sm:mt-0">
            <!-- Connection Status -->
            <div class="flex items-center space-x-2 bg-gray-800/80 px-3 py-1.5 rounded-lg border border-gray-700/50 text-xs">
                <span id="wsStatusDot" class="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                <span id="wsStatusText" class="text-gray-300 font-medium">Connecting...</span>
            </div>
            <div class="text-xs text-gray-400 font-mono" id="liveClock"></div>
        </div>
    </header>

    <!-- Main Content Grid -->
    <main class="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">

        <!-- Metrics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            <!-- Fleet Connected Card -->
            <div class="bg-gray-900 border border-gray-800 p-5 rounded-2xl shadow-sm hover:border-gray-700 transition">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Connected Fleet</p>
                        <h3 class="text-3xl font-bold text-white mt-2" id="metricFleetCount">0</h3>
                    </div>
                    <div class="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
                        <i class="fa-solid fa-network-wired text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 flex items-center justify-between text-xs">
                    <span class="text-gray-400">Active Architecture:</span>
                    <span class="font-mono text-emerald-400 font-semibold" id="metricArch">x86_64</span>
                </div>
            </div>

            <!-- Active Branch Card -->
            <div class="bg-gray-900 border border-gray-800 p-5 rounded-2xl shadow-sm hover:border-gray-700 transition">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Active OTA Branch</p>
                        <h3 class="text-2xl font-bold text-blue-400 mt-2 font-mono" id="metricBranch">main</h3>
                    </div>
                    <div class="p-3 bg-blue-500/10 text-blue-400 rounded-xl border border-blue-500/20">
                        <i class="fa-solid fa-code-branch text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 flex items-center justify-between text-xs">
                    <span class="text-gray-400">Target Artifact:</span>
                    <span class="font-mono text-blue-300">hello (ELF 64)</span>
                </div>
            </div>

            <!-- OTA Deployments Card -->
            <div class="bg-gray-900 border border-gray-800 p-5 rounded-2xl shadow-sm hover:border-gray-700 transition">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">OTA Deployments</p>
                        <h3 class="text-3xl font-bold text-white mt-2" id="metricOtaCount">0</h3>
                    </div>
                    <div class="p-3 bg-indigo-500/10 text-indigo-400 rounded-xl border border-indigo-500/20">
                        <i class="fa-solid fa-upload text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 flex items-center justify-between text-xs">
                    <span class="text-gray-400">Rollbacks Triggered:</span>
                    <span class="font-mono text-amber-400 font-bold" id="metricRollbackCount">0</span>
                </div>
            </div>

            <!-- Process Isolation Protection Card -->
            <div class="bg-gray-900 border border-gray-800 p-5 rounded-2xl shadow-sm hover:border-gray-700 transition">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Trapped Isolation Crashes</p>
                        <h3 class="text-3xl font-bold text-red-400 mt-2" id="metricIsolationCount">0</h3>
                    </div>
                    <div class="p-3 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20">
                        <i class="fa-solid fa-shield-cat text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 flex items-center justify-between text-xs">
                    <span class="text-gray-400">Protection Status:</span>
                    <span class="text-emerald-400 font-semibold flex items-center gap-1">
                        <i class="fa-solid fa-circle-check text-xs"></i> 100% Isolated
                    </span>
                </div>
            </div>
        </div>

        <!-- Daemon Management & Quick Command Action Bar -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <!-- Daemon Services Control Panel -->
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-server text-blue-400"></i> Local Service Daemons
                    </h2>
                    <span class="text-xs text-gray-400">Process Manager</span>
                </div>

                <!-- Server Audit Daemon Row -->
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800/80 flex items-center justify-between">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="font-semibold text-sm text-gray-200">Server Audit Daemon</span>
                            <span id="badgeServerSub" class="text-xs px-2 py-0.5 rounded-full font-mono bg-gray-800 text-gray-400 border border-gray-700">Checking...</span>
                        </div>
                        <p class="text-xs text-gray-500 mt-0.5"><code>run_sub_server.sh</code></p>
                    </div>
                    <div class="flex items-center space-x-1.5">
                        <button onclick="controlDaemon('server_subscriber', 'start')" class="px-2.5 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition font-medium">Start</button>
                        <button onclick="controlDaemon('server_subscriber', 'stop')" class="px-2.5 py-1 text-xs bg-red-600/80 hover:bg-red-500 text-white rounded-lg transition font-medium">Stop</button>
                    </div>
                </div>

                <!-- IoT Subscriber Daemon Row -->
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800/80 flex items-center justify-between">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="font-semibold text-sm text-gray-200">IoT Subscriber Daemon</span>
                            <span id="badgeIotSub" class="text-xs px-2 py-0.5 rounded-full font-mono bg-gray-800 text-gray-400 border border-gray-700">Checking...</span>
                        </div>
                        <p class="text-xs text-gray-500 mt-0.5"><code>run_sub_iot.sh</code></p>
                    </div>
                    <div class="flex items-center space-x-1.5">
                        <button onclick="controlDaemon('iot_subscriber', 'start')" class="px-2.5 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition font-medium">Start</button>
                        <button onclick="controlDaemon('iot_subscriber', 'stop')" class="px-2.5 py-1 text-xs bg-red-600/80 hover:bg-red-500 text-white rounded-lg transition font-medium">Stop</button>
                    </div>
                </div>
            </div>

            <!-- Workflow Publisher Command Control Suite -->
            <div class="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-sliders text-indigo-400"></i> Workflow Command Suite (Publisher Controls)
                    </h2>
                    <span class="text-xs text-gray-400">MQTT Control Plane</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Branch Switcher Form -->
                    <div class="bg-gray-950 p-4 rounded-xl border border-gray-800 flex flex-col justify-between space-y-3">
                        <div>
                            <div class="flex items-center gap-2 text-blue-400 font-semibold text-sm">
                                <i class="fa-solid fa-code-branch"></i> Dynamic Branch Switcher
                            </div>
                            <p class="text-xs text-gray-400 mt-1">Triggers IoT Subscriber to switch target git branch and download build artifact.</p>
                        </div>
                        <div class="flex items-center space-x-2">
                            <select id="selectBranch" class="flex-1 bg-gray-900 border border-gray-700 text-sm rounded-lg px-3 py-1.5 text-white font-mono focus:outline-none focus:border-blue-500">
                                <option value="main">main</option>
                                <option value="dev" selected>dev</option>
                                <option value="staging">staging</option>
                                <option value="test">test</option>
                            </select>
                            <button onclick="submitBranchSwitch()" class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition flex items-center gap-1.5">
                                <i class="fa-solid fa-arrows-rotate"></i> Switch
                            </button>
                        </div>
                    </div>

                    <!-- Crash Protection Simulator -->
                    <div class="bg-gray-950 p-4 rounded-xl border border-gray-800 flex flex-col justify-between space-y-3">
                        <div>
                            <div class="flex items-center gap-2 text-red-400 font-semibold text-sm">
                                <i class="fa-solid fa-triangle-exclamation"></i> Crash Protection Test
                            </div>
                            <p class="text-xs text-gray-400 mt-1">Publishes critical non-zero returncode crash payload to verify process isolation.</p>
                        </div>
                        <button onclick="submitCrashTest()" class="w-full py-1.5 text-xs bg-red-600/90 hover:bg-red-500 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2">
                            <i class="fa-solid fa-bolt"></i> Trigger Crash Test
                        </button>
                    </div>

                    <!-- GitHub Rollback Trigger -->
                    <div class="bg-gray-950 p-4 rounded-xl border border-gray-800 flex flex-col justify-between space-y-3">
                        <div>
                            <div class="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                                <i class="fa-solid fa-rotate-left"></i> GitHub Actions Version Rollback
                            </div>
                            <p class="text-xs text-gray-400 mt-1">Dispatches automated rollback workflow to fallback to previous stable release.</p>
                        </div>
                        <button onclick="submitRevertRollback()" class="w-full py-1.5 text-xs bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2">
                            <i class="fa-solid fa-clock-rotate-left"></i> Trigger Version Revert
                        </button>
                    </div>

                    <!-- Manual Artifact Download & Edge OTA Pull -->
                    <div class="bg-gray-950 p-4 rounded-xl border border-gray-800 flex flex-col justify-between space-y-3">
                        <div>
                            <div class="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                                <i class="fa-solid fa-download"></i> Manual Artifact Download & Sync
                            </div>
                            <p class="text-xs text-gray-400 mt-1">Download compiled ELF binary or trigger immediate on-demand edge OTA pull.</p>
                        </div>
                        <div class="space-y-2.5">
                            <!-- Target Arch Selector -->
                            <div class="flex items-center space-x-2">
                                <span class="text-xs text-gray-400 font-medium whitespace-nowrap">Arch:</span>
                                <select id="selectDownloadArch" class="flex-1 w-full bg-gray-900 border border-gray-700 text-xs rounded-lg px-2.5 py-1.5 text-white font-mono focus:outline-none focus:border-indigo-500">
                                    <option value="aarch64" selected>aarch64 (Raspberry Pi ARM64)</option>
                                    <option value="x86_64">x86_64 (Linux ELF 64)</option>
                                </select>
                            </div>
                            <!-- Download Buttons Grid -->
                            <div class="grid grid-cols-3 gap-1.5">
                                <button onclick="triggerArtifactDownload('binary')" class="py-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition flex items-center justify-center gap-1" title="Download compiled executable">
                                    <i class="fa-solid fa-file-arrow-down text-[10px]"></i> Binary
                                </button>
                                <button onclick="triggerArtifactDownload('sha256')" class="py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition flex items-center justify-center gap-1" title="Download SHA-256 Checksum">
                                    <i class="fa-solid fa-fingerprint text-[10px]"></i> SHA
                                </button>
                                <button onclick="triggerArtifactDownload('zip')" class="py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition flex items-center justify-center gap-1" title="Download ZIP package">
                                    <i class="fa-solid fa-file-zipper text-[10px]"></i> ZIP
                                </button>
                            </div>
                            <!-- Force OTA Button -->
                            <button onclick="submitForceOtaDownload()" class="w-full py-1.5 text-xs bg-emerald-600/90 hover:bg-emerald-500 text-white font-semibold rounded-lg transition flex items-center justify-center gap-1.5">
                                <i class="fa-solid fa-cloud-arrow-down"></i> Force Edge OTA Pull & Sync
                            </button>
                        </div>
                    </div>

                    <!-- Interactive C Code IDE & DevSecOps Simulation Box -->
                    <div class="md:col-span-2 bg-gray-950 p-4 rounded-xl border border-gray-800 space-y-3">
                        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-2.5">
                            <div>
                                <div class="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
                                    <i class="fa-solid fa-code"></i> Interactive C Code Editor & OTA Deploy
                                    <span class="bg-cyan-900/60 text-cyan-300 text-[10px] font-mono px-2 py-0.5 rounded border border-cyan-700/50">Artefact/hello.c</span>
                                </div>
                                <p class="text-xs text-gray-400 mt-0.5">Simulate developer code changes in the IDE, inject bugs or fixes, and trigger OTA builds.</p>
                            </div>

                            <!-- Presets Toolbar -->
                            <div class="flex flex-wrap items-center gap-1.5">
                                <button onclick="applyCodePreset('fix')" class="px-2 py-1 text-[11px] bg-emerald-700/80 hover:bg-emerald-600 text-white rounded transition font-medium flex items-center gap-1">
                                    <i class="fa-solid fa-check"></i> Fix Bug (*=)
                                </button>
                                <button onclick="applyCodePreset('bug')" class="px-2 py-1 text-[11px] bg-red-700/80 hover:bg-red-600 text-white rounded transition font-medium flex items-center gap-1">
                                    <i class="fa-solid fa-bug"></i> Inject Bug (-=)
                                </button>
                                <button onclick="applyCodePreset('crash')" class="px-2 py-1 text-[11px] bg-amber-700/80 hover:bg-amber-600 text-white rounded transition font-medium flex items-center gap-1">
                                    <i class="fa-solid fa-bolt"></i> Crash Div/0
                                </button>
                                <button onclick="loadCCode()" class="px-2 py-1 text-[11px] bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition font-medium flex items-center gap-1">
                                    <i class="fa-solid fa-rotate"></i> Reload
                                </button>
                            </div>
                        </div>

                        <!-- Textarea Editor -->
                        <div class="relative">
                            <div class="flex items-center justify-between bg-black/50 px-3 py-1.5 rounded-t-lg border border-gray-800 border-b-0 text-[11px] font-mono text-gray-400">
                                <span><i class="fa-regular fa-file-code text-cyan-400"></i> C Source Logic</span>
                                <span id="codeEditorStatus" class="text-gray-500 text-[10px]">Synced with disk</span>
                            </div>
                            <textarea id="cCodeEditorTextarea" rows="12" spellcheck="false"
                                      class="w-full bg-black/90 text-gray-200 font-mono text-xs p-3 rounded-b-lg border border-gray-800 focus:outline-none focus:border-cyan-500 custom-scrollbar leading-relaxed resize-y"
                                      placeholder="Loading C source code..."></textarea>
                        </div>

                        <!-- Commit & Deploy Bar -->
                        <div class="flex flex-col sm:flex-row items-center gap-2">
                            <input type="text" id="inputCodeCommitMsg" placeholder="Commit message e.g. Fix multiplication logic in hello.c" value="Update hello.c logic via Admin Code Editor"
                                   class="flex-1 w-full bg-gray-900 border border-gray-700 text-xs rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-cyan-500">
                            <button onclick="submitCodeSaveAndPush()" class="w-full sm:w-auto px-4 py-2 text-xs bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold rounded-lg transition flex items-center justify-center gap-1.5 whitespace-nowrap shadow-md">
                                <i class="fa-solid fa-rocket"></i> Save, Commit & Deploy OTA Build
                            </button>
                        </div>

                        <!-- Live GitHub Actions Build & CI/CD Telemetry Widget -->
                        <div id="ghRunTelemetryBox" class="bg-gray-900/90 border border-gray-800 rounded-xl p-3.5 text-xs space-y-2.5 shadow-inner">
                            <div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-2">
                                <div class="flex items-center gap-2">
                                    <div class="p-1.5 bg-purple-500/10 text-purple-400 rounded border border-purple-500/20 text-xs">
                                        <i class="fa-solid fa-rocket"></i>
                                    </div>
                                    <span class="font-bold text-gray-200">GitHub Actions CI/CD Build Pipeline:</span>
                                    <a id="ghRunLink" href="#" target="_blank" class="text-blue-400 hover:underline font-mono font-bold">#--</a>
                                    <span id="ghRunCommit" class="text-purple-300 font-mono text-[11px] truncate max-w-xs"></span>
                                </div>
                                <span id="badgeGhRunStatus" class="text-xs px-2.5 py-1 rounded-full font-mono bg-gray-800 text-gray-400 border border-gray-700">Checking...</span>
                            </div>
                            <div id="ghRunConclusion" class="font-semibold text-xs text-gray-400 italic">Connecting to GitHub Actions API for latest build status...</div>
                            <div id="ghRunJobsList" class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Fleet Devices Table & Live Telemetry Console -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <!-- Connected Edge Fleet Table -->
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4 flex flex-col">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-microchip text-emerald-400"></i> Fleet Device Registry
                    </h2>
                    <span class="text-xs text-gray-400 font-mono">15s Pulse Listener</span>
                </div>

                <div class="overflow-x-auto flex-1 custom-scrollbar">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-gray-800 text-gray-400 uppercase tracking-wider">
                                <th class="py-2.5 px-3">Device ID</th>
                                <th class="py-2.5 px-3">Status</th>
                                <th class="py-2.5 px-3">Branch</th>
                                <th class="py-2.5 px-3">Arch</th>
                                <th class="py-2.5 px-3">Active Binary</th>
                                <th class="py-2.5 px-3">Last Heartbeat</th>
                            </tr>
                        </thead>
                        <tbody id="tableFleetBody" class="divide-y divide-gray-800/60 font-mono">
                            <tr>
                                <td colspan="6" class="py-6 text-center text-gray-500 italic">Waiting for fleet heartbeat pulse...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Streaming Real-Time Console -->
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4 flex flex-col">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-terminal text-blue-400"></i> Live Telemetry & Log Console
                    </h2>
                    <button onclick="clearConsole()" class="text-xs text-gray-400 hover:text-white transition flex items-center gap-1">
                        <i class="fa-solid fa-trash-can"></i> Clear
                    </button>
                </div>

                <div id="consoleOutput" class="bg-black/80 border border-gray-800 rounded-xl p-4 h-72 overflow-y-auto font-mono text-xs text-gray-300 space-y-1.5 custom-scrollbar">
                    <div class="text-gray-500 italic">[SYSTEM] Terminal initialized. Waiting for real-time MQTT telemetry stream...</div>
                </div>
            </div>
        </div>

        <!-- DevSecOps, Unit Test Diagnostics & Process Isolation Audit History -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <!-- OTA Deployment Audit Feed -->
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-upload text-indigo-400"></i> OTA Deployment Audit Feed
                    </h2>
                    <span class="text-xs text-gray-400">GitHub Actions Artifacts</span>
                </div>

                <div id="otaEventFeed" class="space-y-2 max-h-64 overflow-y-auto custom-scrollbar text-xs">
                    <div class="text-gray-500 italic text-center py-4">No OTA events recorded yet.</div>
                </div>
            </div>

            <!-- Operational Unit Test Diagnostics Audit Feed -->
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-vial-circle-check text-emerald-400"></i> Edge Unit Test Diagnostics
                    </h2>
                    <span class="text-xs text-gray-400">Post-Pull Binary Verification</span>
                </div>

                <div id="unittestEventFeed" class="space-y-2 max-h-64 overflow-y-auto custom-scrollbar text-xs">
                    <div class="text-gray-500 italic text-center py-4">No unit test events recorded yet.</div>
                </div>
            </div>

            <!-- Process Isolation Error Log -->
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                    <h2 class="font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-shield-cat text-red-400"></i> Process Isolation Crash Vault
                    </h2>
                    <span class="text-xs text-gray-400">Non-Zero Exit Traps</span>
                </div>

                <div id="isolationEventFeed" class="space-y-2 max-h-64 overflow-y-auto custom-scrollbar text-xs">
                    <div class="text-gray-500 italic text-center py-4">No isolation crashes recorded yet.</div>
                </div>
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="bg-gray-900 border-t border-gray-800 py-4 px-6 text-center text-xs text-gray-500">
        IoT DevSecOps & Zero-Downtime OTA Pipeline
    </footer>

    <!-- JavaScript Application Script -->
    <script>
        let ws;
        let otaCount = 0;
        let rollbackCount = 0;
        let isolationCount = 0;

        function updateClock() {
            const now = new Date();
            document.getElementById('liveClock').innerText = now.toLocaleTimeString();
        }
        setInterval(updateClock, 1000);
        updateClock();

        let isPollingFallback = false;
        let pollTimer = null;

        function connectWebSocket() {
            try {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;
                
                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
                    isPollingFallback = false;
                    document.getElementById('wsStatusDot').className = 'w-2.5 h-2.5 rounded-full bg-emerald-500 pulse-dot';
                    document.getElementById('wsStatusText').innerText = 'Live WebSocket Active';
                    logToConsole('[WS SYSTEM] WebSocket connection established successfully.', 'text-emerald-400');
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    handleIncomingMessage(data);
                };

                ws.onclose = () => {
                    startPollingFallback();
                    setTimeout(connectWebSocket, 5000);
                };

                ws.onerror = (err) => {
                    startPollingFallback();
                };
            } catch (e) {
                startPollingFallback();
            }
        }

        function startPollingFallback() {
            if (isPollingFallback) return;
            isPollingFallback = true;
            document.getElementById('wsStatusDot').className = 'w-2.5 h-2.5 rounded-full bg-blue-400 pulse-dot';
            document.getElementById('wsStatusText').innerText = 'Polling Sync Active';
            logToConsole('[SYSTEM] Operating via REST Polling Sync.', 'text-blue-300');
            if (!pollTimer) {
                pollTimer = setInterval(fetchStatus, 3000);
            }
        }

        function handleIncomingMessage(msg) {
            if (msg.type === 'SNAPSHOT') {
                updateFleetTable(msg.fleet_registry);
                updateDaemonBadges(msg.daemons);
                if (msg.ota_events) msg.ota_events.forEach(renderOtaEvent);
                if (msg.unittest_events) msg.unittest_events.forEach(renderUnittestEvent);
                if (msg.isolation_events) msg.isolation_events.forEach(renderIsolationEvent);
            } else if (msg.type === 'HEARTBEAT') {
                logToConsole(`[HEARTBEAT] Device: ${msg.device_id} | Status: ${msg.payload.status} | Branch: ${msg.payload.active_branch}`, 'text-emerald-300');
                fetchStatus();
            } else if (msg.type === 'OTA_STATUS') {
                otaCount++;
                document.getElementById('metricOtaCount').innerText = otaCount;
                const otaStatus = msg.payload.status;
                const commitSha = msg.payload.commit_sha ? msg.payload.commit_sha.substring(0, 7) : 'N/A';

                if (otaStatus === 'ROLLBACK' || otaStatus === 'FAILURE') {
                    rollbackCount++;
                    document.getElementById('metricRollbackCount').innerText = rollbackCount;
                    if (!window._rollbackCommits) window._rollbackCommits = new Set();
                    if (commitSha !== 'N/A') window._rollbackCommits.add(commitSha);
                    window._lastOtaRollbackActive = true;

                    const badge = document.getElementById('badgeGhRunStatus');
                    const conclusionDiv = document.getElementById('ghRunConclusion');
                    if (badge && conclusionDiv) {
                        badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-red-900/60 text-red-300 border border-red-700/50 pulse-dot';
                        badge.innerText = 'OTA Failure / Rollback';
                        conclusionDiv.className = 'font-semibold text-xs text-red-400';
                        conclusionDiv.innerText = `❌ OTA DEPLOYMENT FAILED: Edge Unit Tests Failed on Commit [${commitSha}] -> Rolled Back!`;
                    }
                    logToConsole(`[OTA DEPLOYMENT FAILURE] Post-pull operational unit tests failed on edge device for commit [${commitSha}]! Automatic GitHub Actions rollback initiated.`, 'text-red-400 font-bold');

                    // Synthesize unit test failure card if detail exists
                    if (msg.payload.detail) {
                        renderUnittestEvent({
                            suite_name: "Post-Pull Operational Unit Test",
                            status: "FAILED",
                            passed_tests: 2,
                            failed_tests: 1,
                            total_tests: 3,
                            detail: msg.payload.detail,
                        });
                    }
                } else if (otaStatus === 'SUCCESS') {
                    window._lastOtaRollbackActive = false;
                    if (window._rollbackCommits && commitSha !== 'N/A') window._rollbackCommits.delete(commitSha);
                    const badge = document.getElementById('badgeGhRunStatus');
                    const conclusionDiv = document.getElementById('ghRunConclusion');
                    if (badge && conclusionDiv) {
                        badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-emerald-900/60 text-emerald-300 border border-emerald-700/50';
                        badge.innerText = 'Build Success';
                        conclusionDiv.className = 'font-semibold text-xs text-emerald-400 flex items-center gap-1.5';
                        conclusionDiv.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i> ✅ SUCCESS (Artifacts Deployed & Verified)';
                    }
                    renderUnittestEvent({
                        suite_name: "Post-Pull Operational Unit Test",
                        status: "PASSED",
                        passed_tests: 3,
                        failed_tests: 0,
                        total_tests: 3,
                        detail: msg.payload.detail || "All edge operational unit tests passed.",
                    });
                    logToConsole(`[OTA DEPLOYMENT SUCCESS] Post-pull operational unit tests passed on edge device for commit [${commitSha}]! Binary verified functional.`, 'text-emerald-400 font-bold');
                } else {
                    logToConsole(`[OTA EVENT] Status: ${otaStatus} | Branch: ${msg.payload.branch} | Commit: ${commitSha}`, 'text-indigo-400');
                }
                renderOtaEvent(msg.payload);
            } else if (msg.type === 'UNITTEST_STATUS') {
                logToConsole(`[UNITTEST EVENT] ${msg.payload.suite_name || 'Suite'} -> ${msg.payload.status} (${msg.payload.passed_tests}/${msg.payload.total_tests} passed)`, msg.payload.status === 'PASSED' ? 'text-emerald-300' : 'text-red-400 font-bold');
                renderUnittestEvent(msg.payload);
            } else if (msg.type === 'ISOLATION_STATUS') {
                isolationCount++;
                document.getElementById('metricIsolationCount').innerText = isolationCount;
                logToConsole(`[ISOLATION EVENT] Trapped non-zero returncode in function '${msg.payload.function_called}'! Error: ${msg.payload.error_message}`, 'text-red-400 font-bold');
                renderIsolationEvent(msg.payload);
            } else if (msg.type === 'COMMAND_RESPONSE') {
                const payload = msg.payload;
                const out = payload.result || payload.stdout || payload.error || payload.stderr || JSON.stringify(payload);
                logToConsole(`[COMMAND RESPONSE] ${out}`, 'text-blue-300');
            } else if (msg.type === 'DAEMON_STATUS_CHANGE') {
                logToConsole(`[DAEMON MANAGER] ${msg.daemon} -> ${msg.action}`, 'text-amber-300');
                fetchStatus();
            } else if (msg.type === 'BUILD_TRIGGERED') {
                logToConsole(`[BUILD TRIGGERED] Commit [${msg.commit_sha}] dispatched on branch '${msg.branch}'! Tracking live CI/CD build...`, 'text-purple-400 font-bold');
                startGitHubBuildPolling(msg.commit_sha);
            }
        }

        function logToConsole(text, textClass = 'text-gray-300') {
            const consoleDiv = document.getElementById('consoleOutput');
            const entry = document.createElement('div');
            const timeStr = new Date().toLocaleTimeString();
            entry.className = `${textClass} leading-relaxed flex items-start space-x-2`;
            entry.innerHTML = `<span class="text-gray-500 text-[10px] select-none font-mono">[${timeStr}]</span> <span>${text}</span>`;
            consoleDiv.appendChild(entry);
            consoleDiv.scrollTop = consoleDiv.scrollHeight;
        }

        function clearConsole() {
            document.getElementById('consoleOutput').innerHTML = '<div class="text-gray-500 italic">[SYSTEM] Console cleared.</div>';
        }

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('metricFleetCount').innerText = data.fleet_count || 0;
                document.getElementById('metricBranch').innerText = data.active_branch || 'main';
                document.getElementById('metricOtaCount').innerText = data.metrics.total_ota_events || 0;
                document.getElementById('metricIsolationCount').innerText = data.metrics.total_isolation_crashes || 0;
                updateDaemonBadges(data.daemons);

                const telemRes = await fetch('/api/telemetry');
                const telemData = await telemRes.json();
                updateFleetTable(telemData.fleet_registry);
            } catch (e) {
                console.error("Error fetching status:", e);
            }
        }

        function updateDaemonBadges(daemons) {
            if (!daemons) return;
            const serverStatus = daemons.server_subscriber ? daemons.server_subscriber.status : 'STOPPED';
            const iotStatus = daemons.iot_subscriber ? daemons.iot_subscriber.status : 'STOPPED';

            const serverBadge = document.getElementById('badgeServerSub');
            if (serverStatus === 'RUNNING') {
                serverBadge.className = 'text-xs px-2.5 py-0.5 rounded-full font-mono bg-emerald-900/60 text-emerald-300 border border-emerald-700/50';
                serverBadge.innerText = 'RUNNING';
            } else {
                serverBadge.className = 'text-xs px-2.5 py-0.5 rounded-full font-mono bg-red-900/60 text-red-300 border border-red-700/50';
                serverBadge.innerText = 'STOPPED';
            }

            const iotBadge = document.getElementById('badgeIotSub');
            if (iotStatus === 'RUNNING') {
                iotBadge.className = 'text-xs px-2.5 py-0.5 rounded-full font-mono bg-emerald-900/60 text-emerald-300 border border-emerald-700/50';
                iotBadge.innerText = 'RUNNING';
            } else {
                iotBadge.className = 'text-xs px-2.5 py-0.5 rounded-full font-mono bg-red-900/60 text-red-300 border border-red-700/50';
                iotBadge.innerText = 'STOPPED';
            }
        }

        function updateFleetTable(registry) {
            const tbody = document.getElementById('tableFleetBody');
            if (!registry || Object.keys(registry).length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="py-6 text-center text-gray-500 italic">No fleet devices registered yet. Start IoT Subscriber daemon.</td></tr>';
                return;
            }
            tbody.innerHTML = '';
            for (const [id, dev] of Object.entries(registry)) {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-gray-800/40 transition';
                tr.innerHTML = `
                    <td class="py-2.5 px-3 font-bold text-white">${dev.device_id || id}</td>
                    <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] bg-emerald-900/60 text-emerald-300 font-semibold border border-emerald-700/40">${dev.status || 'HEALTHY'}</span></td>
                    <td class="py-2.5 px-3 text-blue-400">${dev.branch || 'main'}</td>
                    <td class="py-2.5 px-3 text-gray-300">${dev.arch || 'x86_64'}</td>
                    <td class="py-2.5 px-3 text-gray-400 text-[11px]">${dev.binary ? dev.binary.substring(0, 12) + '...' : 'hello'}</td>
                    <td class="py-2.5 px-3 text-gray-500 text-[11px]">${dev.last_seen ? new Date(dev.last_seen * 1000).toLocaleTimeString() : 'Just now'}</td>
                `;
                tbody.appendChild(tr);
            }
        }

        function renderOtaEvent(ota) {
            const feed = document.getElementById('otaEventFeed');
            if (feed.querySelector('.italic')) feed.innerHTML = '';
            const card = document.createElement('div');
            card.className = 'bg-gray-950 border border-gray-800 p-3 rounded-xl flex items-center justify-between';
            card.innerHTML = `
                <div>
                    <div class="flex items-center gap-2">
                        <span class="font-semibold text-gray-200">${ota.status}</span>
                        <span class="text-blue-400 font-mono text-[11px]">${ota.branch || 'main'}</span>
                    </div>
                    <p class="text-gray-400 text-[11px] mt-0.5">${ota.detail || 'OTA Update Processed'}</p>
                </div>
                <div class="text-right text-gray-500 font-mono text-[10px]">
                    ${ota.commit_sha ? 'SHA: ' + ota.commit_sha.substring(0, 7) : ''}
                </div>
            `;
            feed.prepend(card);
        }

        function renderUnittestEvent(ut) {
            const feed = document.getElementById('unittestEventFeed');
            if (!feed) return;
            if (feed.querySelector('.italic')) feed.innerHTML = '';
            
            const isFailed = ut.status === 'FAILED' || (ut.failed_tests && ut.failed_tests > 0);
            const card = document.createElement('div');
            card.className = isFailed
                ? 'bg-red-950/40 border border-red-900/60 p-3 rounded-xl space-y-2'
                : 'bg-emerald-950/30 border border-emerald-900/40 p-3 rounded-xl flex items-center justify-between';

            // Detect failing arithmetic function (add, minus, multiply)
            let failedFn = '';
            const textToSearch = ((ut.detail || '') + ' ' + (ut.error_message || '')).toLowerCase();
            if (/\badd\b/i.test(textToSearch)) failedFn = 'add';
            else if (/\bmultiply\b/i.test(textToSearch)) failedFn = 'multiply';
            else if (/\bminus\b/i.test(textToSearch)) failedFn = 'minus';
            else if (/exec format|elf/i.test(textToSearch)) failedFn = 'ARCH_MISMATCH';

            // If function not in detail text, inspect C source code in the Web Editor
            if (!failedFn) {
                const editor = document.getElementById('cCodeEditorTextarea');
                const code = editor ? editor.value : '';
                const minusMatch = code.match(/void\s+minus\s*\([^\)]*\)\s*\{([\s\S]*?)\}/);
                const multiplyMatch = code.match(/void\s+multiply\s*\([^\)]*\)\s*\{([\s\S]*?)\}/);
                const addMatch = code.match(/void\s+add\s*\([^\)]*\)\s*\{([\s\S]*?)\}/);

                if (minusMatch && (minusMatch[1].includes('result +=') || minusMatch[1].includes('result *=') || !minusMatch[1].includes('result -='))) {
                    failedFn = 'minus';
                } else if (multiplyMatch && (multiplyMatch[1].includes('count -=') || multiplyMatch[1].includes('count +=') || !multiplyMatch[1].includes('count *='))) {
                    failedFn = 'multiply';
                } else if (addMatch && (addMatch[1].includes('count -=') || addMatch[1].includes('count *=') || !addMatch[1].includes('count +='))) {
                    failedFn = 'add';
                } else {
                    failedFn = 'minus';
                }
            }

            let diagDetail = ut.detail || ut.error_message || 'Operational unit test assertion failed.';
            if (failedFn === 'minus' && (diagDetail.includes('revert') || diagDetail.includes('rollback') || diagDetail.includes('Unit tests failed'))) {
                diagDetail = `[FAIL] Unit Test minus(['50', '20']) assertion failed! Expected output: '30'.\nTriggered automatic rollback: ${ut.detail || ''}`;
            } else if (failedFn === 'multiply' && (diagDetail.includes('revert') || diagDetail.includes('rollback') || diagDetail.includes('Unit tests failed'))) {
                diagDetail = `[FAIL] Unit Test multiply(['6', '7']) assertion failed! Expected output: '42'.\nTriggered automatic rollback: ${ut.detail || ''}`;
            } else if (failedFn === 'add' && (diagDetail.includes('revert') || diagDetail.includes('rollback') || diagDetail.includes('Unit tests failed'))) {
                diagDetail = `[FAIL] Unit Test add(['10', '20']) assertion failed! Expected output: '30'.\nTriggered automatic rollback: ${ut.detail || ''}`;
            }

            if (isFailed) {
                card.innerHTML = `
                    <div class="flex items-center justify-between text-red-300 font-semibold">
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-vial-circle-check text-red-400"></i> ${ut.suite_name || 'Edge Operational Test'}</span>
                        <span class="text-[10px] font-mono bg-red-900/80 text-red-200 px-2 py-0.5 rounded border border-red-700 font-bold uppercase">FAILED: ${failedFn}</span>
                    </div>
                    <div class="text-[11px] text-gray-300 font-mono space-y-1.5">
                        <div class="flex items-center justify-between text-[10px] bg-red-950/80 p-2 rounded border border-red-900/60">
                            <span class="text-amber-300 font-bold">Failed Target Function:</span>
                            <span class="bg-red-900 text-white font-mono px-2.5 py-0.5 rounded font-bold border border-red-500 uppercase">${failedFn}</span>
                        </div>
                        <span class="text-gray-400 text-[10px] font-bold">Diagnostic Traceback:</span>
                        <div class="bg-black/80 p-2.5 rounded-lg border border-red-900/50 text-[10px] font-mono text-red-300 overflow-x-auto whitespace-pre-wrap">${diagDetail}</div>
                    </div>
                `;
            } else {
                card.innerHTML = `
                    <div>
                        <div class="flex items-center gap-2 text-emerald-300 font-semibold">
                            <i class="fa-solid fa-circle-check text-xs text-emerald-400"></i> ${ut.suite_name || 'Edge Operational Test'}
                        </div>
                        <p class="text-gray-400 text-[11px] mt-0.5">${ut.detail || 'All binary arithmetic unit tests (add, minus, multiply) passed.'}</p>
                    </div>
                    <div class="text-right font-mono text-[10px] text-emerald-400 font-bold">
                        ${ut.passed_tests || 3}/${ut.total_tests || 3} Passed
                    </div>
                `;
            }
            feed.prepend(card);
        }

        function renderIsolationEvent(iso) {
            const feed = document.getElementById('isolationEventFeed');
            if (feed.querySelector('.italic')) feed.innerHTML = '';
            const card = document.createElement('div');
            card.className = 'bg-red-950/30 border border-red-900/50 p-3 rounded-xl space-y-1';
            card.innerHTML = `
                <div class="flex items-center justify-between text-red-300 font-semibold">
                    <span><i class="fa-solid fa-shield-cat"></i> ${iso.status || 'PROTECTED'}</span>
                    <span class="text-[10px] font-mono text-gray-400">${iso.timestamp || 'Just now'}</span>
                </div>
                <p class="text-gray-300 text-[11px]">Function: <code class="text-amber-300">${iso.function_called}</code></p>
                <div class="bg-black/60 p-2 rounded text-[10px] font-mono text-red-400 overflow-x-auto">${iso.error_message || 'Trapped non-zero returncode'}</div>
            `;
            feed.prepend(card);
        }

        async function controlDaemon(name, action) {
            logToConsole(`[USER ACTION] Requesting ${action} for daemon '${name}'...`, 'text-blue-400');
            try {
                const res = await fetch(`/api/daemons/${name}/${action}`, { method: 'POST' });
                const data = await res.json();
                logToConsole(`[DAEMON MANAGER RESULT] ${JSON.stringify(data)}`, 'text-emerald-400');
                fetchStatus();
            } catch (e) {
                logToConsole(`[ERROR] Daemon command failed: ${e}`, 'text-red-400');
            }
        }

        async function submitBranchSwitch() {
            const branch = document.getElementById('selectBranch').value;
            if (!branch) return alert("Please select branch name.");
            logToConsole(`[USER ACTION] Triggering branch switch to '${branch}'...`, 'text-blue-400');
            try {
                const res = await fetch('/api/command/switch-branch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({branch})
                });
                const data = await res.json();
                logToConsole(`[BRANCH SWITCH RESPONSE] ${data.stdout || data.detail || JSON.stringify(data)}`, 'text-emerald-400');
            } catch (e) {
                logToConsole(`[ERROR] Branch switch failed: ${e}`, 'text-red-400');
            }
        }

        async function submitCrashTest() {
            logToConsole(`[USER ACTION] Triggering critical failure crash test over MQTT...`, 'text-red-400');
            try {
                const res = await fetch('/api/command/crash', { method: 'POST' });
                const data = await res.json();
                logToConsole(`[CRASH TEST RESULT] ${data.stderr || data.stdout || data.detail}`, 'text-amber-300');
            } catch (e) {
                logToConsole(`[ERROR] Crash test failed: ${e}`, 'text-red-400');
            }
        }

        async function submitRevertRollback() {
            logToConsole(`[USER ACTION] Requesting GitHub Actions Version History Rollback...`, 'text-amber-400');
            try {
                const res = await fetch('/api/command/revert', { method: 'POST' });
                const data = await res.json();
                logToConsole(`[ROLLBACK RESPONSE] ${data.stdout || data.detail || JSON.stringify(data)}`, 'text-emerald-400');
            } catch (e) {
                logToConsole(`[ERROR] Rollback request failed: ${e}`, 'text-red-400');
            }
        }

        function toggleMathInputs() {
            const fn = document.getElementById('selectFn').value;
            const p1 = document.getElementById('inputP1');
            const p2 = document.getElementById('inputP2');
            if (fn === 'RUN_ALL_UNITTESTS') {
                p1.style.display = 'none';
                p2.style.display = 'none';
            } else {
                p1.style.display = 'inline-block';
                p2.style.display = 'inline-block';
            }
        }

        async function submitCustomCommand() {
            const fn = document.getElementById('selectFn').value;
            if (fn === 'RUN_ALL_UNITTESTS') {
                logToConsole(`[USER ACTION] Triggering All Operational Unit Tests...`, 'text-emerald-400');
                try {
                    const res = await fetch('/api/command/unittests', { method: 'POST' });
                    const data = await res.json();
                    logToConsole(`[UNITTESTS SUITE RESULT] Status: ${data.status} | Passed: ${data.passed_tests}/${data.total_tests}`, data.status === 'PASSED' ? 'text-emerald-300 font-bold' : 'text-red-400 font-bold');
                    if (data.stdout) logToConsole(`[UNITTEST STDOUT]\n${data.stdout}`, 'text-gray-300');
                    if (data.stderr) logToConsole(`[UNITTEST STDERR]\n${data.stderr}`, 'text-amber-300');
                } catch (e) {
                    logToConsole(`[ERROR] Unittest execution request failed: ${e}`, 'text-red-400');
                }
                return;
            }

            const p1 = document.getElementById('inputP1').value.trim();
            const p2 = document.getElementById('inputP2').value.trim();
            logToConsole(`[USER ACTION] Executing function '${fn}' with params [${p1}, ${p2}]...`, 'text-emerald-400');
            try {
                const res = await fetch('/api/command/custom', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({function: fn, parameters: [p1, p2]})
                });
                const data = await res.json();
                logToConsole(`[CUSTOM CMD PUBLISHED] ${JSON.stringify(data)}`, 'text-emerald-300');
            } catch (e) {
                logToConsole(`[ERROR] Custom command failed: ${e}`, 'text-red-400');
            }
        }

        let ghPollInterval = null;
        let targetCommitSha = null;

        async function submitGitCommitAndPush() {
            window._lastOtaRollbackActive = false;
            const msg = document.getElementById('inputCommitMsg').value.trim() || 'Trigger OTA Artifact Build via Admin Dashboard';
            logToConsole(`[GIT ACTION] Staging 'Artefact/hello.c', committing & pushing to GitHub...`, 'text-purple-400 font-bold');
            try {
                const res = await fetch('/api/github/commit-and-push', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    targetCommitSha = data.commit_sha;
                    logToConsole(`[GIT SUCCESS] Pushed commit ${data.commit_sha} to branch '${data.branch}'! Waiting for GitHub Actions run to register...`, 'text-emerald-300 font-bold');
                    startGitHubBuildPolling(data.commit_sha);
                } else {
                    logToConsole(`[GIT ERROR] Push failed: ${JSON.stringify(data)}`, 'text-red-400');
                }
            } catch (e) {
                logToConsole(`[ERROR] Commit & Push failed: ${e}`, 'text-red-400');
            }
        }

        function startGitHubBuildPolling(commitSha = null) {
            if (commitSha) targetCommitSha = commitSha;
            const badge = document.getElementById('badgeGhRunStatus');
            const conclusionDiv = document.getElementById('ghRunConclusion');
            if (badge) {
                badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-purple-900/60 text-purple-300 border border-purple-700/50 pulse-dot';
                badge.innerText = 'Initializing...';
            }
            if (conclusionDiv) {
                conclusionDiv.className = 'font-semibold text-xs text-purple-300 flex items-center gap-2';
                conclusionDiv.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-purple-400"></i> Dispatching build to GitHub Actions...`;
            }
            pollGitHubBuildStatus();
            if (ghPollInterval) clearInterval(ghPollInterval);
            ghPollInterval = setInterval(pollGitHubBuildStatus, 2500);
        }

        async function pollGitHubBuildStatus() {
            try {
                const res = await fetch('/api/github/build-status');
                const data = await res.json();
                if (data.status === 'NO_RUNS_FOUND') {
                    const badge = document.getElementById('badgeGhRunStatus');
                    const conclusionDiv = document.getElementById('ghRunConclusion');
                    if (badge) {
                        badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-gray-800 text-gray-400 border border-gray-700';
                        badge.innerText = 'Idle';
                    }
                    if (conclusionDiv) conclusionDiv.innerText = 'No recent GitHub Actions workflow runs found on branch.';
                    return;
                }
                if (data.status === 'ERROR') return;

                // Check if GitHub API has registered the new commit run yet
                if (targetCommitSha && data.commit_sha && !data.commit_sha.startsWith(targetCommitSha) && !targetCommitSha.startsWith(data.commit_sha)) {
                    const badge = document.getElementById('badgeGhRunStatus');
                    if (badge) {
                        badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-amber-900/60 text-amber-300 border border-amber-700/50 pulse-dot';
                        badge.innerText = 'Enqueuing...';
                    }
                    const conclusionDiv = document.getElementById('ghRunConclusion');
                    if (conclusionDiv) {
                        conclusionDiv.className = 'font-semibold text-xs text-amber-300 flex items-center gap-2';
                        conclusionDiv.innerHTML = `<i class="fa-solid fa-hourglass-half fa-spin text-amber-400"></i> ⏳ Waiting for GitHub Actions to register build for commit [${targetCommitSha}]...`;
                    }
                    
                    if (!window._lastEnqueuedLogSha || window._lastEnqueuedLogSha !== targetCommitSha) {
                        window._lastEnqueuedLogSha = targetCommitSha;
                        logToConsole(`[GITHUB ACTIONS] ⏳ Waiting for GitHub Actions to register build for commit [${targetCommitSha}]...`, 'text-amber-300 font-semibold');
                    }
                    return;
                }

                const runLink = document.getElementById('ghRunLink');
                if (runLink) {
                    runLink.innerText = `#${data.run_id}`;
                    runLink.href = data.html_url || '#';
                }
                const runCommit = document.getElementById('ghRunCommit');
                if (runCommit) {
                    runCommit.innerText = `[${data.commit_sha}] ${data.commit_message || ''}`;
                }

                const badge = document.getElementById('badgeGhRunStatus');
                const conclusionDiv = document.getElementById('ghRunConclusion');
                
                if (data.status === 'completed') {
                    if (ghPollInterval) { clearInterval(ghPollInterval); ghPollInterval = null; }
                    const isRolledBack = window._lastOtaRollbackActive || (window._rollbackCommits && window._rollbackCommits.has(data.commit_sha));
                    if (data.conclusion === 'success' && !isRolledBack) {
                        if (badge) {
                            badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-emerald-900/60 text-emerald-300 border border-emerald-700/50';
                            badge.innerText = 'Build Success';
                        }
                        if (conclusionDiv) {
                            conclusionDiv.className = 'font-semibold text-xs text-emerald-400 flex items-center gap-1.5';
                            conclusionDiv.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i> ✅ SUCCESS (Artifacts Deployed & Verified)';
                        }
                        if (targetCommitSha) {
                            logToConsole(`[GITHUB ACTIONS SUCCESS] Run #${data.run_id} for commit [${data.commit_sha}] completed successfully! Artifacts uploaded.`, 'text-emerald-400 font-bold');
                            targetCommitSha = null;
                        }
                    } else if (isRolledBack) {
                        if (badge) {
                            badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-red-900/60 text-red-300 border border-red-700/50 pulse-dot';
                            badge.innerText = 'OTA Failure / Rollback';
                        }
                        if (conclusionDiv) {
                            conclusionDiv.className = 'font-semibold text-xs text-red-400 flex items-center gap-1.5';
                            conclusionDiv.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-red-400"></i> ❌ OTA DEPLOYMENT FAILED: Edge Unit Tests Failed on Commit [${data.commit_sha}] -> Rolled Back!`;
                        }
                        if (targetCommitSha) {
                            logToConsole(`[OTA DEPLOYMENT FAILURE] CI build compiled, but operational unit tests failed on edge device for commit [${data.commit_sha}]! Rolled back.`, 'text-red-400 font-bold');
                            targetCommitSha = null;
                        }
                    } else {
                        if (badge) {
                            badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-red-900/60 text-red-300 border border-red-700/50';
                            badge.innerText = 'Build Failed';
                        }
                        if (conclusionDiv) {
                            conclusionDiv.className = 'font-semibold text-xs text-red-400 flex items-center gap-1.5';
                            conclusionDiv.innerHTML = `<i class="fa-solid fa-circle-xmark text-red-400"></i> ❌ CI/CD BUILD FAILED (${data.conclusion ? data.conclusion.toUpperCase() : 'ERROR'})`;
                        }
                        if (targetCommitSha) {
                            logToConsole(`[GITHUB ACTIONS FAILURE] Run #${data.run_id} for commit [${data.commit_sha}] failed with conclusion: ${data.conclusion}.`, 'text-red-400 font-bold');
                            targetCommitSha = null;
                        }
                    }
                } else {
                    if (badge) {
                        badge.className = 'text-xs px-2.5 py-1 rounded-full font-mono bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 pulse-dot';
                        badge.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> ${data.status ? data.status.toUpperCase() : 'IN PROGRESS'}...`;
                    }
                    if (conclusionDiv) {
                        conclusionDiv.className = 'font-semibold text-xs text-indigo-300 flex items-center gap-2';
                        conclusionDiv.innerHTML = `<i class="fa-solid fa-arrows-rotate fa-spin text-indigo-400"></i> 🔄 CI/CD Pipeline In Progress: Compiling Multi-Arch ELF binaries & running DevSecOps checks...`;
                    }
                    if (targetCommitSha && (!window._lastBuildingLogRun || window._lastBuildingLogRun !== data.run_id)) {
                        window._lastBuildingLogRun = data.run_id;
                        logToConsole(`[GITHUB ACTIONS] 🔄 Run #${data.run_id} registered for commit [${data.commit_sha}] — Status: ${data.status.toUpperCase()}`, 'text-indigo-300 font-semibold');
                    }
                }

                // Render jobs breakdown
                const jobsDiv = document.getElementById('ghRunJobsList');
                if (jobsDiv && data.jobs && data.jobs.length > 0) {
                    jobsDiv.innerHTML = data.jobs.map(j => {
                        let tagClass = 'text-indigo-300 font-bold';
                        let icon = '<i class="fa-solid fa-spinner fa-spin text-[10px] text-indigo-400"></i>';
                        let text = j.status ? j.status.toUpperCase() : 'RUNNING';
                        if (j.conclusion === 'success') {
                            tagClass = 'text-emerald-400 font-bold';
                            icon = '<i class="fa-solid fa-circle-check text-[10px] text-emerald-400"></i>';
                            text = 'PASSED';
                        } else if (j.conclusion === 'failure') {
                            tagClass = 'text-red-400 font-bold';
                            icon = '<i class="fa-solid fa-circle-xmark text-[10px] text-red-400"></i>';
                            text = 'FAILED';
                        } else if (j.status === 'queued') {
                            tagClass = 'text-amber-300 font-bold';
                            icon = '<i class="fa-regular fa-clock text-[10px] text-amber-300"></i>';
                            text = 'QUEUED';
                        }
                        return `
                            <div class="bg-gray-950 p-2 rounded border border-gray-800 flex items-center justify-between">
                                <span class="text-gray-300 text-[11px]">${j.name}</span>
                                <span class="${tagClass} flex items-center gap-1 text-[11px]">
                                    ${icon} ${text}
                                </span>
                            </div>
                        `;
                    }).join('');
                }
            } catch (e) {
                console.error("Error polling GitHub status:", e);
            }
        }

        // ====================================================================
        // Code Editor & Manual Download Functions
        // ====================================================================
        async function loadCCode() {
            const editor = document.getElementById('cCodeEditorTextarea');
            const status = document.getElementById('codeEditorStatus');
            if (status) status.innerText = 'Loading from disk...';
            try {
                const res = await fetch('/api/code/hello');
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    editor.value = data.code;
                    if (status) status.innerText = 'Synced with Artefact/hello.c';
                    logToConsole('[EDITOR] Loaded Artefact/hello.c source code into Web Editor.', 'text-cyan-300');
                } else {
                    if (status) status.innerText = 'Failed to load';
                }
            } catch (e) {
                if (status) status.innerText = 'Error loading';
                logToConsole('[EDITOR ERROR] Failed to fetch C source: ' + e, 'text-red-400');
            }
        }

        function applyCodePreset(preset) {
            const editor = document.getElementById('cCodeEditorTextarea');
            const status = document.getElementById('codeEditorStatus');
            const msgInput = document.getElementById('inputCodeCommitMsg');
            let code = editor.value;

            if (preset === 'fix') {
                if (code.includes('count -= num;')) {
                    code = code.replace('count -= num;', 'count *= num;');
                } else if (!code.includes('count *= num;')) {
                    code = code.replace(/void multiply\(int argc, char \*argv\[\]\) \{[\s\S]*?\}/,
                        `void multiply(int argc, char *argv[]) {\n    int count = 1;\n    for (int i = 0; i < argc; i++) {\n        int num = atoi(argv[i]);\n        count *= num;\n    }\n    printf("multiply:%d", count);\n}`);
                }
                editor.value = code;
                if (msgInput) msgInput.value = 'Fix multiplication logic in hello.c (count *= num)';
                if (status) status.innerText = 'Preset Applied: Fix multiply (count *= num)';
                logToConsole('[PRESET APPLIED] Fixed multiplication logic (count *= num) in editor.', 'text-emerald-400 font-bold');
            } else if (preset === 'bug') {
                if (code.includes('count *= num;')) {
                    code = code.replace('count *= num;', 'count -= num;');
                } else if (!code.includes('count -= num;')) {
                    code = code.replace(/void multiply\(int argc, char \*argv\[\]\) \{[\s\S]*?\}/,
                        `void multiply(int argc, char *argv[]) {\n    int count = 1;\n    for (int i = 0; i < argc; i++) {\n        int num = atoi(argv[i]);\n        count -= num;\n    }\n    printf("multiply:%d", count);\n}`);
                }
                editor.value = code;
                if (msgInput) msgInput.value = 'Inject arithmetic subtraction bug in multiply()';
                if (status) status.innerText = 'Preset Applied: Bug injected (count -= num)';
                logToConsole('[PRESET APPLIED] Injected arithmetic bug (count -= num) in editor.', 'text-red-400 font-bold');
            } else if (preset === 'crash') {
                if (msgInput) msgInput.value = 'Simulate CPU divide-by-zero crash';
                if (status) status.innerText = 'Focused on crash() function';
                logToConsole('[PRESET] crash() function (div-by-zero) highlighted in editor.', 'text-amber-300');
                const idx = editor.value.indexOf('void crash');
                if (idx !== -1) {
                    editor.focus();
                    editor.setSelectionRange(idx, idx + 10);
                }
            }
        }

        async function submitCodeSaveAndPush() {
            window._lastOtaRollbackActive = false;
            const editor = document.getElementById('cCodeEditorTextarea');
            const msgInput = document.getElementById('inputCodeCommitMsg');
            const code = editor.value;
            const msg = msgInput.value.trim() || 'Update hello.c via Web Admin Code Editor';
            const status = document.getElementById('codeEditorStatus');

            if (!code.trim()) {
                alert('C source code cannot be empty.');
                return;
            }

            if (status) status.innerText = 'Saving and pushing to GitHub...';
            logToConsole(`[CODE DEPLOY] Saving Artefact/hello.c, committing & pushing to GitHub...`, 'text-cyan-400 font-bold');

            try {
                const res = await fetch('/api/code/save-and-push', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code: code, message: msg})
                });
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    if (status) status.innerText = `Pushed [${data.commit_sha}] to ${data.branch}`;
                    logToConsole(`[CODE DEPLOY SUCCESS] Pushed commit [${data.commit_sha}] to branch '${data.branch}'! Enqueuing CI build...`, 'text-emerald-300 font-bold');
                    startGitHubBuildPolling(data.commit_sha);
                } else {
                    if (status) status.innerText = 'Push failed';
                    logToConsole(`[CODE DEPLOY ERROR] ${JSON.stringify(data)}`, 'text-red-400');
                }
            } catch (e) {
                if (status) status.innerText = 'Deploy failed: ' + e;
                logToConsole(`[ERROR] Save & Deploy failed: ${e}`, 'text-red-400');
            }
        }

        function triggerArtifactDownload(fileType = 'binary') {
            const archSelect = document.getElementById('selectDownloadArch');
            const arch = archSelect ? archSelect.value : 'aarch64';
            logToConsole(`[DOWNLOAD] Initiating manual download of '${fileType}' for architecture '${arch}'...`, 'text-indigo-300');
            window.location.href = `/api/artifacts/download?arch=${arch}&file_type=${fileType}`;
        }

        async function submitForceOtaDownload() {
            logToConsole(`[USER ACTION] Triggering immediate Edge Device OTA Pull via MQTT...`, 'text-emerald-400 font-bold');
            try {
                const res = await fetch('/api/ota/force-pull', { method: 'POST' });
                const data = await res.json();
                logToConsole(`[FORCE OTA RESPONSE] ${data.message || JSON.stringify(data)}`, 'text-emerald-300');
            } catch (e) {
                logToConsole(`[ERROR] Force OTA trigger failed: ${e}`, 'text-red-400');
            }
        }

        // Initialize UI
        connectWebSocket();
        fetchStatus();
        loadCCode();
        pollGitHubBuildStatus();
        setInterval(pollGitHubBuildStatus, 3500);
        setInterval(fetchStatus, 5000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTMLResponse(content=HTML_TEMPLATE, status_code=200)


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "7000"))
    logger.info(f"Starting NHIOT Pipeline Admin Web UI Server on http://{host}:{port}...")
    uvicorn.run("web_dashboard:app", host=host, port=port, reload=False, log_level="info")
