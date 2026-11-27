"""Shared Streamlit components."""
import hashlib
import html
from pathlib import Path

import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from core import db, graph, report
from core.config import CHECK_LABELS, DECISION_COLORS, WEIGHTS
from core.scoring import summary_text

CSS = """
<style>
.block-container {padding-top: 2rem;}
.kg-badge {display:inline-block;padding:.45rem 1rem;border-radius:.5rem;color:#fff;font-weight:700;font-size:1.15rem;letter-spacing:.02em}
.kg-score {font-size:2.6rem;font-weight:800;line-height:1}
.kg-card {border:1px solid rgba(128,128,128,.25);border-radius:.75rem;padding:.8rem 1rem;margin-bottom:.6rem}
.kg-card h4 {margin:0 0 .3rem 0;font-size:.95rem}
.kg-bar {height:10px;border-radius:5px;background:rgba(128,128,128,.18);margin:.35rem 0}
.kg-bar > div {height:10px;border-radius:5px}
.kg-reason {padding:.45rem .7rem;border-left:4px solid;margin:.3rem 0;border-radius:.25rem;background:rgba(128,128,128,.07)}
.kg-muted {opacity:.7;font-size:.85rem}
.kg-pill {display:inline-block;padding:.1rem .5rem;border-radius:1rem;font-size:.75rem;font-weight:600;color:#fff}
</style>
"""

SEV_COLORS = {"critical": "#c62828", "high": "#d4561c", "medium": "#b58500", "low": "#5c7cfa", "info": "#1a7f37"}
STATUS_LABELS = {
    "AUTO_APPROVED": "Auto-approved", "PENDING_REVIEW": "Pending review", "RECAPTURE_REQUESTED": "Re-capture requested",
    "AUTO_REJECTED": "Auto-rejected", "APPROVED": "Approved by reviewer", "REJECTED": "Rejected by reviewer",
}


def risk_color(v):
    return "#1a7f37" if v <= 30 else "#b58500" if v <= 60 else "#d4561c" if v <= 80 else "#c62828"


def setup():
    st.markdown(CSS, unsafe_allow_html=True)


def badge(decision):
    return f"<span class='kg-badge' style='background:{DECISION_COLORS.get(decision, '#555')}'>{html.escape(decision)}</span>"


def device_fingerprint() -> str:
    ua = ""
    try:
        ua = st.context.headers.get("User-Agent", "")
    except Exception:
        pass
    return "DEV-" + hashlib.sha1(ua.encode()).hexdigest()[:4].upper()


def client_ip() -> str:
    try:
        ip = getattr(st.context, "ip_address", None)
        return ip or "127.0.0.1"
    except Exception:
        return "127.0.0.1"


def load_images(app) -> dict:
    out = {}
    for name in ("face", "selfie_face", "id_face", "ela"):
        b = report.app_image(app["id"], name)
        if b:
            out[name] = b
    return out


def render_result(app: dict, images: dict | None = None, key=""):
    images = images if images is not None else load_images(app)
    res = app["results"]
    s, checks = res["scoring"], res["checks"]

    c1, c2, c3 = st.columns([1.3, 1, 2.2])
    with c1:
        st.markdown("**Decision**")
        st.markdown(badge(app["decision"]), unsafe_allow_html=True)
        st.caption(STATUS_LABELS.get(app["status"], app["status"]))
    with c2:
        st.markdown("**Risk score**")
        st.markdown(f"<div class='kg-score' style='color:{risk_color(app['score'])}'>{app['score']}<span style='font-size:1rem;opacity:.6'>/100</span></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("**How the score was built**")
        txt = f"Weighted blend of 6 checks = **{s['weighted']}**"
        if s["floor"] and s["floor"] > s["weighted"]:
            txt += f"  \nRaised to **{s['floor']}** by hard rule `{s['floor_reason']}`"
        st.markdown(txt)
        st.caption("0–30 Approve · 31–60 Re-verify · 61–80 Manual review · 81–100 Reject")

    st.markdown("#### Check results")
    cols = st.columns(3)
    for i, k in enumerate(WEIGHTS):
        if k not in checks:
            continue
        r = checks[k]
        top = max(r["findings"], key=lambda f: f["points"]) if r["findings"] else None
        with cols[i % 3]:
            st.markdown(
                f"<div class='kg-card'><h4>{CHECK_LABELS[k]} <span class='kg-muted'>· weight {int(WEIGHTS[k]*100)}%</span></h4>"
                f"<b style='color:{risk_color(r['risk'])};font-size:1.3rem'>{r['risk']}</b><span class='kg-muted'> / 100 risk</span>"
                f"<div class='kg-bar'><div style='width:{max(r['risk'],2)}%;background:{risk_color(r['risk'])}'></div></div>"
                f"<span class='kg-muted'>{html.escape(top['message'] if top else '')}</span></div>",
                unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### Why this decision")
        for r in s["reasons"][:8]:
            col = SEV_COLORS.get(r["severity"], "#888")
            st.markdown(f"<div class='kg-reason' style='border-color:{col}'><span class='kg-pill' style='background:{col}'>{r['severity'].upper()}</span> "
                        f"<b>{html.escape(r['check'])}</b> — {html.escape(r['message'])} <code>{r['code']}</code></div>", unsafe_allow_html=True)
        if not s["reasons"]:
            st.success("No risk signals — all checks passed.")
        with st.expander("Checks passed"):
            for p in s["passed"]:
                st.markdown(f"✅ **{p['check']}** — {p['message']}")
        st.markdown("**Audit-ready explanation**")
        st.code(summary_text(app["id"], s), language=None, wrap_lines=True)
    with right:
        st.markdown("#### Evidence")
        f1, f2 = st.columns(2)
        sf = images.get("selfie_face") or images.get("face")
        if sf:
            f1.image(sf, caption="Selfie face", width="stretch")
        elif app.get("selfie_path") and Path(app["selfie_path"]).exists():
            f1.image(app["selfie_path"], caption="Selfie", width="stretch")
        if images.get("id_face"):
            conf = checks.get("face", {}).get("details", {}).get("confidence")
            f2.image(images["id_face"], caption=f"ID photo · match {conf:.0%}" if conf is not None else "ID photo", width="stretch")
        if images.get("ela"):
            st.image(images["ela"], caption="Tamper analysis — red boxes = edited after the ID was issued", width="stretch")
        elif app.get("id_path") and Path(app["id_path"]).exists():
            st.image(app["id_path"], caption="ID document", width="stretch")
        if not app.get("selfie_path"):
            st.info("Seeded demo record — no images stored.")
        qr = checks.get("document", {}).get("details", {}).get("qr_identity")
        if qr:
            st.markdown("**Identity data from the signed QR**")
            st.table({"Field": ["Name", "DOB", "Gender", "ID", "Address", "Issuer"],
                      "Value": [qr.get("name"), qr.get("dob"), qr.get("gender"), qr.get("id_number_masked"), qr.get("address"), qr.get("issuer")]})

    with st.expander("Raw check details (JSON)"):
        st.json({k: {"risk": v["risk"], "floor": v["floor"], "details": v["details"], "findings": v["findings"]} for k, v in checks.items()})

    c = db.conn()
    st.download_button("⬇️ Download audit report (HTML)", report.build(db.get(c, app["id"]), db.audit_for(c, app["id"])),
                       file_name=f"{app['id']}_report.html", mime="text/html", key=f"dl_{app['id']}_{key}")


NODE_STYLE = {
    "applicant": ("dot", 22), "device": ("square", 16), "phone": ("triangle", 14),
    "email": ("diamond", 12), "address": ("box", 12), "id": ("star", 18),
}
KIND_COLORS = {"device": "#8e44ad", "phone": "#2980b9", "email": "#16a085", "address": "#d35400", "id": "#c0392b"}


def network_html(g: nx.Graph, height=560, highlight=None) -> str:
    net = Network(height=f"{height}px", width="100%", cdn_resources="in_line", bgcolor="#ffffff")
    # hide attributes used by only one applicant: they carry no link information
    g = g.subgraph([n for n, d in g.nodes(data=True) if d.get("kind") == "applicant" or g.degree(n) > 1])
    net.set_options("""{
      "nodes": {"scaling": {"label": {"enabled": true, "min": 12, "max": 16, "drawThreshold": 1}}},
      "physics": {"barnesHut": {"gravitationalConstant": -9000, "springLength": 140},
                  "stabilization": {"iterations": 250, "fit": true}},
      "interaction": {"hover": true, "navigationButtons": false}
    }""")
    for n, d in g.nodes(data=True):
        kind = d.get("kind")
        shape, size = NODE_STYLE.get(kind, ("dot", 12))
        if kind == "applicant":
            color = DECISION_COLORS.get(d.get("decision"), "#607d8b")
            label = f"{d.get('label')}\n{n}"
            title = f"{n} · {d.get('label')} · score {d.get('score')} · {d.get('decision')}"
            if highlight and n == highlight:
                size = 34
        else:
            color = KIND_COLORS.get(kind, "#999")
            label = str(d.get("label", ""))[:22]
            title = f"{kind}: {d.get('label')}"
        net.add_node(n, label=label, title=title, color=color, shape=shape, size=size,
                     font={"size": 13 if kind == "applicant" else 10, "face": "arial", "color": "#222"})
    for a, b, d in g.edges(data=True):
        face = d.get("kind") == "face"
        net.add_edge(a, b, color="#c62828" if face else "#b0bec5", width=4 if face else 1.5,
                     title="same face" if face else d.get("kind", ""), dashes=face)
    return net.generate_html()


def show_network(g: nx.Graph, height=560, highlight=None):
    components.html(network_html(g, height, highlight), height=height + 20, scrolling=False)


def apps_graph(include_emb=True):
    return graph.build_graph(db.all_apps(db.conn(), include_emb=include_emb))
