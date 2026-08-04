#!/usr/bin/env python3
import base64
import os

import requests

# Define the Mermaid code templates
diagram_horizontal = """graph LR
    %% Styling Definitions
    classDef actor fill:#e17055,stroke:#d63031,stroke-width:2px,color:#ffffff;
    classDef cicd fill:#1f1e33,stroke:#6c5ce7,stroke-width:2px,color:#ffffff;
    classDef registry fill:#2d1b4e,stroke:#a29bfe,stroke-width:2px,color:#ffffff;
    classDef mqtt fill:#132d2f,stroke:#00cec9,stroke-width:2px,color:#ffffff;
    classDef edge fill:#1e272e,stroke:#ffeaa7,stroke-width:2px,color:#ffffff;
    classDef audit fill:#2d3436,stroke:#dfe6e9,stroke-width:2px,color:#ffffff;
    classDef elf fill:#2f3542,stroke:#747d8c,stroke-width:1px,stroke-dasharray: 3 3,color:#ffffff;

    Developer([Developer / DevSecOps]):::actor
    Operator([System Administrator]):::actor

    subgraph Management ["Server Audit & Management Plane"]
        PubSuite["Publisher Command Suite<br>(switch_branch, send_revert, send_crash)"]:::audit
        FleetAudit["Server Fleet Audit Daemon<br>(server_subscriber.py)"]:::audit
    end

    subgraph MQTT_Broker ["MQTT Topics"]
        CmdTopic["nhiot/fleet/command<br>(SET_BRANCH / TRIGGER_REVERT / Execute Task)"]:::mqtt
        ResTopic["nhiot/fleet/response<br>(Execution Output & Diagnostic stdout/stderr)"]:::mqtt
        OTATopic["nhiot/ota/status<br>(OTAStatusPayload telemetry: SUCCESS / ROLLBACK)"]:::mqtt
        HBTopic["nhiot/heartbeat<br>(HeartbeatPayload 15s pulse)"]:::mqtt
        IsoTopic["nhiot/isolation/status<br>(Crash telemetry: PROTECTED returncode)"]:::mqtt
    end

    subgraph IoT_Edge ["Autonomous IoT Edge Device Gateway"]
        subgraph Daemon_Core ["NHIOTSubscriber Class (Core Thread)"]
            SubClient["Subscriber Client"]:::edge
            GHClient["GitHub REST API Client"]:::edge
            IntegritySvc["Artifact Integrity Check Service<br>(SHA-256 & ELF Header Parser)"]:::edge
            TestSuite["Post-Pull Operational Test Gate<br>(add, minus, multiply checks)"]:::edge
            Executor["Process Isolation Boundary<br>(Subprocess Spawn Wrapper)"]:::edge
            Watchdog["Heartbeat Watchdog Daemon"]:::edge
            
            subgraph Exec_Context ["Isolated Executable Process"]
                HardenedELF["Hardened C Executable<br>(hello_x86_64 / hello_aarch64)"]:::elf
            end
        end
    end

    subgraph GitHub_Registry ["Artifact Delivery Registry"]
        RepoArtifacts["GitHub Run Artifacts Registry"]:::registry
        GithubAPI["GitHub Action Run API"]:::registry
    end

    subgraph CI_CD ["CI/CD Pipeline Plane (GitHub Actions)"]
        GitPush["Git Push / PR"]:::cicd --> Security["DevSecOps Security Scans<br>(Trivy, Cppcheck, Gitleaks)"]:::cicd
        Security --> Compiler["GCC Cross-Compiler<br>(Hardening flags: -fstack-protector-strong)"]:::cicd
        Compiler --> Packager["Checksum Generator & Archiver<br>(ZIP + SHA-256)"]:::cicd
    end

    %% Human actor interactions
    Operator -->|Dispatches CLI commands| PubSuite
    Developer -->|Pushes updates| GitPush

    %% Command flow: Admin -> MQTT
    PubSuite -.->|Publish commands| CmdTopic
    %% Command delivery: MQTT -> Edge
    CmdTopic -.->|Subscribe| SubClient

    %% Edge execution: SubClient -> GHClient -> GitHub Registry
    GHClient -->|HTTPS REST: Poll Workflow Runs| GithubAPI
    RepoArtifacts -->|HTTPS REST: Download ZIP| GHClient
    Packager -->|HTTPS Upload| RepoArtifacts

    %% Local validation & execution
    SubClient -->|Validates bytes| IntegritySvc
    SubClient -->|Verifies arithmetic| TestSuite
    SubClient -->|Executes active binary in| Executor
    Executor -->|Hot Swaps and monitors| HardenedELF
    
    %% Self-healing logic connections
    TestSuite -.->|FAIL: Triggers history rollback request| GHClient
    Watchdog -.->|FAIL 3 consecutive: Triggers emergency rollback| GHClient

    %% Edge response / telemetry publication: Edge -> MQTT
    SubClient -.->|Publish OTA Results| OTATopic
    SubClient -.->|Publish execution output| ResTopic
    Executor -.->|Publish crash protection status| IsoTopic
    Watchdog -->|Publishes health| HBTopic

    %% Telemetry delivery: MQTT -> Admin / Management
    ResTopic -.->|Deliver responses| FleetAudit
    HBTopic -.->|Deliver heartbeats| FleetAudit
    OTATopic -.->|Deliver OTA results| FleetAudit
    IsoTopic -.->|Deliver crash events| FleetAudit

    class Management,MQTT_Broker,IoT_Edge,GitHub_Registry,CI_CD default;
"""

diagram_vertical = diagram_horizontal.replace("graph LR", "graph TD")

# Destination folders
output_dir = "./Artefact"
os.makedirs(output_dir, exist_ok=True)


def generate_assets(mermaid_code, prefix, width):
    svg_path = os.path.join(output_dir, f"{prefix}.svg")
    png_path = os.path.join(output_dir, f"{prefix}.png")

    # 1. SVG via Kroki
    try:
        response_svg = requests.post("https://kroki.io/mermaid/svg", data=mermaid_code)
        if response_svg.status_code == 200:
            with open(svg_path, "wb") as f:
                f.write(response_svg.content)
            print(f"Successfully generated SVG: {svg_path}")
        else:
            print(f"Failed to generate SVG: {response_svg.status_code}")
    except Exception as e:
        print(f"Error generating SVG for {prefix}: {e}")

    # 2. PNG via mermaid.ink (with scale=3)
    try:
        encoded_bytes = base64.b64encode(mermaid_code.encode("utf-8"))
        encoded_str = encoded_bytes.decode("utf-8")
        ink_url = f"https://mermaid.ink/img/{encoded_str}?scale=3&width={width}"

        response_png = requests.get(ink_url)
        if response_png.status_code == 200:
            with open(png_path, "wb") as f:
                f.write(response_png.content)
            print(f"Successfully generated 3x PNG: {png_path}")
        else:
            print(f"Failed to generate PNG: {response_png.status_code}")
    except Exception as e:
        print(f"Error generating PNG for {prefix}: {e}")


print("Rendering Horizontal Diagram (graph LR)...")
generate_assets(diagram_horizontal, "system_architecture_horizontal", width=1200)

print("\nRendering Vertical Diagram (graph TD)...")
# Vertical TD layout fits portrait documents better, so we use a narrower width to optimize aspect ratio rendering
generate_assets(diagram_vertical, "system_architecture_vertical", width=800)
