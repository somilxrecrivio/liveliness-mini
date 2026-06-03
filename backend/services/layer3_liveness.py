"""Layer 3 - Active Liveness Verification.

Proves a live human is physically present. Operates on a short sequence of
frames and fuses seven stages:

1. Face position (oval alignment)           - 10%
2. Lighting quality                          - 10%
3. Blink detection (involuntary/prompted)    - 25%
4. Head-turn challenge (motion parallax)     - 25%
5. Depth verification (non-planarity)        - 20%
6. Micro-movement analysis                   - 10%
7. Replay detection (periodicity)            - penalty on the fused score
   rPPG                                       - advisory only, never gates

The Quality Compensation System ensures poor capture conditions reduce
*confidence* with an explanation rather than causing a hard failure.
"""
from __future__ import annotations

import cv2
import numpy as np

from backend.schemas.requests import ChallengeType
from backend.schemas.responses import LivenessResult
from backend.utils.face_engine import LandmarkResult, detect_landmarks
from backend.utils.image import sample_frames
from backend.utils.logger import logger
from backend.utils.metrics import (
    clamp,
    dominant_frequency,
    linear_map,
    periodicity_score,
)
from backend.utils.quality import assess_quality

# --- MediaPipe FaceLandmarker (478-pt) indices ---
NOSE_TIP = 1
LEFT_EYE_OUTER, LEFT_EYE_INNER = 33, 133
RIGHT_EYE_INNER, RIGHT_EYE_OUTER = 362, 263
MOUTH_LEFT, MOUTH_RIGHT = 61, 291
MOUTH_TOP, MOUTH_BOTTOM = 13, 14
LEFT_CHEEK, RIGHT_CHEEK = 234, 454   # face silhouette sides
CHIN, FOREHEAD = 152, 10
# Rigid, age-stable points used for the planar (homography) depth test.
RIGID_POINTS = [33, 133, 362, 263, 1, 61, 291, 199, 4, 6, 168, 152]
# Tracked points for micro-movement (eye corners, nose, mouth corners).
MICRO_POINTS = [33, 263, 1, 61, 291]
MAX_FRAMES = 60


def _interocular(lm: np.ndarray) -> float:
    return float(np.linalg.norm(lm[RIGHT_EYE_OUTER, :2] - lm[LEFT_EYE_OUTER, :2])) + 1e-6


def _head_signals(lm: np.ndarray) -> tuple[float, float]:
    """Robust, scale-invariant yaw & pitch proxies from 2-D landmarks.

    These reflect *visible* head rotation directly and are far more reliable for
    detecting a head-turn than MediaPipe's (often damped) transformation matrix.

    * **yaw**  - based on how close the nose projects to each cheek silhouette;
      ``(d_right - d_left)/(d_right + d_left)`` in roughly ``[-1, 1]``. Sign
      flips with turn direction; ~0 when facing forward.
    * **pitch** - vertical nose offset between forehead and chin, normalised to
      ``[-1, 1]`` (negative looking up, positive looking down).
    """
    nose = lm[NOSE_TIP, :2]
    lc = lm[LEFT_CHEEK, :2]
    rc = lm[RIGHT_CHEEK, :2]
    d_left = float(np.linalg.norm(nose - lc))
    d_right = float(np.linalg.norm(nose - rc))
    yaw = (d_right - d_left) / (d_right + d_left + 1e-6)

    fore = lm[FOREHEAD, :2]
    chin = lm[CHIN, :2]
    span = float(np.linalg.norm(chin - fore)) + 1e-6
    # 0 at forehead, 1 at chin -> centre ~0.5; remap to [-1,1].
    pitch = (float(nose[1] - fore[1]) / span) * 2.0 - 1.0
    return yaw, pitch


# --------------------------------------------------------------------------- #
# Stage 1 - Face position
# --------------------------------------------------------------------------- #
def _position_stage(results: list[LandmarkResult]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    scores = []
    for r in results:
        if not r.found:
            continue
        w, h = r.image_size
        lm = r.landmarks
        cx, cy = lm[:, 0].mean(), lm[:, 1].mean()
        # Centering: distance of face centre from frame centre.
        off = np.hypot((cx - w / 2) / w, (cy - h / 2) / h)
        center_score = clamp(linear_map(off, 0.30, 0.0, 0.0, 100.0))
        # Size: face span vs frame height.
        span = (lm[:, 1].max() - lm[:, 1].min()) / h
        size_score = clamp(linear_map(span, 0.25, 0.75, 0.0, 100.0))
        # Pose: small roll/pitch preferred for the neutral position frames.
        roll = abs(r.pose["roll"])
        roll_score = clamp(linear_map(roll, 25.0, 0.0, 0.0, 100.0))
        scores.append(0.45 * center_score + 0.35 * size_score + 0.20 * roll_score)

    if not scores:
        reasons.append("No face detected for position validation.")
        return 0.0, reasons
    score = float(np.mean(scores))
    if score < 60:
        reasons.append("Face not well centred/sized within the oval guide.")
    else:
        reasons.append("Face correctly positioned within the oval guide.")
    return clamp(score), reasons


# --------------------------------------------------------------------------- #
# Stage 2 - Lighting
# --------------------------------------------------------------------------- #
def _lighting_stage(frames: list[np.ndarray], results: list[LandmarkResult]) -> tuple[float, list[str]]:
    reports = []
    for f, r in zip(frames, results):
        bbox = None
        if r.found:
            lm = r.landmarks
            bbox = (int(lm[:, 0].min()), int(lm[:, 1].min()),
                    int(lm[:, 0].max()), int(lm[:, 1].max()))
        reports.append(assess_quality(f, bbox))
    bright = float(np.mean([q.brightness_score for q in reports]))
    contrast = float(np.mean([q.contrast_score for q in reports]))
    score = clamp(0.6 * bright + 0.4 * contrast)
    reasons: list[str] = []
    if bright < 55:
        reasons.append("Lighting reduced confidence; scene is under-exposed.")
    elif bright > 90 and contrast > 70:
        reasons.append("Lighting conditions are good.")
    return score, reasons


# --------------------------------------------------------------------------- #
# Stage 3 - Blink
# --------------------------------------------------------------------------- #
def _blink_stage(results: list[LandmarkResult]) -> tuple[float, bool, list[str]]:
    """Detect a blink as a transient spike in eye-blink blendshapes."""
    reasons: list[str] = []
    left = np.array([r.blendshapes.get("eyeBlinkLeft", 0.0) for r in results if r.found])
    right = np.array([r.blendshapes.get("eyeBlinkRight", 0.0) for r in results if r.found])
    if left.size < 3:
        # Fall back to eye-aspect-ratio if blendshapes unavailable.
        ear = _ear_series(results)
        if ear.size < 3:
            reasons.append("Insufficient frames for blink detection.")
            return 0.0, False, reasons
        closed = ear < (np.median(ear) * 0.75)
        blinked = bool(np.any(closed) and np.any(~closed))
        score = 85.0 if blinked else 25.0
        reasons.append("Blink detected (EAR)." if blinked else "No blink observed.")
        return score, blinked, reasons

    signal = np.maximum(left, right)
    peak = float(signal.max())
    baseline = float(np.percentile(signal, 20))
    transient = peak - baseline
    blinked = peak > 0.5 and transient > 0.3
    # Reward a clear, transient closure.
    score = clamp(linear_map(transient, 0.1, 0.6, 20.0, 100.0)) if blinked else \
        clamp(linear_map(peak, 0.0, 0.5, 0.0, 45.0))
    reasons.append("Natural blink detected." if blinked else "No clear blink detected.")
    return score, blinked, reasons


def _ear_series(results: list[LandmarkResult]) -> np.ndarray:
    vals = []
    for r in results:
        if not r.found:
            continue
        lm = r.landmarks
        # Vertical eye opening over horizontal width (left eye).
        horiz = np.linalg.norm(lm[LEFT_EYE_OUTER, :2] - lm[LEFT_EYE_INNER, :2]) + 1e-6
        vert = np.linalg.norm(lm[159, :2] - lm[145, :2]) if lm.shape[0] > 159 else 0.0
        vals.append(vert / horiz)
    return np.asarray(vals)


# --------------------------------------------------------------------------- #
# Stage 4 - Head-turn challenge (motion parallax)
# --------------------------------------------------------------------------- #
def _challenge_stage(
    results: list[LandmarkResult], challenge: ChallengeType
) -> tuple[float, bool, list[str]]:
    """Validate the requested head movement using landmark-based yaw/pitch.

    A challenge passes when the user produces enough motion along the *correct
    axis* (horizontal for turn-left/right, vertical for look-up/down). Exact
    left-vs-right direction is rewarded but not required, because front cameras
    are often mirrored — the liveness signal is responding with the right kind
    of motion on cue.
    """
    reasons: list[str] = []
    valid = [r for r in results if r.found]
    if len(valid) < 4:
        reasons.append("Insufficient frames for the head-turn challenge.")
        return 0.0, False, reasons

    sigs = np.array([_head_signals(r.landmarks) for r in valid])  # (N, 2): yaw, pitch
    yaw, pitch = sigs[:, 0], sigs[:, 1]
    yaw_range = float(yaw.max() - yaw.min())
    pitch_range = float(pitch.max() - pitch.min())

    horizontal = challenge in (ChallengeType.TURN_LEFT, ChallengeType.TURN_RIGHT)
    if horizontal:
        axis_range, other_range = yaw_range, pitch_range
        signed = float(yaw[int(np.argmax(np.abs(yaw - yaw[0])))] - yaw[0])
        # Mirrored cameras flip sign, so direction is a soft bonus only.
        want_negative = challenge == ChallengeType.TURN_LEFT
    else:
        axis_range, other_range = pitch_range, yaw_range
        signed = float(pitch[int(np.argmax(np.abs(pitch - pitch[0])))] - pitch[0])
        want_negative = challenge == ChallengeType.LOOK_UP

    # Calibrated for the normalised signals: ~0.05 weak, >=0.20 strong turn.
    mag_score = clamp(linear_map(axis_range, 0.05, 0.22, 0.0, 100.0))
    axis_dominant = axis_range >= (other_range * 0.7)
    passed = axis_range >= 0.09 and axis_dominant
    direction_ok = (signed < 0) == want_negative

    score = mag_score
    if not axis_dominant:
        score *= 0.7
        reasons.append("Head motion was not predominantly along the requested axis.")
    if passed:
        axis = "left/right" if horizontal else "up/down"
        if direction_ok:
            reasons.append(f"Successful '{challenge.value}' head-turn challenge.")
        else:
            reasons.append(f"Correct {axis} head motion detected (camera may be mirrored).")
    else:
        reasons.append("Head-turn motion was insufficient; turn more clearly on cue.")

    return clamp(score), bool(passed), reasons


# --------------------------------------------------------------------------- #
# Stage 5 - Depth verification (non-planarity / parallax)
# --------------------------------------------------------------------------- #
def _depth_stage(results: list[LandmarkResult]) -> tuple[float, bool, list[str]]:
    """A flat photo/screen maps frame-to-frame by a homography; a real 3D face
    leaves large residuals (parallax) under rotation."""
    reasons: list[str] = []
    valid = [r for r in results if r.found]
    if len(valid) < 4:
        reasons.append("Insufficient frames for depth verification.")
        return 0.0, False, reasons

    # Pick the two frames with the most yaw separation (landmark-based signal).
    yaw = np.array([_head_signals(r.landmarks)[0] for r in valid])
    i_min, i_max = int(np.argmin(yaw)), int(np.argmax(yaw))
    if abs(yaw[i_max] - yaw[i_min]) < 0.06:
        # Genuinely cannot measure depth without rotation -> neutral, NOT planar.
        reasons.append("Not enough head rotation to measure depth (turn your head for this check).")
        return 55.0, False, reasons

    a = valid[i_min].landmarks[RIGID_POINTS, :2].astype(np.float32)
    b = valid[i_max].landmarks[RIGID_POINTS, :2].astype(np.float32)
    if a.shape[0] < 8:
        return 50.0, False, reasons

    H, _ = cv2.findHomography(a, b, cv2.RANSAC, 3.0)
    if H is None:
        reasons.append("Could not fit planar model; depth check neutral.")
        return 55.0, False, reasons

    proj = cv2.perspectiveTransform(a.reshape(-1, 1, 2), H).reshape(-1, 2)
    residual = np.linalg.norm(proj - b, axis=1)
    iod = _interocular(valid[i_min].landmarks)
    norm_residual = float(np.median(residual) / iod)

    # Planar surface (photo/screen) -> tiny residual; real 3D face -> larger.
    score = clamp(linear_map(norm_residual, 0.008, 0.06, 0.0, 100.0))
    passed = norm_residual >= 0.02
    if passed:
        reasons.append("Strong depth parallax observed (genuine 3D structure).")
    else:
        reasons.append("Motion is planar; possible photo or screen replay.")
    return score, passed, reasons


# --------------------------------------------------------------------------- #
# Stage 6 - Micro-movement
# --------------------------------------------------------------------------- #
def _micro_movement_stage(results: list[LandmarkResult]) -> tuple[float, np.ndarray, list[str]]:
    reasons: list[str] = []
    valid = [r for r in results if r.found]
    if len(valid) < 5:
        reasons.append("Insufficient frames for micro-movement analysis.")
        return 0.0, np.array([]), reasons

    series = []  # normalized micro-point positions per frame, nose-anchored
    for r in valid:
        lm = r.landmarks
        iod = _interocular(lm)
        nose = lm[NOSE_TIP, :2]
        pts = (lm[MICRO_POINTS, :2] - nose) / iod  # remove global translation
        series.append(pts.flatten())
    arr = np.asarray(series)
    motion = np.linalg.norm(np.diff(arr, axis=0), axis=1)  # per-frame micro displacement
    mean_motion = float(np.mean(motion))

    # Too still -> photo; healthy involuntary motion -> alive; too much -> noise.
    score = clamp(linear_map(mean_motion, 0.002, 0.03, 0.0, 100.0))
    if mean_motion < 0.002:
        reasons.append("Almost no micro-movement; possible static image.")
    else:
        reasons.append("Involuntary micro-movements consistent with a live subject.")
    return score, motion, reasons


# --------------------------------------------------------------------------- #
# Stage 7 - Replay detection
# --------------------------------------------------------------------------- #
def _replay_stage(motion: np.ndarray) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if motion.size < 8:
        return 70.0, reasons
    period = periodicity_score(motion)
    # High periodicity => looping replay => low resistance.
    resistance = clamp(linear_map(period, 0.2, 0.85, 100.0, 0.0))
    if period > 0.7:
        reasons.append("Periodic, repeating motion detected (replay indicator).")
    else:
        reasons.append("No replay/looping characteristics detected.")
    return resistance, reasons


# --------------------------------------------------------------------------- #
# Optional - rPPG (advisory only)
# --------------------------------------------------------------------------- #
def _rppg_bpm(frames: list[np.ndarray], results: list[LandmarkResult], fps: float) -> float | None:
    greens = []
    for f, r in zip(frames, results):
        if not r.found:
            continue
        lm = r.landmarks
        # Forehead ROI above the eyes.
        x1 = int(lm[:, 0].min()); x2 = int(lm[:, 0].max())
        ytop = int(lm[:, 1].min())
        eye_y = int(lm[LEFT_EYE_OUTER, 1])
        roi = f[max(0, ytop):max(1, eye_y), max(0, x1):max(1, x2)]
        if roi.size == 0:
            continue
        greens.append(float(roi[:, :, 1].mean()))  # green channel
    g = np.asarray(greens)
    if g.size < int(fps * 2):  # need ~2s of signal
        return None
    freq, power = dominant_frequency(g, fps)
    if power < 0.1 or not (0.7 <= freq <= 4.0):
        return None
    return round(freq * 60.0, 1)


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def verify_liveness(
    frames: list[np.ndarray],
    challenge: ChallengeType = ChallengeType.TURN_LEFT,
    fps: float = 15.0,
) -> LivenessResult:
    """Run the full Layer 3 active-liveness pipeline over a frame sequence."""
    frames = sample_frames(frames, MAX_FRAMES)
    if len(frames) < 4:
        return LivenessResult(
            liveness_score=0.0, reasons=["Need at least 4 frames for liveness verification."]
        )

    results = [detect_landmarks(f) for f in frames]
    found = sum(1 for r in results if r.found)
    if found < 3:
        return LivenessResult(
            liveness_score=0.0,
            reasons=["Face was not reliably detected across the sequence."],
        )

    position_score, r_pos = _position_stage(results)
    lighting_score, r_light = _lighting_stage(frames, results)
    blink_score, blinked, r_blink = _blink_stage(results)
    challenge_score, challenge_passed, r_ch = _challenge_stage(results, challenge)
    depth_score, depth_passed, r_depth = _depth_stage(results)
    motion_score, motion, r_micro = _micro_movement_stage(results)
    replay_score, r_replay = _replay_stage(motion)
    rppg = _rppg_bpm(frames, results, fps)

    base = (
        0.10 * position_score
        + 0.10 * lighting_score
        + 0.25 * blink_score
        + 0.25 * challenge_score
        + 0.20 * depth_score
        + 0.10 * motion_score
    )
    # Replay resistance gates multiplicatively (anti-spoof), never inflates.
    replay_factor = linear_map(replay_score, 0.0, 100.0, 0.55, 1.0)
    liveness_score = clamp(base * replay_factor)

    reasons = r_pos + r_light + r_blink + r_ch + r_depth + r_micro + r_replay
    if rppg is not None:
        reasons.append(f"Advisory rPPG pulse estimate: {rppg:.0f} bpm (not used in scoring).")

    logger.info(
        "Layer3 liveness={:.1f} pos={:.0f} light={:.0f} blink={:.0f} chal={:.0f} "
        "depth={:.0f} micro={:.0f} replay={:.0f}",
        liveness_score, position_score, lighting_score, blink_score,
        challenge_score, depth_score, motion_score, replay_score,
    )

    return LivenessResult(
        liveness_score=round(liveness_score, 1),
        position_score=round(position_score, 1),
        lighting_score=round(lighting_score, 1),
        blink_score=round(blink_score, 1),
        challenge_score=round(challenge_score, 1),
        depth_score=round(depth_score, 1),
        motion_score=round(motion_score, 1),
        replay_resistance_score=round(replay_score, 1),
        blink_detected=bool(blinked),
        challenge_passed=bool(challenge_passed),
        depth_passed=bool(depth_passed),
        rppg_bpm=rppg,
        reasons=reasons,
    )
