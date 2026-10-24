# Lumio  
## An Agentic Visual Diagnostic System for Machine Indicator Signals

### Abstract

Lumio is a visual diagnostic agent that uses OpenCV 5 to interpret machine indicator lights as temporal signals rather than isolated images.

Many devices communicate operational state through LED color, blink count, timing, and pause duration. These signals are simple for an experienced technician to recognize but can be difficult for users to interpret consistently, especially when documentation is unavailable or the observation begins midway through a blink sequence.

Lumio converts those visual signals into a closed diagnostic loop:

**SEE → DECODE → DIAGNOSE → GUIDE → VERIFY**

The system observes an indicator through a camera, extracts temporal behavior with OpenCV, compares the observed signal with known diagnostic profiles, handles uncertainty by re-observing or escalating rather than forcing a diagnosis, recommends an appropriate corrective action, and continues observing until recovery can be verified.

Verified sessions can be recorded to AWS DynamoDB to provide an auditable history of faults, interventions, and recovery.

---

## 1. Problem

Machine indicator lights are a compact diagnostic interface used across routers, industrial equipment, appliances, embedded systems, medical equipment, and other hardware.

A single LED can encode several dimensions of information:

- color
- blink count
- ON duration
- OFF duration
- long pauses
- repetition pattern
- transition to a healthy state

Traditional computer-vision classification often treats each frame independently. That approach is insufficient for signals where meaning depends on behavior over time.

For example, an amber light alone may not identify a fault. Three amber flashes followed by a long pause may represent a specific condition.

Lumio therefore treats the indicator as a **temporal visual signal**.

---

## 2. Core System Loop

Lumio follows five stages.

### SEE

OpenCV captures frames from the camera and monitors a user-selected indicator region.

### DECODE

The vision engine extracts:

- whether the LED is ON or OFF
- dominant LED color
- ON duration
- short OFF duration
- long pause duration
- blink count

These observations are accumulated across time to form a signal pattern.

### DIAGNOSE

The observed pattern is compared with known diagnostic profiles.

Lumio generates a confidence score based on how closely the observed timing, color, and blink behavior match the expected profile.

The system does not assume that every observation must produce a diagnosis.

### GUIDE

When sufficient evidence exists, Lumio provides the associated recommended action.

For the current WAN failure profile:

**Diagnosis:** WAN connection unavailable  
**Recommended action:** Check the WAN cable connection.

### VERIFY

Lumio continues observing after the recommended intervention.

If the indicator transitions to sustained green for the required period, Lumio verifies that the fault has cleared.

This creates a closed loop rather than stopping after classification.

---

## 3. OpenCV 5 Vision Pipeline

OpenCV 5 performs the runtime visual perception for Lumio.

The pipeline begins when the user draws a region of interest around the indicator.

Each frame within that region is converted from BGR to HSV color space. A mask isolates illuminated LED pixels, and the ratio of active pixels determines whether the indicator is currently ON or OFF.

Hysteresis thresholds and minimum stable-state timing reduce noise around state transitions.

When an ON/OFF transition is confirmed, Lumio measures the duration of the previous state.

For ON states, Lumio records:

- LED color
- ON duration
- blink count

For OFF states, it distinguishes short inter-blink gaps from long pauses that mark the end of a complete signal cycle.

A completed cycle is then passed to the signal decoder.

The vision pipeline therefore converts continuous video into structured temporal observations instead of attempting to diagnose directly from a single frame.

---

## 4. Agentic Vision Behavior

Lumio is designed so that visual perception changes what the system does next.

It does not follow a fixed sequence regardless of evidence.

### Grounded match

When the observed signal closely matches a known profile, Lumio produces a diagnosis and recommended intervention.

### Incomplete or ambiguous observation

If the confidence is insufficient, Lumio does not force the closest diagnosis.

It can instead request another full observation cycle.

This is particularly important when the camera begins observing halfway through an existing blink sequence.

### Unsupported signal

When a complete pattern does not safely correspond to a known diagnostic profile, Lumio classifies it as an unknown signal and can route it toward human review rather than fabricating an answer.

### Recovery

Once a fault has been diagnosed, the system remains aware of the active fault and continues observing the indicator.

A sustained healthy green signal changes the system's state from active fault to verified recovery.

This provides a direct perception-to-decision loop:

**visual observation → confidence decision → diagnostic action → continued observation → recovery decision**

---

## 5. Example WAN Failure Flow

A representative WAN failure signal consists of:

**Color:** Amber  
**Blinks:** 3  
**Approximate ON duration:** 0.47–0.50 seconds  
**Short OFF duration:** approximately 0.13–0.17 seconds  
**Long pause:** approximately 1.9 seconds

When this complete pattern is observed, Lumio identifies:

**WAN FAILURE DETECTED**

Diagnosis:

**WAN connection unavailable**

Recommended action:

**Check the WAN cable connection.**

Lumio then continues monitoring.

When the indicator becomes sustained green, the system outputs:

**RECOVERY VERIFIED**

and clears the active WAN fault.

---

## 6. Uncertainty and Human Control

Diagnostic systems should not treat uncertainty as certainty.

Lumio therefore includes explicit abstention behavior.

During camera-in-the-loop testing, observation began partway through a repeating WAN pattern. The first captured cycle appeared to contain four amber blinks rather than the expected three.

The resulting confidence was approximately 78.8%.

Lumio classified the observation as:

**UNKNOWN SIGNAL**

instead of incorrectly assigning the WAN failure diagnosis.

After another complete cycle was observed, the pattern contained the expected three blinks and produced approximately 93% matching confidence.

Lumio then issued the WAN diagnosis.

This behavior demonstrates that additional visual evidence can change the subsequent system decision.

---

## 7. Controlled Evaluation

Lumio includes a reproducible controlled evaluation containing 120 simulated observations.

The benchmark compares Lumio against a fixed baseline that always selects the nearest known diagnostic profile and cannot abstain.

Results:

| Metric | Fixed Baseline | Lumio |
|---|---:|---:|
| Baseline diagnostic accuracy / Lumio safe decision rate | 66.7% | 95.0% |
| Unsafe diagnosis rate on unknown patterns | 100.0% | 0.0% |

Lumio also produced:

**8 re-observation requests**

and

**46 human-review escalations**

during the controlled evaluation.

These results demonstrate the intended safety behavior of the decision logic under the synthetic benchmark.

They are **controlled simulation results and should not be interpreted as real-world field accuracy**.

---

## 8. Camera-in-the-Loop Validation

Lumio was also sanity-tested end-to-end through a live camera feed while observing the browser-based signal simulator.

During repeated complete WAN cycles, the OpenCV vision engine measured approximately:

- 3 amber blinks
- 0.43–0.50 second ON periods
- 0.13–0.17 second short OFF periods
- approximately 1.9 second long pauses

Complete cycles produced WAN-profile matching confidence of approximately **91–93%** during the recorded tests.

The system also demonstrated the expected uncertainty behavior when capture began during an incomplete sequence.

After the indicator was changed to the healthy state, Lumio detected sustained green, verified recovery, cleared the active WAN fault, and recorded the successful session to AWS.

This validation is intended as a **functional camera-in-the-loop sanity test**, not a claim of broad device compatibility or general real-world diagnostic accuracy.

---

## 9. Recovery Verification

Classification alone does not demonstrate whether the recommended intervention solved the problem.

Lumio therefore treats recovery as a separate perception task.

After a fault is active, the vision engine continues monitoring the selected indicator.

If OpenCV detects sustained green for at least the configured healthy interval, Lumio reports:

**RECOVERY VERIFIED**

The corresponding fault state is cleared only after visual evidence of recovery has been observed.

A later improvement also prevents sustained healthy green from being incorrectly interpreted as a new blink sequence.

---

## 10. AWS Integration

Lumio uses AWS DynamoDB as an optional persistence layer for verified diagnostic sessions.

When recovery is confirmed, the system records a session containing information such as:

- detected signal
- confidence
- recommended or performed action
- result
- device
- session identifier

The current implementation has successfully written and retrieved Lumio session records from the DynamoDB table.

AWS therefore acts as an audit and observability layer rather than performing the core visual diagnosis.

The OpenCV perception loop remains functional locally without requiring AWS logging.

---

## 11. Architecture

The system consists of four main layers.

**Signal source / physical indicator**

The observed machine or signal simulator produces visual LED behavior.

↓

**OpenCV 5 perception engine**

Camera frames are converted into color, state, timing, and blink observations.

↓

**Diagnostic and agentic decision layer**

Lumio performs profile matching, confidence assessment, abstention, re-observation, escalation, intervention guidance, and recovery-state management.

↓

**AWS observability layer**

Verified sessions can be recorded to DynamoDB for audit and later analysis.

The browser interface provides a demonstration environment for the currently implemented signal profiles.

The public web interface does not replace the local OpenCV camera runtime.

---

## 12. Reproducibility

The project repository includes pinned Python dependencies.

Tested versions:

**OpenCV:** 5.0.0  
**NumPy:** 2.5.4  
**Boto3:** 1.43.118

A clean virtual environment was created from `requirements.txt`.

All three dependencies installed successfully and imported with the expected versions.

The controlled evaluation was then executed from that new environment and reproduced the expected benchmark results.

The primary commands are:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python evaluation/run_evaluation.py
python vision/blink_detector.py
```

---

## 13. Public Resources

**Live browser demonstration**

https://lumio-theta-nine.vercel.app

**Source repository**

https://github.com/hoykay/lumio

The repository contains:

- OpenCV vision engine
- camera test
- browser signal simulator
- evaluation script
- evaluation results
- architecture documentation
- reproducible dependency specification

---

## 14. Current Limitations

Lumio is currently a competition prototype rather than a production diagnostic platform.

The implemented diagnostic library contains a limited number of known signal profiles.

The current evaluation is primarily controlled and synthetic, supplemented by camera-in-the-loop functional testing.

Performance has not yet been validated across large numbers of physical device models, camera types, viewing angles, lighting conditions, reflections, LED geometries, or environmental conditions.

The current profile-matching approach also depends on predefined diagnostic signal definitions.

These limitations are intentional and visible rather than hidden behind unsupported accuracy claims.

---

## 15. Responsible Operation

Lumio is designed around uncertainty-aware behavior.

When visual evidence is incomplete or unsupported, the preferred behavior is to gather more evidence or request human review rather than force a potentially unsafe diagnosis.

The system does not claim to replace manufacturer documentation, trained technicians, or safety procedures.

Future versions intended for high-risk environments would require substantially broader validation, device-specific certification, stronger access controls, and explicit human oversight.

---

## 16. Future Work

Future development could expand Lumio from predefined LED profiles into a broader visual diagnostic platform.

Potential directions include automatic profile onboarding from device documentation, support for multiple indicators simultaneously, learned temporal representations, fleet-level device health analysis, and integration with maintenance workflows.

A larger real-device benchmark would also measure robustness across lighting conditions, camera position, indicator geometry, and diverse hardware.

The core design principle would remain unchanged:

**The system should act only when visual evidence supports the action.**

---

## Conclusion

Lumio demonstrates that machine indicator lights can be treated as temporal visual language rather than static image labels.

OpenCV 5 provides the perception layer required to transform camera frames into structured signal behavior.

Lumio then uses that information to determine whether to diagnose, observe again, escalate, guide an intervention, or verify recovery.

The resulting system is not simply:

**camera → classification**

It is:

**SEE → DECODE → DIAGNOSE → GUIDE → VERIFY**

By combining temporal computer vision, uncertainty-aware decisions, recovery verification, controlled evaluation, and cloud-backed observability, Lumio demonstrates a practical closed-loop approach to agentic visual diagnostics.