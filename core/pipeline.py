"""Orchestrates all six checks for one onboarding request."""
import time

from . import crossverify, db, device, document, facematch, graph, liveness, scoring
from .config import UPLOAD_DIR
from .idcard import mask_id


def process(form: dict, selfie: bytes, id_doc: bytes, source: str = "upload",
            challenge: dict | None = None, device_ctx: dict | None = None,
            progress=None) -> dict:
    """Run every check, score, decide, store. Returns the stored application
    plus transient images for display."""
    device_ctx = device_ctx or {}
    c = db.conn()
    history = db.all_apps(c, include_emb=True)
    app_id = db.new_app_id(c)
    timings, images = {}, {}

    def step(name, fn):
        if progress:
            progress(name)
        t = time.time()
        out = fn()
        timings[name] = round(time.time() - t, 2)
        return out

    live = step("Deepfake & liveness", lambda: liveness.run(selfie, source, challenge, device_ctx.get("virtual_camera", False)))
    doc = step("Document verification", lambda: document.run(id_doc))
    fm, emb = step("Face match", lambda: facematch.run(selfie, id_doc))
    data = step("Data cross-verification", lambda: crossverify.run(form, doc.details))
    dev = step("Device & network", lambda: device.run(device_ctx, form, history))

    candidate = {
        "id": app_id, "name": form.get("name", ""), "phone": form.get("phone", ""),
        "email": form.get("email", ""), "address": form.get("address", ""),
        "id_hash": db.id_hash(form.get("id_number", "")), "id_masked": mask_id(form.get("id_number", "")),
        "device_id": device_ctx.get("device_id", ""), "face_emb": emb,
    }
    syn = step("Synthetic identity graph", lambda: graph.run(candidate, history))

    checks = {"liveness": live, "document": doc, "face": fm, "data": data, "device": dev, "synthetic": syn}
    for r in checks.values():
        images.update(r.images)
    results = {k: r.to_dict() for k, r in checks.items()}
    results["document"]["details"].pop("_qr_id_number", None)
    s = scoring.score(results)

    selfie_path = UPLOAD_DIR / f"{app_id}_selfie.jpg"
    id_path = UPLOAD_DIR / f"{app_id}_id.jpg"
    selfie_path.write_bytes(selfie)
    id_path.write_bytes(id_doc)
    for name, png in images.items():
        (UPLOAD_DIR / f"{app_id}_{name}.png").write_bytes(png)

    row = {
        "id": app_id, "created_at": db.now(), "name": form.get("name", ""), "dob": form.get("dob", ""),
        "gender": form.get("gender", ""), "phone": form.get("phone", ""), "email": form.get("email", ""),
        "address": form.get("address", ""), "id_masked": candidate["id_masked"], "id_hash": candidate["id_hash"],
        "device_id": device_ctx.get("device_id", ""), "ip": device_ctx.get("ip", ""),
        "selfie_path": str(selfie_path), "id_path": str(id_path), "face_emb": emb,
        "results": {"checks": results, "scoring": s, "timings": timings, "source": source},
        "score": s["score"], "decision": s["decision"], "status": db.STATUS_FOR_DECISION[s["decision"]],
    }
    db.insert(c, row)
    db.log(c, app_id, "AI-ENGINE", s["decision"], f"Score {s['score']}/100")
    out = db.get(c, app_id)
    out["images"] = images
    return out
