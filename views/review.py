import networkx as nx
import pandas as pd
import streamlit as st

import ui
from core import db, graph

st.title("🧑‍⚖️ Reviewer Dashboard")
st.caption("Applications the AI was not fully confident about land here. The reviewer sees all the evidence and makes the final call.")

c = db.conn()
apps = db.all_apps(c)
if not apps:
    st.info("No applications yet. Load demo data from the Overview page or submit a new application.")
    st.stop()

counts = pd.Series([a["status"] for a in apps]).value_counts()
m = st.columns(4)
m[0].metric("Pending review", int(counts.get("PENDING_REVIEW", 0)))
m[1].metric("Re-capture requested", int(counts.get("RECAPTURE_REQUESTED", 0)))
m[2].metric("Approved", int(counts.get("AUTO_APPROVED", 0) + counts.get("APPROVED", 0)))
m[3].metric("Rejected", int(counts.get("AUTO_REJECTED", 0) + counts.get("REJECTED", 0)))

all_status = list(ui.STATUS_LABELS)
default = ["PENDING_REVIEW", "RECAPTURE_REQUESTED", "AUTO_REJECTED"]
flt = st.multiselect("Show", all_status, default=default, format_func=ui.STATUS_LABELS.get)
rows = [a for a in apps if a["status"] in flt]

df = pd.DataFrame([{
    "ID": a["id"], "Submitted": a["created_at"].replace("T", " "), "Name": a["name"], "Score": a["score"],
    "AI decision": a["decision"], "Status": ui.STATUS_LABELS.get(a["status"], a["status"]),
    "Top reason": (a["results"]["scoring"]["reasons"][0]["message"] if a["results"]["scoring"]["reasons"] else "—"),
} for a in rows])
if df.empty:
    st.info("Nothing in this queue.")
    st.stop()
st.dataframe(df, hide_index=True, width="stretch",
             column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")})

ids = [a["id"] for a in rows]
pre = st.session_state.pop("review_select", None)
idx = ids.index(pre) if pre in ids else 0
sel = st.selectbox("Open application", ids, index=idx,
                   format_func=lambda i: next(f"{a['id']} · {a['name']} · {a['score']}/100 · {a['decision']}" for a in rows if a["id"] == i))
app = db.get(c, sel)

st.divider()
st.markdown(f"## {app['id']} · {app['name']}")
ui.render_result(app, key="review")

st.markdown("#### Linked applications")
g = graph.build_graph(db.all_apps(c, include_emb=True))
comp = nx.node_connected_component(g, app["id"])
members = [n for n in comp if g.nodes[n].get("kind") == "applicant"]
if len(members) > 1:
    st.warning(f"This applicant is connected to {len(members) - 1} other application(s) through shared attributes.")
    ui.show_network(g.subgraph(comp), height=380, highlight=app["id"])
else:
    st.success("No links to other applicants.")

st.markdown("#### Reviewer decision")
with st.form("review_form"):
    a, b = st.columns([1, 2])
    reviewer = a.text_input("Reviewer", st.session_state.get("reviewer", "Reviewer-01"))
    note = b.text_input("Note (required for audit)", placeholder="e.g. Verified via video call; name mismatch was a typo")
    x, y, z = st.columns(3)
    approve = x.form_submit_button("✅ Approve", width="stretch")
    reject = y.form_submit_button("⛔ Reject", width="stretch")
    recap = z.form_submit_button("🔁 Request re-capture", width="stretch")
    if approve or reject or recap:
        if not note.strip():
            st.error("Please add a note — every manual decision is recorded in the audit trail.")
        else:
            status = "APPROVED" if approve else "REJECTED" if reject else "RECAPTURE_REQUESTED"
            st.session_state.reviewer = reviewer
            db.review(c, app["id"], status, reviewer, note.strip())
            st.session_state.review_select = app["id"]
            st.toast(f"{app['id']} → {ui.STATUS_LABELS[status]}")
            st.rerun()

st.markdown("#### Audit trail")
st.dataframe(pd.DataFrame(db.audit_for(c, app["id"]))[["ts", "actor", "action", "note"]], hide_index=True, width="stretch")
