# 🛡️ Enterprise Liveness & Identity Verification System

A complete, **training-free**, **CPU-only**, **explainable** end-to-end liveness
and identity verification system. It answers three questions:

1. **Is the video stream coming from a real camera?** (Capture Integrity)
2. **Is the person the same as the reference ID image?** (Identity)
3. **Is the person physically present and alive right now?** (Active Liveness)

Built with FastAPI + Streamlit, MediaPipe, InsightFace (ArcFace) and ONNX
Runtime. No GPU and no model training required — it uses only lightweight
pre-trained models, downloaded automatically on first run.

---

## Architecture

```
User ─► Layer 1: Capture Integrity ─► Layer 2: Identity ─► Layer 3: Liveness
                                                                  │
                                                                  ▼
                                            Final Risk Engine ─► Decision + Report
```

| Layer | Service | What it does | Weight |
|-------|---------|--------------|:------:|
| 1 | `layer1_capture.py` | Frame-timing jitter, virtual-camera detection, temporal entropy | 0.20 |
| 2 | `layer2_identity.py` | ArcFace embeddings, multi-crop, aging-tolerant adaptive threshold, landmark geometry | 0.35 |
| 3 | `layer3_liveness.py` | Position, lighting, blink, head-turn challenge, motion-parallax depth, micro-movement, replay detection, rPPG (advisory) | 0.45 |

```python
final_score = 0.20*capture + 0.35*identity + 0.45*liveness
```

### Decision bands

| Score | Status |
|-------|--------|
| 95–100 | Verified |
| 90–95 | Verified (High Confidence) |
| 80–90 | Verified (Medium Confidence) |
| 70–80 | Manual Review |
| < 70 | Rejected |

The **Quality Compensation System** converts poor capture conditions into an
explained *confidence penalty* instead of an unfair rejection.

---

## Project structure

```text
live-mini/
├── backend/
│   ├── app.py                  # FastAPI entry point
│   ├── config.py               # Central settings (pydantic-settings)
│   ├── routes/                 # verify / capture / identity / liveness / score / health
│   ├── services/               # layer1-3, scoring, reporting, pipeline, aadhaar_extractor
│   ├── schemas/                # pydantic requests & responses
│   ├── models/                 # auto-downloaded model cache
│   └── utils/                  # image, metrics, quality, logger, face_engine,
│                               #   face_alignment, model_manager
├── frontend/
│   ├── streamlit_app.py        # Home
│   ├── api_client.py           # backend client
│   ├── capture.py              # local camera: photo + live video recorder (oval guide)
│   ├── components.py           # gauges / cards / banners
│   └── pages/                  # capture / identity / liveness / final report
├── docs/
├── requirements.txt
├── setup.sh · run_backend.sh · run_frontend.sh
└── .env.example
```

---

## Quick start

### 1. Setup (creates venv, installs deps, downloads models)

```bash
./setup.sh
# or manually:
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.utils.model_manager   # download models
```

> On Windows: `python -m venv .venv && .venv\Scripts\activate`

### 2. Run the backend

```bash
./run_backend.sh
# API docs at http://localhost:8000/docs
```

```
source .venv/bin/activate
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### 3. Run the frontend (in a second terminal)

```bash
./run_frontend.sh
# UI at http://localhost:8501
```

```
source .venv/bin/activate
streamlit run frontend/streamlit_app.py
```

---

## API

Base URL: `http://localhost:8000/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/verify` | Full pipeline (reference + clip) → final report |
| POST | `/capture-check` | Layer 1 only |
| POST | `/identity-check` | Layer 2 only (reference + probe) |
| POST | `/liveness-check` | Layer 3 only (clip) |
| POST | `/score` | Fuse three pre-computed layer scores → decision (used by Final Report) |
| GET  | `/health` | Service & model readiness |

### Example: full verification

```bash
curl -X POST http://localhost:8000/api/v1/verify \
  -F "reference=@id_photo.jpg" \
  -F "video=@liveness_clip.mp4" \
  -F 'payload={"challenge":"turn_left","fps":15,"metadata":{"device_name":"FaceTime HD Camera"}}'
```

### Example: identity check

```bash
curl -X POST http://localhost:8000/api/v1/identity-check \
  -F "reference=@aadhaar.jpg" \
  -F "probe=@selfie.jpg"
```

### Response shape

```json
{
  "status": "verified_high_confidence",
  "capture_score": 93.0,
  "identity_score": 88.0,
  "liveness_score": 95.0,
  "final_score": 92.1,
  "confidence": "high",
  "reasons": ["Strong embedding match ...", "Natural blink detected ...", "..."],
  "warnings": [],
  "capture": { "...": "..." },
  "identity": { "...": "..." },
  "liveness": { "...": "..." },
  "quality": { "capture_quality_index": 84.0, "confidence_penalty_pct": 1.0, "issues": [] }
}
```

---

## How each anti-spoof signal works

- **Frame timing** — real cameras show small but non-zero jitter; perfectly
  deterministic cadence (injected) or wildly irregular timing both raise the
  injection score. The frontend captures **real per-frame timestamps** while
  recording so this analysis runs on genuine cadence.
- **Virtual-camera detection** — device name / driver matched against specific
  virtual-camera signatures (`OBS Virtual Camera`, ManyCam, v4l2loopback, …).
  Signatures are precise enough not to flag legitimate hardware (e.g. *OBSBOT*).
- **Temporal entropy** — replay loops repeat frames; we measure frame-difference
  entropy and variance.
- **Aging-tolerant identity** — a production-grade matching pipeline tuned for
  the hard Aadhaar↔selfie case, **lightweight and CPU-only** (no heavy PyTorch
  models):
  - **Aadhaar portrait extraction** — accepts the whole card; a face-driven
    extractor orientation-corrects it, crops the portrait, and restores +
    upscales small/faded portraits.
  - **Face alignment** — every face is warped to the canonical ArcFace 112×112
    template (5-point similarity transform) so the recogniser sees a consistent
    pose — a big accuracy win across selfie-vs-ID angle differences.
  - **TTA embedding** — aligned + flipped + restored + restored-flipped views are
    embedded in one batched ArcFace call and averaged (suppresses beard / glasses
    / hairstyle / fading).
  - **Subject-face selection** — picks the largest (closest) face, so background
    people in a selfie don't get matched by mistake.
  - **Quality-adaptive threshold** (ArcFace KYC operating points: ~0.26 for very
    degraded old IDs … 0.40 for crisp photos) + **threshold-relative scoring** +
    a **multi-signal decision** (borderline embedding confirmed by age-stable
    facial geometry), so a genuine but degraded ID isn't unfairly rejected while
    impostors (≈0.05–0.20) stay far below the bar.
- **Head-turn challenge** — validated from a **landmark-based yaw/pitch signal**
  (nose position relative to the cheek silhouettes / forehead–chin), which
  tracks visible rotation far more reliably than the raw head-pose matrix.
- **Motion-parallax depth** — a flat photo/screen maps frame-to-frame by a
  homography (low residual); a real 3D face leaves large residuals under
  rotation. Reported as *neutral* (not "planar") when there isn't enough
  rotation to measure.
- **Replay detection** — autocorrelation periodicity of the motion signal.
- **rPPG** — green-channel pulse estimate from the forehead ROI; **advisory only**,
  never gates the decision.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

---

## Configuration

All tunables live in `.env` (see `.env.example`): decision thresholds, score
weights, similarity thresholds, model pack, and ONNX providers (CPU by default).

---

## Frontend capture

- **Photos** (identity / reference) use the browser's `st.camera_input`.
- **Video** (capture-integrity & liveness) is recorded straight from the local
  webcam via OpenCV, with a **countdown, live preview and oval face guide**, and
  records genuine continuous frames + real timestamps. A virtual camera (OBS) is
  usually a higher camera index, so the default index `0` selects the real
  webcam; change the **camera index** in the UI if needed.
- **Final Report** captures nothing itself — it aggregates the three stored test
  results and calls `/score` for the fused decision.

## Edge cases & robustness

Hardening applied after an explicit edge-case audit:

- **Thread-safe inference** — MediaPipe FaceLandmarker and InsightFace are not
  safe for concurrent inference on one instance; all model calls are serialised
  behind an inference lock so concurrent requests can't corrupt/crash them.
- **Whole-clip sampling** — uploaded videos are sampled *evenly across the entire
  clip* (not truncated to the first N frames), so a blink / head-turn performed
  late in the clip is not lost.
- **Rotation-robust faces** — identity detection retries 0/90/180/270° for
  sideways ID photos.
- **Depth honesty** — insufficient head rotation is reported as *neutral*, never
  mislabelled as a planar (spoof) result.
- **Probe selection** — the identity probe is the sharpest frame **that actually
  contains a detectable face**, not merely the sharpest frame.
- **Precise virtual-camera signatures** — avoid false positives on legitimate
  hardware (e.g. *OBSBOT*).
- **Quality compensation** — poor lighting/blur reduces *confidence* with an
  explanation instead of hard-failing a genuine user.

## Deployment notes

- CPU-only; works on low-end devices. For best latency keep `DET_SIZE=640` or
  lower and limit liveness clips to ~3–5 seconds.
- Inference is serialised per-process. For throughput, run multiple uvicorn
  workers behind a reverse proxy (each worker holds its own model instances):
  `uvicorn backend.app:app --workers 4 --host 0.0.0.0 --port 8000`.
- The **recorded-webcam** path sends consecutive frames (best for timing /
  entropy / replay analysis); uploaded clips are evenly sampled and are the
  secondary path.
- Models are cached under `backend/models/` and verified against a sha256
  manifest on every start.

## Screenshots

_Add screenshots of the Streamlit pages here (`docs/screenshots/`)._

| Page | Description |
|------|-------------|
| Home | Overview + backend status |
| Capture Integrity | Layer 1 gauges & reasoning |
| Identity Verification | Reference vs live similarity |
| Liveness Verification | Challenge, stage scores |
| Final Report | Decision banner + gauges |

---

## License

Internal / proprietary — Recrivio.