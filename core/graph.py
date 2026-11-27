"""Check 6 — Synthetic Identity & Mule-Ring detection with an identity graph.

Applicants are linked to the attributes they used (device, phone, email,
address, ID number, face). Fraud rings show up as clusters of different
"people" sharing the same attributes.
"""
import re

import networkx as nx

from . import face as F
from .crossverify import norm_name
from .types import CheckResult

LINK_TYPES = {
    "device_id": ("device", "#8e44ad"),
    "phone": ("phone", "#2980b9"),
    "email": ("email", "#16a085"),
    "address": ("address", "#d35400"),
    "id_hash": ("id", "#c0392b"),
}


def norm_addr(a: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(a).lower())[:40]


def attr_value(app: dict, key: str) -> str:
    v = app.get(key) or ""
    if key == "address":
        return norm_addr(v)
    if key == "phone":
        return "".join(ch for ch in str(v) if ch.isdigit())[-10:]
    return str(v).lower().strip()


def build_graph(apps: list[dict]) -> nx.Graph:
    g = nx.Graph()
    for a in apps:
        g.add_node(a["id"], kind="applicant", label=a.get("name", a["id"]),
                   decision=a.get("decision", ""), score=a.get("score"))
        for key, (kind, _) in LINK_TYPES.items():
            v = attr_value(a, key)
            if v:
                node = f"{kind}:{v}"
                g.add_node(node, kind=kind, label=(a.get("id_masked") if kind == "id" else
                                                   a.get("address", "")[:28] if kind == "address" else v))
                g.add_edge(a["id"], node, kind=kind)
    # face links (same face, different application)
    with_emb = [a for a in apps if a.get("face_emb") is not None and len(a["face_emb"])]
    for i in range(len(with_emb)):
        for j in range(i + 1, len(with_emb)):
            c = F.match_confidence(F.cosine(with_emb[i]["face_emb"], with_emb[j]["face_emb"]))
            if c >= 0.75:
                g.add_edge(with_emb[i]["id"], with_emb[j]["id"], kind="face")
    return g


def cluster_of(g: nx.Graph, app_id: str):
    comp = nx.node_connected_component(g, app_id)
    return comp, [n for n in comp if g.nodes[n].get("kind") == "applicant"]


def run(new_app: dict, history: list[dict]) -> CheckResult:
    """new_app needs: id, name, phone, email, address, id_hash, device_id, face_emb (optional)."""
    res = CheckResult("synthetic")
    me = norm_name(new_app.get("name", ""))

    # identity reuse
    for h in history:
        same_person_name = norm_name(h.get("name", "")) == me
        if new_app.get("id_hash") and h.get("id_hash") == new_app["id_hash"] and not same_person_name:
            res.add("SAME_ID_DIFFERENT_NAME", f"This ID number was already used by '{h['name']}' ({h['id']}) — synthetic identity.", 70, "critical", floor=85)
            break
    if new_app.get("face_emb") is not None:
        for h in history:
            if h.get("face_emb") is None or not len(h["face_emb"]):
                continue
            c = F.match_confidence(F.cosine(new_app["face_emb"], h["face_emb"]))
            if c >= 0.75 and norm_name(h.get("name", "")) != me:
                res.add("FACE_REUSED", f"Same face already applied as '{h['name']}' ({h['id']}, {c:.0%} match) — one person, multiple identities.", 70, "critical", floor=85)
                break
            if c >= 0.75:
                res.add("RETURNING_APPLICANT", f"Same person applied before ({h['id']}).", 5)
                break

    # shared attributes with other identities
    for key, label in (("phone", "phone number"), ("email", "email"), ("address", "address")):
        v = attr_value(new_app, key)
        if not v:
            continue
        others = {norm_name(h["name"]) for h in history if attr_value(h, key) == v} - {me}
        if others:
            pts = {"phone": 20, "email": 25, "address": 10}[key] * min(len(others), 3)
            res.add(f"SHARED_{key.upper()}", f"{label.capitalize()} is shared with {len(others)} other identit{'y' if len(others) == 1 else 'ies'}.", min(pts, 50))

    # cluster / mule ring
    g = build_graph(history + [new_app])
    _, members = cluster_of(g, new_app["id"])
    names = {norm_name(g.nodes[m]["label"]) for m in members}
    res.details["cluster_size"] = len(members)
    res.details["cluster_identities"] = len(names)
    res.details["cluster_members"] = sorted(m for m in members if m != new_app["id"])[:25]
    if len(names) >= 4:
        res.add("MULE_RING", f"Linked to a cluster of {len(names)} identities sharing devices/phones/addresses — suspected mule-account ring.", 35, "high", floor=65)
    elif len(names) >= 2:
        res.add("LINKED_APPLICATIONS", f"Linked to {len(names) - 1} other identit{'y' if len(names) == 2 else 'ies'} through shared attributes.", 10)
    if not res.findings:
        res.add("NO_LINKS", "No hidden links to other applicants.", 0)
    return res
