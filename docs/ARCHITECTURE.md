# Architecture & Design

This document explains the design decisions behind each layer and how scores
are computed. The system is **training-free** (only pre-trained MediaPipe and
InsightFace models), **CPU-only**, and **explainable** (every score ships with
human-readable reasons).

## Pipeline overview

```
frames + timestamps + metadata
        │
        ▼
┌──────────────────────────┐
│ Layer 1 Capture Integrity│  timing(60%) · metadata(20%) · entropy(20%)
└──────────────────────────┘
        │
reference + best probe frame
        ▼
┌──────────────────────────┐
│ Layer 2 Identity         │  ArcFace(70%) · geometry(20%) · quality(10%)
└──────────────────────────┘
        │
frame sequence + challenge
        ▼
┌──────────────────────────┐
│ Layer 3 Active Liveness  │  pos(10) light(10) blink(25) turn(25) depth(20) micro(10)
└──────────────────────────┘  × replay-resistance gate
        │
        ▼
   Final Risk Engine: 0.20·cap + 0.35·id + 0.45·live  →  bands  →  report
```

## Layer 1 — Capture Integrity (`services/layer1_capture.py`)

| Signal | Method | Rationale |
|--------|--------|-----------|
| Timing | median cadence, MAD-based robust jitter, coefficient of variation | Real sensors jitter slightly; injected feeds are too perfect or too chaotic |
| Metadata | substring match vs **specific** virtual-camera & driver signatures | Detects OBS Virtual Camera / ManyCam / v4l2loopback without flagging legit hardware (e.g. *OBSBOT*) |
| Entropy | frame-difference Shannon entropy + temporal variance + duplicate-frame ratio | Replay loops repeat frames and have low entropy |

Output: `capture_score`, plus an `injection_score` (higher = riskier).

Timing uses **real per-frame timestamps** captured by the frontend during
recording. When no timestamps are available (e.g. an uploaded clip), timing is
reported as neutral rather than guessed.

## Layer 2 — Identity (`services/layer2_identity.py`)

A face is prepared once, then embedded from canonical alignment — a deliberate
choice to **maximise accuracy and minimise latency without heavy models**
(AdaFace / DepthAnything were evaluated and intentionally *not* added: they need
PyTorch + manually-sourced checkpoints and are slow on CPU, against this
project's lightweight, auto-provisioning design).

- **Detection + recognition**: InsightFace `buffalo_l` (ArcFace `w600k_r50`) on
  CPU — a strong recogniser already bundled and auto-downloaded.
- **Portrait extraction** (`services/aadhaar_extractor.py`): users upload the
  whole card, not a cropped face. Extraction is *face-driven* (orientation sweep
  → strongest face → crop + restore + upscale small portraits → re-validate),
  which is far more robust to old/new Aadhaar layouts, scans, phone photos and
  skew than brittle contour/template heuristics, and inherently validates a face
  is present. (No OCR / field extraction — out of scope.)
- **Face alignment** (`utils/face_alignment.py`): every face is warped to the
  canonical ArcFace 112×112 template via a similarity transform on the 5
  keypoints (`norm_crop`). This removes pose/tilt/scale variation so the
  recogniser sees a consistent frame — a large, cheap accuracy win.
- **Robust embedding** (TTA): the aligned face is embedded from four views —
  aligned, horizontally-flipped, restored (`utils/image.enhance_for_recognition`:
  gray-world white balance + CLAHE + upscale + unsharp), and restored+flipped —
  in **one batched recognition call**, and the L2-normalised vectors are
  averaged. This suppresses pose, lighting and degradation (faded red-cast ID
  prints) and raises genuine-pair similarity. Aligning once + batching is also
  *faster* than the previous re-detect-per-view approach.
- **Subject-face selection**: a selfie often contains small background faces
  that can out-score the main subject; the matcher picks the **largest** face
  (`face_engine.primary_face`), not merely the highest-scoring one — otherwise it
  would compare the ID against a bystander.
- **Adaptive threshold**: `min(ref_quality, probe_quality)` maps to a cosine
  threshold between a degraded-photo floor (~0.26) and `SIMILARITY_THRESHOLD_HIGH`
  (0.40). These are ArcFace `w600k_r50` KYC operating points — impostors score
  ≈0.05–0.20, leaving a wide margin.
- **Multi-signal decision**: a match is a direct embedding pass **or** a
  borderline embedding (within ~0.06 of threshold, ≥0.33) corroborated by
  strongly consistent facial geometry (≥72/100, age-stable). Geometry is a
  scale-invariant secondary signal that genuine aged pairs preserve.
- **Threshold-relative score**: similarity is scored relative to the adaptive
  threshold (a match exactly at threshold ≈ 65/100, scaling to 100 with margin),
  so a genuine but degraded ID isn't unfairly low just because its absolute
  cosine is modest.

Validated on a real hard pair — a faded, red-cast Aadhaar print (sideways, ~4-yr
age gap, beard + glasses added) vs a busy office selfie with background people:
the pipeline orientation-corrects + extracts the portrait, selects the subject
face (not a bystander), and matches (similarity ≈ 0.42, geometry ≈ 78,
identity ≈ 72/100) — while a stranger against the same Aadhaar rejects cleanly
(similarity ≈ 0.05).
- **Landmark geometry**: scale-invariant ratios between the 5 keypoints
  (eyes/nose/mouth) provide age-stable secondary evidence.
- **Rotation-robust detection**: when no face is found upright, detection is
  retried at 90°/180°/270°, and the best-scoring orientation is used for
  embeddings, geometry and quality. This handles ID-card photos shot sideways
  (a very common failure mode) and is short-circuited for normal upright selfies.

Score = `0.70·similarity + 0.20·geometry + 0.10·quality`.

## Layer 3 — Active Liveness (`services/layer3_liveness.py`)

Operates on a short **continuous video** (recorded by the frontend or uploaded).
Uses MediaPipe FaceLandmarker (478 landmarks + blendshapes + head-pose matrix).

| Stage | Signal | Spoof it defeats |
|-------|--------|------------------|
| Position | centering, face size, roll | misframed / partial faces |
| Lighting | brightness + contrast | unusable captures |
| Blink | transient spike in `eyeBlink*` blendshapes (EAR fallback) | static photo |
| Head-turn | landmark-based yaw/pitch range + axis dominance | static photo, wrong-axis motion |
| Depth | homography reprojection residual (non-planarity) | printed photo, screen replay |
| Micro-movement | nose-anchored landmark displacement | rigid prints |
| Replay | autocorrelation periodicity of the motion signal | looped video |
| rPPG | forehead green-channel pulse band (advisory) | — never gates |

**Head-pose signal.** Rather than the raw transformation-matrix angles (which
are often too damped to register a deliberate turn), yaw/pitch are derived
directly from landmarks: yaw from how the nose projects between the two cheek
silhouettes, pitch from the nose's position between forehead and chin. Both are
scale-invariant. A challenge passes on sufficient motion along the **correct
axis** (horizontal for left/right, vertical for up/down); exact left-vs-right is
a soft bonus only, because front cameras are commonly mirrored.

**Depth.** The extreme-rotation frames (by the same yaw signal) are matched with
a homography; a flat photo/screen yields a tiny reprojection residual while a
real 3-D face leaves large residuals. With too little rotation to measure, depth
returns **neutral** — it is never falsely labelled planar.

Base score uses the documented weights; **replay resistance** applies a
multiplicative gate (0.55–1.0) so a looped replay can't pass on stage scores
alone. A static still produces no blink, no axis motion and planar/neutral
depth, so it cannot accumulate a passing liveness score.

## Final Decision Engine (`services/scoring.py`)

```python
final = 0.20*capture + 0.35*identity + 0.45*liveness
```

Bands (configurable in `.env`): 95+ Verified · 90+ High · 80+ Medium ·
70+ Manual Review · else Rejected. Confidence is downgraded when the identity
doesn't match or when the capture-quality penalty is large.

The full pipeline (`/verify`) computes all three layers from one upload. The
**Final Report** page instead aggregates results already computed on the
individual layer pages and calls `/score` (`routes/score.py`) to fuse them with
the same weights and bands — a single source of truth for the decision logic.

## Frontend capture (`frontend/capture.py`)

- **Photos** (identity/reference): `st.camera_input` (browser camera).
- **Video** (capture-integrity, liveness): recorded directly from the local
  webcam via OpenCV with a countdown, live preview and an **oval face guide**.
  Real per-frame timestamps are captured for the timing analysis; the oval is
  drawn on the preview only, never on the analysed frames.

## Robustness & concurrency

- **Thread-safe inference.** FastAPI dispatches requests on a threadpool, but
  MediaPipe FaceLandmarker and the InsightFace app are not safe for concurrent
  inference on a single instance. All model calls are serialised behind an
  inference lock (`utils/face_engine.py`); model *loading* is double-checked
  locked separately.
- **Whole-clip video sampling.** `utils/image.decode_video_bytes` samples frames
  evenly across the entire clip instead of truncating to the first N, so a
  late blink / head-turn is never dropped.
- **Probe selection.** `pipeline._best_probe_frame` returns the sharpest frame
  that actually contains a confident face, not merely the sharpest frame.
- **Graceful degradation.** Every stage has neutral fallbacks for missing faces,
  too few frames, degenerate timestamps or failed homography fits, and reports
  the reason rather than crashing.

## Quality Compensation (`utils/quality.py`)

A `QualityReport` aggregates blur, brightness, contrast, face size and
resolution into a Capture Quality Index. Poor conditions become an explained
*confidence penalty* (capped at 30%) rather than a hard failure — protecting
genuine users on bad cameras / lighting.

## Explainability

Every layer returns a `reasons` list; the reporting engine
(`services/reporting.py`) merges them with warnings and notes into the final
`VerificationResponse`, so each decision is fully auditable.
