"""SQLite storage. Privacy by design: the full ID number is never stored —
only a masked form for display and a keyed hash (HMAC) for duplicate linking."""
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime

import numpy as np

from .config import DB_PATH, DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY, created_at TEXT, name TEXT, dob TEXT, gender TEXT,
  phone TEXT, email TEXT, address TEXT, id_masked TEXT, id_hash TEXT,
  device_id TEXT, ip TEXT, selfie_path TEXT, id_path TEXT, face_emb BLOB,
  results TEXT, score INTEGER, decision TEXT, status TEXT,
  reviewer TEXT, review_note TEXT, reviewed_at TEXT, seeded INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT, ts TEXT,
  actor TEXT, action TEXT, note TEXT
);
"""

STATUS_FOR_DECISION = {
    "APPROVE": "AUTO_APPROVED",
    "RE-VERIFY": "RECAPTURE_REQUESTED",
    "MANUAL REVIEW": "PENDING_REVIEW",
    "REJECT": "AUTO_REJECTED",
}


def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _secret() -> bytes:
    p = DATA_DIR / "hash_secret.key"
    if not p.exists():
        p.write_bytes(secrets.token_bytes(32))
    return p.read_bytes()


def id_hash(id_number: str) -> str:
    d = "".join(ch for ch in str(id_number) if ch.isdigit())
    return hmac.new(_secret(), d.encode(), hashlib.sha256).hexdigest() if d else ""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_app_id(c) -> str:
    n = c.execute("SELECT COUNT(*) FROM applications").fetchone()[0] + 1001
    while c.execute("SELECT 1 FROM applications WHERE id=?", (f"APP-{n}",)).fetchone():
        n += 1
    return f"APP-{n}"


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def insert(c, row: dict):
    row = dict(row)
    if isinstance(row.get("results"), (dict, list)):
        row["results"] = json.dumps(row["results"], default=_json_default)
    if row.get("face_emb") is not None and not isinstance(row["face_emb"], bytes):
        row["face_emb"] = np.asarray(row["face_emb"], dtype=np.float32).tobytes()
    cols = ",".join(row)
    c.execute(f"INSERT INTO applications ({cols}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    c.commit()


def log(c, app_id, actor, action, note=""):
    c.execute("INSERT INTO audit (app_id, ts, actor, action, note) VALUES (?,?,?,?,?)",
              (app_id, now(), actor, action, note))
    c.commit()


def all_apps(c, include_emb=False):
    rows = [dict(r) for r in c.execute("SELECT * FROM applications ORDER BY created_at DESC")]
    for r in rows:
        r["results"] = json.loads(r["results"]) if r.get("results") else {}
        if include_emb and r.get("face_emb"):
            r["face_emb"] = np.frombuffer(r["face_emb"], dtype=np.float32)
        elif not include_emb:
            r.pop("face_emb", None)
    return rows


def get(c, app_id):
    r = c.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not r:
        return None
    r = dict(r)
    r["results"] = json.loads(r["results"]) if r.get("results") else {}
    r.pop("face_emb", None)
    return r


def audit_for(c, app_id):
    return [dict(r) for r in c.execute("SELECT * FROM audit WHERE app_id=? ORDER BY id", (app_id,))]


def review(c, app_id, status, reviewer, note):
    c.execute("UPDATE applications SET status=?, reviewer=?, review_note=?, reviewed_at=? WHERE id=?",
              (status, reviewer, note, now(), app_id))
    c.commit()
    log(c, app_id, reviewer, status, note)


def reset(c):
    c.executescript("DELETE FROM applications; DELETE FROM audit;")
    c.commit()


def clear_live(c):
    """Delete applications submitted during the demo, keep the seeded history."""
    from .config import UPLOAD_DIR
    ids = [r[0] for r in c.execute("SELECT id FROM applications WHERE seeded=0")]
    for i in ids:
        for p in UPLOAD_DIR.glob(f"{i}_*"):
            p.unlink(missing_ok=True)
    c.execute("DELETE FROM audit WHERE app_id IN (SELECT id FROM applications WHERE seeded=0)")
    c.execute("DELETE FROM applications WHERE seeded=0")
    c.commit()
    return len(ids)


def purge_old_live(c, hours=24):
    """Public-demo hygiene: delete visitor submissions (and their photos) older than `hours`."""
    from datetime import timedelta
    from .config import UPLOAD_DIR
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    ids = [r[0] for r in c.execute("SELECT id FROM applications WHERE seeded=0 AND created_at < ?", (cutoff,))]
    for i in ids:
        for p in UPLOAD_DIR.glob(f"{i}_*"):
            p.unlink(missing_ok=True)
        c.execute("DELETE FROM audit WHERE app_id=?", (i,))
        c.execute("DELETE FROM applications WHERE id=?", (i,))
    c.commit()
    return len(ids)
