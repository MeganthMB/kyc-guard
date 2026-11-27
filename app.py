"""KYC Guard — AI digital bank employee for onboarding fraud detection.

Run:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="KYC Guard", page_icon="🛡️", layout="wide")

import ui  # noqa: E402
from core import db, seed  # noqa: E402


@st.cache_resource(show_spinner="Preparing demo data…")
def _bootstrap():
    """First start on a fresh server (e.g. Streamlit Cloud): load the demo history."""
    c = db.conn()
    if c.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0:
        seed.seed(c)
    return True


_bootstrap()
db.purge_old_live(db.conn())
ui.setup()

pages = {
    "KYC Guard": [
        st.Page("views/home.py", title="Overview", icon="🛡️", default=True),
        st.Page("views/onboard.py", title="New Application", icon="📝"),
        st.Page("views/review.py", title="Reviewer Dashboard", icon="🧑‍⚖️"),
        st.Page("views/network.py", title="Fraud Network", icon="🕸️"),
    ],
    "Demo tools": [
        st.Page("views/idgen.py", title="Demo ID Generator", icon="🪪"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.caption("Hackathon POC · open-source models · no paid APIs")
    st.info("**Public demo.** Please don't upload real ID documents — use the Demo ID Generator. "
            "Visitor submissions are deleted after 24 hours.", icon="🔒")

nav.run()
