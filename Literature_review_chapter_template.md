# Chapter 2: Literature Review
**Chapter Word Budget**: 1,200 words (+/- 10%: ~1,080 to 1,320 words)  
*Use this template to write your Literature Review. Under each subheading, analyze the technological trade-offs, research existing academic papers, and draft your arguments to hit the targeted word counts.*

---

## H2: 2.1 Over-the-Air (OTA) Update Paradigms: Push vs. Pull Models (Target: ~350 words)
*Focus: Critically evaluate the architectural differences between server-push updates (like Ansible or standard SSH-based script deployments) and client-pull update agents (like Mender, balenaOS, or custom polling daemons).*

*   **The Technical Concept**: 
    *   **Push Models**: The central cloud server opens SSH/TCP connections to each edge device and forces binary updates down.
    *   **Pull Models**: The edge target runs an internal background service that periodically polls secure repositories (`Section 5.3.2`) to check for completed releases, initiating its own download.
*   **Strengths to Discuss (Positive)**:
    *   *Firewall & NAT-Traversal*: Pull models work seamlessly behind strict, private roadside corporate firewalls because the connection is initiated *outbound* from the device. This removes the massive security threat of assigning public IP addresses to roadside cameras.
    *   *Resilience & Scheduling*: Edge devices control the timing of updates, making it safe to delay downloads if local telemetry conditions are critical.
*   **Weaknesses to Discuss (Negative)**:
    *   *Deployment Latency*: Updates are not instant; they are delayed by the device's polling interval.
    *   *Edge Resource Footprint*: Requires running a continuous polling daemon locally, which consumes memory and processing cycles on the device.
*   **Academic Prompts & Citations**:
    *   *Search academic databases (Google Scholar, IEEE Xplore) for: "IoT pull-based software updates", "NAT-traversal in remote sensor networks".*
    *   *Key Question: Why does the pull model solve National Highways' requirement to avoid opening external inbound ports on roadside devices?*

---

## H2: 2.2 IoT Communication Protocols: MQTT vs. HTTP and CoAP (Target: ~300 words)
*Focus: Compare messaging protocols to defend why MQTT over AWS IoT Core is ideal for critical roadside diagnostic telemetry.*

*   **The Technical Concept**: Comparative evaluation of protocol overhead, transport layers (TCP vs. UDP), and messaging patterns (Publish/Subscribe vs. Request/Response).
*   **Strengths of MQTT (Positive)**:
    *   *Lightweight Overhead*: Packet headers are tiny (as small as 2 bytes) compared to verbose HTTP headers, saving mobile data bandwidth on cellular networks.
    *   *Pub/Sub Decoupling*: Allows multiple roadside edge devices to subscribe to distinct topics (`machineB/recv`) while a publisher listens to results (`machineA/recv`), eliminating tight client-server coupling.
    *   *Persistent Keep-Alives*: Ideal for unstable roadside wireless links.
*   **Weaknesses of MQTT (Negative)**:
    *   *TCP Handshake Overhead*: Unlike UDP-based CoAP, MQTT runs on TCP, meaning initial connection handshakes require more network round-trips.
    *   *Security Dependency*: Lacks built-in transport security, meaning it must be wrapped inside a heavy TLS socket, which increases packet size.
*   **Academic Prompts & Citations**:
    *   *Search academic databases for: "MQTT vs. HTTP energy overhead in IoT", "CoAP vs MQTT for low-bandwidth cellular telemetry".*
    *   *Key Question: How does the Pub/Sub model support National Highways' requirement to handle simultaneous bidirectional diagnostic messaging?*

---

## H2: 2.3 Edge Security Architectures: mTLS vs. Traditional Authentication (Target: ~300 words)
*Focus: Critical review of modern IoT security frameworks, using the STRIDE threat model to defend the necessity of Mutual TLS (mTLS).*

*   **The Technical Concept**: Evaluating security mechanism trade-offs (standard password MQTT vs. OAuth tokens vs. X.509 asymmetric digital certificate handshakes).
*   **Strengths of mTLS (Positive)**:
    *   *Cryptographic Dual Verification*: The client validates the server's identity, and the server validates the client's X.509 certificate. This completely blocks Man-in-the-Middle (MITM) attacks and device spoofing.
    *   *No Shared Secrets*: No passwords or API keys are stored on the edge storage that could be physically extracted if a roadside camera is compromised.
*   **Weaknesses of mTLS (Negative)**:
    *   *Computational Load*: Asymmetric cryptography (RSA/ECC handshake operations) requires high CPU and memory, which can cause latency spikes on low-cost microcontrollers.
    *   *Certificate Lifecycle Management*: Managing, distributing, and renewing thousands of digital certificates and revoking compromised keys adds massive operational complexity.
*   **Academic Prompts & Citations**:
    *   *Search academic databases for: "mTLS overhead on edge microcontrollers", "STRIDE threat model applied to Industrial IoT".*
    *   *Key Question: Why does mTLS satisfy the security demands of Critical National Infrastructure (CNI) compared to basic credential-based MQTT?*

---

## H2: 2.4 DevOps pipelines & Cross-Compilation Theory (Target: ~250 words)
*Focus: Analyze the theoretical advantages of continuous integration and cross-compilation in heterogeneous hardware clusters.*

*   **The Technical Concept**: 
    *   **Native Compilation**: Compiling code directly on the target hardware (slow and manually intensive).
    *   **Cross-Compilation**: Using a fast compiler on standard servers (`x86_64`) running specialized toolchains (`gcc-aarch64-linux-gnu`) to target foreign processor architectures (`aarch64`).
*   **Strengths of Cross-Compilation (Positive)**:
    *   *DevOps Automation*: Integrates seamlessly into CI/CD pipelines (GitHub Actions build matrix), removing human error from building binaries.
    *   *Build Speed*: Server-grade cloud runners compile code in seconds compared to low-power edge targets.
*   **Weaknesses of Cross-Compilation (Negative)**:
    *   *Toolchain Complexity*: Configuring cross-compilers, linking target-specific libraries (like glibc), and managing header files is highly error-prone.
    *   *Optimization Losses*: Cross-compilers cannot easily test native execution, sometimes leading to compilation errors that are only caught during runtime on the physical edge hardware.
*   **Academic Prompts & Citations**:
    *   *Search academic databases for: "Continuous Integration for heterogeneous IoT nodes", "Cross-compilation performance in cloud-edge architectures".*
    *   *Key Question: Why is cross-compilation a prerequisite for scaling automated software updates across varied National Highways roadside platforms?*
