# Major Project: Problem Statement & Rationale Alignment Guide
**Module**: BSc DTS Major Project (BSc Digital and Technology Solutions)  
**Author**: Amari Hussey Lawal  
**Project Application**: NHIOTPipeline  
**Focus**: Aligning Software Architecture to National Highways Operational Problems  

---

## 1. Executive Problem Statement: National Highways Context

Critical roadside IoT assets managed by National Highways (such as Automatic Number Plate Recognition (ANPR) systems, high-speed closed-circuit telemetry cameras, and weather sensors) face continuous operational, security, and maintenance challenges. 

Historically, updating the operational scripts or verifying computational health on these devices required:
1. **Manual Engineer Dispatch**: Dispatching sub-contracted technicians directly to high-risk live roadside areas.
2. **Safety & Lane Closure Risks**: Exposing personnel to high-speed motorway traffic hazards, requiring massive logistical setups and emergency warning systems.
3. **Severe Road Network Downtime**: Implementing lane closures or hard-shoulder blocks that directly increase traffic congestion and cause measurable financial loss.
4. **Platform Heterogeneity**: Dealing with a varied fleet of hardware setups, ranging from legacy low-power ARM microcontrollers (`aarch64`) to modern x86 Smart Gateways (`x86_64`).

---

## 2. Technical Alignment: How `NHIOTPipeline` Solves the Brief

The technical architecture implemented within the `NHIOTPipeline` codebase acts as a direct software solution to these four primary industrial challenges. Below is the mapping from the operational problem to your implementation architecture.

```
┌──────────────────────────────────────────────┐       ┌──────────────────────────────────────────────┐
│         National Highways Problem            │       │        NHIOTPipeline Software Solution       │
├──────────────────────────────────────────────┤       ├──────────────────────────────────────────────┤
│ 1. Safety Risks / Physical Dispatch Needs    │ ────> │ Remote, Automatic Pull-Based OTA Updates     │
│ 2. Roadside Security / MITM Hijacking        │ ────> │ Mutual TLS (mTLS) & Pydantic Sanitization    │
│ 3. Hardware Fleet Heterogeneity              │ ────> │ GitHub Actions Multi-Arch Compiler Matrix    │
│ 4. Diagnostics & Live Performance Verification│ ────> │ Dynamic C Subprocess Execution & Telemetry   │
└──────────────────────────────────────────────┘       └──────────────────────────────────────────────┘
```

---

## 3. Detailed Component-by-Component Alignment

### 3.1 Over-The-Air (OTA) Updates vs. Physical Worker Dispatch
*   **Operational Mandate**: Eliminate manual engineer physical visits to high-risk roadside zones to maintain near-zero road network disruptions.
*   **Code Implementation**: The `NHIOTSubscriber` background daemon runs locally on the edge node. It actively monitors your GitHub Actions compilation builds via a stateful loop (`monitor_workflow()`).
*   **Academic Justification**: The subscriber implements a **Pull-Based client-initiated model**. Because it establishes outbound HTTPS/MQTT connections from the roadside camera to GitHub and AWS, it naturally traverses corporate NAT/firewalls. This completely removes the necessity of assigning public IP addresses to roadside cameras (which is a massive security hazard) or dispatching humans to plug in physical update cables.

### 3.2 Secure Cloud Communication vs. Roadside Network Hijacking
*   **Operational Mandate**: Protect critical public transport infrastructure from malicious tampering or arbitrary code injection.
*   **Code Implementation**:
    *   `NHIOTMQTT` implements Mutual TLS (mTLS) leveraging standard RSA/X.509 client certificates and private keys.
    *   `CommandPayload` defines incoming commands using rigid Pydantic models.
*   **Academic Justification**: A threat model analysis (STRIDE) reveals that roadside systems are highly vulnerable to eavesdropping and data injection. Utilizing mTLS guarantees that only authentic National Highways publisher instances can issue commands. Furthermore, because incoming parameters are explicitly parsed and validated using a Pydantic model (`CommandPayload`), the device is robustly protected against remote terminal command injection vulnerabilities.

### 3.3 Handling Fleet Heterogeneity (Hardware Diversity)
*   **The Problem**: Roadside systems utilize multiple hardware platforms—some use modern x86-64 industrial PC gateways, while older cameras run on cost-effective ARM (ARM64/aarch64) SBC microcontrollers.
*   **Outline Alignment (Section 5.2.1, 5.2.2 & 5.3.3)**:
    *   **5.2.1 (Multi-Arch Build Matrix)**: Demonstrates how your GitHub Actions CI pipeline compiles parallel binaries for different architectures.
    *   **5.2.2 (Cross-compilation)** and **5.3.3 (Artifact Service)**: Show how the system is hardware-agnostic; the edge device dynamically determines its native architecture and only retrieves its corresponding compiled C executable (`hello_aarch64` vs `hello_x86_64`).
*   **Academic Justification**: Rather than managing multiple codebases or forcing manual compilation on site, your DevOps model coordinates automated targets. The edge client dynamically queries its native platform environment and updates the target executable transparently, minimizing remote management overhead and ensuring fleet consistency.

### 3.4 Zero-Downtime Telemetry Verification (Testing & Operations)
*   **The Problem**: Engineers need to run physical diagnostics (e.g. testing camera telemetry, camera filters, sensors) without causing service downtime.
*   **Outline Alignment (Section 5.4.2 & 5.5.2)**:
    *   **5.4.2 (Bidirectional MQTT Topics)**: Establishes distinct messaging pathways (`machineB/recv` and `machineA/recv`), separating commands and metrics.
    *   **5.5.2 (Native C Contract)**: Integrates standard C diagnostics (`add`, `minus`, `multiply` functions serving as lightweight processing stubs) returning formatted payloads to the caller, showcasing how live camera analytics can be queried on the fly.
*   **Academic Justification**: Standard telemetry testing must be asynchronous to prevent roadside edge crashes. The `Executor` runs these diagnostics in isolated processes (`subprocess.run`), shielding the main daemon. By structuring communications using bidirectional channels, remote administrators can trigger lightweight, in-memory diagnostic runs securely and receive validated telemetry data instantly.

---

## 4. Key Academic Terms to Use in Your Report

To maximize the quality of your academic writing, integrate the following professional DTS terminologies throughout your chapters:
1. **Critical National Infrastructure (CNI)**: Refer to your camera network as "National Highways CNI Edge Assets."
2. **NAT-Traversal / Outbound-Only Firewalls**: Describe why the subscriber's pull-based polling architecture is superior to a server-push pattern.
3. **STRIDE Threat Modeling / Attack Vector Mitigation**: Frame your Pydantic input validation and mTLS certificate handshake as crucial security mitigation implementations.
4. **Heterogeneous Device Fleets**: Describe the Raspberry Pi and Smart Gateways as "heterogeneous edge environments requiring dynamic architectural targeting."
5. **Operational Downtime Minimization**: Discuss how the automated pipeline directly supports National Highways' strategic goal to minimize road network delays and motorway lane closures.
