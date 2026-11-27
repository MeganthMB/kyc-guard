import random
from datetime import date

import streamlit as st

import ui
from core import pipeline
from core.seed import MULE_DEVICE, MULE_IP

st.title("📝 New Account Application")
st.caption("What the customer sees in the bank's onboarding app — plus a demo panel for simulating device signals.")

pre = st.session_state.get("prefill", {})
if pre:
    st.info(f"Pre-filled from the demo card for **{pre.get('name')}**. Edit any field to simulate a mismatch.")

if "challenge_dir" not in st.session_state:
    st.session_state.challenge_dir = random.choice(["LEFT", "RIGHT"])

# ---------------- device signals (simulated) ----------------
with st.sidebar:
    st.markdown("### 📱 Device signals (demo)")
    preset = st.selectbox("Device", ["This computer", f"Known mule phone ({MULE_DEVICE})", "Brand-new random device"])
    if preset.startswith("This"):
        dev_default, ip_default = ui.device_fingerprint(), ui.client_ip()
    elif preset.startswith("Known"):
        dev_default, ip_default = MULE_DEVICE, MULE_IP
    else:
        dev_default, ip_default = f"DEV-{random.randint(0x1000, 0xFFFF):04X}", f"49.{random.randint(30, 200)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    device_id = st.text_input("Device fingerprint", dev_default, key=f"dev_{preset}")
    ip = st.text_input("IP address", ip_default, key=f"ip_{preset}")
    emulator = st.toggle("Emulator detected")
    rooted = st.toggle("Rooted / jailbroken")
    vpn = st.toggle("VPN / proxy")
    virtual_cam = st.toggle("Virtual camera (injection attack)")

# ---------------- step 1: details ----------------
st.markdown("### 1 · Personal details")
c1, c2, c3 = st.columns(3)
name = c1.text_input("Full name (as on ID)", pre.get("name", ""))
dob_default = date.fromisoformat(pre["dob"]) if pre.get("dob") else date(1998, 1, 1)
dob = c2.date_input("Date of birth", dob_default, min_value=date(1920, 1, 1), max_value=date.today())
genders = ["Male", "Female", "Other"]
gender = c3.selectbox("Gender", genders, index=genders.index(pre["gender"]) if pre.get("gender") in genders else 0)
c4, c5, c6 = st.columns(3)
id_number = c4.text_input("ID number", pre.get("id_number", ""))
if "phone_default" not in st.session_state:
    st.session_state.phone_default = "98" + str(random.randint(10000000, 99999999))
phone = c5.text_input("Mobile number", st.session_state.phone_default)
email = c6.text_input("Email", (pre.get("name", "user").split()[0].lower() + "@example.com") if pre else "")
address = st.text_input("Address", pre.get("address", ""))

# ---------------- step 2: ID document ----------------
st.markdown("### 2 · ID document")
id_bytes = None
if pre.get("card"):
    use_pre = st.checkbox("Use the demo card from the ID Generator", True)
    if use_pre:
        id_bytes = pre["card"]
        st.image(id_bytes, width=420)
if id_bytes is None:
    up = st.file_uploader("Upload a photo/scan of the ID card", type=["jpg", "jpeg", "png"])
    id_bytes = up.getvalue() if up else None

# ---------------- step 3: selfie ----------------
st.markdown("### 3 · Selfie & liveness")
mode = st.radio("Capture method", ["Live camera with liveness challenge (recommended)", "Upload a photo"], horizontal=True)
selfie, challenge, source = None, None, "upload"
if mode.startswith("Live"):
    source = "camera"
    d = st.session_state.challenge_dir
    a, b = st.columns(2)
    with a:
        fa = st.camera_input("Step 1 — look straight at the camera", key="cam_a")
    with b:
        fb = st.camera_input(f"Step 2 — now turn your head to your **{d}**", key="cam_b")
    if fa:
        selfie = fa.getvalue()
        challenge = {"frame_a": fa.getvalue(), "frame_b": fb.getvalue() if fb else None, "direction": d}
    st.caption("The direction is random each session, so a pre-recorded video can't anticipate it.")
else:
    up = st.file_uploader("Upload a selfie", type=["jpg", "jpeg", "png"], key="selfie_up")
    selfie = up.getvalue() if up else None

# ---------------- submit ----------------
st.divider()
ready = all([name, id_number, id_bytes, selfie])
if st.button("🔍 Submit & verify", type="primary", disabled=not ready):
    form = dict(name=name.strip(), dob=dob.isoformat(), gender=gender, id_number=id_number,
                phone=phone, email=email, address=address)
    ctx = dict(device_id=device_id, ip=ip, emulator=emulator, rooted=rooted, vpn=vpn, virtual_camera=virtual_cam)
    with st.status("AI verification running…", expanded=True) as status:
        app = pipeline.process(form, selfie, id_bytes, source, challenge, ctx,
                               progress=lambda s: st.write(f"⏳ {s}"))
        status.update(label=f"Done — {app['id']}: {app['decision']} ({app['score']}/100)", state="complete", expanded=False)
    st.session_state.last_result = app
    st.session_state.challenge_dir = random.choice(["LEFT", "RIGHT"])

if not ready:
    st.caption("Fill in name and ID number, add the ID document and a selfie to enable verification.")

if st.session_state.get("last_result"):
    app = st.session_state.last_result
    st.markdown(f"## Result · {app['id']}")
    ui.render_result(app, app.get("images"), key="onboard")
    if app["status"] == "PENDING_REVIEW":
        if st.button("Open in Reviewer Dashboard →"):
            st.session_state.review_select = app["id"]
            st.switch_page("views/review.py")
