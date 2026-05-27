# Chapter 4: Methodology
**Chapter Word Budget**: 1,000 words (+/- 10%: ~900 to 1,100 words)  
*Use this template to write your Methodology chapter. Review the positive and negative prompts under each subheading, align with your NHIOTPipeline files, and draft your text to meet your word target.*

---

## H2: 4.1 Software Development Lifecycle (SDLC) Framework (Target: ~300 words)
*Focus: Detail the structured software engineering process (Agile DevSecOps vs. traditional approaches) used to plan, compile, and execute your pipeline.*

*   **Positive / Selection Rationale**:
    *   Explain why a **DevSecOps continuous integration (CI) methodology** (using GitHub Actions) was selected over traditional Waterfall development.
    *   Detail how the matrix-compilation approach allowed you to build parallel sprints for diverse hardware platforms (`x86_64` and `aarch64`) concurrently.
    *   Discuss the Agile Scrum method: breaking tasks into rapid sprint loops (e.g., local C compiling first, followed by AWS IoT broker integration, and final E2E subscriber automation).
*   **Negative / SDLC Trade-offs**:
    *   Acknowledge that pure Agile assumes complete hardware decoupling. Because you had to test on physical target boards (Raspberry Pi), hardware procurement delays and physical connection dropouts limited fast sprint cycles.
*   **Drafting Prompts**:
    *   *How did the automated CI matrix (`main.yml`) support rapid feedback loops during sprint cycles?*
    *   *Why was a DevSecOps methodology necessary given the critical security needs of roadside highway infrastructure?*

---

## H2: 4.2 Architectural Design Methodology & Choices (Target: ~250 words)
*Focus: Defending your software engineering patterns—Clean Architecture, Dependency Injection, and Language selection.*

*   **Positive / Selection Rationale**:
    *   **Clean Decoupled Architecture**: Explain the decision to separate the messaging client, target executor, and application configuration. This ensured components could be tested in isolation.
    *   **Dependency Injection**: Justify using `container.py` to inject instances (like the MQTT client and Executor service). This allows you to hot-swap simulated stubs in local unit tests.
    *   **Language Selection**: Defend why **Python** was chosen for high-level daemon orchestration (due to rich libraries like AWS CRT and Pydantic) and **C** for the execution module (due to native compile speed, minimal memory foot-print, and direct access to roadside hardware).
*   **Negative / Architectural Trade-offs**:
    *   Decoupling via dependency injection containers increases initialization overhead and adds software complexity, which could be an issue for highly resource-constrained, legacy 8-bit edge microcontrollers.
*   **Drafting Prompts**:
    *   *How does Clean Architecture support the long-term maintainability of National Highways edge assets?*
    *   *Why is Dependency Injection superior to hard-coding configuration values within the subscriber files?*

---

## H2: 4.3 Testing Methodology & Scientific Evaluation (Target: ~250 words)
*Focus: Explain the scientific, repeatable methods you used to gather metrics, verify operations, and evaluate security.*

*   **Positive / Selection Rationale**:
    *   **Automated E2E Unit Testing**: Detail how your publisher test harness (`NHUnitPub.py`) programmatically sends commands over mTLS, executes them natively on the remote subscriber node, and asserts output responses to verify arithmetic accuracy.
    *   **Simulated Stress and Attack Vectors**: Detail your scientific testing of dropouts (Dataset 3) and injection attacks (Dataset 2) to gather empirical success rates rather than relying on manual console logs.
*   **Negative / Testing Limitations**:
    *   Simulating network drops and attacks inside a sandbox environment cannot fully capture live high-speed roadside challenges (such as electrical power surges, heavy rain signal attenuation, or physical cabinet vandalism).
*   **Drafting Prompts**:
    *   *Why is programmatic test assertion (`NHUnitPub`) superior to manual CLI debugging for distributed edge gateways?*
    *   *How does scientific exception testing prove the robustness of the C execution sandbox (`Executor.py`)?*

---

## H2: 4.4 Ethical and Data Protection Methodology (Target: ~200 words)
*Focus: Establish the rigorous ethical boundaries, privacy-by-design standards, and GDPR compliance frameworks applied during research.*

*   **Positive / Selection Rationale**:
    *   **GDPR Data Minimization (Article 5)**: Emphasize that your methodology utilizes **synthetic parameters** (`add`, `minus`, `multiply`) rather than extracting live vehicle registration plates, camera images, or telemetry feeds from motorway sensors.
    *   **Isolated Sandbox Boundaries**: The system was tested in a local, secure laboratory environment with stubbed AWS endpoints, preventing any security threats to National Highways' operational systems.
    *   **Log Sanitization**: Local diagnostic logging on the subscriber nodes blocks the printing of plain-text passwords or secret system credentials, preventing administrative credential leaks.
*   **Negative / Ethical Trade-offs**:
    *   Using synthetic stubs removes ethical risks, but it means the evaluation metrics lack the performance load characteristics of processing raw high-definition video frames or real live telemetry streams.
*   **Drafting Prompts**:
    *   *How does the methodology satisfy the Roehampton BSc Digital & Technology Solutions major project ethical guidelines?*
    *   *Why is privacy-by-design critical when developing edge systems for public motorways?*
