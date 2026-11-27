"""Demo history: normal customers + a mule-account ring sharing one device.

Device and graph checks are computed with the real engine; image-based checks
get plausible clean values (seeded rows have no photos)."""
import random
from datetime import datetime, timedelta

from . import db, device, graph, scoring
from .idcard import new_id_number, mask_id
from .types import CheckResult

MULE_DEVICE = "DEV-MULE-7F3A"
MULE_IP = "103.21.58.44"

NORMAL = [
    ("Ananya Sharma", "1994-06-11", "Female", "Bengaluru"), ("Vikram Singh", "1989-02-23", "Male", "Delhi"),
    ("Fatima Sheikh", "1997-09-02", "Female", "Hyderabad"), ("Arjun Nair", "1992-12-15", "Male", "Kochi"),
    ("Meera Pillai", "1999-03-30", "Female", "Chennai"), ("Karan Mehta", "1986-07-19", "Male", "Mumbai"),
    ("Sneha Kulkarni", "1995-11-08", "Female", "Pune"), ("Rohan Das", "1993-01-27", "Male", "Kolkata"),
    ("Divya Menon", "1998-05-05", "Female", "Thiruvananthapuram"),
]
RING = [
    ("Suresh Patil", "1990-04-14", "Male"), ("Ganesh Shinde", "1991-08-21", "Male"),
    ("Pooja Jadhav", "1996-10-03", "Female"), ("Imran Shaikh", "1988-12-29", "Male"),
    ("Kavita More", "1994-02-17", "Female"), ("Nitin Pawar", "1993-06-06", "Male"),
]
RING_ADDRESS = "Room 4, Lodge Building, Nehru Nagar, Pune 411001"


def _clean(key, risk=None, msg="Passed"):
    r = CheckResult(key)
    risk = random.randint(0, 12) if risk is None else risk
    r.add("SEEDED_" + key.upper(), msg, risk, "info" if risk < 10 else "low")
    return r


def seed(c=None, reset=True):
    c = c or db.conn()
    if reset:
        db.reset(c)
        from .config import UPLOAD_DIR
        for p in UPLOAD_DIR.glob("APP-*"):
            p.unlink(missing_ok=True)
    random.seed(7)
    history = []
    base = datetime.now()

    entries = []
    for i, (name, dob, g, city) in enumerate(NORMAL):
        entries.append(dict(name=name, dob=dob, gender=g, phone=f"9{random.randint(100000000, 999999999)}",
                            email=name.split()[0].lower() + f"{random.randint(1, 99)}@example.com",
                            address=f"{random.randint(1, 300)}, {random.choice(['MG Road', 'Station Road', 'Lake View', 'Park Street'])}, {city}",
                            device_id=f"DEV-{random.randint(0x1000, 0xFFFF):04X}", ip=f"49.{random.randint(30, 200)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
                            ts=base - timedelta(days=random.randint(2, 20), hours=random.randint(0, 23))))
    for i, (name, dob, g) in enumerate(RING):
        entries.append(dict(name=name, dob=dob, gender=g, phone="9000011122" if i % 2 == 0 else f"90000{random.randint(10000, 99999)}",
                            email=f"{name.split()[0].lower()}.acc{i}@example.com", address=RING_ADDRESS,
                            device_id=MULE_DEVICE, ip=MULE_IP, ts=base - timedelta(hours=20 - i * 3)))
    entries.sort(key=lambda e: e["ts"])

    for e in entries:
        app_id = db.new_app_id(c)
        idn = new_id_number()
        form = dict(name=e["name"], dob=e["dob"], gender=e["gender"], phone=e["phone"], email=e["email"], address=e["address"])
        # compute device/graph checks relative to history at that time
        dev = device.run({"device_id": e["device_id"], "ip": e["ip"]}, form,
                         [dict(h, created_at=h["created_at"]) for h in history])
        cand = dict(form, id=app_id, id_hash=db.id_hash(idn), id_masked=mask_id(idn), device_id=e["device_id"], face_emb=None)
        syn = graph.run(cand, history)
        checks = {
            "liveness": _clean("liveness", msg="Live head-turn challenge passed (seeded)"),
            "document": _clean("document", 0, "Secure QR signature verified (seeded)"),
            "face": _clean("face", random.randint(5, 18), "Selfie matches the ID photo (seeded)"),
            "data": _clean("data", 0, "Form data matches the document (seeded)"),
            "device": dev, "synthetic": syn,
        }
        results = {k: r.to_dict() for k, r in checks.items()}
        s = scoring.score(results)
        row = dict(id=app_id, created_at=e["ts"].isoformat(timespec="seconds"), name=e["name"], dob=e["dob"],
                   gender=e["gender"], phone=e["phone"], email=e["email"], address=e["address"],
                   id_masked=mask_id(idn), id_hash=db.id_hash(idn), device_id=e["device_id"], ip=e["ip"],
                   selfie_path="", id_path="", face_emb=None,
                   results={"checks": results, "scoring": s, "timings": {}, "source": "seeded"},
                   score=s["score"], decision=s["decision"], status=db.STATUS_FOR_DECISION[s["decision"]], seeded=1)
        db.insert(c, row)
        db.log(c, app_id, "AI-ENGINE", s["decision"], f"Score {s['score']}/100 (seeded demo data)")
        history.append(dict(row, face_emb=None))
    return len(entries)


if __name__ == "__main__":
    print("Seeded", seed(), "applications")
