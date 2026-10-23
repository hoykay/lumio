# Lumio Architecture

## Overview

Lumio is a visual diagnostic agent that reads temporal machine indicator signals, reasons over device state, recommends the next action, re-observes the device, and verifies recovery.

The system is designed around a closed-loop agentic vision workflow:

**SEE → DECODE → DIAGNOSE → GUIDE → VERIFY**

---

## System Architecture

```mermaid
flowchart LR

    A[Camera / Phone Feed]
    --> B[OpenCV 5 Vision Engine]

    B --> C[Indicator ROI]

    C --> D[Color Classification]

    C --> E[Temporal Signal Extraction]

    E --> F[Blink Count]

    E --> G[ON / OFF Timing]

    E --> H[Long Pause Detection]

    D --> I[Signal Feature Vector]
    F --> I
    G --> I
    H --> I

    I --> J[Grounded Signal Profile Matcher]

    J --> K{Confidence + Exact Match?}

    K -->|Yes| L[Diagnosis]

    K -->|Incomplete Capture| M[Request Re-observation]

    K -->|Unsupported Pattern| N[Human Review / Abstain]

    L --> O[Recommended Action]

    O --> P[User Intervention]

    P --> Q[OpenCV Re-observation]

    Q --> R{Solid Green Sustained?}

    R -->|Yes| S[Recovery Verified]

    R -->|No| T[Continue Monitoring]

    S --> U[AWS DynamoDB Session Log]