import networkx as nx
import pandas as pd
import streamlit as st

import ui
from core import db
from core.crossverify import norm_name

st.title("🕸️ Fraud Network")
st.caption("Every applicant (circle) is linked to the device ■, phone ▲, email ◆, address ▭ and ID number ★ they used. "
           "Red dashed edges = the same face under different applications. Rings of different 'people' sharing attributes are mule-account suspects.")

c = db.conn()
apps = db.all_apps(c, include_emb=True)
if not apps:
    st.info("No applications yet. Load demo data from the Overview page.")
    st.stop()

g = ui.apps_graph()
only_linked = st.toggle("Show only linked clusters", True)

clusters = []
for comp in nx.connected_components(g):
    members = [n for n in comp if g.nodes[n].get("kind") == "applicant"]
    identities = {norm_name(g.nodes[m]["label"]) for m in members}
    shared = sorted({g.nodes[n]["kind"] for n in comp if g.nodes[n].get("kind") != "applicant" and g.degree(n) > 1})
    face = any(d.get("kind") == "face" for _, _, d in g.subgraph(comp).edges(data=True))
    if face:
        shared.append("face")
    clusters.append({"nodes": comp, "members": sorted(members), "identities": len(identities), "shared": shared})
clusters.sort(key=lambda x: -x["identities"])

view = nx.Graph()
for cl in clusters:
    if not only_linked or cl["identities"] > 1:
        view = nx.compose(view, g.subgraph(cl["nodes"]))
if view.number_of_nodes() == 0:
    st.success("No linked clusters — every applicant is independent.")
else:
    ui.show_network(view, height=560)

st.markdown("### Suspicious clusters")
sus = [cl for cl in clusters if cl["identities"] > 1]
if not sus:
    st.success("None found.")
for i, cl in enumerate(sus):
    level = "🔴 Suspected mule ring" if cl["identities"] >= 4 else "🟠 Linked identities"
    with st.expander(f"{level} — {cl['identities']} identities sharing {', '.join(cl['shared'])}", expanded=i == 0):
        rows = [db.get(c, m) for m in cl["members"]]
        st.dataframe(pd.DataFrame([{"ID": r["id"], "Name": r["name"], "Device": r["device_id"], "Phone": r["phone"],
                                    "Score": r["score"], "Status": ui.STATUS_LABELS.get(r["status"], r["status"])} for r in rows]),
                     hide_index=True, width="stretch")
        approved = [r for r in rows if r["status"] in ("AUTO_APPROVED", "APPROVED")]
        if approved:
            st.warning(f"{len(approved)} account(s) in this cluster were already approved before the ring was visible.")
            if st.button(f"🚩 Send all {len(approved)} approved accounts back to manual review", key=f"flag_{i}"):
                for r in approved:
                    db.review(c, r["id"], "PENDING_REVIEW", "AI-ENGINE",
                              f"Retroactive flag: member of a {cl['identities']}-identity cluster sharing {', '.join(cl['shared'])}")
                st.toast(f"{len(approved)} accounts sent to review")
                st.rerun()
