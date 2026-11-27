"""Check 4 — Data Cross-Verification: what the applicant typed vs what the
signed document says (the QR is the trusted source, because it is signed)."""
import re
from datetime import date
from difflib import SequenceMatcher

from .idcard import verhoeff_valid
from .types import CheckResult

HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "shri", "sri", "smt", "kumari", "km"}
DISPOSABLE = {"mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
              "yopmail.com", "trashmail.com", "temp-mail.org", "getnada.com"}


def norm_name(s: str) -> str:
    toks = [t for t in re.sub(r"[^a-z ]", " ", str(s).lower()).split() if t not in HONORIFICS]
    return " ".join(sorted(toks))


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()


def norm_address(s: str) -> set:
    return {t for t in re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).split() if len(t) > 1}


def digits(s) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())


def run(form: dict, doc_details: dict) -> CheckResult:
    res = CheckResult("data")
    qr = doc_details.get("qr_identity")
    qr_id = doc_details.get("_qr_id_number", "")
    form_id = digits(form.get("id_number", ""))

    # ID number format (Verhoeff checksum, like Aadhaar)
    if len(form_id) != 12 or not verhoeff_valid(form_id):
        res.add("ID_CHECKSUM_INVALID", "ID number entered fails the checksum — mistyped or fabricated.", 30, "medium")

    # Age
    try:
        dob = date.fromisoformat(str(form.get("dob")))
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        res.details["age"] = age
        if age < 18:
            res.add("MINOR_APPLICANT", f"Applicant is {age}: a minor account needs a guardian-operated flow.", 20)
        elif age > 100:
            res.add("IMPLAUSIBLE_AGE", f"Implausible age ({age}).", 30)
    except Exception:
        res.add("DOB_INVALID", "Date of birth is not a valid date.", 20)

    # Contact sanity
    phone = digits(form.get("phone", ""))[-10:]
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        res.add("PHONE_INVALID", "Mobile number is not a valid 10-digit Indian number.", 10)
    email = str(form.get("email", "")).lower()
    if "@" in email and email.split("@")[-1] in DISPOSABLE:
        res.add("DISPOSABLE_EMAIL", f"Disposable email domain ({email.split('@')[-1]}).", 20)

    if not qr:
        res.add("NO_TRUSTED_SOURCE", "No verified document data to compare against (QR unreadable).", 30, "medium")
        return res

    # Name
    sim = name_similarity(form.get("name", ""), qr.get("name", ""))
    res.details["name_similarity"] = round(sim, 3)
    res.details["form_name"], res.details["document_name"] = form.get("name"), qr.get("name")
    if sim >= 0.999:
        res.add("NAME_MATCH", "Name matches the document.", 0)
    elif sim >= 0.93:
        res.add("NAME_MINOR_VARIATION", f"Minor spelling variation: '{form.get('name')}' vs '{qr.get('name')}'.", 5)
    else:
        res.add("NAME_MISMATCH", f"Name mismatch: form says '{form.get('name')}' but ID says '{qr.get('name')}'.",
                40, "high", floor=61)

    # DOB
    if str(form.get("dob")) != str(qr.get("dob")):
        res.add("DOB_MISMATCH", f"Date of birth mismatch: form {form.get('dob')} vs ID {qr.get('dob')}.", 35, "high", floor=61)

    # ID number
    if qr_id and form_id and form_id != digits(qr_id):
        res.add("ID_NUMBER_MISMATCH", "ID number entered does not match the document.", 50, "high", floor=61)

    # Gender
    if form.get("gender") and qr.get("gender") and form["gender"] != qr["gender"]:
        res.add("GENDER_MISMATCH", "Gender differs between form and document.", 15)

    # Address (people move, so this is soft)
    fa, da = norm_address(form.get("address", "")), norm_address(qr.get("address", ""))
    if fa and da:
        j = len(fa & da) / len(fa | da)
        res.details["address_overlap"] = round(j, 2)
        if j < 0.4:
            res.add("ADDRESS_MISMATCH", "Address differs substantially from the document.", 15)
    return res
