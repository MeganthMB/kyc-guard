"""Check 5 — Device & Network: reuse and velocity of devices and IP addresses."""
from datetime import datetime, timedelta

from .crossverify import norm_name
from .types import CheckResult


def _recent(ts: str, hours=24) -> bool:
    try:
        return datetime.fromisoformat(ts) >= datetime.now() - timedelta(hours=hours)
    except Exception:
        return False


def run(ctx: dict, form: dict, history: list[dict]) -> CheckResult:
    """ctx: device_id, ip, emulator, rooted, vpn. history: previous applications."""
    res = CheckResult("device")
    dev, ip = ctx.get("device_id", ""), ctx.get("ip", "")
    me = norm_name(form.get("name", ""))

    same_dev = [h for h in history if dev and h.get("device_id") == dev]
    others = {norm_name(h["name"]) for h in same_dev} - {me}
    dev_24h = [h for h in same_dev if _recent(h["created_at"])]
    ip_24h = [h for h in history if ip and h.get("ip") == ip and _recent(h["created_at"])]
    res.details.update(device_id=dev, ip=ip, device_total_apps=len(same_dev),
                       device_other_identities=len(others), device_apps_24h=len(dev_24h), ip_apps_24h=len(ip_24h))

    n = len(others)
    if n >= 5:
        res.add("DEVICE_FARM", f"Device was used across {len(same_dev)} applications for {n} other identities.", 75, "critical", floor=65)
    elif n >= 3:
        res.add("DEVICE_SHARED_MANY", f"Device was used across {len(same_dev)} applications for {n} other identities.", 50, "high", floor=61)
    elif n >= 1:
        res.add("DEVICE_SHARED", f"Device was previously used by {n} other applicant(s).", 25)

    if len(dev_24h) >= 3:
        res.add("DEVICE_VELOCITY", f"{len(dev_24h) + 1} applications from this device in 24 hours.", 20)
    if len(ip_24h) >= 5:
        res.add("IP_VELOCITY_HIGH", f"{len(ip_24h) + 1} applications from IP {ip} in 24 hours.", 25)
    elif len(ip_24h) >= 3:
        res.add("IP_VELOCITY", f"{len(ip_24h) + 1} applications from IP {ip} in 24 hours.", 10)

    if ctx.get("emulator"):
        res.add("EMULATOR", "Application submitted from an emulator, not a real phone.", 40, "high", floor=61)
    if ctx.get("rooted"):
        res.add("ROOTED_DEVICE", "Device is rooted / jailbroken.", 15)
    if ctx.get("vpn"):
        res.add("VPN_PROXY", "Traffic comes through a VPN / proxy / hosting provider.", 15)
    if not res.findings:
        res.add("DEVICE_CLEAN", "New device, normal network activity.", 0)
    return res
