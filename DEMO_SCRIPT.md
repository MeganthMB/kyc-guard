# 5-minute hackathon demo script

## Before you go on stage
1. `run.bat` → **Overview** → **Load demo data**.
2. **Demo ID Generator**: create **two cards with your own photo** (webcam or upload) and download both:
   - `genuine`, name *Rahul Kumar* (or your name)
   - `edited_name`, fake name *Rohit Kumar*
3. Test the webcam once on **New Application** (browser camera permission). If the head-turn says "wrong direction", set `CAMERA_MIRRORED = True` in `core/config.py`.
4. Click **Clear my test applications** so your face starts fresh.

## On stage

**0:00 — The problem (30 s)**
"Banks now open accounts remotely: a selfie, an ID and a form. Fraudsters use deepfakes, edited IDs and the same phone to create dozens of mule accounts. A human reviewer misses these tricks. KYC Guard is an AI bank employee that checks every application in seconds and explains why."
Show **Overview**: six checks, scoring with hard rules, decision bands.

**0:45 — Scenario 1: genuine customer → APPROVE (60 s)**
New Application → upload the genuine card, fill in the matching details → **Live camera**: look straight, then turn your head as instructed → Submit.
Point out: live challenge passed, QR signature verified, face match %, score in the green. Download the HTML report.

**1:45 — Scenario 2: edited ID → caught (60 s)**
Home → **Clear my test applications**. New Application → upload the **edited_name** card and type *Rohit Kumar* → upload a selfie instead of the camera → Submit.
Point out: the **red box exactly on the edited name**, "form says Rohit but the signed QR says Rahul", and that the uploaded selfie is riskier than a live capture. Read the audit-ready explanation aloud.

**2:45 — Scenario 3: mule ring → caught (60 s)**
Sidebar → Device: **Known mule phone**. Submit any application.
Point out: "Device used across 6 applications", "mule-account ring".
Open **Fraud Network**: the cluster around one device and one lodge address. "The first three got approved before the pattern was visible. The graph catches them retroactively." Click **Send all approved accounts back to manual review**.

**3:45 — Human in the loop (45 s)**
**Reviewer Dashboard**: open a pending case, show the evidence and linked accounts, then approve or reject with a note. Show the audit trail.

**4:30 — Close (30 s)**
"Runs fully offline on a laptop with open-source models. Privacy by design: we never store the full ID number. Next steps: a trained deepfake classifier, a mobile SDK for real device signals, and verifying the real UIDAI Secure QR / DigiLocker."

## Optional extra attacks
- **Forged QR card** → "signature INVALID" → automatic REJECT.
- **Photo swap card** (needs a second person's photo) → "printed photo doesn't match the face in the signed QR".
- Sidebar **Virtual camera** toggle → camera-injection attack → REJECT.
- Apply twice with your face under two names → "same face, multiple identities".
- Hold a phone showing a photo up to the webcam → the challenge fails (the photo can't turn its head).
