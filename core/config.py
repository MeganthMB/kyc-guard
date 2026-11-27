"""Central configuration: paths, weights, thresholds and decision bands."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "kyc_guard.db"
ISSUER_KEY_PATH = DATA_DIR / "demo_issuer_key.pem"

for _d in (DATA_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

YUNET_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
MODEL_URLS = {
    YUNET_MODEL.name: "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    SFACE_MODEL.name: "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}

# SFace cosine-similarity threshold recommended by OpenCV for "same person".
FACE_MATCH_COSINE = 0.363

# Weight of each check in the blended score (must sum to 1.0).
WEIGHTS = {
    "liveness": 0.25,   # deepfake & liveness
    "document": 0.20,
    "face": 0.20,
    "data": 0.15,
    "device": 0.10,
    "synthetic": 0.10,
}

CHECK_LABELS = {
    "liveness": "Deepfake & Liveness",
    "document": "Document Verification",
    "face": "Face Match",
    "data": "Data Cross-Verification",
    "device": "Device & Network",
    "synthetic": "Synthetic Identity",
}

# Decision bands from the project brief.
BANDS = [
    (30, "APPROVE"),
    (60, "RE-VERIFY"),
    (80, "MANUAL REVIEW"),
    (100, "REJECT"),
]

DECISION_COLORS = {
    "APPROVE": "#1a7f37",
    "RE-VERIFY": "#b58500",
    "MANUAL REVIEW": "#d4561c",
    "REJECT": "#c62828",
}

# Set True if your webcam images come out mirrored (affects LEFT/RIGHT challenge).
CAMERA_MIRRORED = False
