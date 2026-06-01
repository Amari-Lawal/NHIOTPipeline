# Chapter 1: Introduction
**Chapter Word Budget**: 600 words (+/- 10%: ~540 to 660 words)  
*Use this template to write your Introduction chapter. Review the prompts under each subheading, align with your NHIOTPipeline files, and draft your text to meet your word target.*

---

## H2: 1.1 Problem Statement & Opportunity (Target: ~150 words)
*Focus: Establish the industrial context, pain points, and opportunity for the client, setting the scene for the report.*

*   **What to write**:
    *   Introduce **National Highways** and their extensive, remote networks of CCTV, ANPR cameras, and smart motorway telemetry sensors.
    *   Detail the operational problem: manual software updates are slow, expensive, and dangerous, requiring highway contractor lane closures and exposing workers to high-speed traffic hazards.
    *   Identify the opportunity: utilizing cloud DevOps automation, containerized architectures, and secure IoT messaging protocols to execute safe, over-the-air updates remotely.
*   **Drafting Prompts**:
    *   *What are the specific hazards and economic costs associated with manual roadside device updates?*
    *   *Why do private corporate firewalls represent an opportunity to design a pull-based network architecture?*

---

## H2: 1.2 Project Aims & SMART Objectives (Target: ~250 words)
*Focus: Define the high-level aim and establish 4-5 Specific, Measurable, Achievable, Relevant, and Time-Bound (SMART) objectives.*

*   **The Primary Project Aim**: 
    *   To design and implement a secure, hardware-agnostic, and automated Over-The-Air (OTA) update and remote execution pipeline for distributed National Highways roadside edge devices.
*   **SMART Objectives to Adapt**:
    *   **Objective 1 (Specific/Measurable)**: To build a DevSecOps CI/CD compilation pipeline in GitHub Actions targeting both `x86_64` and `aarch64` targets, compiling standard binaries dynamically in under 60 seconds.
    *   **Objective 2 (Specific/Measurable)**: To design and implement a secure, pull-based Python edge subscriber daemon that polls for completed releases asynchronously.
    *   **Objective 3 (Specific/Measurable)**: To secure the messaging boundary using AWS IoT Core wrapped in Mutual TLS (mTLS) with X.509 certificates, ensuring a 100% rejection rate of unauthorized keys.
    *   **Objective 4 (Specific/Measurable)**: To implement a sandboxed subprocess execution engine (`Executor.py`) that executes compiled C diagnostics locally, keeping active device downtime under 1 second.
*   **Drafting Prompts**:
    *   *How does each objective directly link to a specific quantitative metric (latency, security rate, downtime) that you evaluated in Chapter 6?*

---

## H2: 1.3 Ethical and Data Protection Implications (Target: ~200 words)
*Focus: Address the ethical challenges and GDPR requirements of developing software for public motorway networks.*

*   **What to write**:
    *   **GDPR Data Minimization (Article 5)**: State that the project enforces strict privacy by design by using **synthetic arithmetic stubs** (`add`, `minus`, `multiply`) rather than capturing, processing, or transmitting real motorist registration plates, image feeds, or location telemetry.
    *   **Isolated Testing Safeguards**: Confirm that all evaluations were conducted in an isolated, simulated laboratory sandbox, ensuring zero risk of disrupting live National Highways traffic systems.
    *   **Secure Edge Log Management**: Explain that the edge nodes sanitize diagnostic logging, preventing credentials, network configurations, or sensitive corporate keys from printing in clear-text.
*   **Drafting Prompts**:
    *   *How does data minimization satisfy both university ethical approvals and government data protection policies?*
    *   *Why is keeping the development environment isolated critical to public transport safety?*
