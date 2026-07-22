# Welch's $t$-Test Significance Analysis: CI Build Times (Simulation Dataset)

This document records the statistical significance analysis conducted on the compilation times of the custom OTA pipeline across two target architectures: the Host Gateway (`x86_64`) and the Edge Node (`aarch64` / Raspberry Pi 4). 

The analysis is performed using **Welch's $t$-test** (unpaired two-sample $t$-test with unequal variances) to validate the compilation latency differences observed across **350 runs** (175 per cohort) from the active simulation dataset (`artifacts/dataset1_ota_performance.csv`).

---

## 1. Hypothesis Formulation

*   **Null Hypothesis ($H_0$):** $\mu_{\text{x86\_64}} = \mu_{\text{aarch64}}$  
    *There is no statistically significant difference between the mean CI build times of the two target architectures.*
*   **Alternative Hypothesis ($H_1$):** $\mu_{\text{x86\_64}} \neq \mu_{\text{aarch64}}$  
    *There is a statistically significant difference between the mean CI build times of the two target architectures.*

---

## 2. Methodology & Mathematical Formulas

Welch's $t$-test is chosen over Student's $t$-test because the two groups have different variances ($s_1^2 \neq s_2^2$).

### $t$-Statistic Formula
The $t$-statistic is calculated as:
$$t = \frac{\bar{X}_1 - \bar{X}_2}{\sqrt{\frac{s_1^2}{N_1} + \frac{s_2^2}{N_2}}}$$

Where:
*   $\bar{X}_1, \bar{X}_2$ = sample means of the two cohorts.
*   $s_1^2, s_2^2$ = sample variances (unbiased with $N-1$ degrees of freedom).
*   $N_1, N_2$ = sample sizes.

### Degrees of Freedom ($\nu$)
The degrees of freedom are approximated using the **Welch–Satterthwaite equation**:
$$\nu \approx \frac{\left(\frac{s_1^2}{N_1} + \frac{s_2^2}{N_2}\right)^2}{\frac{\left(s_1^2/N_1\right)^2}{N_1-1} + \frac{\left(s_2^2/N_2\right)^2}{N_2-1}}$$

---

## 3. High-Precision Summary Statistics

The table below outlines the statistics extracted from the active simulation dataset:

| Target Architecture Group | Sample Size ($N$) | Mean $\mu$ (sec) | Std. Dev. $\sigma$ (sec) | Variance $s^2$ |
| :--- | :---: | :---: | :---: | :---: |
| **💻 Smart Gateway (`x86_64`)** | 175 | 38.7375 | 0.9507 | 0.9038 |
| **🍓 Raspberry Pi 4 (`aarch64`)** | 175 | 42.4937 | 1.1958 | 1.4300 |

---

## 4. Welch's $t$-Test Results

The calculations yield the following results:

*   **Calculated $t$-statistic:** $-32.5255$ (or absolute $|t| = 32.5255$)
*   **Degrees of Freedom ($\nu$):** $331.1673$
*   **Two-Tailed $p$-value:** $4.6570 \times 10^{-232}$

### Significance Level Decision
With a chosen significance level $\alpha = 0.05$:
$$\text{p-value } (4.66 \times 10^{-232}) \ll \alpha \ (0.05)$$

Therefore, we **reject the null hypothesis ($H_0$)** and accept the alternative hypothesis ($H_1$). The difference in build times is **overwhelmingly statistically significant**.

---

## 5. Academic Interpretation & Architectural Rationale

The analysis shows that compiling for the `aarch64` target incurs a **$+9.70\%$** compilation latency penalty (an average increase of **$\approx 3.76\text{ seconds}$**) compared to native `x86_64` builds.

### Physical/Systems Engineering Cause:
1. **Emulation Translation Tax:** The GitHub Actions hosted runners operate natively on standard server-grade `x86_64` hardware. Building the `x86_64` binary is a direct and native task.
2. **QEMU Overhead:** To build the `aarch64` binary on the same runners, the workflow must spawn a **QEMU user-static CPU translator wrapper** to translate ARM assembly instructions on the fly. This CPU-level instruction translation layer is responsible for the statistically significant latency gap.
