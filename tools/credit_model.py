#!/usr/bin/env python3
"""Deterministic credit model: the eight-pillar Index of CLAUDE.md section 5.

This is the single source of truth for the scoring rules on the Desk side.
Any change here must be mirrored in CLAUDE.md section 5 and in the Jetty
Credit `deterministic` / `computeIndex` logic (CLAUDE.md section 12.5).

Usage:
    python3 -I tools/credit_model.py deal.json
where deal.json holds the inputs documented in `INPUT_DOC` below. Prints the
calculated tests, pillar scores, caps applied, Index, band and an indicative
facility. Every rate used is stated in the output as an assumption.
"""
import json
import sys

WEIGHTS = {
    "document_integrity": 0.15, "identity_ownership": 0.10, "track_record": 0.10,
    "scale": 0.15, "repayment_capacity": 0.20, "leverage": 0.10,
    "account_conduct": 0.10, "security_structure": 0.10,
}
ASSESSED = {"document_integrity", "identity_ownership", "account_conduct", "security_structure"}
# Assumed all-in SME rates by currency. Review against playbook/rates.md.
RATES = {"USD": .10, "EUR": .08, "GBP": .09, "AED": .09, "SAR": .09, "TRY": .48, "KES": .16,
         "NGN": .30, "GHS": .30, "ZAR": .13, "EGP": .30, "PKR": .18, "INR": .12, "UGX": .20,
         "TZS": .18, "BRL": .18}
SHORT_INSTRUMENTS = {"working_capital", "trade", "warehouse", "receivables", "purchase_order", "revenue_based"}
HAIRCUT = {"property": .60, "receivables": .75, "stock": .50, "equipment": .40, "cash": .95}

INPUT_DOC = """
{
  "deal": "CODE", "currency": "KES",
  "request": 36000000, "instrument": "trade",            # or "term"
  "tenor_months": 12, "rate_override": null,
  "declared_revenue": 0, "bank_inflows_annualised": 0,  # operating, net of inter-account transfers
  "ebitda": 0, "existing_debt": 0, "existing_debt_service_annual": 0, "existing_interest_annual": 0,
  "years_trading": 0, "track_record_assessment": 50,
  "assessed": {"document_integrity": null, "identity_ownership": null,
               "account_conduct": null, "security_structure": null},   # 0 to 100, null = no evidence
  "critical_integrity_finding": false, "arrears": false,
  "documentary_standard_supplied": 0.0,                 # share of tracker items received, 0 to 1
  "collateral": [{"type": "stock", "value": 0}],
  "startup": {"equity_raised": 0, "cash": 0, "monthly_burn": 0}   # optional
}
"""


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def lin(x, bad, good):
    """Linear score: 0 at `bad`, 100 at `good` (works either direction)."""
    if good == bad:
        return 50
    return clamp((x - bad) / (good - bad) * 100)


def evaluate(d):
    ccy = d.get("currency", "USD").upper()
    rate = d.get("rate_override") or RATES.get(ccy)
    if rate is None:
        raise SystemExit(f"No assumed rate for {ccy}; add it to RATES and to CLAUDE.md section 5.8.")
    req = float(d["request"])
    short = d.get("instrument") in SHORT_INSTRUMENTS
    tenor_y = max(d.get("tenor_months", 12), 1) / 12
    declared = float(d.get("declared_revenue") or 0)
    bank = float(d.get("bank_inflows_annualised") or 0)
    # like-for-like integrity test: bank inflows for the same period as the declared revenue
    bank_same_period = float(d.get("bank_inflows_same_period_as_declared") or bank)
    revenue = min(x for x in [declared, bank] if x > 0) if (declared or bank) else 0
    ebitda = float(d.get("ebitda") or 0)
    debt0 = float(d.get("existing_debt") or 0)
    tests, findings = {}, []
    F = lambda sev, t: findings.append({"severity": sev, "finding": t})

    # Revenue integrity
    if declared and bank_same_period:
        ratio = declared / bank_same_period
        tests["declared_to_bank"] = round(ratio, 2)
        if ratio > 2:
            F("critical", f"Declared revenue is {ratio:.1f}x annualised bank inflows.")
        elif ratio > 1.5:
            F("major", f"Declared revenue is {ratio:.1f}x annualised bank inflows.")
    elif declared and not bank:
        F("major", "No bank evidence of turnover. Scale is measured on the declaration alone.")

    # Scale
    scale_ratio = req / revenue if revenue else None
    tests["request_to_revenue"] = round(scale_ratio, 3) if scale_ratio else None
    if scale_ratio is None:
        scale_score = 0
        F("critical", "No revenue evidence; scale cannot be tested.")
    elif short:
        scale_score = 100 if scale_ratio <= .35 else lin(scale_ratio, .75, .35)
        if scale_ratio > .75:
            F("critical", f"Short line is {scale_ratio:.0%} of turnover (limit 35%, critical above 75%).")
        elif scale_ratio > .35:
            F("major", f"Short line is {scale_ratio:.0%} of turnover (limit 35%).")
    else:
        scale_score = 100 if scale_ratio <= .5 else lin(scale_ratio, 1.0, .5)
        if scale_ratio > 1:
            F("critical", f"Term debt is {scale_ratio:.0%} of revenue (critical above 100%).")
        elif scale_ratio > .5:
            F("major", f"Term debt is {scale_ratio:.0%} of revenue (limit 50%).")

    # Repayment capacity
    st = d.get("startup")
    capacity_demonstrated = True
    new_interest = req * rate
    if st and ebitda <= 0:
        equity, cash, burn = st.get("equity_raised", 0), st.get("cash", 0), st.get("monthly_burn", 0)
        ds_month = (new_interest if short else req / tenor_y + new_interest) / 12 + d.get("existing_debt_service_annual", 0) / 12
        runway = cash / (burn + ds_month) if (burn + ds_month) else 99
        tests["runway_months_after_debt_service"] = round(runway, 1)
        tests["debt_to_equity_raised"] = round(req / equity, 2) if equity else None
        cap_score = lin(runway, 6, 18)
        if runway < 6:
            F("critical", f"Runway after debt service is {runway:.1f} months.")
            capacity_demonstrated = False
        elif runway < 12:
            F("major", f"Runway after debt service is {runway:.1f} months.")
        if equity and req / equity > .35:
            F("major", f"Debt is {req / equity:.0%} of equity raised (guide 25% to 35%).")
    elif short:
        interest = new_interest + d.get("existing_interest_annual", 0)
        icr = ebitda / interest if interest else 99
        tests["interest_cover"] = round(icr, 2)
        cap_score = lin(icr, 1.0, 2.5)
        if icr < 1.5:
            F("critical" if icr < 1 else "major", f"Interest cover {icr:.2f}x against a minimum of 1.5x.")
            capacity_demonstrated = icr >= 1.5
    else:
        principal = req / tenor_y
        ds = principal + new_interest + d.get("existing_debt_service_annual", 0)
        dscr = ebitda / ds if ds else 99
        tests["dscr"] = round(dscr, 2)
        cap_score = lin(dscr, 0.9, 1.75)
        if dscr < 1.25:
            F("critical" if dscr < 1 else "major", f"Debt service cover {dscr:.2f}x against a minimum of 1.25x.")
            capacity_demonstrated = False
    if ebitda <= 0 and not st:
        capacity_demonstrated = False
        cap_score = min(cap_score, 20)

    # Leverage
    if st and ebitda <= 0:
        base = st.get("cash", 0) + st.get("equity_raised", 0)
        lev = (debt0 + req) / base if base else 99
        tests["debt_to_cash_plus_equity"] = round(lev, 2)
        lev_score = lin(lev, 1.0, .25)
    else:
        lev = (debt0 + req) / ebitda if ebitda > 0 else 99
        tests["leverage_x_ebitda"] = round(lev, 2) if ebitda > 0 else "n/m (EBITDA <= 0)"
        lev_score = lin(lev, 6, 2)
        if lev > 6:
            F("critical", f"Leverage {lev:.1f}x EBITDA (critical above 6x).")
        elif lev > 4:
            F("major", f"Leverage {lev:.1f}x EBITDA (major above 4x).")

    # Track record: calculated half from years trading
    yrs = float(d.get("years_trading") or 0)
    tr_calc = lin(yrs, 0, 5)
    tr = .5 * tr_calc + .5 * (d.get("track_record_assessment") if d.get("track_record_assessment") is not None else 40)

    # Security
    cover_value = sum(HAIRCUT.get(c["type"], 0) * c["value"] for c in d.get("collateral", []))
    cover = cover_value / req if req else 0
    tests["collateral_cover_after_haircut"] = round(cover, 2)
    if cover < .5:
        F("major", f"Collateral cover after haircut is {cover:.0%} (flag below 50%).")

    scores = {"scale": scale_score, "repayment_capacity": cap_score, "leverage": lev_score, "track_record": tr}
    for p in ASSESSED:
        v = (d.get("assessed") or {}).get(p)
        scores[p] = 40 if v is None else min(v, 100)  # no evidence: at most 40
        if v is None:
            F("info", f"{p.replace('_', ' ').title()}: no evidence, scored at the 40 ceiling.")
    raw = sum(WEIGHTS[p] * scores[p] for p in WEIGHTS)

    caps = []
    if d.get("critical_integrity_finding"):
        caps.append(("critical integrity finding", 34))
    if d.get("arrears"):
        caps.append(("arrears on existing debt", 34))
    if (d.get("documentary_standard_supplied") or 0) < .4:
        caps.append(("under 40% of the documentary standard", 34))
    if not capacity_demonstrated:
        caps.append(("repayment capacity not demonstrated", 50))
    index = raw
    for _, c in caps:
        index = min(index, c)
    index = round(index)
    band = ("Lender-ready" if index >= 75 else "Fundable with remedies" if index >= 55
            else "Restructuring required" if index >= 35 else "Not yet fundable")

    # Indicative facility: the largest size the evidence supports
    if short:
        by_scale = .30 * revenue
        by_cover = (ebitda / 1.5 - d.get("existing_interest_annual", 0)) / rate if ebitda > 0 else 0
    else:
        by_scale = .50 * revenue
        ann_cap = ebitda / 1.25 - d.get("existing_debt_service_annual", 0)
        by_cover = ann_cap / (1 / tenor_y + rate) if ann_cap > 0 else 0
    by_lev = max(0, 4 * ebitda - debt0) if ebitda > 0 else 0
    candidates = {"scale": by_scale, "cover": by_cover, "leverage": by_lev}
    if short and d.get("peak_month_inflow"):  # seasonal traders only, never term debt
        candidates["one_peak_cycle"] = d["peak_month_inflow"]
    indicative = max(0, min(min(candidates.values()), req))

    order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    return {
        "deal": d.get("deal"), "currency": ccy,
        "assumption": f"All-in rate assumed at {rate:.0%} for {ccy}; instrument treated as "
                      f"{'short (interest cover)' if short else 'term (debt service cover)'}.",
        "revenue_basis": revenue, "tests": tests,
        "pillar_scores": {p: round(scores[p]) for p in WEIGHTS},
        "raw_index": round(raw, 1), "caps_applied": caps, "index": index, "band": band,
        "indicative_facility": round(indicative, -3),
        "sizing_constraints": {k: round(v, -3) for k, v in candidates.items()},
        "findings": sorted(findings, key=lambda f: order[f["severity"]]),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(INPUT_DOC)
        sys.exit(0)
    print(json.dumps(evaluate(json.load(open(sys.argv[1]))), indent=2))
