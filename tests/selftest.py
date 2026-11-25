#!/usr/bin/env python3
"""Self-test on synthetic, Illustrative data. Run: python3 -I tests/selftest.py"""
import os, random, sys, tempfile, datetime as dt, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import statement_recon as sr, credit_model as cm

def make(offset_from=None, offset=0, n=180, seed=1):
    random.seed(seed); bal = 250000.0; d = dt.date(2025, 11, 1); lines = []
    for i in range(n):
        d += dt.timedelta(days=random.choice([1, 1, 2]))
        if random.random() < .55:
            a = round(random.uniform(5000, 90000), 2); bal += a; narr = f"MPESA C2B FROM PAYER{random.randint(1,40)}"
        else:
            a = -round(random.uniform(3000, 80000), 2)
            if bal + a < 0: a = -round(bal * .3, 2)
            bal += a; narr = "TPG/IMB/SUPPLIER" if random.random() < .5 else "LOAN REPAYMENT FULIZA" if random.random() < .1 else "PAYMENT TO SUPPLIER"
        shown = bal + (offset if offset_from is not None and i >= offset_from else 0)
        dr, cr = (f"{-a:,.2f}", "") if a < 0 else ("", f"{a:,.2f}")
        lines.append(f"{d:%d-%m-%Y}  {narr:<32} {dr:>14} {cr:>14} {shown:>16,.2f}")
    return "\n".join(lines), 250000.0, bal

ok = True
def check(name, cond):
    global ok; ok &= cond; print(("PASS " if cond else "FAIL ") + name)

for label, kw in [("clean", {}), ("constant +600", {"offset_from": 0, "offset": 600}), ("step at row 90", {"offset_from": 90, "offset": 15000})]:
    txt, op, cl = make(**kw)
    p = tempfile.mktemp(suffix=".txt"); open(p, "w").write(txt)
    rows = sr.parse_text(p); res = sr.analyse(rows, opening=op, closing=cl)
    sev = [f["severity"] for f in res["findings"]]; text = " ".join(f["finding"] for f in res["findings"])
    print(f"-- {label}: rows={res['rows']} mismatches={res['row_mismatches']} findings={sev}")
    if label == "clean": check("clean has no critical", "critical" not in sev and res["rows"] == 180)
    if label.startswith("constant"): check("constant offset detected", "constant 600.00" in text)
    if label.startswith("step"): check("step detected", "offset changes at 1 point" in text)

deal = {"deal": "TEST", "currency": "KES", "request": 36e6, "instrument": "trade", "tenor_months": 12,
        "declared_revenue": 80e6, "bank_inflows_annualised": 29.2e6, "ebitda": 2.5e6, "existing_debt": 2.5e6,
        "years_trading": 2, "track_record_assessment": 40,
        "assessed": {"document_integrity": 10, "identity_ownership": 60, "account_conduct": 30, "security_structure": None},
        "critical_integrity_finding": True, "documentary_standard_supplied": .6,
        "collateral": [{"type": "stock", "value": 10e6}], "peak_month_inflow": 6e6}
r = cm.evaluate(deal)
print(json.dumps({k: r[k] for k in ["index", "band", "tests", "indicative_facility", "caps_applied"]}))
check("Illustrative Blossom-like case is Not yet fundable", r["band"] == "Not yet fundable" and r["index"] <= 34)
sys.exit(0 if ok else 1)
