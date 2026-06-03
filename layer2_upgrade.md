# Production-Grade KYC Upgrade Plan

## Objective

Upgrade the existing identity verification pipeline to achieve production-grade KYC performance similar to modern eKYC providers by implementing the following four enhancements:

1. Face Alignment Before Embedding
2. AdaFace-Based Recognition
3. Aadhaar Portrait Extraction
4. DepthAnything-Based Depth Consistency Verification

**Important:**
Do NOT implement OCR-based Aadhaar data extraction.
Do NOT modify existing API contracts unless absolutely necessary.
Maintain FastAPI compatibility and modular architecture.

---

# Upgrade 1: Face Alignment Before Embedding

## Current Problem

Embeddings are generated directly from detected faces.

This causes:

* Pose sensitivity
* Head tilt issues
* Reduced similarity scores
* Higher false negatives

---

## Goal

Align all faces into a canonical orientation before embedding generation.

---

## Requirements

### Use 5-Point Facial Landmarks

Expected landmark order:

```python
left_eye
right_eye
nose
left_mouth
right_mouth
```

### Apply Similarity Transform

Use:

```python
cv2.estimateAffinePartial2D()
```

or equivalent.

### Standard Output Size

All aligned faces should be:

```python
112 x 112
```

or model-required size.

### Alignment Must Be Applied To

* Aadhaar portrait
* Passport photo
* Driving license photo
* Live selfie
* Enhanced image
* Flipped image
* Multi-crop image

---

## New Utility

Create:

```text
backend/utils/face_alignment.py
```

Functions:

```python
align_face(image, landmarks)
get_aligned_face(image, face)
```

---

## Existing Files To Modify

```text
backend/layers/identity_verification.py
backend/utils/face_engine.py
```

---

## Expected Benefits

* Better pose invariance
* Better selfie matching
* Reduced angle sensitivity
* Higher verification accuracy

---

# Upgrade 2: Replace ArcFace With AdaFace

## Current Problem

ArcFace struggles with:

* Old Aadhaar photos
* Low-quality scans
* Blur
* Compression artifacts
* Aging effects

---

## Goal

Replace ArcFace embeddings with AdaFace embeddings.

---

## Requirements

### Model

Use:

```text
AdaFace
```

Recommended:

```text
ir_50
```

or

```text
ir_101
```

pretrained checkpoints.

---

## Create New Service

Create:

```text
backend/services/adaface_service.py
```

API:

```python
get_embedding(face_image)
```

Returns:

```python
np.ndarray
```

---

## Requirements

### Embedding Processing

Apply:

```python
L2 normalization
```

before returning.

---

### Inference Support

Must support:

* GPU inference
* CPU fallback
* Batch processing

---

## Preserve Existing Logic

Keep:

* Multi-crop embeddings
* Flip TTA
* Enhanced image embeddings
* Similarity calculations

Only replace embedding generation.

---

## Expected Benefits

* Better aging robustness
* Better Aadhaar matching
* Improved low-quality performance

---

# Upgrade 3: Aadhaar Portrait Extraction

## Current Problem

The pipeline expects a cropped face image.

Real users upload:

* Entire Aadhaar cards
* Camera photos
* Scanned copies

---

## Goal

Automatically extract the portrait region.

---

# Stage 1: Orientation Detection

Support:

```text
0°
90°
180°
270°
```

Automatically rotate the Aadhaar image.

---

# Stage 2: Document Detection

Detect Aadhaar boundaries.

Support:

* Scans
* Mobile photos
* Slight perspective distortion

Recommended methods:

```python
contours
perspective transform
document detection
```

---

# Stage 3: Portrait Localization

Extract the Aadhaar photograph region.

Supported approaches:

* Layout-based heuristics
* Object detection
* Template matching
* OCR-assisted layout detection

---

## Must Support

### Old Aadhaar Layout

Photo on left side.

### New Aadhaar Layout

Photo on left side with modified spacing.

---

# Stage 4: Face Validation

Verify:

```python
face exists
```

inside extracted portrait.

Return:

```python
portrait_image
portrait_bbox
confidence
```

---

## New Module

Create:

```text
backend/services/aadhaar_extractor.py
```

Functions:

```python
detect_aadhaar()
extract_portrait()
validate_portrait()
```

---

## Integration

Verification endpoint should accept:

```python
full Aadhaar image
```

instead of requiring a manually cropped face.

---

# Upgrade 4: DepthAnything-Based Depth Consistency Verification

## Goal

Detect spoof attacks using passive liveness verification.

---

## Supported Attacks

Detect:

* Printed photo attacks
* Mobile screen replay attacks
* Tablet replay attacks
* Flat paper attacks

---

## Model

Use:

```text
DepthAnything V2
```

Recommended:

```text
DepthAnythingV2-Small
```

for fast inference.

---

## Create Service

Create:

```text
backend/services/depth_service.py
```

Functions:

```python
generate_depth_map()
compute_depth_consistency()
```

---

# Pipeline

```text
Selfie
  ↓
Face Detection
  ↓
DepthAnything
  ↓
Depth Map
  ↓
Face Region Analysis
```

---

# Required Measurements

## Nose Depth

Measure:

```python
nose depth
```

---

## Cheek Depth

Measure:

```python
left cheek depth
right cheek depth
```

---

## Jaw Depth

Measure:

```python
jaw depth
```

---

## Face Relief Score

Generate:

```python
depth_consistency_score
```

Range:

```python
0-100
```

---

## Expected Behavior

### Real Face

```python
score > 70
```

### Spoof Attack

```python
score < 30
```

---

# Identity Result Changes

Extend:

```python
IdentityResult
```

with:

```python
depth_score: float
```

Example:

```python
IdentityResult(
    identity_score=92.1,
    similarity=0.84,
    landmark_score=87.0,
    depth_score=81.2,
)
```

---

# Final Verification Pipeline

```text
Aadhaar Card
    ↓
Orientation Correction
    ↓
Document Detection
    ↓
Portrait Extraction
    ↓
Face Alignment
    ↓
AdaFace Embedding
    ↓
Multi-Crop Matching
    ↓
Similarity Score

Live Selfie
    ↓
Face Detection
    ↓
Face Alignment
    ↓
DepthAnything
    ↓
Depth Consistency Score
    ↓
AdaFace Embedding

Fusion Layer
    ↓
Identity Result
```

---

# Suggested Project Structure

```text
backend/
│
├── services/
│   ├── adaface_service.py
│   ├── aadhaar_extractor.py
│   └── depth_service.py
│
├── utils/
│   ├── face_alignment.py
│   └── depth_utils.py
│
├── layers/
│   └── identity_verification.py
│
└── schemas/
    └── responses.py
```

---

# Dependencies

Install:

```bash
torch
torchvision
onnxruntime-gpu
onnxruntime
opencv-python
numpy
scipy
insightface
depth-anything
timm
einops
```

Optional:

```bash
albumentations
```

for preprocessing.

---

# Deliverables

The implementation must include:

1. Complete production-ready code.
2. Exact file modifications.
3. New utility modules.
4. FastAPI-compatible integration.
5. Type hints throughout.
6. GPU optimization.
7. CPU fallback support.
8. Testing strategy.
9. Benchmarking instructions.
10. Backward compatibility with existing APIs.

Focus ONLY on the four upgrades defined in this document.
Do not add OCR-based Aadhaar field extraction, blink detection, rPPG, or other liveness modules in this phase.
