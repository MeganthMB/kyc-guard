"""Risk score = weighted blend of the six checks, but never lower than the
strongest hard rule ("floor"). A plain average would let one clean check
hide a critical red flag, e.g. a forged document with a perfect selfie."""
from .config import WEIGHTS, BANDS, CHECK_LABELS

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def decide(score: int) -> str:
    for upper, label in BANDS:
        if score <= upper:
            return label
    return "REJECT"


def score(results: dict) -> dict:
    weighted = sum(WEIGHTS[k] * results[k]["risk"] for k in WEIGHTS if k in results)
    floor, floor_reason = 0, None
    for k, r in results.items():
        if r.get("floor", 0) > floor:
            floor = r["floor"]
            top = max(r["findings"], key=lambda f: f["points"])
            floor_reason = f"{CHECK_LABELS[k]}: {top['code']}"
    final = int(round(max(weighted, floor)))
    final = max(0, min(100, final))

    reasons = []
    for k, r in results.items():
        for f in r["findings"]:
            if f["points"] > 0:
                reasons.append({**f, "check": CHECK_LABELS[k]})
    reasons.sort(key=lambda f: (SEV_ORDER.get(f["severity"], 5), -f["points"]))
    passed = [{**f, "check": CHECK_LABELS[k]} for k, r in results.items()
              for f in r["findings"] if f["points"] == 0]
    return {
        "score": final,
        "weighted": round(weighted, 1),
        "floor": floor,
        "floor_reason": floor_reason,
        "decision": decide(final),
        "reasons": reasons,
        "passed": passed,
    }


def summary_text(app_id: str, s: dict) -> str:
    lines = [f"Applicant {app_id} routed to {s['decision'].title()} because:"]
    for r in s["reasons"][:6]:
        lines.append(f"  - {r['message']}")
    if not s["reasons"]:
        lines.append("  - All checks passed with no risk signals.")
    lines.append(f"Final Risk Score: {s['score']}/100")
    if s["floor"] and s["floor"] > s["weighted"]:
        lines.append(f"(Weighted score {s['weighted']} raised to {s['floor']} by hard rule {s['floor_reason']}.)")
    return "\n".join(lines)
