#!/usr/bin/env python3
"""PDF provenance and tamper screen for borrower documents.

Usage:
    python3 -I tools/pdf_forensics.py FILE.pdf [--password-env VAR]

The password, if any, is read from an environment variable so it never lands
in shell history, logs or the repository. It is never printed.

Checks (CLAUDE.md section 4, step 2, extended):
  1. Info dictionary and XMP: Producer, Creator, CreationDate, ModDate.
  2. Producer classification: bank-system, desktop editor, unknown.
  3. Gap between creation and modification (more than one day = major).
  4. Incremental updates: count of %%EOF markers and xref sections. A bank
     export is normally written once; extra revisions mean the file was
     saved again after issue.
  5. Info dictionary and XMP disagreeing on producer or dates.
  6. Font inventory per page: a figure set in a font that appears nowhere
     else on the page is a classic overlay edit.
  7. Text objects drawn on top of other text, and white rectangles (redaction
     style cover-ups) placed under text.
  8. Encryption, permissions, digital signatures, embedded files, JavaScript.
  9. File name hints: "_unprotected", "unlock", "decrypted", "compressed".

Severity scale follows CLAUDE.md: critical, major, minor, info.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

import pymupdf as fitz
import pikepdf

BANK_PRODUCERS = [
    "wkhtmltopdf", "omnioms", "newgen", "jasper", "jasperreports", "itext",
    "finacle", "flexcube", "temenos", "t24", "bancs", "oracle", "crystal reports",
    "birt", "apache fop", "fop", "pdflib", "ibm", "sap", "qt ", "reportlab",
    "aspose", "dompdf", "tcpdf", "fpdf", "chrome", "skia", "headless",
]
DESKTOP_EDITORS = [
    "microsoft word", "microsoft excel", "microsoft® word", "microsoft® excel",
    "word", "excel", "ilovepdf", "smallpdf", "sejda", "foxit", "nitro", "canva",
    "preview", "quartz pdfcontext", "libreoffice", "openoffice", "pdfescape",
    "pdf-xchange", "pdfelement", "wondershare", "adobe acrobat pro",
    "acrobat pro", "pdf candy", "pdf24", "soda pdf", "inkscape", "photoshop",
    "illustrator", "google docs", "wps",
]
NAME_HINTS = ["unprotected", "unlock", "decrypt", "compressed", "edited", "copy", "final"]


def parse_pdf_date(s):
    if not s:
        return None
    s = str(s)
    m = re.match(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", s)
    if not m:
        try:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    parts = [int(p) if p else d for p, d in zip(m.groups(), [0, 1, 1, 0, 0, 0])]
    try:
        return dt.datetime(*parts)
    except ValueError:
        return None


def classify_producer(text):
    t = (text or "").lower()
    if not t:
        return "missing"
    for d in DESKTOP_EDITORS:
        if d in t:
            return "desktop_editor"
    for b in BANK_PRODUCERS:
        if b in t:
            return "system"
    return "unknown"


def raw_structure(path):
    with open(path, "rb") as f:
        data = f.read()
    return {
        "eof_markers": len(re.findall(rb"%%EOF", data)),
        "xref_sections": len(re.findall(rb"\bstartxref\b", data)),
        "has_javascript": bool(re.search(rb"/JavaScript|/JS\b", data)),
        "has_embedded_files": b"/EmbeddedFile" in data,
        "has_signature": b"/Sig" in data and b"/ByteRange" in data,
        "bytes": len(data),
    }


def font_anomalies(doc, max_pages=60):
    """Spans whose font is used for very few characters on a page that is
    otherwise set in another font, restricted to spans that look numeric."""
    out = []
    for pno in range(min(len(doc), max_pages)):
        page = doc[pno]
        counts, spans = {}, []
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for sp in line["spans"]:
                    key = (sp["font"], round(sp["size"], 1))
                    counts[key] = counts.get(key, 0) + len(sp["text"].strip())
                    spans.append((key, sp["text"].strip(), sp["bbox"]))
        total = sum(counts.values()) or 1
        for key, text, bbox in spans:
            share = counts[key] / total
            if share < 0.02 and re.search(r"\d[\d,]*\.\d{2}", text):
                out.append({"page": pno + 1, "font": key[0], "size": key[1],
                            "text": text[:40], "share_of_page": round(share, 4)})
    return out


def overlay_checks(doc, max_pages=60):
    """White filled rectangles with text on top of them."""
    hits = []
    for pno in range(min(len(doc), max_pages)):
        page = doc[pno]
        try:
            drawings = page.get_drawings()
        except Exception:
            continue
        whites = [d["rect"] for d in drawings
                  if d.get("fill") and all(c > 0.97 for c in d["fill"][:3])
                  and 5 < d["rect"].width < page.rect.width * 0.6
                  and 3 < d["rect"].height < 40]
        if not whites:
            continue
        words = page.get_text("words")
        for r in whites:
            covered = [w[4] for w in words if fitz.Rect(w[:4]).intersects(r)]
            if covered and any(re.search(r"\d", w) for w in covered):
                hits.append({"page": pno + 1, "rect": [round(v, 1) for v in r],
                             "text_on_top": " ".join(covered)[:60]})
    return hits[:50]


def run(path, password=None):
    findings = []
    report = {"file": os.path.basename(path)}

    lname = report["file"].lower()
    hints = [h for h in NAME_HINTS if h in lname]
    if hints:
        findings.append(("info", f"File name suggests handling after issue: {hints}. "
                                 "Fine for review; ask for a bank-direct copy for the lender."))

    raw = raw_structure(path)
    report["structure"] = raw

    try:
        pdf = pikepdf.open(path, password=password or "")
    except pikepdf.PasswordError:
        print(json.dumps({"file": report["file"], "error": "password required or wrong"}))
        sys.exit(2)
    info = {str(k)[1:]: str(v) for k, v in (pdf.docinfo or {}).items()}
    report["encrypted"] = pdf.is_encrypted
    xmp = {}
    try:
        with pdf.open_metadata() as meta:
            for k in ["xmp:CreatorTool", "pdf:Producer", "xmp:CreateDate", "xmp:ModifyDate",
                      "xmp:MetadataDate", "xmpMM:DocumentID", "xmpMM:InstanceID"]:
                if k in meta:
                    xmp[k] = str(meta[k])
            history = meta.get("xmpMM:History")
            if history:
                xmp["xmpMM:History"] = str(history)[:400]
    except Exception:
        pass
    report["info"] = info
    report["xmp"] = xmp

    producer = info.get("Producer", "") or xmp.get("pdf:Producer", "")
    creator = info.get("Creator", "") or xmp.get("xmp:CreatorTool", "")
    pc, cc = classify_producer(producer), classify_producer(creator)
    report["producer_class"], report["creator_class"] = pc, cc
    if "desktop_editor" in (pc, cc):
        findings.append(("major", f"Desktop editor in metadata (Producer='{producer}', "
                                  f"Creator='{creator}'). Note: a genuine file re-saved on a Mac reads as Preview/Quartz."))
    elif pc == "missing" and cc == "missing":
        findings.append(("minor", "Producer and Creator both empty. Metadata may have been stripped."))
    elif pc == "unknown":
        findings.append(("info", f"Producer not in known lists: '{producer}'. Compare with other statements from the same bank."))

    cdate = parse_pdf_date(info.get("CreationDate") or xmp.get("xmp:CreateDate"))
    mdate = parse_pdf_date(info.get("ModDate") or xmp.get("xmp:ModifyDate"))
    report["created"], report["modified"] = str(cdate), str(mdate)
    if cdate and mdate:
        gap = (mdate - cdate).total_seconds() / 86400
        report["mod_gap_days"] = round(gap, 3)
        if gap > 1:
            findings.append(("major", f"Modified {gap:.1f} days after creation."))
        elif gap < -0.01:
            findings.append(("major", "ModDate earlier than CreationDate. Dates were set by hand or by a converter."))
    if "xmpMM:History" in xmp:
        findings.append(("major", "XMP edit history present: the file passed through an editing application."))

    if raw["eof_markers"] > 1:
        sev = "major" if raw["eof_markers"] > 2 or "desktop_editor" in (pc, cc) else "minor"
        findings.append((sev, f"{raw['eof_markers']} %%EOF markers: incremental save(s) after first write. "
                              "Some banks sign or linearise (which adds one); more than that, or with an editor producer, is a flag."))
    if raw["has_javascript"]:
        findings.append(("minor", "Contains JavaScript. Do not open in a full viewer; unusual for a statement."))
    if raw["has_embedded_files"]:
        findings.append(("info", "Contains embedded files. Extract and review."))
    if raw["has_signature"]:
        findings.append(("info", "Digital signature present. Validate it in Acrobat; a valid bank signature strongly supports authenticity."))

    doc = fitz.open(path)
    if doc.needs_pass:
        doc.authenticate(password or "")
    report["pages"] = len(doc)
    text_chars = sum(len(doc[i].get_text()) for i in range(min(len(doc), 5)))
    report["text_layer"] = text_chars > 50
    if not report["text_layer"]:
        findings.append(("minor", "No text layer on first pages: scanned or image-only. Bank exports usually carry text. OCR and treat figures with care."))

    fa = font_anomalies(doc)
    report["font_anomalies"] = fa[:30]
    if fa:
        findings.append(("major", f"{len(fa)} numeric span(s) set in a font used for under 2% of the page. "
                                  "Inspect visually: typical of an amount typed over the original."))
    ov = overlay_checks(doc)
    report["overlays"] = ov
    if ov:
        findings.append(("major", f"{len(ov)} white box(es) under numeric text: possible cover-and-retype edit."))

    order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    findings.sort(key=lambda f: order[f[0]])
    report["findings"] = [{"severity": s, "finding": t} for s, t in findings]
    worst = findings[0][0] if findings else "none"
    report["verdict"] = {"critical": "Critical", "major": "Accepted with findings (major)",
                         "minor": "Accepted with findings (minor)", "info": "No metadata concern",
                         "none": "No metadata concern"}[worst]
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--password-env", help="name of env var holding the password")
    a = ap.parse_args()
    pw = os.environ.get(a.password_env) if a.password_env else None
    for f in a.files:
        print(json.dumps(run(f, pw), indent=2, default=str))
