import random
from datetime import date

import streamlit as st

from core import idcard

st.title("🪪 Demo ID Generator")
st.markdown("Create **fictional SPECIMEN ID cards** with a digitally signed QR — genuine or with a specific fraud built in — "
            "so you can demo the system without any real documents.")

if "gen_id_number" not in st.session_state:
    st.session_state.gen_id_number = idcard.new_id_number()

VARIANTS = {
    "genuine": "✅ Genuine — signed and untouched",
    "edited_name": "✏️ Edited name — name painted over in an image editor after issue",
    "photo_swap": "🔁 Photo swap — printed photo replaced with someone else's",
    "forged_qr": "🧾 Forged QR — QR rebuilt with fake data and signed with a fraudster's key",
}

c1, c2 = st.columns([1, 1])
with c1:
    st.markdown("#### Card holder")
    name = st.text_input("Full name", "Rahul Kumar")
    dob = st.date_input("Date of birth", date(1998, 4, 12), min_value=date(1920, 1, 1), max_value=date.today())
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    a, b = st.columns([3, 1])
    id_number = a.text_input("ID number (12 digits, Verhoeff checksum)", st.session_state.gen_id_number)
    if b.button("🎲 New", help="Generate a new valid ID number"):
        st.session_state.gen_id_number = idcard.new_id_number()
        st.rerun()
    address = st.text_input("Address", "12 MG Road, Bengaluru, Karnataka 560001")
with c2:
    st.markdown("#### Photo on the card")
    src = st.radio("Photo source", ["Webcam", "Upload"], horizontal=True)
    photo = (st.camera_input("Take the ID photo") if src == "Webcam"
             else st.file_uploader("Upload a face photo", type=["jpg", "jpeg", "png"]))

st.markdown("#### Card type")
variant = st.radio("Variant", list(VARIANTS), format_func=VARIANTS.get, label_visibility="collapsed")
alt_name, alt_photo = "", None
if variant in ("edited_name", "forged_qr"):
    alt_name = st.text_input("Fake name to put on the card", "Rohit Kumar")
if variant == "photo_swap":
    alt_photo = st.file_uploader("Photo of the OTHER person to paste on the card", type=["jpg", "jpeg", "png"], key="alt")

if st.button("Generate card", type="primary", disabled=photo is None or (variant == "photo_swap" and alt_photo is None)):
    digits = "".join(ch for ch in id_number if ch.isdigit())
    if len(digits) != 12 or not idcard.verhoeff_valid(digits):
        st.warning("That ID number fails the checksum — the card will be generated, but the system will flag it.")
    person = dict(name=name.strip(), dob=dob.isoformat(), gender=gender, id_number=digits, address=address.strip())
    with st.spinner("Issuing and signing card…"):
        card = idcard.make_card(person, photo.getvalue(), variant, alt_name=alt_name,
                                alt_photo=alt_photo.getvalue() if alt_photo else None)
    st.session_state.demo_card = {"person": person, "card": card, "variant": variant, "alt_name": alt_name}

dc = st.session_state.get("demo_card")
if dc:
    st.divider()
    st.image(dc["card"], caption=f"{VARIANTS[dc['variant']]}", width=640)
    x, y = st.columns(2)
    x.download_button("⬇️ Download card (JPG)", dc["card"], file_name=f"demo_id_{dc['variant']}.jpg", mime="image/jpeg")
    if y.button("➡️ Use this card in a new application", type="primary"):
        st.session_state.prefill = dict(dc["person"], card=dc["card"])
        if dc["variant"] in ("edited_name", "forged_qr") and dc.get("alt_name"):
            st.session_state.prefill["name"] = dc["alt_name"]  # the fraudster types the fake name
        st.switch_page("views/onboard.py")
    st.caption("Tip: download the original file and upload it as-is. Screenshots or heavily compressed copies can make the QR unreadable.")
