# Additional Project Generation Requirements

## Technology Stack, Project Structure, Backend APIs, Environment Setup

The generated project must be a complete production-ready implementation.

The AI should not generate pseudocode.

It should generate actual runnable code.

---

# Primary Stack

Backend:

* Python 3.11
* FastAPI
* Uvicorn
* Pydantic

Frontend:

* Streamlit

Computer Vision:

* OpenCV
* MediaPipe
* InsightFace
* ONNX Runtime

Signal Processing:

* NumPy
* SciPy
* Pandas

Visualization:

* Plotly
* Matplotlib

Utilities:

* Pillow
* Loguru
* Python-dotenv

---

# Development Philosophy

Requirements:

* No model training
* No GPU required
* CPU-only execution
* Cross-platform
* Modular architecture
* Production-grade logging
* Explainable outputs
* Fast inference
* Lightweight deployment

The system should prioritize:

1. Accuracy
2. Explainability
3. Speed
4. Maintainability

---

# Project Generation Order

The AI should generate the project in the following sequence.

Do not skip steps.

---

## Step 1 — Create Project Structure

Generate complete folder structure.

Example:

```text
liveliness-verification/

├── backend/
│   ├── app.py
│   ├── routes/
│   │   ├── verify.py
│   │   ├── identity.py
│   │   ├── liveness.py
│   │   └── capture.py
│   │
│   ├── services/
│   │   ├── layer1_capture.py
│   │   ├── layer2_identity.py
│   │   ├── layer3_liveness.py
│   │   ├── scoring.py
│   │   └── reporting.py
│   │
│   ├── models/
│   │   ├── face_landmarker.task
│   │   ├── blaze_face_short_range.tflite
│   │   └── insightface/
│   │
│   ├── schemas/
│   │   ├── requests.py
│   │   └── responses.py
│   │
│   └── utils/
│       ├── image.py
│       ├── metrics.py
│       ├── quality.py
│       └── logger.py
│
├── frontend/
│   ├── streamlit_app.py
│   ├── pages/
│   │   ├── capture_integrity.py
│   │   ├── identity_verification.py
│   │   ├── liveness_verification.py
│   │   └── final_report.py
│
├── docs/
│
├── requirements.txt
├── .env.example
├── setup.sh
├── run_backend.sh
├── run_frontend.sh
└── README.md
```

---

# Step 2 — Create Virtual Environment

Generate setup instructions.

Linux/macOS:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

---

# Step 3 — Generate requirements.txt

Must contain:

```txt
fastapi
uvicorn
streamlit

opencv-python
opencv-contrib-python

mediapipe

insightface
onnxruntime

numpy
scipy
pandas

plotly
matplotlib

pillow

python-dotenv

loguru

python-multipart
requests
```

Pin versions where possible.

---

# Step 4 — Model Download Automation

Generate code that automatically:

Downloads:

* MediaPipe Face Landmarker
* BlazeFace
* InsightFace models

Caches:

```text
/models
```

Behavior:

* Download only if missing
* Verify checksum
* Retry failed downloads
* Use atomic downloads

No manual model management.

---

# Step 5 — Implement Layer 1

File:

```text
backend/services/layer1_capture.py
```

Must implement:

### Frame Timing Analysis

* robust variance
* jitter analysis
* cadence consistency

### Camera Metadata Validation

* device inspection
* virtual camera detection

### Temporal Entropy

* repeated frame detection
* replay indicators

Output:

```json
{
  "capture_score": 94,
  "reasons": []
}
```

---

# Step 6 — Implement Layer 2

File:

```text
backend/services/layer2_identity.py
```

Must implement:

### Face Detection

MediaPipe

### Face Embeddings

InsightFace

### Aging Tolerance

Support:

* beard
* hairstyle
* aging

Use:

* multiple face crops
* adaptive thresholds

Output:

```json
{
  "identity_score": 88,
  "similarity": 0.71,
  "match": true,
  "reasons": []
}
```

---

# Step 7 — Implement Layer 3

File:

```text
backend/services/layer3_liveness.py
```

Must implement:

### Face Oval Guidance

Real-time alignment

### Lighting Quality

Brightness
Contrast
Exposure

### Blink Detection

MediaPipe Face Landmarker

### Head Turn Challenge

Randomized

Examples:

* Turn Left
* Turn Right
* Look Up
* Look Down

### Motion Parallax

### Micro-Movement Analysis

### Replay Detection

### Advisory rPPG

Not part of final score.

Output:

```json
{
  "liveness_score": 95,
  "blink_detected": true,
  "challenge_passed": true,
  "depth_passed": true,
  "reasons": []
}
```

---

# Step 8 — Scoring Engine

File:

```text
backend/services/scoring.py
```

Formula:

```python
final_score = (
    capture_score * 0.20
    + identity_score * 0.35
    + liveness_score * 0.45
)
```

Return:

* score
* confidence
* decision

---

# Step 9 — Reporting Engine

File:

```text
backend/services/reporting.py
```

Generate:

* layer-wise results
* confidence
* warnings
* quality issues
* human-readable explanations

---

# Step 10 — FastAPI Backend

Generate complete APIs.

Base URL:

```text
/api/v1
```

Endpoints:

### POST

```text
/api/v1/verify
```

Runs full pipeline.

---

### POST

```text
/api/v1/capture-check
```

Runs Layer 1.

---

### POST

```text
/api/v1/identity-check
```

Runs Layer 2.

---

### POST

```text
/api/v1/liveness-check
```

Runs Layer 3.

---

### GET

```text
/api/v1/health
```

Health check.

---

# API Response Format

```json
{
  "status": "verified",

  "capture_score": 94,
  "identity_score": 88,
  "liveness_score": 95,

  "final_score": 92,

  "confidence": "high",

  "reasons": [],

  "warnings": []
}
```

---

# Step 11 — Streamlit Frontend

Generate a professional UI.

Pages:

### Home

Overview

### Capture Integrity

Real-time camera status

### Identity Verification

Reference upload

Live capture

Similarity score

### Liveness Verification

Oval guide

Blink guidance

Head-turn challenge

Lighting indicator

Progress tracker

### Final Report

Layer-wise cards

Score gauges

Warnings

Decision banner

---

# UX Requirements

Show live feedback:

Examples:

```text
Move closer to camera
Face not centered
Increase lighting
Remove sunglasses
Turn your head left
Blink naturally
Hold still
```

---

# Step 12 — Logging

Log:

* scores
* timings
* failures
* quality issues

Use:

```python
from loguru import logger
```

---

# Step 13 — README Generation

Generate:

* installation
* setup
* architecture
* API docs
* screenshots section
* deployment instructions

---

# Step 14 — Run Scripts

Generate:

run_backend.sh

```bash
uvicorn backend.app:app --reload
```

run_frontend.sh

```bash
streamlit run frontend/streamlit_app.py
```

setup.sh

```bash
pip install -r requirements.txt
```

---

# Expected Output

The AI should generate:

1. Folder structure
2. requirements.txt
3. Setup scripts
4. Backend code
5. Frontend code
6. FastAPI routes
7. Services
8. Model download manager
9. Reporting engine
10. README

All code must be complete, runnable, modular, and production-oriented.

No pseudocode.
No placeholders.
No TODO comments.
Generate actual implementation files in sequence.
