1. Eliminating Field Engineer Dispatch (Aims & Objectives) $
The Problem: Motorway closures and physical worker exposure to high-speed roadside environments are dangerous and financially inefficient. Updates must happen remotely.
Outline Alignment (Section 5.1.1 & 5.3.2):
5.1.1 (Pull-Based OTA) details how the system is designed to bypass private roadside firewalls without needing public IP addresses (NAT-traversal) by having the device check for updates itself.
5.3.2 (Subscriber Polling State Machine) demonstrates how the edge subscriber tracks workflow runs in real-time, executing background downloads asynchronously without interrupting roadside operation or requiring human intervention.
2. Protecting Critical National Infrastructure (Security & Risk)
The Problem: Roadside ANPR/CCTV devices constitute critical national infrastructure. A hijacked update loop could lead to major network-wide cyber-attacks or data breaches.
Outline Alignment (Section 5.1.2 & 5.4.1):
5.1.2 (Mutual TLS with AWS IoT) explains how X.509 digital certificates and mTLS ensure that only verified National Highways testing servers can trigger executions, mitigating STRIDE vulnerabilities.
5.4.1 (Pydantic-Validated Data Schemas) enforces strict schema validation. This acts as a primary software guard, sanitizing and parsing inputs to guarantee that attackers cannot inject arbitrary terminal commands into the camera subprocesses.
3. Handling Fleet Heterogeneity (Hardware Diversity)
The Problem: Roadside systems utilize multiple hardware platforms—some use modern x86-64 industrial PC gateways, while older cameras run on cost-effective ARM (ARM64/aarch64) SBC microcontrollers.
Outline Alignment (Section 5.2.1, 5.2.2 & 5.3.3):
5.2.1 (Multi-Arch Build Matrix) demonstrates how your GitHub Actions CI pipeline compiles parallel binaries for different architectures.
5.2.2 (Cross-compilation) and 5.3.3 (Artifact Service) show how the system is hardware-agnostic; the edge device dynamically determines its native architecture and only retrieves its corresponding compiled C executable (hello_aarch64 vs hello_x86_64).
4. Zero-Downtime Telemetry Verification (Testing & Operations)
The Problem: Engineers need to run physical diagnostics (e.g. testing camera telemetry, camera filters, sensors) without causing service downtime.
Outline Alignment (Section 5.4.2 & 5.5.2):
5.4.2 (Bidirectional MQTT Topics) establishes distinct messaging pathways (machineB/recv and machineA/recv), separating commands and metrics.
5.5.2 (Native C Contract) integrates standard C diagnostics (add, minus, multiply functions serving as lightweight processing stubs) returning formatted payloads to the caller, showcasing how live camera analytics can be queried on the fly.
