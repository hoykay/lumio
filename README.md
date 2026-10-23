# Lumio

**Visual diagnostics for machine signals.**

Lumio is an agentic vision system that watches machine indicator lights, decodes temporal signal patterns, diagnoses grounded device states, recommends the next action, and visually verifies whether the intervention worked.

> **Machines already talk. Lumio lets cameras understand them.**

---

## Why Lumio

Many machines communicate through LEDs, blink patterns, colors, and timing sequences.

A single image may only show:

> amber light

But the actual diagnostic signal may be:

> amber → OFF → amber → OFF → amber → long pause

Lumio treats video as a **temporal sensor**, not just a sequence of still images.

This allows the system to reason over how a machine communicates over time.

---

## Core Loop

**SEE → DECODE → DIAGNOSE → GUIDE → VERIFY**

1. **See** — OpenCV observes a machine indicator.
2. **Decode** — Lumio measures color, blink count, ON/OFF timing, and pauses.
3. **Diagnose** — The signal is matched against grounded diagnostic profiles.
4. **Guide** — Lumio recommends the next action.
5. **Verify** — The camera re-observes the device and confirms whether recovery occurred.

---

## Demo

The current demo uses a simulated network gateway with four states:

### Healthy

- Solid green
- No active fault
- Lumio continues monitoring

### WAN Failure

- Amber
- 3 blinks
- ~0.42 s ON
- ~0.18 s short OFF
- ~1.80 s long pause

Diagnosis:

`WAN connection unavailable`

Recommended action:

`Check WAN cable connection`

### Configuration Error

- Red
- 2 blinks
- ~0.35 s ON
- ~0.25 s short OFF
- ~2.00 s long pause

Diagnosis:

`Device configuration error`

Recommended action:

`Review the device configuration`

### Unsupported Pattern

- Purple
- 4 blinks
- Complete temporal cycle
- No grounded profile match

Lumio does **not** force this signal into a known diagnosis.

Instead it:

`Abstains → escalates for human review`

---

## Agentic Vision Behavior

Lumio does more than classify what the camera sees.

Visual output determines the system's next action.

### Incomplete capture

If Lumio observes only part of a blink sequence:

`Request another observation`

Example:

> Keep the camera steady and observe one more full blink cycle.

### Grounded match

If the signal matches a known profile with sufficient confidence:

`Diagnose → recommend action`

### Complete unsupported signal

If the visual signal is clear but no known profile matches:

`Abstain → human review`

### Recovery

After an intervention:

`Re-observe → verify healthy state`

If the indicator becomes solid green for at least 1.5 seconds:

`RECOVERY VERIFIED`

---

## Example Closed Loop

```text
Camera observes WAN LED
        ↓
AMBER
3 blinks
~0.43 s ON
~0.17 s OFF
~1.97 s pause
        ↓
95% confidence
        ↓
WAN FAILURE DETECTED
        ↓
Check WAN cable connection
        ↓
User performs intervention
        ↓
Camera continues observing
        ↓
Solid GREEN
        ↓
RECOVERY VERIFIED
        ↓
Session logged to AWS
## Setup & Reproducibility

Lumio was tested with Python and the following pinned dependencies:

- OpenCV 5.0.0
- NumPy 2.5.4
- Boto3 1.43.118

Create a virtual environment and install the required packages:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the controlled evaluation:

```bash
python evaluation/run_evaluation.py
```

Run the OpenCV vision engine:

```bash
python vision/blink_detector.py
```

The browser-based signal simulator is available at:

https://lumio-theta-nine.vercel.app

AWS logging is optional for local reproduction and requires valid AWS credentials with access to the configured DynamoDB table.
