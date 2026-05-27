# NHIOT Pipeline
To start in on terminal run the subscriber which would be the Raspberry Pi or IOT. Make sure that in Github actions the correct aarch/x86_64 compiler is installed.
```
./run_sub.py
```
Then first build the artifact with this will build the artifact, in the NHSub window it should say "Downloading artifact 'hello_x86'...":
```
./build_artifact.sh
```

Then run the publisher which will be the main device. This would be the admin that wants to test the executable from a distance with unittests.
```
./run_pub.sh
```

When creating a function to test in the C artefact ensure that it prints out to the stdout using:
```
printf("add:%d", count);
```
For error handling to send an error to the publisher use:
```
fprintf(stderr, "add: no arguments provided\n");
```
Ensure that  the string is in the format of:
```
printf("<function_name>:<result>", count);

```
and
```
fprintf(stderr, "<function_name>:<error_message>");

```
## Limitations 
So far two out of three architectures have been developed for:
1. Desktop x86_64 
2. Embedded Linux - Raspbery Pi and ARM devices.
3. MicroControllers - Can be done but requires refactor from python to C.
Libraries Needed for Microcontrollers
1. awscrt Python -> AWS CRT (C Libraries)
2. awsiot (Python SDK v2) -> AWS IoT Embedded C SDK
3. requests (Python) -> C Equivalent.


## System Architecture
An end-to-end, Over-the-Air (OTA) update and execution system designed for IoT edge nodes. It integrates automated cross-compilation pipelines, secure cloud messaging via AWS IoT Core, and distributed executable unit testing on target hardware architectures (e.g., Raspberry Pi, ARM, and Desktop Linux).

### Architecture Diagram

```mermaid
flowchart TD
    %% Node Styling Definitions
    classDef devStyle fill:#EFF6FF,stroke:#3B82F6,stroke-width:2px,stroke-dasharray: 5 5;
    classDef gitStyle fill:#F3F4F6,stroke:#4B5563,stroke-width:2px;
    classDef awsStyle fill:#FFFBEB,stroke:#F59E0B,stroke-width:2px;
    classDef edge1 fill:#ECFDF5,stroke:#10B981,stroke-width:2px;
    classDef edge2 fill:#F0FDFA,stroke:#0D9488,stroke-width:2px;
    classDef edge3 fill:#F0FDF4,stroke:#16A34A,stroke-width:2px;
    classDef pubStyle fill:#FDF2F8,stroke:#EC4899,stroke-width:2px;

    %% Subgraphs
    subgraph CI_CD ["CI/CD Pipeline & GitHub Automation"]
        Developer["Developer Workstation<br>(hello.c update)"]:::devStyle
        GH_Actions["GitHub Actions CI Workflow"]:::gitStyle
        GH_Artifacts["GitHub Build Artifacts<br>(hello_x86_64 / hello_aarch64)"]:::gitStyle
    end

    subgraph AWS_Core ["Cloud Messaging (AWS IoT Core)"]
        AWS_IoT["AWS IoT Core Broker<br>(Secure mTLS Connect)"]:::awsStyle
        Topic_B["Topic: machineB/recv<br>(Function Commands)"]:::awsStyle
        Topic_A["Topic: machineA/recv<br>(Execution Results)"]:::awsStyle
    end

    subgraph Control_Center ["Control & Verification (Publisher)"]
        Pub_Client["NHUnitPub Unit Tester<br>(Admin/Testing Suite)"]:::pubStyle
    end

    %% Device 1 Subgraph
    subgraph Edge_Device_1 ["IoT Edge Device 1 (Raspberry Pi - aarch64)"]
        Sub_Daemon_1["NHIOTSubscriber Daemon 1"]:::edge1
        Artifact_Service_1["Artifact Service 1"]:::edge1
        Local_Binary_1["Local C Binary<br>(hello_aarch64)"]:::edge1
        MQTT_Handler_1["MQTT Message Handler 1"]:::edge1
        Executor_1["Executor Service 1"]:::edge1
    end

    %% Device 2 Subgraph
    subgraph Edge_Device_2 ["IoT Edge Device 2 (Smart Gateway - x86_64)"]
        Sub_Daemon_2["NHIOTSubscriber Daemon 2"]:::edge2
        Artifact_Service_2["Artifact Service 2"]:::edge2
        Local_Binary_2["Local C Binary<br>(hello_x86_64)"]:::edge2
        MQTT_Handler_2["MQTT Message Handler 2"]:::edge2
        Executor_2["Executor Service 2"]:::edge2
    end

    %% Device 3 Subgraph
    subgraph Edge_Device_3 ["IoT Edge Device 3 (Industrial PC - aarch64)"]
        Sub_Daemon_3["NHIOTSubscriber Daemon 3"]:::edge3
        Artifact_Service_3["Artifact Service 3"]:::edge3
        Local_Binary_3["Local C Binary<br>(hello_aarch64)"]:::edge3
        MQTT_Handler_3["MQTT Message Handler 3"]:::edge3
        Executor_3["Executor Service 3"]:::edge3
    end

    %% CI/CD Flow
    Developer -->|1. Git Push Code| GH_Actions
    GH_Actions -->|2. Multi-Arch Compile| GH_Artifacts
    
    %% OTA Update Flow
    Sub_Daemon_1 -->|3a. Polls Workflow| GH_Actions
    Sub_Daemon_2 -->|3b. Polls Workflow| GH_Actions
    Sub_Daemon_3 -->|3c. Polls Workflow| GH_Actions

    GH_Artifacts -->|4a. Downloads aarch64| Artifact_Service_1
    GH_Artifacts -->|4b. Downloads x86_64| Artifact_Service_2
    GH_Artifacts -->|4c. Downloads aarch64| Artifact_Service_3

    Artifact_Service_1 -->|5a. Installs| Local_Binary_1
    Artifact_Service_2 -->|5b. Installs| Local_Binary_2
    Artifact_Service_3 -->|5c. Installs| Local_Binary_3

    %% Message Flow - Execution Request
    Pub_Client -->|6. Publishes Request| Topic_B
    
    Topic_B -->|7a. Delivers Command| MQTT_Handler_1
    Topic_B -->|7b. Delivers Command| MQTT_Handler_2
    Topic_B -->|7c. Delivers Command| MQTT_Handler_3
    
    %% Execution Flow on Edge 1
    MQTT_Handler_1 -->|8a. Invokes| Executor_1
    Executor_1 -->|9a. Runs| Local_Binary_1
    Local_Binary_1 -->|10a. Returns| Executor_1
    Executor_1 -->|11a. Parses| MQTT_Handler_1

    %% Execution Flow on Edge 2
    MQTT_Handler_2 -->|8b. Invokes| Executor_2
    Executor_2 -->|9b. Runs| Local_Binary_2
    Local_Binary_2 -->|10b. Returns| Executor_2
    Executor_2 -->|11b. Parses| MQTT_Handler_2

    %% Execution Flow on Edge 3
    MQTT_Handler_3 -->|8c. Invokes| Executor_3
    Executor_3 -->|9c. Runs| Local_Binary_3
    Local_Binary_3 -->|10c. Returns| Executor_3
    Executor_3 -->|11c. Parses| MQTT_Handler_3
    
    %% Message Flow - Execution Response
    MQTT_Handler_1 -->|12a. Publishes Response| Topic_A
    MQTT_Handler_2 -->|12b. Publishes Response| Topic_A
    MQTT_Handler_3 -->|12c. Publishes Response| Topic_A

    Topic_A -->|13. Delivers Result| Pub_Client
    
    %% Association connections
    AWS_IoT -.-> Topic_B
    AWS_IoT -.-> Topic_A
```

### Component Details

1. **CI/CD Pipeline (GitHub Actions)**:
   - Compiles C executable code targeting multiple architectures (`x86_64` and `aarch64`) dynamically on commit to the `main` branch.
   - Uploads compiled platform-specific executables as workflow build artifacts.
2. **OTA Update Subscriber (Edge Daemon)**:
   - Polling daemon running locally on the edge device that tracks GitHub workflow statuses.
   - Automatically downloads, verifies, and launches newly compiled binaries dynamically upon successful completion of a remote build.
3. **AWS IoT Core Message Broker**:
   - Manages secure, bidirectional communication between the central controller and the edge devices using MQTT over mutual TLS (mTLS) authentication.
4. **Edge Execution Subprocess**:
   - Spawns the native C binary securely, executing request-driven business logic (`add`, `minus`, `multiply`) and formatting results (`stdout` and `stderr`) into a unified JSON format validated by **Pydantic**.
5. **Publisher Controller**:
   - Remote client triggering test execution, injecting payloads containing targeting functions and variables, and asserting the output from the edge device.


# TODO 
1. Determine testing metrics like *Mean Time To Repair (MTTR)* and Mean Time Between Failures (MTBF).
2. Make automated tests and analytics data points for metric making sure it aligns with the brief specifcation.
3. Make or choose a more complex functions in the artifact and parameters and use them for metrics and datapoints
#  TODO Meh
1. Automate AWSMqtt Authentication and Policy creation process.
Here you go, Amari — clear, concrete, numerically measurable testing, analysis, and evaluation methods you can use in your Results & Analysis and Critical Evaluation chapters. These will map cleanly to your OTA-update IoT pipeline project and help you produce strong, evidence‑based results.

I’ll give you:

SMART metrics you can measure
Testing and analysis methods you can apply
How to present numeric results
Critical evaluation angles
✅ 1. SMART Numerical Metrics You Can Use
System Performance Metrics
Goal
SMART Version
Example Measurement
Reduce manual update time
Reduce average manual update time from X minutes to under Y minutes per update by May 2025
Time benchmarks before & after solution
Increase update success rate
Achieve ≥ 98% OTA update success rate across N test runs by final demo week
Pass/fail logs
Reduce device downtime
Reduce device downtime during update from legacy average (e.g., 2 min) to ≤ 10 seconds by project completion
Measured via device heartbeat logs
Quality & Reliability Metrics
Goal
SMART Version
Measurement Method
Improve software reliability
Ensure ≥ 90% unit test coverage of update-related functions using automated GitHub Actions before submission
Coverage report
Detect update-related defects earlier
Achieve 100% automated test execution for every commit by integrating CI pipeline
GitHub Actions logs
Reduce update-caused failures
Target 0 critical failures and ≤ 2 minor fails across 30 OTA update test cycles
Error logs and device telemetry
Network & Deployment Metrics
Goal
SMART Version
Measurement Method
Measure dead-zone resilience
Ensure device reconnects and resumes update within ≤ 5 seconds after a forced signal drop
Network simulation tests
Measure update package size efficiency
Compress update bundles to ≤ X MB to meet bandwidth constraints
File size logs
✅ 2. Methods You Can Use to Analyse Your Results
Below are specific, academically acceptable methods tied to your project.

A. Quantitative System Testing (Core for Your Project)
1. Automated CI/CD Test Results (Unit Test Analytics)
You already automated unit tests — now analyse:

Number of test cases run
Number of tests passed/failed
Coverage percentage
Trends across commits (e.g., decreasing failures)
How to display:
Line charts, bar charts, coverage heatmaps, failure rate percentages.

2. OTA Update Time Benchmarks
Run repeated update cycles (e.g., 30 runs) and record:

Start → finish time
Verification time
Device reboot time
Downtime intervals
How to analyse:

Mean, median, standard deviation
Box-plot to show variation
Compare with manual update baseline
3. Failure Rate & Reliability Testing
For each OTA update iteration:

Did it succeed?
If failed, what stage?
Error type classification
Compute:

MTBF — Mean Time Between Failures
Failure Rate %
Recovery time
This is gold for an engineering-style report.

4. Network Interruption Testing
Simulate:

Weak signal
Total drop
Packet loss
Partial update failure
Measure:

Recovery time
Partial update handling
Package integrity checks success
Use bar graphs to show % recoveries under different conditions.

B. Comparative Evaluation
Compare:

Legacy Manual Process vs Your Automated Pipeline
Criterion
Manual
Automated
Improvement
Time to update
e.g., 20 mins
2 mins
90% faster
Human resource cost
1 contractor
0
100% reduction
Device downtime
2 mins
10 sec
92% reduction
Success rate
85%
98%
+13%
Error detection
None
Unit tests + CI
Major benefit
Graphs + tables = strong marks.

C. Risk Analysis (Quantitative)
Measure risk severity before and after automation.
Use a Risk Matrix with numerical scoring:

Likelihood (1–5)
Impact (1–5)
Risk = L × I
Example:

Risk
Before
After
Update failure
20
5
Downtime
15
3
Contractor dependency
25
0
This gives compelling numerical evidence.

D. Ethical & Data Protection Considerations
Focus on:

No live ANPR or personal data used
Only synthetic or stubbed telemetry
GDPR compliance
Secure handling of device logs
Controlled test environment
This is required for marks.

✅ 3. How to Display Your Analysis in Your Report
Use clean, measurable displays:

Graphs
OTA update time comparison (bar chart)
Test coverage increase over time (line graph)
Failure rate under different network conditions (bar or pie chart)
Tables
SMART objective progress
Comparison of manual vs automated processes
Error type frequency distribution
Diagrams
Workflow of OTA pipeline
Sequence diagram of update process
Statistical Methods
Averages
Standard deviation
Confidence intervals
Boxplots for variability
✅ 4. Critical Evaluation of Results (What You Can Say)
This answers the “So what?” part of your brief.

Discuss:

What worked well
Significant reduction in time and human labour
CI/CD enforcing higher code quality
Reliable automated recovery mechanisms
Near-zero downtime prototype performance
What didn’t work or needs improvement
Limited real-world device diversity
Only tested under controlled network simulations
Hardware constraints of the legacy IoT device
No integration with National Highways real backend systems
Impact on operational area
Removes need for field engineer dispatch
Cuts maintenance cost per camera
Reduces road network downtime
Scales across thousands of devices
Supports safer, more reliable roadside systems
Remaining Questions (your brief requires this!)
How would this scale to millions of deployed devices?
Can the OTA system handle security updates for critical systems?
How does this integrate with National Highways’ central platform?
What regulatory approvals would be required?
These questions show "room for future research," which the brief expects.

✅ Want me to create your Results & Analysis chapter or Critical Evaluation chapter?
I can write them in academic style, properly structured, and tailored to your exact project.
Just say “write my Results & Analysis chapter” or “write my Critical Evaluation section”.



Test