import streamlit as st

from core import db, seed
from core.face import ensure_models

st.title("🛡️ KYC Guard")
st.markdown("#### An AI-powered digital bank employee that verifies a new customer is **real, genuine and not a fraudster** — in seconds, with explainable evidence.")

apps = db.all_apps(db.conn())
total = len(apps)
by = lambda *s: sum(1 for a in apps if a["status"] in s)  # noqa: E731
m = st.columns(5)
m[0].metric("Applications", total)
m[1].metric("Approved", by("AUTO_APPROVED", "APPROVED"))
m[2].metric("Needs review", by("PENDING_REVIEW"))
m[3].metric("Re-capture", by("RECAPTURE_REQUESTED"))
m[4].metric("Rejected", by("AUTO_REJECTED", "REJECTED"))

st.divider()
st.markdown("### Six checks on every onboarding request")
checks = [
    ("🎭 Deepfake & Liveness", "Random head-turn challenge defeats photos, replays and pre-rendered deepfakes. Flags virtual-camera injection, AI-generator metadata and screen-replay moiré."),
    ("🪪 Document Verification", "Verifies the digital signature in the ID's secure QR, detects photo swaps, and uses JPEG-ghost Error Level Analysis to box edited regions."),
    ("🙂 Face Match", "Compares the selfie with the ID photo using OpenCV's SFace neural face-recognition model."),
    ("🔎 Data Cross-Verification", "Form vs signed document: name (fuzzy), DOB, ID number + Verhoeff checksum, gender, address, contact sanity."),
    ("📱 Device & Network", "Device reuse across identities, application velocity per device and per IP, emulator / rooted / VPN signals."),
    ("🕸️ Synthetic Identity", "Identity graph links applicants by device, phone, email, address, ID number and face to expose mule rings."),
]
cols = st.columns(3)
for i, (t, d) in enumerate(checks):
    with cols[i % 3]:
        st.markdown(f"<div class='kg-card'><h4>{t}</h4><span class='kg-muted'>{d}</span></div>", unsafe_allow_html=True)

st.markdown("### From signals to a decision")
c1, c2 = st.columns([1.2, 1])
with c1:
    st.markdown(
        "- Each check returns a **0–100 risk** and **reason codes**.\n"
        "- Risks are blended by weight (liveness 25%, document 20%, face 20%, data 15%, device 10%, synthetic 10%).\n"
        "- **Hard rules** set a minimum score, so one critical red flag (forged QR, face mismatch, "
        "reused face) can never be averaged away by clean checks.\n"
        "- Every decision comes with a plain-English explanation and an audit trail.")
with c2:
    st.markdown(
        "| Score | Decision |\n|---|---|\n| 0–30 | ✅ APPROVE |\n| 31–60 | 🔁 RE-VERIFY |\n| 61–80 | 🧑‍⚖️ MANUAL REVIEW |\n| 81–100 | ⛔ REJECT |")

st.divider()
st.markdown("### Demo setup")
a, b, c3 = st.columns(3)
with c3:
    if st.button("🧹 Clear my test applications", help="Removes applications you submitted; keeps the seeded history. "
                 "Use between demo scenarios so your own face isn't flagged as 'reused'."):
        n = db.clear_live(db.conn())
        st.session_state.pop("last_result", None)
        st.success(f"Removed {n} test application(s).")
        st.rerun()
with a:
    if st.button("🔄 Load demo data (resets database)", type="primary"):
        with st.spinner("Seeding normal customers and a mule-account ring…"):
            n = seed.seed()
        st.success(f"Loaded {n} historical applications, including a 6-person mule ring on device `{seed.MULE_DEVICE}`.")
        st.rerun()
with b:
    if st.button("⬇️ Check face models"):
        with st.spinner("Checking / downloading face models (~38 MB, first run only)…"):
            ensure_models()
        st.success("Face detection and recognition models are ready.")
st.caption("Privacy by design: full ID numbers are never stored — only a masked value and a keyed hash used to detect reuse. "
           "Demo IDs are fictional SPECIMEN cards from a made-up issuer.")
