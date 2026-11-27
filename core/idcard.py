"""Demo identity document issuer.

Real Indian IDs (e.g. Aadhaar Secure QR) carry a QR code that is digitally
signed by the issuing authority, so any change to the data breaks the
signature. This module simulates that with a *fictional* demo issuer and an
Ed25519 key pair, so the hackathon demo never needs a real ID card.

Cards are clearly marked SPECIMEN and use a made-up issuer name.
"""
import base64
import io
import json
import random

import cv2
import numpy as np
import qrcode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image, ImageDraw, ImageFont

from .config import ISSUER_KEY_PATH

ISSUER = "DEMO-NIA"  # fictional "National Identity Authority (Demo)"
CARD_W, CARD_H = 1012, 638
PHOTO_BOX = (40, 150, 280, 450)   # x0, y0, x1, y1
QR_BOX = (702, 300, 992, 590)
BG = (246, 249, 252)

# ---------------------------------------------------------------- Verhoeff --
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
      [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
      [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
      [9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
      [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
      [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
_INV = [0,4,3,2,1,5,6,7,8,9]


def verhoeff_valid(num: str) -> bool:
    """12-digit Aadhaar-style numbers end in a Verhoeff check digit."""
    if not num.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_digit(num: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


def new_id_number() -> str:
    base = str(random.randint(2, 9)) + "".join(str(random.randint(0, 9)) for _ in range(10))
    return base + verhoeff_digit(base)


def fmt_id(num: str) -> str:
    return " ".join(num[i:i + 4] for i in range(0, len(num), 4))


def mask_id(num: str) -> str:
    num = "".join(ch for ch in str(num) if ch.isdigit())
    return "XXXX XXXX " + num[-4:] if len(num) >= 4 else "XXXX"


# ---------------------------------------------------------------- Keys -------
def issuer_private_key():
    if ISSUER_KEY_PATH.exists():
        return serialization.load_pem_private_key(ISSUER_KEY_PATH.read_bytes(), None)
    key = Ed25519PrivateKey.generate()
    ISSUER_KEY_PATH.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    return key


def issuer_public_key():
    return issuer_private_key().public_key()


def _canonical(payload: dict) -> bytes:
    return json.dumps({k: v for k, v in payload.items() if k != "s"},
                      sort_keys=True, separators=(",", ":")).encode()


def sign_payload(payload: dict, key=None) -> dict:
    key = key or issuer_private_key()
    payload = dict(payload)
    payload["s"] = base64.b64encode(key.sign(_canonical(payload))).decode()
    return payload


def verify_payload(payload: dict) -> bool:
    try:
        sig = base64.b64decode(payload["s"])
        issuer_public_key().verify(sig, _canonical(payload))
        return True
    except Exception:
        return False


def pack_embedding(vec) -> str:
    """Compress the 128-d face fingerprint to 64 bytes (4 bits per value)."""
    v = np.asarray(vec, dtype=np.float32)
    v = v / (np.abs(v).max() + 1e-9)
    q = np.clip(np.round(v * 7), -7, 7).astype(np.int8) + 8          # 1..15
    packed = (q[0::2].astype(np.uint8) << 4) | q[1::2].astype(np.uint8)
    return base64.b64encode(packed.tobytes()).decode()


def unpack_embedding(s: str):
    b = np.frombuffer(base64.b64decode(s), dtype=np.uint8)
    out = np.empty(b.size * 2, dtype=np.float32)
    out[0::2] = (b >> 4).astype(np.float32) - 8
    out[1::2] = (b & 15).astype(np.float32) - 8
    return out


# ---------------------------------------------------------------- Drawing ----
def _font(size, bold=False):
    names = (["arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold
             else ["arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit_photo(face_img: Image.Image) -> Image.Image:
    x0, y0, x1, y1 = PHOTO_BOX
    bw, bh = x1 - x0, y1 - y0
    im = face_img.convert("RGB")
    r = max(bw / im.width, bh / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1))
    left, top = (im.width - bw) // 2, (im.height - bh) // 2
    return im.crop((left, top, left + bw, top + bh))


def portrait_from_photo(photo_bytes: bytes) -> Image.Image:
    """Crop a passport-style portrait around the largest face, if one is found."""
    from . import face as F
    img = F.decode_image(photo_bytes)
    img, faces = F.detect_faces(img)
    if len(faces):
        x, y, w, h = faces[0][:4]
        cx, cy = x + w / 2, y + h / 2
        bh = h * 2.0
        bw = bh * (PHOTO_BOX[2] - PHOTO_BOX[0]) / (PHOTO_BOX[3] - PHOTO_BOX[1])
        H, W = img.shape[:2]
        x0, y0 = int(max(0, cx - bw / 2)), int(max(0, cy - bh * 0.45))
        x1, y1 = int(min(W, cx + bw / 2)), int(min(H, cy + bh * 0.55))
        img = img[y0:y1, x0:x1]
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def _qr_image(payload: dict) -> Image.Image:
    """Render the QR with whole-pixel modules so it stays machine-readable."""
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=1, border=2)
    q.add_data(json.dumps(payload, separators=(",", ":")))
    q.make(fit=True)
    size = QR_BOX[2] - QR_BOX[0]
    modules = q.modules_count + 4
    q.box_size = max(2, size // modules)
    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
    canvas = Image.new("RGB", (size, size), "white")
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def _wrap(text, width=30, max_lines=2):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def draw_card(person: dict, portrait: Image.Image, payload: dict) -> Image.Image:
    card = Image.new("RGB", (CARD_W, CARD_H), BG)
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, CARD_W, 110), fill=(23, 54, 93))
    d.text((40, 22), "NATIONAL IDENTITY AUTHORITY (DEMO)", font=_font(34, True), fill="white")
    d.text((40, 68), "Fictional issuer for hackathon testing - not a government document", font=_font(20), fill=(200, 215, 235))
    d.rectangle((0, CARD_H - 12, CARD_W, CARD_H), fill=(236, 128, 36))

    card.paste(_fit_photo(portrait), PHOTO_BOX[:2])
    d.rectangle(PHOTO_BOX, outline=(23, 54, 93), width=3)

    lx, y = 320, 150
    rows = [("Name", person["name"]), ("Date of Birth", person["dob"]),
            ("Gender", person.get("gender", "")), ("Address", person.get("address", ""))]
    for label, val in rows:
        d.text((lx, y), label.upper(), font=_font(17, True), fill=(90, 105, 125))
        y += 22
        val = str(val)
        lines = _wrap(val) if label == "Address" else [val]
        for line in lines:
            d.text((lx, y), line, font=_font(28 if label == "Name" else 24), fill=(20, 25, 35))
            y += 32
        y += 12
    d.text((40, 500), fmt_id(person["id_number"]), font=_font(46, True), fill=(20, 25, 35))
    d.text((40, 560), "ID NUMBER", font=_font(17, True), fill=(90, 105, 125))

    d.text((QR_BOX[0], QR_BOX[1] - 26), "SIGNED SECURE QR", font=_font(16, True), fill=(90, 105, 125))

    # diagonal SPECIMEN watermark
    wm = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(wm).text((250, 250), "SPECIMEN  -  DEMO ONLY", font=_font(64, True), fill=(200, 30, 30, 45))
    card = Image.alpha_composite(card.convert("RGBA"), wm.rotate(18, center=(CARD_W / 2, CARD_H / 2))).convert("RGB")
    card.paste(_qr_image(payload), QR_BOX[:2])  # QR last, so the watermark never covers it
    return card


def jpeg_bytes(img: Image.Image, q=85) -> bytes:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return b.getvalue()


def build_payload(person: dict, face_vec=None) -> dict:
    p = {"v": 1, "iss": ISSUER, "n": person["name"], "d": person["dob"],
         "g": person.get("gender", ""), "i": person["id_number"], "a": person.get("address", "")}
    if face_vec is not None:
        p["f"] = pack_embedding(face_vec)
    return p


def make_card(person: dict, photo_bytes: bytes, variant: str = "genuine",
              alt_name: str = "", alt_photo: bytes | None = None) -> bytes:
    """Create a demo ID card as JPEG bytes.

    variant:
      genuine      - correctly signed, untouched
      edited_name  - printed name painted over after issuing (pixel edit)
      photo_swap   - printed photo replaced with someone else's
      forged_qr    - QR re-generated with fake data, signed with a fraudster key
    """
    from . import face as F
    portrait = portrait_from_photo(photo_bytes)
    face_vec = None
    try:
        p_bgr = cv2.cvtColor(np.array(_fit_photo(portrait)), cv2.COLOR_RGB2BGR)
        im, faces = F.detect_faces(p_bgr)
        if len(faces):
            face_vec = F.embedding(im, faces[0])
    except Exception:
        pass

    payload = sign_payload(build_payload(person, face_vec))

    if variant == "forged_qr":
        fake = dict(person, name=alt_name or person["name"])
        payload = sign_payload(build_payload(fake, face_vec), key=Ed25519PrivateKey.generate())
        person = fake

    card = draw_card(person, portrait, payload)
    data = jpeg_bytes(card, 85)  # the "issued" card

    if variant == "edited_name":
        im = Image.open(io.BytesIO(data)).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle((318, 172, 735, 206), fill=BG)
        d.text((320, 172), alt_name or "Rohit Kumar", font=_font(28), fill=(20, 25, 35))
        data = jpeg_bytes(im, 95)  # saved again by the fraudster's editor
    elif variant == "photo_swap" and alt_photo:
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.paste(_fit_photo(portrait_from_photo(alt_photo)), PHOTO_BOX[:2])
        ImageDraw.Draw(im).rectangle(PHOTO_BOX, outline=(23, 54, 93), width=3)
        data = jpeg_bytes(im, 95)
    return data
