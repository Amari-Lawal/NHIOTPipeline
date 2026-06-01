import asyncio
import os
import sys
import pandas as pd
import json
import logging
from typing import Generator
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Dynamically determine the project root and add to sys.path for robust imports
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(current_dir)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NHIOTFastAPI")

app = FastAPI(
    title="NHIOTPipeline Examiner Center",
    description="Full-stack FastAPI server managing edge nodes, real-time unbuffered sub-processes, and quantitative rubric assets.",
    version="2.0.0"
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global trackers for active subprocesses
active_sub_process = None
sub_stdout_queue = asyncio.Queue()

# Ensure artifacts directory is mounted
artifacts_dir = os.path.join(PROJECT_ROOT, "artifacts")
if not os.path.exists(artifacts_dir):
    os.makedirs(artifacts_dir, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=artifacts_dir), name="artifacts")

# Helper to read unbuffered subprocess output lines
async def read_stream(stream, queue):
    while True:
        line = await stream.readline()
        if not line:
            break
        await queue.put(line.decode("utf-8"))

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dashboard_path = os.path.join(current_dir, "dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail="dashboard.html not found")
    with open(dashboard_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# --- Process Control APIs ---

@app.post("/api/sub/start")
async def start_subscriber():
    global active_sub_process, sub_stdout_queue
    if active_sub_process and active_sub_process.returncode is None:
        return {"status": "running", "message": "Subscriber is already active."}
    
    # Flush existing queue
    while not sub_stdout_queue.empty():
        sub_stdout_queue.get_nowait()
        
    try:
        # Launch subscriber daemon in unbuffered mode (-u) to guarantee real-time line streams
        python_executable = os.path.join(PROJECT_ROOT, "venv/bin/python")
        if not os.path.exists(python_executable):
            python_executable = sys.executable
        active_sub_process = await asyncio.create_subprocess_exec(
            python_executable, "-u", "-m", "NHIOTSub.main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=PROJECT_ROOT
        )
        
        # Read stdout in a non-blocking background task
        asyncio.create_task(read_stream(active_sub_process.stdout, sub_stdout_queue))
        logger.info(f"Subscriber daemon started with PID {active_sub_process.pid}")
        return {"status": "started", "pid": active_sub_process.pid}
    except Exception as e:
        logger.error(f"Failed to start subscriber: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to launch subscriber: {str(e)}")

@app.post("/api/sub/stop")
async def stop_subscriber():
    global active_sub_process
    if not active_sub_process or active_sub_process.returncode is not None:
        return {"status": "stopped", "message": "Subscriber is already terminated."}
        
    try:
        active_sub_process.terminate()
        await active_sub_process.wait()
        logger.info("Subscriber process terminated successfully.")
        return {"status": "stopped", "message": "Subscriber terminated successfully."}
    except Exception as e:
        logger.error(f"Error terminating subscriber: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping process: {str(e)}")

@app.get("/api/sub/logs")
async def stream_subscriber_logs():
    global active_sub_process, sub_stdout_queue
    
    async def log_generator():
        # Yield connection success/logs so frontend sees instant feed
        yield "data: [SYSTEM] Connected to active daemon standard output.\n\n"
        while True:
            try:
                line = await asyncio.wait_for(sub_stdout_queue.get(), timeout=1.0)
                yield f"data: {line}\n\n"
            except asyncio.TimeoutError:
                # If process died, break stream
                if active_sub_process and active_sub_process.returncode is not None:
                    yield "data: [SYSTEM] Process exited.\n\n"
                    break
                # Keep-alive ping
                yield ": keep-alive\n\n"
                
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/api/sub/status")
async def get_subscriber_status():
    global active_sub_process
    if active_sub_process and active_sub_process.returncode is None:
        return {"status": "active", "pid": active_sub_process.pid}
    return {"status": "inactive"}

@app.post("/api/sub/dropout")
async def simulate_outage_dropout():
    global active_sub_process, sub_stdout_queue
    if not active_sub_process or active_sub_process.returncode is not None:
        raise HTTPException(status_code=400, detail="Subscriber is not active.")
        
    try:
        # 1. Terminate the active subscriber process (physically cuts the mTLS connection!)
        active_sub_process.terminate()
        await active_sub_process.wait()
        logger.info("Outage simulation: Terminated active subscriber to sever mTLS connection.")
        
        # 2. Wait for a simulated outage duration (2 seconds)
        await asyncio.sleep(2.0)
        
        # 3. Flush the queue
        while not sub_stdout_queue.empty():
            sub_stdout_queue.get_nowait()
            
        # 4. Restart the subscriber daemon (starts mTLS connection handshake with AWS!)
        python_executable = os.path.join(PROJECT_ROOT, "venv/bin/python")
        if not os.path.exists(python_executable):
            python_executable = sys.executable
        active_sub_process = await asyncio.create_subprocess_exec(
            python_executable, "-u", "-m", "NHIOTSub.main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=PROJECT_ROOT
        )
        
        # Read stdout in a background task
        asyncio.create_task(read_stream(active_sub_process.stdout, sub_stdout_queue))
        logger.info(f"Outage recovery: Restarted subscriber daemon with PID {active_sub_process.pid}")
        
        return {"status": "recovered", "pid": active_sub_process.pid}
    except Exception as e:
        logger.error(f"Error during outage simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Outage simulation failed: {str(e)}")

@app.get("/api/maturity")
async def get_maturity_assessment():
    try:
        maturity_file_path = os.path.join(PROJECT_ROOT, "nist_maturity_assessment.md")
        if not os.path.exists(maturity_file_path):
            maturity_file_path = os.path.join(PROJECT_ROOT, "Thesis", "nist_maturity_assessment.md")
        if not os.path.exists(maturity_file_path):
            raise HTTPException(status_code=404, detail="nist_maturity_assessment.md file not found")
        with open(maturity_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"markdown": content}
    except Exception as e:
        logger.error(f"Error reading maturity assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tests/run")
async def run_unit_tests():
    # Stream the real-time execution of the unittest discovery
    async def test_execution_generator():
        yield "data: [INFO] Initializing unittest suite runner...\n\n"
        yield "data: [INFO] Command: python -m unittest discover -s NHIOTPub/tests -t .\n\n"
        
        try:
            # Run the unbuffered unittest discover
            python_executable = os.path.join(PROJECT_ROOT, "venv/bin/python")
            if not os.path.exists(python_executable):
                python_executable = sys.executable
            process = await asyncio.create_subprocess_exec(
                python_executable, "-u", "-m", "unittest", "discover", "-s", "NHIOTPub/tests", "-t", ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=PROJECT_ROOT
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8")
                yield f"data: {decoded_line}\n\n"
                # Small pause to allow concurrent frontend rendering
                await asyncio.sleep(0.01)
                
            rc = await process.wait()
            yield f"data: \n\n"
            if rc == 0:
                yield "data: [SUCCESS] ALL UNIT TESTS COMPLETED SUCCESSFULLY! (Exit Code 0)\n\n"
            else:
                yield f"data: [ERROR] Unit test suite failed with non-zero exit code: {rc}\n\n"
        except Exception as e:
            yield f"data: [CRITICAL EXCEPTION] Failed to run test runner: {str(e)}\n\n"
            
    return StreamingResponse(test_execution_generator(), media_type="text/event-stream")


# --- Empirical Data APIs ---

@app.get("/api/datasets/{name}")
async def get_csv_dataset(name: str):
    # Mapping dataset names to their respective generated CSV paths
    file_map = {
        "dataset1": os.path.join(PROJECT_ROOT, "artifacts/dataset1_ota_performance.csv"),
        "dataset2": os.path.join(PROJECT_ROOT, "artifacts/dataset2_security_sanitization.csv"),
        "dataset3": os.path.join(PROJECT_ROOT, "artifacts/dataset3_network_interruption.csv"),
        "dataset4": os.path.join(PROJECT_ROOT, "artifacts/dataset4_e2e_diagnostic.csv"),
        "dataset5": os.path.join(PROJECT_ROOT, "artifacts/dataset5_operational_cost.csv"),
        "dataset6": os.path.join(PROJECT_ROOT, "artifacts/dataset6_self_healing_savings.csv")
    }
    
    if name not in file_map:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    csv_path = file_map[name]
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail=f"CSV file '{csv_path}' has not been generated yet.")
        
    try:
        df = pd.read_csv(csv_path)
        # Handle possible NaN values to prevent JSON parse errors
        df = df.fillna("")
        records = df.to_dict(orient="records")
        columns = list(df.columns)
        return {
            "dataset": name,
            "columns": columns,
            "data": records
        }
    except Exception as e:
        logger.error(f"Error reading CSV {csv_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse dataset CSV: {str(e)}")

@app.get("/api/evaluation/metrics")
async def get_evaluation_metrics():
    metrics_path = os.path.join(PROJECT_ROOT, "artifacts/evaluation_metrics.json")
    if not os.path.exists(metrics_path):
        raise HTTPException(status_code=404, detail="evaluation_metrics.json not found")
    with open(metrics_path, "r") as f:
        data = json.load(f)
    return data

@app.post("/api/ota/trigger")
async def trigger_ota_git_push():
    try:
        from NHIOTSub.config import Envs
        
        # 1. Run git status to see if there are any changes
        status_proc = await asyncio.create_subprocess_exec(
            "git", "status", "--porcelain",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await status_proc.communicate()
        has_changes = len(stdout.strip()) > 0
        
        # 2. Add and commit changes or allow-empty
        if has_changes:
            # Commit local changes
            add_proc = await asyncio.create_subprocess_exec(
                "git", "add", ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await add_proc.communicate()
            
            commit_proc = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", "Auto-trigger OTA: live deployment update",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            # Commit empty
            commit_proc = await asyncio.create_subprocess_exec(
                "git", "commit", "--allow-empty", "-m", "Auto-trigger OTA: matrix compile [CI Skip]",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
        c_stdout, c_stderr = await commit_proc.communicate()
        c_rc = await commit_proc.wait()
        if c_rc != 0:
            c_err = c_stderr.decode("utf-8").strip()
            logger.warning(f"Git commit process returned code {c_rc}: {c_err}")
        
        # 3. Push commit to remote branch
        branch = Envs.BRANCH or "main"
        push_proc = await asyncio.create_subprocess_exec(
            "git", "push", "origin", branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        p_stdout, p_stderr = await push_proc.communicate()
        p_rc = await push_proc.wait()
        
        if p_rc != 0:
            err_msg = p_stderr.decode("utf-8").strip()
            raise Exception(f"Git push failed: {err_msg}")
            
        # 4. Get the latest commit hash that was pushed
        hash_proc = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD",
            stdout=asyncio.subprocess.PIPE
        )
        h_stdout, _ = await hash_proc.communicate()
        commit_hash = h_stdout.decode("utf-8").strip()
        
        return {
            "status": "success",
            "commit_hash": commit_hash,
            "has_changes": has_changes
        }
    except Exception as e:
        logger.error(f"Failed to trigger Git-push OTA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ota/status")
async def get_ota_workflow_status(sha: str = None):
    try:
        from NHIOTSub.config import Envs
        from NHIOTSub.config import Config
        import requests
        
        workflow_url = (
            f"{Config.BASE_URL}"
            f"{Envs.OWNER}/{Envs.REPO}"
            f"/actions/workflows/{Envs.WORKFLOW_ID}/runs"
        )
        
        response = requests.get(
            workflow_url,
            headers=Config.GITHUB_HEADERS,
            params={"per_page": 10}
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("workflow_runs"):
            return {"status": "unknown", "message": "No workflow runs found"}
            
        target_run = None
        if sha:
            # Look for the run matching the pushed commit SHA
            for run in data["workflow_runs"]:
                run_sha = run.get("head_sha", "")
                if run_sha == sha or run_sha.startswith(sha) or sha.startswith(run_sha):
                    target_run = run
                    break
            
            # If no run has registered for this SHA yet, it is still queued/registering
            if not target_run:
                return {
                    "status": "queued",
                    "conclusion": None,
                    "run_number": None,
                    "html_url": None,
                    "message": "Commit registered, waiting for GitHub runner allocation..."
                }
        else:
            target_run = data["workflow_runs"][0]
            
        return {
            "status": target_run.get("status"),
            "conclusion": target_run.get("conclusion"),
            "run_number": target_run.get("run_number"),
            "html_url": target_run.get("html_url")
        }
    except Exception as e:
        logger.error(f"Error checking workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sub/publish_command")
async def publish_sub_command(payload: dict):
    try:
        from NHIOTMQTT.NHIOTMQTT import NHIOTMQTT
        
        client = NHIOTMQTT()
        client.connect(verbose=False)
        client.publish(json.dumps(payload), topic="machineB/recv", verbose=False)
        await asyncio.sleep(0.5)
        client.disconnect(verbose=False)
        return {"status": "published"}
    except Exception as e:
        logger.error(f"Error publishing command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8000)
