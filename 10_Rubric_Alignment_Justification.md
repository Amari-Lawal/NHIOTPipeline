# Academic Rubric Alignment & High-Grade Justification
**Module**: BSc DTS Major Project & EPA 1.2 (QAC030X345 - Level 6)  
**Author**: Amari Hussey Lawal  
**Project Application**: NHIOTPipeline  
**Focus**: Academic Mapping to the 80% to 100% (Outstanding / First-Class) Grade Band  

---

## 1. Rubric Verification: Why This Alignment Secures a First-Class Grade

To secure the highest mark band (80% to 100%) under the **University of Roehampton BSc Digital & Technology Solutions Major Project marking rubric**, the project must show deep, specialized academic integration and clear organizational value. 

Below is the justification mapping showing how your code and templates satisfy the grading descriptors.

---

### Task 1: Introduction (10 Marks)
*   **Grade Band Goal**: *Outstanding introduction which documents the aim and objectives of the project and incorporates any ethical implications.*
*   **Alignment Strategy (01_Introduction_Chapter_Template.md)**:
    *   **SMART Objectives**: Defines four clear, measurable milestones (CI build speed under 60s, client outbound polling connection limits, X.509 mTLS encryption rate, and subprocess device downtime under 1s).
    *   **Ethics & GDPR**: Incorporates **UK GDPR compliance (Data Minimization - Article 5)** by documenting the use of synthetic math stubs (`add`, `minus`, `multiply`) over live motorist registration database or camera feeds.

### Task 2: Literature Review (15 Marks)
*   **Grade Band Goal**: *Outstanding literature review which documents the current research in this field well. The relevance to their own project has also been well explained.*
*   **Alignment Strategy (02_Literature_Review_Chapter_Template.md)**:
    *   **Pull vs. Push Updates**: Evaluates Server-Push (Ansible, SSH) vs. Client-Pull (Mender, custom edge daemons) architectures to justify NAT-traversal behind private corporate firewalls.
    *   **Protocol Evaluation**: Critically compares **MQTT vs. HTTP vs. CoAP** (overhead, payload sizes, TCP vs. UDP).
    *   **Security Frameworks**: Reviews Mutual TLS (mTLS) certificates, applying the **STRIDE threat model** to Critical National Infrastructure.
    *   **DevOps Pipelines**: Reviews the theory of multi-architecture cross-compilation toolchains (`gcc-aarch64`).

### Task 3: Methodology (10 Marks)
*   **Grade Band Goal**: *Outstanding approach which documents the rationale behind selecting the chosen methodologies.*
*   **Alignment Strategy (03_Methodology_Chapter_Template.md)**:
    *   **DevSecOps SDLC**: Justifies combining Agile Scrum sprint cycles with continuous integration (CI) automation matrix builds.
    *   **Decoupled Architecture**: Explains the rationale of Clean Architecture and Dependency Injection (`container.py`) to isolate systems.
    *   **Scientific Testing**: Justifies shifting from manual verification to programmatic E2E automated unittest assertions (`NHUnitPub.py`) to record empirical metrics.

### Task 4: Design and Implementation (20 Marks)
*   **Grade Band Goal**: *Outstanding review of how the project was designed and implemented.*
*   **Alignment Strategy (04_Design_and_Implementation_Template.md & README.md)**:
    *   **Mermaid Visualizations**: Integrates highly scalable, parallel edge fleet Mermaid diagrams showing dual architecture routing (`aarch64` and `x86_64`) over secure mTLS channels.
    *   **Code Rationales**: Documents the exact software implementation blocks: Pydantic parameter deserialization validators, process subprocess permissions `os.chmod 0o755`, and native C diagnostics, ending on the required transition to results.

### Task 5: Results and Analysis (15 Marks)
*   **Grade Band Goal**: *The learner has described and analysed the results outstandingly. The testing methods have been discussed well with appropriate levels of justification.*
*   **Alignment Strategy (05_Results_and_Analysis_Template.md)**:
    *   **Quantitative Datasets**: Outlines 4 distinct, scientific testing tables:
        *   *Dataset 1*: 30 deployments measuring edge sync latency and active hot-swap downtime (**0.16 seconds** average).
        *   *Dataset 2*: 100 attack vectors (rejections of malicious payloads and unauthorized certificates).
        *   *Dataset 3*: 20 forced network dropouts (proving automatic socket reconnection in **3.5 seconds**).
        *   *Dataset 4*: 100 E2E RTT latency diagnostic query runs.
    *   **Ethics**: Details data minimization logs and GDPR-compliant simulated data boundaries.

### Task 6: Critical Evaluation of Results (10 Marks)
*   **Grade Band Goal**: *The learner has critically evaluated the impact of the project outstandingly well along with how the aims and objectives have been met.*
*   **Alignment Strategy (06_Critical_Evaluation_Template.md)**:
    *   **Operational Client Value**: Maps technical results to National Highways strategic business value:
        *   *HSE Safety*: How zero dispatches support the *"Home Safe and Well"* corporate framework.
        *   *Financial ROI*: How 0.16s active downtime avoids lane closures and gridlock penalties.
    *   **Limitations & Self-Reflection**: Honestly evaluates critical limits (GitHub Actions API rate scaling, remote sector cellular bandwidth constraints, and the necessity of passing formal National Highways TASS Type Approvals).

### Task 7: Further Work (10 Marks)
*   **Grade Band Goal**: *The learner has identified what the next steps for their project could be, outstandingly well.*
*   **Alignment Strategy (07_Further_Work_Template.md)**:
    *   **OCI Container Registries**: Scaling edge distribution to 10,000+ nodes using AWS ECR.
    *   **Binary Diff-Patching**: Compiling differential byte-level diff patches (`bsdiff`) to cut payload data sizes by 80% on remote roads.
    *   **ANPR Diagnostics**: Transitioning simple math stubs to run live edge character-segmentation stubs.
    *   **Track HIL Testing**: Coordinating track hardware-in-the-loop tests for TASS certification.
