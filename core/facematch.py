"""Check 3 — Face Match: selfie vs the photo printed on the ID."""
from . import face as F
from .types import CheckResult


def run(selfie: bytes, id_bytes: bytes) -> tuple[CheckResult, object]:
    """Returns (result, selfie_embedding or None)."""
    res = CheckResult("face")
    s_img, s_faces = F.detect_faces(F.decode_image(selfie))
    d_img, d_faces = F.detect_faces(F.decode_image(id_bytes))
    if len(s_faces) == 0 or len(d_faces) == 0:
        where = "selfie" if len(s_faces) == 0 else "ID document"
        res.add("FACE_MATCH_IMPOSSIBLE", f"Face match not possible: no face found on the {where}.", 60, "high", floor=61)
        return res, None

    s_vec = F.embedding(s_img, s_faces[0])
    d_vec = F.embedding(d_img, d_faces[0])
    cos = F.cosine(s_vec, d_vec)
    conf = F.match_confidence(cos)
    res.details.update(cosine=round(cos, 3), confidence=round(conf, 3))
    res.images["selfie_face"] = F.to_png(F.crop(s_img, s_faces[0]))
    res.images["id_face"] = F.to_png(F.crop(d_img, d_faces[0]))

    risk = int(round(100 * (1 - conf)))
    if conf >= 0.80:
        res.add("FACE_MATCH", f"Selfie matches the ID photo (confidence {conf:.0%}).", risk, "info")
    elif conf >= 0.50:
        res.add("FACE_MATCH_WEAK", f"Face match confidence is only {conf:.0%}.", risk, "medium")
    else:
        res.add("FACE_MISMATCH", f"Selfie and ID photo appear to be DIFFERENT people (confidence {conf:.0%}).", risk, "critical", floor=75)
    return res, s_vec
