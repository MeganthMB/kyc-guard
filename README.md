# 🛡️ KYC Guard — AI Digital Bank Employee (Hackathon POC)

> An AI-powered identity verification platform that detects deepfakes, fake documents, synthetic identities and onboarding fraud in real time, then generates a risk score and decision with explainable evidence.

**Runs 100% on your laptop. No cloud, no paid APIs, no real ID documents needed.**

## Quick start (Windows)

1. Install **Python 3.10 or newer** from python.org (tick *"Add python.exe to PATH"*).
2. Unzip this folder and double-click **`run.bat`**.
   The first run takes 2–4 minutes to install packages, then your browser opens at `http://localhost:8501`.

macOS/Linux: `bash run.sh`

Manual setup:
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m core.seed             # loads demo history + a mule ring
streamlit run app.py
```

## What it does

| # | Check | How (all free / open source) |
|---|---|---|
| 1 | **Deepfake & liveness** | Random head-turn challenge over two live webcam frames (defeats photos, replays, pre-rendered deepfakes) · virtual-camera injection flag · AI-generator metadata (C2PA, Stable Diffusion params, editing tools) · screen-replay moiré in the frequency spectrum · plug-in point for a trained deepfake classifier |
| 2 | **Document verification** | Ed25519 **digitally signed QR** (like Aadhaar Secure QR) · **photo-swap** detection (printed photo vs face fingerprint inside the signed QR) · **JPEG-ghost Error Level Analysis** that draws red boxes around edited regions |
| 3 | **Face match** | OpenCV YuNet face detector + SFace face recognition (ONNX, CPU) |
| 4 | **Data cross-verification** | Form vs signed QR: fuzzy name match, DOB, ID number + **Verhoeff checksum**, gender, address, age, phone, disposable email |
| 5 | **Device & network** | Device reuse across identities, velocity per device / IP (24 h), emulator / rooted / VPN signals |
| 6 | **Synthetic identity** | NetworkX identity graph linking applicants by device, phone, email, address, ID number and **face** → mule-ring clusters |

**Scoring:** weighted blend (25/20/20/15/10/10) **plus hard rules**. A critical finding sets a minimum score, so a forged QR or a reused face can never be averaged away by clean checks. Bands: 0–30 Approve · 31–60 Re-verify · 61–80 Manual review · 81–100 Reject.

**Explainability:** every finding has a reason code and a plain-English message. Each application gets an audit-ready summary, a reviewer audit trail and a downloadable HTML report.

**Privacy by design:** the full ID number is never stored, only a masked value (`XXXX XXXX 1234`) and an HMAC hash used to detect reuse.

## Pages

- **Overview**: summary metrics, the approach, and demo setup buttons
- **New Application**: the customer journey (details → ID → live selfie with challenge) plus a sidebar to simulate device signals
- **Reviewer Dashboard**: queue, full evidence, linked applications, and Approve / Reject / Request re-capture with mandatory notes
- **Fraud Network**: interactive identity graph, suspicious clusters, retroactive flagging of already-approved mule accounts
- **Demo ID Generator**: fictional SPECIMEN cards, either genuine or with built-in fraud (edited name, photo swap, forged QR)

## Project layout

```
app.py              Streamlit entry + navigation
ui.py               shared UI components (result view, network graph)
views/              the five pages
core/
  liveness.py       check 1     document.py   check 2
  facematch.py      check 3     crossverify.py check 4
  device.py         check 5     graph.py      check 6
  scoring.py        weights, hard rules, decision bands, explanation
  pipeline.py       runs all checks, stores the result
  idcard.py         demo issuer: signed QR, card drawing, Verhoeff
  db.py             SQLite + audit log      report.py  HTML audit report
  seed.py           demo history + mule ring
models/             YuNet + SFace ONNX models (auto-downloaded if missing)
data/               created at runtime: database, uploads, demo keys
```

## Honest limitations (good to say out loud to the judges)

- Passive deepfake detection here is heuristic. The strong defenses are the **active challenge**, **injection detection** and **cryptographic document checks**. A trained classifier (e.g. EfficientNet on FaceForensics++ / Celeb-DF) plugs into `liveness.model_deepfake_score()`.
- Device signals are simulated in the sidebar. In production they come from a mobile SDK (device attestation, emulator, virtual-camera detection).
- ELA catches edits re-saved as JPEG after issue. An edit saved at exactly the original quality, or a phone photo of a printed card, needs other checks (the signed QR still catches data changes).
- The demo issuer is fictional. In production, verify the real issuer's signature, e.g. UIDAI Secure QR, or pull data from DigiLocker / CKYC.

## Configuration

`core/config.py` holds the weights, thresholds and decision bands. If the head-turn challenge always says "wrong direction", your webcam image is mirrored: set `CAMERA_MIRRORED = True`.
