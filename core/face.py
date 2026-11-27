"""Face detection (YuNet) and face recognition (SFace) using OpenCV's built-in DNN.

Both models are small, free ONNX models from the OpenCV Model Zoo and run on CPU.
"""
import math
import urllib.request

import cv2
import numpy as np

from .config import YUNET_MODEL, SFACE_MODEL, MODEL_URLS, FACE_MATCH_COSINE

_detector = None
_recognizer = None


def ensure_models():
    """Download the two ONNX models on first run if they are missing."""
    for path in (YUNET_MODEL, SFACE_MODEL):
        if not path.exists() or path.stat().st_size < 100_000:
            path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(MODEL_URLS[path.name], path)


def _models():
    global _detector, _recognizer
    if _detector is None:
        ensure_models()
        _detector = cv2.FaceDetectorYN.create(str(YUNET_MODEL), "", (320, 320), 0.6, 0.3, 5000)
        _recognizer = cv2.FaceRecognizerSF.create(str(SFACE_MODEL), "")
    return _detector, _recognizer


def decode_image(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read image")
    return img


def _limit_size(img, max_side=1280):
    h, w = img.shape[:2]
    s = max(h, w)
    if s > max_side:
        f = max_side / s
        img = cv2.resize(img, (int(w * f), int(h * f)))
    return img


def detect_faces(img):
    """Return (resized_img, faces) where faces is an Nx15 array sorted by area desc."""
    det, _ = _models()
    img = _limit_size(img)
    h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    if faces is None:
        return img, np.zeros((0, 15), dtype=np.float32)
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    return img, np.array(faces)


def embedding(img, face):
    _, rec = _models()
    aligned = rec.alignCrop(img, face)
    return rec.feature(aligned).flatten().astype(np.float32)


def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def match_confidence(cos: float) -> float:
    """Map SFace cosine similarity to a 0-1 'same person' confidence.

    Centred on OpenCV's recommended threshold (0.363 -> 50%).
    """
    return 1.0 / (1.0 + math.exp(-(cos - FACE_MATCH_COSINE) * 14))


def yaw_ratio(face) -> float:
    """Rough head yaw from YuNet landmarks: nose offset from the eye midpoint,
    normalised by the distance between the eyes. ~0 = frontal."""
    rex, rey, lex, ley, nx, ny = face[4:10]
    eye_mid = (rex + lex) / 2
    eye_dist = abs(lex - rex) + 1e-6
    return float((nx - eye_mid) / eye_dist)


def crop(img, face, pad=0.25):
    x, y, w, h = [int(v) for v in face[:4]]
    px, py = int(w * pad), int(h * pad)
    H, W = img.shape[:2]
    x0, y0 = max(0, x - px), max(0, y - py)
    x1, y1 = min(W, x + w + px), min(H, y + h + py)
    return img[y0:y1, x0:x1]


def to_png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""
