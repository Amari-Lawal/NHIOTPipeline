import paramiko
import os
import json
from dotenv import load_dotenv
from scp import SCPClient

class DistributedEdgeOrchestrator:
    """
    DistributedEdgeOrchestrator manages secure remote orchestration of OTA metrics collection
    across distributed mixed-architecture hardware (e.g. Raspberry Pi 4 nodes).
    
    It coordinates SSH tunnels, manages SCP code distribution, executes on-device CPU 
    evaluation, downloads physical trials, and merges metrics into system telemetry.
    """
    
    def __init__(self, env_path="/home/amari/Desktop/NHIOTPipeline/NHIOTSub/.env"):
        self.env_path = env_path
        load_dotenv(self.env_path)
        
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.owner = os.getenv("OWNER")
        self.repo = os.getenv("REPO")
        self.workflow_id = os.getenv("WORKFLOW_ID")
        
        self._validate_config()

    def _validate_config(self):
        """Validates that all necessary environmental variables are populated."""
        if not all([self.github_token, self.owner, self.repo, self.workflow_id]):
            raise ValueError("Configuration Error: One or more environment variables missing from .env!")
        
        print("=== DISTRIBUTED EDGE ORCHESTRATION ENGINE INITIALIZED ===")
        print(f"Target Repository: {self.owner}/{self.repo} | Workflow: {self.workflow_id}")

    def generate_client_script(self) -> str:
        """
        Dynamically constructs the client-side Python execution script 
        injected with necessary GitHub API credentials and direct redirect-handling logic.
        """
        return f"""import urllib.request
import json
import time
import zipfile
import io
import os

# Credential Injection
GITHUB_TOKEN = "{self.github_token}"
OWNER = "{self.owner}"
REPO = "{self.repo}"
WORKFLOW_ID = "{self.workflow_id}"

class AuthStrippingRedirectHandler(urllib.request.HTTPRedirectHandler):
    \"\"\"Custom redirect handler to safely strip Authorization headers when GitHub redirects to AWS S3.\"\"\"
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None and "Authorization" in new_req.headers:
            new_req.remove_header("Authorization")
        return new_req

# Install redirect opener globally
opener = urllib.request.build_opener(AuthStrippingRedirectHandler)
urllib.request.install_opener(opener)

headers = {{
    "Authorization": f"Bearer {{GITHUB_TOKEN}}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "NHIOTPipeline-RPi-Eval"
}}

try:
    # Query GitHub API to fetch latest successful action run
    url = f"https://api.github.com/repos/{{OWNER}}/{{REPO}}/actions/workflows/{{WORKFLOW_ID}}/runs?per_page=1"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        runs = json.loads(resp.read().decode())["workflow_runs"]
    
    if not runs:
        raise Exception("No workflow runs found!")
        
    latest_run = runs[0]
    run_id = latest_run["id"]
    
    art_url = f"https://api.github.com/repos/{{OWNER}}/{{REPO}}/actions/runs/{{run_id}}/artifacts"
    req_art = urllib.request.Request(art_url, headers=headers)
    with urllib.request.urlopen(req_art) as resp:
        artifacts = json.loads(resp.read().decode())["artifacts"]
        
    target_name = "hello_aarch64"
    artifact = next((a for a in artifacts if a["name"] == target_name), None)
    
    if not artifact:
        raise Exception(f"Artifact '{{target_name}}' not found on GitHub!")
        
    dl_url = artifact["archive_download_url"]
    
    download_times = []
    extract_times = []
    sizes = []
    
    os.makedirs("./temp_rpi_eval", exist_ok=True)
    
    # Execute 10 consecutive trials to build a physical baseline average
    for i in range(1, 11):
        t_start = time.perf_counter()
        req_dl = urllib.request.Request(dl_url, headers=headers)
        with urllib.request.urlopen(req_dl) as resp:
            content = resp.read()
        t_dl = time.perf_counter() - t_start
        download_times.append(t_dl)
        sizes.append(len(content) / 1024)
        
        t_ext_start = time.perf_counter()
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            z.extractall("./temp_rpi_eval")
        t_ext = time.perf_counter() - t_ext_start
        extract_times.append(t_ext)
        
        print(f"  [Trial {{i:02d}}] Download: {{t_dl:.3f}}s | Extraction: {{t_ext:.4f}}s | Size: {{sizes[-1]:.1f}} KB")
        
    results = {{
        "size": sum(sizes) / len(sizes),
        "dl": sum(download_times) / len(download_times),
        "ext": sum(extract_times) / len(extract_times)
    }}
    
    with open("rpi_metrics.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("SUCCESS: Physical metrics recorded locally in 'rpi_metrics.json'")
except Exception as e:
    print(f"ERROR executing RPi benchmark: {{e}}")
"""

    def execute_remote_eval(self, ip, username, password, local_script_path="rpi_run_eval.py"):
        """
        Deploys and executes the benchmark suite on the remote hardware unit 
        over secure SSH, fetching raw data back upon completion.
        """
        # Write client-side script locally first
        script_content = self.generate_client_script()
        with open(local_script_path, "w") as f:
            f.write(script_content)
            
        print(f"\n[1/4] Writing local client wrapper: {local_script_path}")
        
        # Configure SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            print(f"[2/4] Connecting SSH to {username}@{ip}...")
            ssh.connect(ip, username=username, password=password, look_for_keys=False, allow_agent=False)
            print("      Secure SSH connection established!")
            
            # SCP upload
            print("[3/4] Uploading execution code to edge node...")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(local_script_path, f"/home/{username}/rpi_run_eval.py")
            print("      Upload completed successfully.")
            
            # Execution
            print("[4/4] Executing benchmark suite on remote edge architecture...")
            stdin, stdout, stderr = ssh.exec_command(f"python3 /home/{username}/rpi_run_eval.py")
            
            for line in stdout:
                print(f"      [RPi4] {line.strip()}")
                
            # Download results
            print("\nRetrieving physical edge telemetry...")
            with SCPClient(ssh.get_transport()) as scp:
                scp.get(f"/home/{username}/rpi_metrics.json", "/home/amari/Desktop/NHIOTPipeline/artifacts/rpi_metrics.json")
            print("      Physical metrics downloaded.")
            
            # Remote Cleanup
            ssh.exec_command(f"rm /home/{username}/rpi_run_eval.py")
            print("      Remote cleanup complete.")
            
        except Exception as e:
            print(f"Orchestration Error: {e}")
            raise
        finally:
            ssh.close()
            if os.path.exists(local_script_path):
                os.remove(local_script_path)

    def merge_telemetry_metrics(self, rpi_json="artifacts/rpi_metrics.json", system_json="artifacts/evaluation_metrics.json"):
        """Merges downloaded physical telemetry metrics into the global evaluation database."""
        print("\n==================================================")
        print("MERGING REMOTE TELEMETRY INTO GLOBAL SYSTEM DB")
        print("==================================================")
        
        with open(rpi_json, "r") as f:
            rpi_metrics = json.load(f)
            
        with open(system_json, "r") as f:
            metrics = json.load(f)
            
        metrics["rpi_dataset_1"] = {
            "size": rpi_metrics["size"],
            "dl": rpi_metrics["dl"],
            "ext": rpi_metrics["ext"]
        }
        
        with open(system_json, "w") as f:
            json.dump(metrics, f, indent=4)
            
        print("Telemetry merge complete! System metrics populated successfully.")

if __name__ == "__main__":
    # Demonstration of programmatic API usage
    orchestrator = DistributedEdgeOrchestrator()
    # To run:
    # orchestrator.execute_remote_eval("192.168.1.11", "amari", "kya63amari")
    # orchestrator.merge_telemetry_metrics()
