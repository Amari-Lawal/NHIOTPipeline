# Major Project Report: Design & Implementation Chapter Outline
**Module**: BSc DTS Major Project (BSc Digital and Technology Solutions)  
**Author**: Amari Hussey Lawal  
**Project Application**: NHIOTPipeline (Over-The-Air IoT Update & Remote Execution Pipeline)  
**Target Word Count**: 1,333 words (+/- 10%: ~1,200 to 1,460 words)  
**Chapter Weight**: 20 Marks (20% of total mark)

---

## 1. Chapter Overview and Word Allocation

This chapter details the architectural design and actual technical implementation of the `NHIOTPipeline` system. The implementation has been divided into distinct structural layers: the CI/CD compilation pipeline, the secure messaging layer, the edge client application, and the sandboxed execution environment. 

To maintain academic rigor and stay perfectly within the **1,333-word limit**, the chapter is structured into **1 primary chapter heading (H1)**, **5 main section headings (H2)**, **10 subheadings (H3)**, and **6 sub-subheadings (H4)**:

| Heading Level | Title / Topic | Target Word Count | Percentage of Chapter |
| :--- | :--- | :---: | :---: |
| **H1 (1)** | **Chapter 5: Design and Implementation** | *N/A (Introductory)* | *N/A* |
| **H2 (1.1)** | 5.1 System Architecture & Design Rationale | ~200 words | 15% |
| **H3 (1.1.1)** | 5.1.1 Event-Driven Pull-Based OTA Architecture | ~100 words | 7.5% |
| **H3 (1.1.2)** | 5.1.2 Security-by-Design: Mutual TLS (mTLS) Model | ~100 words | 7.5% |
| **H2 (1.2)** | 5.2 Automated Compilation & DevOps CI/CD Design | ~300 words | 22.5% |
| **H3 (1.2.1)** | 5.2.1 Multi-Architecture Build Matrix Configuration | ~150 words | 11.25% |
| **H3 (1.2.2)** | 5.2.2 Cross-Compilation Toolchains (`x86_64` vs `aarch64`) | ~150 words | 11.25% |
| **H2 (1.3)** | 5.3 IoT Edge Agent (Subscriber Daemon) Architecture | ~350 words | 26.25% |
| **H3 (1.3.1)** | 5.3.1 Clean Architecture & Dependency Injection | ~100 words | 7.5% |
| **H3 (1.3.2)** | 5.3.2 Polling Loop & State Machine for OTA Updates | ~100 words | 7.5% |
| **H3 (1.3.3)** | 5.3.3 Artifact Retrieval & Integrity Verification Service | ~150 words | 11.25% |
| **H2 (1.4)** | 5.4 Secure Messaging Protocols & Data Schema | ~250 words | 18.75% |
| **H3 (1.4.1)** | 5.4.1 Pydantic-Validated Message Payload Schema | ~125 words | 9.38% |
| **H3 (1.4.2)** | 5.4.2 Bidirectional Topic Routing (`machineA` vs `machineB`) | ~125 words | 9.38% |
| **H2 (1.5)** | 5.5 Sandboxed Execution & Native Integration | ~233 words | 17.5% |
| **H3 (1.5.1)** | 5.5.1 Subprocess Spawning & Process Isolation | ~113 words | 8.5% |
| **H3 (1.5.2)** | 5.5.2 Native C Application & Interface Contract | ~120 words | 9.0% |

---

## 2. In-Depth Chapter Hierarchy and Drafting Guide

Below is the precise structure, including the exact academic angles, code files to reference, and content guidelines for each heading level.

### H1: Chapter 5: Design and Implementation
*Drafting Note: Write a brief introductory paragraph (30-50 words) stating the purpose of the chapter, outline its sections, and introduce the NHIOTPipeline design objectives (scalability, security, and hardware-agnostic cross-compilation).*

---

### H2: 5.1 System Architecture & Design Rationale (Target: ~200 words)
*Focus on the high-level design topology and the decisions made to ensure decoupling, platform flexibility, and absolute communication security.*

#### H3: 5.1.1 Event-Driven Pull-Based OTA Architecture
- **Concept**: Explain why a pull-based (subscriber polls CI/CD) update strategy was selected instead of a push-based model (server forces binary onto edge).
- **Academic Rationale**: Emphasize network resilience, NAT-traversal capabilities (since edge devices sit behind private firewalls without public IPs), and self-healing features of the edge client.

#### H3: 5.1.2 Security-by-Design: Mutual TLS (mTLS) Model
- **Concept**: Detail the decision to use **AWS IoT Core** with mutual TLS (mTLS) instead of standard username/password MQTT.
- **Academic Rationale**: Discuss STRIDE security threat mitigations. Explain the role of the cryptographic handshake, X.509 certificates (`CERT_FILE`, `PRIVATE_KEY_FILE`), and root CA verification (`CA_FILE`) in preventing eavesdropping and Man-in-the-Middle (MITM) attacks.

---

### H2: 5.2 Automated Compilation & DevOps CI/CD Design (Target: ~300 words)
*Provide the exact implementation details of the software delivery pipeline, highlighting how compiler tasks are automated.*

#### H3: 5.2.1 Multi-Architecture Build Matrix Configuration
- **File Reference**: [build.yml](file:///home/amari/Desktop/NHIOTPipeline/.github/workflows/build.yml)
- **Concept**: Discuss how the GitHub Actions runner automatically coordinates concurrent builds for heterogeneous hardware targets.
- **Key Evidence**: Highlight the YAML configuration using a build matrix to target both standard servers/desktops (`x86_64`) and low-power SBCs like Raspberry Pi (`aarch64`).

#### H3: 5.2.2 Cross-Compilation Toolchains (`x86_64` vs `aarch64`)
- **File Reference**: [build.yml:L12-36](file:///home/amari/Desktop/NHIOTPipeline/.github/workflows/build.yml#L12-L36)
- **Concept**: Explain the difference between native compilation and cross-compilation.
- **Implementation**: Describe how `gcc-aarch64-linux-gnu` is used within an Ubuntu-latest runner to build stand-alone binary files without requiring native ARM64 hardware for compilation.

---

### H2: 5.3 IoT Edge Agent (Subscriber Daemon) Architecture (Target: ~350 words)
*This is the core software design section. Explain the structure of the edge Python daemon (`NHIOTSub`).*

#### H3: 5.3.1 Clean Architecture & Dependency Injection
- **File Reference**: [container.py](file:///home/amari/Desktop/NHIOTPipeline/NHIOTSub/container.py)
- **Concept**: Discuss the use of the Dependency Injection container pattern.
- **Rationale**: Explain how decoupling services (such as logging, GitHub clients, artifact download services, and the subprocess executor) makes the codebase testable and adaptable.

#### H3: 5.3.2 Polling Loop & State Machine for OTA Updates
- **File Reference**: [NHIOTSubscriber.py](file:///home/amari/Desktop/NHIOTPipeline/NHIOTSub/subscriber/NHIOTSubscriber.py)
- **Concept**: Walk the reader through the background update lifecycle loop (`monitor_workflow`).
- **Logic**: Use a structural narrative to show how the status cycles:
  1. Poll GitHub Actions API.
  2. Parse latest run status.
  3. Trigger download when transition to `"completed"` occurs.
  4. Avoid redundant downloads via state tracking flags.

#### H3: 5.3.3 Artifact Retrieval & Integrity Verification Service
- **File Reference**: [ArtifactService.py](file:///home/amari/Desktop/NHIOTPipeline/NHIOTSub/services/ArtifactService.py)
- **Concept**: How the binary is fetched securely.
- **Details**: Explain HTTP file streaming, writing to localized filesystems under strict environment directories, and filtering by architecture flags to choose matching files.

---

### H2: 5.4 Secure Messaging Protocols & Data Schema (Target: ~250 words)
*Define how data is structured and transmitted across the public internet between the controller and the edge.*

#### H3: 5.4.1 Pydantic-Validated Message Payload Schema
- **File Reference**: [CommandPayload.py](file:///home/amari/Desktop/NHIOTPipeline/NHIOTSub/models/payloads/CommandPayload.py) and [CommandResponse.py](file:///home/amari/Desktop/NHIOTPipeline/NHIOTSub/models/responses/CommandResponse.py)
- **Concept**: Rationale for Pydantic-based data schema definition.
- **Academic Value**: Discuss input validation and sanitization as security mitigation vectors. Highlight how the deserializer acts as a guard against remote command injection by explicitly parsing the strict JSON keys `function` (string) and `parameters` (array).

#### H3: 5.4.2 Bidirectional Topic Routing (`machineA` vs `machineB`)
- **File Reference**: [NHUnitPub.py:L8-11](file:///home/amari/Desktop/NHIOTPipeline/NHIOTPub/NHUnitPub.py#L8-L11)
- **Concept**: Explain the pub-sub topic topography.
- **Details**: 
  - `machineB/recv`: Used by the test publisher to issue remote execution instructions.
  - `machineA/recv`: Used by edge subscribers to return execution outputs back to the testing controller.

---

### H2: 5.5 Sandboxed Execution & Native Integration (Target: ~233 words)
*Detail how incoming commands are safely executed at the operating system level on the target IoT hardware.*

#### H3: 5.5.1 Subprocess Spawning & Process Isolation
- **File Reference**: [Executor.py](file:///home/amari/Desktop/NHIOTPipeline/NHIOTSub/executors/Executor.py)
- **Concept**: Describe operating system operations.
- **Details**: Walk through the dynamic permission grant using `os.chmod(file_path, 0o755)` followed by spawning a separate OS-level process using Python's `subprocess.run` to isolate execution from the main subscriber loop.

#### H3: 5.5.2 Native C Application & Interface Contract
- **File Reference**: [hello.c](file:///home/amari/Desktop/NHIOTPipeline/Artefact/hello.c)
- **Concept**: The executable interface contract.
- **Details**: Detail how the native C application parses shell arguments via `int main(int argc, char *argv[])` to route calls dynamically to internal functions (e.g. `add`, `minus`, `multiply`). Highlight the interface boundary using stdout formats like `<function_name>:<result>` to permit clean parsing by the Python container parent.

---

## 3. Leaving Critical Questions Unanswered (Transition to Results)

> [!IMPORTANT]
> The assignment brief specifically states:
> *"at the end of this chapter, questions should still remain around the actual results and the overall impact of your work."*

To satisfy this academic requirement, you should end the chapter with a brief concluding paragraph (50-60 words) structured like this:
*   **Drafting Template**: 
    > *"While the structural design, deployment mechanics, and message brokers are fully implemented as described above, several fundamental operational questions remain open. Specifically, the system has not yet been subjected to quantitative evaluation regarding its end-to-end latency, packet recovery rates during connection loss, the accuracy of computational executions under load, or the practical Mean Time to Repair (MTTR) achieved during updates. These metrics, alongside the comparative performance of the system against legacy processes, will be examined and evaluated in Chapter 6 (Results & Analysis) and Chapter 7 (Critical Evaluation)."*
