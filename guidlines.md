# Enterprise Liveness Verification System

## Lightweight, Training-Free, Production-Grade Architecture

---

# Goal

Build a complete end-to-end liveness and identity verification system that answers three questions:

1. Is the video stream coming from a real camera?
2. Is the person the same person as the reference ID image?
3. Is the person physically present and alive right now?

The system must:

* Require no model training.
* Use lightweight pre-trained models only.
* Run on CPU.
* Be explainable.
* Produce detailed reasoning.
* Be robust to:

  * poor lighting
  * poor camera quality
  * network degradation
  * aging
  * beard changes
  * hairstyle changes
  * glasses
  * pose variation
  * low-end devices

---

# High-Level Pipeline

User opens verification

↓

Layer 1: Capture Integrity

↓

Layer 2: Identity Verification

↓

Layer 3: Active Liveness Verification

↓

Final Risk Engine

↓

Decision + Detailed Report

---

# Layer 1 — Capture Integrity

Goal:

Verify the source is a real camera and not:

* OBS Virtual Camera
* Replay stream
* ManyCam
* Virtual webcam
* Deepfake software feed
* Injected video stream

Checks:

## Frame Timing Analysis

Measure:

* Inter-frame delta
* Robust variance
* Median cadence
* Jitter profile

Output:

Injection Score (0–100)

---

## Camera Metadata Validation

Collect:

* Resolution
* FPS
* Device name
* Device ID
* Driver information

Flag:

* Virtual devices
* Blacklisted drivers

Output:

Metadata Trust Score

---

## Frame Entropy Analysis

Replay streams often have:

* repeated frames
* deterministic cadence

Compute:

* frame difference entropy
* temporal variance

Output:

Temporal Authenticity Score

---

## Layer 1 Score

Weights:

Timing Analysis      60%
Metadata Validation  20%
Temporal Entropy     20%

Output:

Capture Integrity Score

Example:

93 / 100

Reasoning:

Real hardware timing observed.
Natural frame jitter detected.
No virtual-camera signatures found.

---

# Layer 2 — Identity Verification

Goal:

Verify the live user matches the reference image.

Reference image:

* Aadhaar
* Passport
* Driver License

---

## Face Detection

Use:

MediaPipe Face Detector

or

BlazeFace

---

## Face Embedding

Use:

InsightFace ArcFace

Requirements:

CPU mode only

Reference embedding:

cached

Probe embedding:

computed live

---

## Aging Adaptation

Must handle:

* 10+ year age gap
* beard growth
* hairstyle changes
* weight changes

Techniques:

### Multiple Crops

Generate:

* full face
* lower-face emphasis
* upper-face emphasis

Average embeddings.

---

### Dynamic Thresholding

Instead of:

fixed threshold

Use:

quality-aware threshold

Example:

high-quality images:
0.50

old Aadhaar:
0.35–0.40

---

### Landmark Stability

Compare:

* eye geometry
* nose geometry
* interocular ratio

These remain stable across years.

Used as secondary evidence.

---

## Face Quality Checks

Evaluate:

* blur
* brightness
* face size
* occlusion

Output:

Face Quality Score

---

## Layer 2 Score

Weights:

ArcFace Similarity        70%
Landmark Geometry         20%
Image Quality Confidence  10%

Output:

Identity Match Score

Example:

88 / 100

Reasoning:

Strong embedding match.
Age-related appearance changes detected.
Geometry remained highly consistent.

---

# Layer 3 — Active Liveness Verification

Goal:

Prove a live human is physically present.

This is the most important layer.

---

# Capture Requirements

Show oval guide.

Require:

* Face inside oval
* Both eyes visible
* Mouth visible
* Adequate lighting
* Neutral background

Live feedback:

Move closer.
Center your face.
Increase lighting.
Remove sunglasses.

---

# Stage 1 — Face Position Validation

Verify:

* Face inside oval
* Face size acceptable
* Roll angle acceptable
* Pitch angle acceptable

Output:

Position Score

---

# Stage 2 — Lighting Validation

Compute:

* brightness
* contrast
* dynamic range
* exposure

Reject:

* too dark
* overexposed
* backlit

Output:

Lighting Score

---

# Stage 3 — Blink Detection

Use:

MediaPipe FaceLandmarker

Detect:

* involuntary blink
* prompted blink

Output:

Blink Score

---

# Stage 4 — Head Turn Challenge

Random challenge:

Turn Left

OR

Turn Right

OR

Look Up

OR

Look Down

Use:

Motion Parallax

Validate:

* actual head rotation
* expected landmark movement
* expected parallax

Output:

Parallax Score

---

# Stage 5 — Depth Verification

Use:

Motion-based depth

Not monocular depth alone.

Compute:

Non-planarity score

Detect:

* photo
* screen replay

Output:

Depth Score

---

# Stage 6 — Micro-Movement Analysis

Track:

* nose
* mouth
* eye corners

Measure:

* involuntary movement
* breathing motion

Output:

Motion Score

---

# Stage 7 — Replay Detection

Detect:

* periodic movement
* repeated motion cycles

Output:

Replay Resistance Score

---

# Optional Signal

rPPG

Advisory only.

Never gate verification.

---

# Layer 3 Score

Weights:

Face Position        10%
Lighting             10%
Blink                25%
Head Turn            25%
Depth Parallax       20%
Micro-Movement       10%

Output:

Liveness Score

Example:

95 / 100

Reasoning:

Natural blink detected.
Successful head-turn challenge.
Strong depth parallax observed.
No replay characteristics detected.

---

# Quality Compensation System

Before any rejection:

Calculate:

Capture Quality Index

Inputs:

* lighting
* blur
* resolution
* fps
* face size

Example:

Poor lighting:

Instead of

"Liveness Failed"

Return:

"Lighting conditions reduced confidence by 18%."

This prevents unfair rejections.

---

# Final Decision Engine

Final Score

Capture Integrity: 93

Identity Match: 88

Liveness: 95

Final Score:

0.20 × Capture
+
0.35 × Identity
+
0.45 × Liveness

Result:

92.1 / 100

---

# Decision Bands

95–100

Verified

90–95

Verified (High Confidence)

80–90

Verified (Medium Confidence)

70–80

Manual Review

<70

Rejected

---

# Final Report

Return:

Verification Status

Layer-wise scores

Confidence

Quality issues

Warnings

Reasons

Example:

Verification Status:
Verified

Capture Integrity:
93/100

Identity Match:
88/100

Liveness:
95/100

Final Score:
92.1/100

Notes:

Minor lighting issues detected.
Reference image appears 9–12 years old.
Facial geometry strongly matched.
Blink and head-turn challenge successfully completed.

Confidence:
High
