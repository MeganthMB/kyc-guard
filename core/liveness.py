"""Check 1 — Deepfake & Liveness.

Layers (strongest first):
  1. Active liveness: a random head-turn challenge across two live frames.
     A static photo, printed picture or pre-recorded clip cannot follow a
     challenge it did not know in advance.
  2. Capture integrity: uploaded files and virtual-camera / injected streams
     are riskier than a live in-app capture.
  3. Content provenance: AI-generator and editing-tool fingerprints in the
     file (C2PA content credentials, Stable Diffusion PNG parameters, EXIF
     Software tags).
  4. Passive image forensics: screen-replay moiré (periodic peaks in the
     frequency spectrum), blur, and an experimental GAN spectral check.

Layer 4 is a lightweight POC heuristic. A trained deepfake classifier can be
plugged in at `model_deepfake_score()` without touching the rest of the app.
"""
import io

import cv2
import numpy as np
from PIL import Image

from . import face as F
from .config import CAMERA_MIRRORED
from .types import CheckResult

AI_MARKERS = {
    b"c2pa": "C2PA content credentials present (used by AI generators such as Firefly / DALL-E)",
    b"Stable Diffusion": "Stable Diffusion generation metadata",
    b"Midjourney": "Midjourney metadata",
    b"DALL-E": "DALL-E metadata",
    b"ComfyUI": "ComfyUI workflow metadata",
    b"FaceApp": "FaceApp editing metadata",
    b"Reface": "Reface face-swap metadata",
    b"DeepFaceLab": "DeepFaceLab metadata",
}
EDIT_TOOLS = ("photoshop", "gimp", "snapseed", "picsart", "facetune", "lightroom", "canva")


def provenance_findings(data: bytes, res: CheckResult):
    head = data[:2_000_000]
    for marker, desc in AI_MARKERS.items():
        if marker in head:
            res.add("AI_GENERATOR_METADATA", f"Selfie file contains {desc}.", 45, "high", floor=70)
            break
    try:
        im = Image.open(io.BytesIO(data))
        info = " ".join(str(v) for v in im.info.values() if isinstance(v, (str, bytes)))
        if "parameters" in im.info or "Negative prompt" in info:
            res.add("AI_PROMPT_METADATA", "Image carries text-to-image prompt parameters.", 45, "high", floor=70)
        exif = im.getexif()
        software = str(exif.get(0x0131, "")).lower()
        if any(t in software for t in EDIT_TOOLS):
            res.add("EDITED_SELFIE", f"Selfie was processed with editing software ({exif.get(0x0131)}).", 20)
    except Exception:
        pass


def moire_score(gray_face) -> float:
    """Peakiness of the high-frequency spectrum. Screens and prints add sharp,
    periodic peaks (moiré); natural skin gives a smooth fall-off."""
    g = cv2.resize(gray_face, (256, 256)).astype(np.float32)
    g = g - cv2.GaussianBlur(g, (0, 0), 3)  # keep fine texture only
    spec = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(g))))
    yy, xx = np.ogrid[:256, :256]
    r = np.hypot(yy - 128, xx - 128)
    ring = spec[(r > 25) & (r < 120)]
    return float((ring.max() - ring.mean()) / (ring.std() + 1e-6))


def spectral_tail(gray_face) -> float:
    """Experimental GAN check: share of energy in the top frequency band of the
    azimuthally averaged spectrum. Up-sampling layers in generators often
    leave an unnaturally flat / bumpy high-frequency tail."""
    g = cv2.resize(gray_face, (256, 256)).astype(np.float32)
    p = np.abs(np.fft.fftshift(np.fft.fft2(g))) ** 2
    yy, xx = np.indices(p.shape)
    r = np.hypot(yy - 128, xx - 128).astype(int)
    radial = np.bincount(r.ravel(), p.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    radial = radial[1:128]
    return float(radial[96:].sum() / (radial.sum() + 1e-9))


def model_deepfake_score(face_bgr):
    """Plug-in point for a trained deepfake classifier (e.g. an EfficientNet
    fine-tuned on FaceForensics++). Return a probability 0-1, or None."""
    return None


def run(selfie: bytes, source: str = "upload", challenge: dict | None = None,
        virtual_camera: bool = False) -> CheckResult:
    res = CheckResult("liveness")
    img = F.decode_image(selfie)
    img, faces = F.detect_faces(img)

    if len(faces) == 0:
        res.add("NO_FACE", "No face could be detected in the selfie.", 70, "high", floor=61)
        return res
    if len(faces) > 1:
        res.add("MULTIPLE_FACES", f"{len(faces)} faces detected in the selfie (possible coaching or photo-of-photo).", 25)

    face = faces[0]
    res.details["face_score"] = round(float(face[14]), 3)
    H, W = img.shape[:2]
    area = face[2] * face[3] / (H * W)
    res.details["face_area_pct"] = round(area * 100, 1)
    if area < 0.03:
        res.add("FACE_TOO_SMALL", "Face occupies less than 3% of the frame.", 10)

    crop = F.crop(img, face, pad=0.05)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    res.images["face"] = F.to_png(F.crop(img, face))

    # --- Capture integrity -------------------------------------------------
    res.details["source"] = source
    if virtual_camera:
        res.add("VIRTUAL_CAMERA", "Virtual camera / injected video stream reported by the device (camera-injection attack).", 60, "critical", floor=82)
    if source == "upload":
        res.add("NOT_LIVE_CAPTURE", "Selfie was uploaded as a file, not captured live in the app.", 20)

    # --- Provenance --------------------------------------------------------
    provenance_findings(selfie, res)

    # --- Active liveness challenge ------------------------------------------
    if challenge and challenge.get("frame_a") and challenge.get("frame_b"):
        try:
            ia, fa = F.detect_faces(F.decode_image(challenge["frame_a"]))
            ib, fb = F.detect_faces(F.decode_image(challenge["frame_b"]))
            if len(fa) == 0 or len(fb) == 0:
                res.add("CHALLENGE_NO_FACE", "Face not visible in one of the challenge frames.", 35, "high")
            else:
                ya, yb = F.yaw_ratio(fa[0]), F.yaw_ratio(fb[0])
                delta = yb - ya
                same = F.match_confidence(F.cosine(F.embedding(ia, fa[0]), F.embedding(ib, fb[0])))
                res.details.update(yaw_a=round(ya, 3), yaw_b=round(yb, 3), challenge_same_person=round(same, 3))
                want = challenge.get("direction", "LEFT")
                # In an un-mirrored image, the person turning to THEIR left moves the nose towards image-right (+x).
                expected_sign = 1 if want == "LEFT" else -1
                if CAMERA_MIRRORED:
                    expected_sign = -expected_sign
                if same < 0.5:
                    res.add("CHALLENGE_PERSON_CHANGED", "Different person in the two challenge frames.", 60, "critical", floor=82)
                elif abs(delta) < 0.12:
                    res.add("CHALLENGE_FAILED", f"Head did not turn when asked to turn {want} (static photo or replay suspected).", 45, "high", floor=61)
                elif np.sign(delta) != expected_sign:
                    res.add("CHALLENGE_WRONG_DIRECTION", f"Head turned the wrong way for the '{want}' challenge.", 15)
                else:
                    res.add("CHALLENGE_PASSED", f"Live head-turn challenge ({want}) passed by the same person.", 0)
        except Exception as e:  # never crash the pipeline on a bad frame
            res.add("CHALLENGE_ERROR", f"Challenge frames could not be analysed ({e}).", 20)
    elif source == "camera":
        res.add("NO_CHALLENGE", "Live capture without an active liveness challenge.", 10)

    # --- Passive forensics ---------------------------------------------------
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    moire = moire_score(gray)
    tail = spectral_tail(gray)
    res.details.update(sharpness=round(sharp, 1), moire=round(moire, 2), spectral_tail=round(tail, 5))
    if sharp < 15:
        res.add("BLURRY_FACE", "Face is very blurry (re-capture or replayed screen suspected).", 15)
    if moire > 4.6:
        strong = moire > 5.5
        res.add("SCREEN_REPLAY_PATTERN", f"Periodic moiré pattern found (score {moire:.1f}) — typical of a photo of a screen or print.",
                35 if strong else 25, "high" if strong else "medium", floor=61 if strong else 0)
    if tail > 0.02:
        res.add("SPECTRAL_ANOMALY", "Unusual high-frequency spectrum (experimental GAN artefact check).", 15)

    p = model_deepfake_score(crop)
    if p is not None:
        res.details["model_deepfake_prob"] = round(p, 3)
        if p > 0.5:
            res.add("DEEPFAKE_MODEL", f"Deepfake classifier probability {p:.0%}.", int(70 * p), "high", floor=70 if p > 0.8 else 0)
    return res
