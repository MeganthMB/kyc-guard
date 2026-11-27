"""Check 2 — Document Verification.

  * Secure QR: decode the QR on the ID and verify the issuer's digital
    signature. Any edit to the identity data breaks the signature.
  * Photo-swap: compare the face printed on the card with the face
    fingerprint embedded inside the signed QR.
  * Error Level Analysis (ELA): re-compress the image and look for regions
    with a different compression history (pasted / painted-over areas).
  * Metadata: editing software tags, image quality / readability.
"""
import io
import json

import cv2
import numpy as np
from PIL import Image

from . import face as F
from . import idcard
from .liveness import EDIT_TOOLS
from .types import CheckResult


def decode_qr(img_bgr):
    """Try OpenCV's two QR decoders at a few scales / binarisations."""
    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        detectors.append(cv2.QRCodeDetectorAruco())
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates = [img_bgr, th]
    for scale in (1.5, 2.0, 0.75):
        candidates.append(cv2.resize(th, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST if scale > 1 else cv2.INTER_AREA))
    for im in candidates:
        for det in detectors:
            try:
                text, _, _ = det.detectAndDecode(im)
            except cv2.error:
                continue
            if text:
                return text
    return None


_STD_LUM = [16,11,10,16,24,40,51,61,12,12,14,19,26,58,60,55,14,13,16,24,40,57,69,56,
            14,17,22,29,51,87,80,62,18,22,37,56,68,109,103,77,24,35,55,64,81,104,113,92,
            49,64,78,87,103,121,120,101,72,92,95,98,112,100,103,99]


def jpeg_quality(im) -> int | None:
    """Estimate the last JPEG save quality from the luminance quantisation table."""
    q = getattr(im, "quantization", None)
    if not q:
        return None
    observed = sum(q[0])
    best, bq = None, None
    for quality in range(1, 101):
        s = 5000 / quality if quality < 50 else 200 - 2 * quality
        tbl = sum(min(255, max(1, (v * s + 50) // 100)) for v in _STD_LUM)
        if best is None or abs(tbl - observed) < best:
            best, bq = abs(tbl - observed), quality
    return bq


def _blocks(a, bs=16):
    H, W = (a.shape[0] // bs) * bs, (a.shape[1] // bs) * bs
    return a[:H, :W].reshape(H // bs, bs, W // bs, bs)


def _err_map(orig_rgb, lum, q):
    """Mean absolute luminance change per 16x16 block after re-saving at quality q."""
    buf = io.BytesIO()
    orig_rgb.save(buf, "JPEG", quality=q)
    r = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("L"), dtype=np.float32)
    return _blocks(np.abs(lum - r)).mean(axis=(1, 3))


def ela(data: bytes):
    """JPEG-ghost Error Level Analysis.

    An ID issued as a JPEG at quality Q, then edited and re-saved at a higher
    quality, keeps a "ghost": re-compressing at Q barely changes untouched
    areas, but changes edited areas a lot. We find Q from the dip in the
    error curve, then flag blocks that do NOT show the dip.
    Returns (stats dict, overlay PNG with suspicious regions boxed in red).
    """
    im = Image.open(io.BytesIO(data))
    last_q = jpeg_quality(im)
    orig = im.convert("RGB")
    lum = np.asarray(orig.convert("L"), dtype=np.float32)
    sd = _blocks(lum).std(axis=(1, 3))
    textured = sd > 12
    stats = {"last_quality": last_q, "ghost_quality": None, "tamper_blocks": 0, "regions": []}
    base = cv2.cvtColor(np.asarray(orig), cv2.COLOR_RGB2BGR).copy()

    ghost_q = None
    if last_q and last_q >= 70 and textured.sum() > 20:
        qs = list(range(55, last_q - 3, 2))
        curve = {q: float(_err_map(orig, lum, q)[textured].mean()) for q in qs}
        best = 0.0
        for i in range(1, len(qs) - 1):
            q = qs[i]
            depth = (curve[qs[i - 1]] + curve[qs[i + 1]]) / 2 - curve[q]
            if depth > best and depth > 0.1 * curve[q]:
                best, ghost_q = depth, q
    if ghost_q and last_q - ghost_q >= 6:
        stats["ghost_quality"] = ghost_q
        lo, hi = ghost_q - 8, min(ghost_q + 6, last_q - 3)
        e0 = _err_map(orig, lum, ghost_q)
        ref = (_err_map(orig, lum, lo) + _err_map(orig, lum, hi)) / 2
        valid = ref > 1.0
        ratio = e0 / np.maximum(ref, 1e-3)
        hot = ((ratio > 0.8) & valid).astype(np.uint8)
        hot = cv2.morphologyEx(hot, cv2.MORPH_CLOSE, np.ones((1, 3), np.uint8))
        k, _, st, _ = cv2.connectedComponentsWithStats(hot)
        stats["hot_fraction"] = round(float(hot.sum()) / max(1, int(valid.sum())), 3)
        regions = []
        for i in range(1, k):
            x, y, w, h, area = [int(v) for v in st[i]]
            if area >= 6:
                regions.append({"x": x * 16, "y": y * 16, "w": w * 16, "h": h * 16, "blocks": area})
                cv2.rectangle(base, (x * 16 - 4, y * 16 - 4), ((x + w) * 16 + 4, (y + h) * 16 + 4), (0, 0, 255), 4)
        stats["regions"] = sorted(regions, key=lambda r: -r["blocks"])
        stats["tamper_blocks"] = stats["regions"][0]["blocks"] if regions else 0
        # light tint on every block that lacks the ghost
        tint = cv2.resize(hot * 255, (orig.width, orig.height), interpolation=cv2.INTER_NEAREST)
        overlay = base.copy()
        overlay[tint > 0] = (0, 0, 255)
        base = cv2.addWeighted(base, 0.75, overlay, 0.25, 0)
    return stats, F.to_png(F._limit_size(base, 900))


def run(id_bytes: bytes) -> CheckResult:
    res = CheckResult("document")
    img = F.decode_image(id_bytes)
    h, w = img.shape[:2]
    res.details["resolution"] = f"{w}x{h}"
    if min(h, w) < 400:
        res.add("LOW_RESOLUTION", f"Document image is low resolution ({w}x{h}); text may be unreadable.", 15)

    sharp = float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    res.details["sharpness"] = round(sharp, 1)
    if sharp < 30:
        res.add("BLURRY_DOCUMENT", "Document is blurry; text may be unreadable.", 15)

    # --- metadata ---
    try:
        exif = Image.open(io.BytesIO(id_bytes)).getexif()
        sw = str(exif.get(0x0131, ""))
        if any(t in sw.lower() for t in EDIT_TOOLS):
            res.add("EDITING_SOFTWARE", f"Document image saved by editing software: {sw}.", 25)
    except Exception:
        pass

    # --- secure QR ---
    payload = None
    text = decode_qr(img)
    if not text:
        res.add("QR_NOT_READABLE", "Secure QR code missing or unreadable — identity data cannot be verified offline.", 35, "high")
    else:
        try:
            payload = json.loads(text)
        except Exception:
            res.add("QR_INVALID_FORMAT", "QR code does not contain a valid identity payload.", 50, "high", floor=61)
    if payload:
        res.details["qr_identity"] = {
            "name": payload.get("n"), "dob": payload.get("d"), "gender": payload.get("g"),
            "id_number_masked": idcard.mask_id(payload.get("i", "")), "address": payload.get("a"),
            "issuer": payload.get("iss"),
        }
        res.details["_qr_id_number"] = payload.get("i", "")
        if idcard.verify_payload(payload):
            res.add("QR_SIGNATURE_VALID", f"Secure QR signature verified against issuer {payload.get('iss')}.", 0)
        else:
            res.add("QR_SIGNATURE_INVALID", "Secure QR signature is INVALID — the identity data was forged or altered.", 80, "critical", floor=85)

        # --- photo swap: printed face vs face fingerprint inside the signed QR ---
        if payload.get("f"):
            x0, y0, x1, y1 = idcard.PHOTO_BOX
            sx, sy = w / idcard.CARD_W, h / idcard.CARD_H
            photo = img[int(y0 * sy):int(y1 * sy), int(x0 * sx):int(x1 * sx)]
            try:
                pim, pf = F.detect_faces(photo)
                if len(pf):
                    sim = F.match_confidence(F.cosine(F.embedding(pim, pf[0]), idcard.unpack_embedding(payload["f"])))
                    res.details["printed_photo_vs_qr"] = round(sim, 3)
                    if sim < 0.5:
                        res.add("PHOTO_SWAP", f"Printed photo does not match the face stored in the signed QR ({sim:.0%}) — photo was replaced.", 70, "critical", floor=85)
            except Exception:
                pass

    # --- ELA / JPEG ghost ---
    try:
        st, heat = ela(id_bytes)
        res.details["ela"] = st
        res.images["ela"] = heat
        tb, hf = st.get("tamper_blocks", 0), st.get("hot_fraction", 0)
        if st.get("ghost_quality") and tb >= 6 and hf < 0.3:
            res.add("TAMPERING_ELA", f"Error Level Analysis: a region was edited after the document was issued "
                    f"(original quality ~{st['ghost_quality']}, re-saved at ~{st['last_quality']}).", 40, "high", floor=61)
        elif st.get("ghost_quality"):
            res.add("RESAVED_DOCUMENT", "Document was re-saved after issue (no localised edit found).", 5)
    except Exception:
        pass

    # --- printed face for face match ---
    _, faces = F.detect_faces(img)
    res.details["faces_on_document"] = int(len(faces))
    if len(faces) == 0:
        res.add("NO_PHOTO_ON_ID", "No face photo found on the ID document.", 30, "high")
    return res
