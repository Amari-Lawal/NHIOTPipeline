# Executive Summary
**Length Constraint**: Max 1 page (Suggested: 300 to 450 words)  
**Chapter Weight**: No Word Count (Must be comprehensible to non-technical stakeholders)  
*Use this template to write your Executive Summary. Summarize the business challenge, the software engineering solution, and the key quantitative findings in three distinct paragraphs.*

---

### Paragraph 1: The Business Challenge & Operational Context
*Focus: Introduce the client, the critical roadside assets, and the operational pain points (safety, cost, congestion).*

*   **What to write**: 
    *   State that **National Highways** is responsible for maintaining critical roadside assets (ANPR cameras, CCTV, telemetry sensors) across England's motorways.
    *   Explain that manual, on-site engineer dispatches for software updates represent a major operational risk: exposing contractors to high-speed roadside traffic, incurring high mobilization fees, and causing traffic delays due to lane closures.
*   **Drafting Prompts**:
    *   *What are the safety and financial liabilities of manually updating roadside edge nodes?*
    *   *How does motorway congestion directly impact the national economy?*

---

### Paragraph 2: The Technical Solution (NHIOTPipeline)
*Focus: Briefly outline your architecture, DevOps pipeline, and secure messaging layer.*

*   **What to write**:
    *   Detail the development of `NHIOTPipeline`—a secure, pull-based Over-The-Air (OTA) update and remote execution system.
    *   Explain how the DevOps pipeline leverages **GitHub Actions** to cross-compile architecture-specific binaries (`hello_x86_64` and `hello_aarch64`) dynamically in the cloud.
    *   Describe the use of **AWS IoT Core** wrapped in **Mutual TLS (mTLS)** cryptography to establish secure, bidirectional communication with edge targets.
*   **Drafting Prompts**:
    *   *Why was a client-pull model selected instead of server-push SSH scripts?*
    *   *How does the background edge subscriber daemon safely execute binaries in process isolation?*

---

### Paragraph 3: Key Quantitative Findings & Client ROI
*Focus: Document the core results of your testing and the strategic return on investment (ROI) for National Highways.*

*   **What to write**:
    *   Document your quantitative achievements: active edge hot-swap downtime is reduced to just **0.16 seconds**, completely eliminating lane closures.
    *   State that the system achieved a **100% success rate** in rejecting malicious inputs (via Pydantic schemas) and unauthorized client connections (mTLS).
    *   Highlight that connection dropouts are resolved asynchronously, reconnecting secure sockets in under **3.5 seconds** with a **100% download resume success rate**.
    *   Conclude that this project successfully fulfills National Highways' *"Home Safe and Well"* directive, delivering robust cost savings and high infrastructure availability.
*   **Drafting Prompts**:
    *   *What are the exact metrics (downtime, security rejection, reconnection speed) that validate success?*
    *   *In final terms, how does this application revolutionize roadside edge maintenance for the client?*
