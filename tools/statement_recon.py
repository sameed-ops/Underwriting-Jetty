#!/usr/bin/env python3
"""Bank statement reconstruction, reconciliation and conduct analysis.

Implements the parsing playbook in CLAUDE.md section 4: parse each transaction
by its date and final running balance, derive the amount from the change in
balance, then compare with the printed amount and the printed summary.

Usage:
    pdftotext -layout statement.pdf /tmp/s.txt
    python3 -I tools/statement_recon.py /tmp/s.txt [--opening X] [--closing Y]
        [--printed-credits C] [--printed-debits D] [--currency KES] [--json out.json]
    python3 -I tools/statement_recon.py ledger.csv   # columns: date,narrative,debit,credit,balance

What it reports:
  * row-level mismatches between printed amount and change in balance;
  * a constant offset in the running balance (the Statement_8 pattern) and
    step changes in the offset (rows edited mid-statement);
  * summary reconciliation (opening + credits - debits = closing; last running
    balance = closing);
  * monthly inflows and outflows, last 3 months against the peak month;
  * share of days overdrawn, returned items, loan and digital-lender traffic,
    counterparty concentration, round-number and cash deposits, weekend
    postings, duplicate references, date order.
"""
import argparse
import collections
import csv
import datetime as dt
import json
import re
import statistics
import sys

AMT = r"-?\(?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\)?|-?\(?\d+(?:\.\d{1,2})?\)?"
AMT_RE = re.compile(r"(?<![\w/:.-])(" + AMT + r")(\s?(?:Cr|CR|Dr|DR))?(?![\w/:])")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_PATTERNS = [
    (re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})"), "ymd"),
    (re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"), "dmY"),
    (re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\b"), "dmy"),
    (re.compile(r"^\s*(\d{1,2})[ -]([A-Za-z]{3})[a-z]*[ -,]*(\d{2,4})"), "dMy"),
]

RETURN_KW = r"\b(RTN|RTD|RETURN(ED)?|UNPAID|BOUNCE|DISHONOU?R|INSUFF|NSF|REFER TO DRAWER|CHQ RET)"
REVERSAL_KW = r"\b(REVERS|REFUND|RVSL|CHARGEBACK)"
LOAN_KW = (r"\b(LOAN|DISB|DISBURSE|REPAY|INSTAL|EMI|FULIZA|M-?SHWARI|KCB ?M-?PESA|BRANCH|TALA|"
           r"ZENKA|OKASH|HUSTLER|SACCO|MFB|MICROFIN|OVERDRAFT|O/D|LIEN|ASSET FIN|LEASE)")
CASH_KW = r"\b(CASH DEP|CSH DEP|CASH DEPOSIT|CDM|AGENT DEP|BY CASH)"
CHARGE_KW = r"\b(CHARGE|FEE|COMMISSION|EXCISE|LEDGER FEE|SMS)\b"
XB_KW = r"(\+?255\d{6,}|\+?256\d{6,}|\+?250\d{6,}|\+?211\d{6,}|SWIFT|TT IN|TT OUT|FX|FOREIGN|USD|EUR|GBP|AED)"


def parse_amount(tok, suffix=None):
    neg = tok.startswith("-") or (tok.startswith("(") and tok.endswith(")"))
    v = float(tok.strip("-()").replace(",", ""))
    if suffix and suffix.strip().upper() == "DR":
        neg = True
    return -v if neg else v


def parse_date(line):
    for rx, kind in DATE_PATTERNS:
        m = rx.match(line)
        if not m:
            continue
        a, b, c = m.groups()
        try:
            if kind == "ymd":
                d = dt.date(int(a), int(b), int(c))
            elif kind == "dmY":
                d = dt.date(int(c), int(b), int(a))
            elif kind == "dmy":
                d = dt.date(2000 + int(c), int(b), int(a))
            else:
                mon = MONTHS.get(b[:3].lower())
                if not mon:
                    continue
                y = int(c) + (2000 if len(c) == 2 else 0)
                d = dt.date(y, mon, int(a))
        except ValueError:
            continue
        return d, m.end()
    return None, None


def parse_text(path):
    rows, pending_narr = [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    for ln in lines:
        d, end = parse_date(ln)
        if not d:
            s = ln.strip()
            if s and rows and len(s) < 120 and not AMT_RE.fullmatch(s):
                rows[-1]["narrative"] += " | " + s
            continue
        rest = ln[end:]
        amts = [(m.group(1), m.group(2), m.start()) for m in AMT_RE.finditer(rest)]
        # drop things that are obviously not money: 4+ digit integers without separators
        # that look like references, unless they are the balance.
        if not amts:
            continue
        bal_tok, bal_suf, _ = amts[-1]
        try:
            bal = parse_amount(bal_tok, bal_suf)
        except ValueError:
            continue
        printed = []
        for tok, suf, pos in amts[:-1]:
            if "." in tok or "," in tok:
                try:
                    printed.append(abs(parse_amount(tok, suf)))
                except ValueError:
                    pass
        narr = AMT_RE.sub("", rest).strip()
        narr = re.sub(r"\s{2,}", " ", narr)
        rows.append({"date": d, "narrative": narr, "printed": printed[-1] if printed else None,
                     "printed_all": printed, "balance": bal, "line": ln.strip()[:160]})
    return rows


MPESA_RE = re.compile(r"^\s*([A-Z0-9]{10})\s+(\d{4}-\d\d-\d\d) \d\d:\d\d:\d\d\s+(.*?)\s+(Completed|Failed|Reversed)\s+(.*)$")


def parse_mpesa(path):
    """Safaricom M-Pesa statement (pdftotext -layout). Failed rows are skipped."""
    rows = []
    for ln in open(path, encoding="utf-8", errors="replace").read().splitlines():
        m = MPESA_RE.match(ln)
        if not m:
            if rows and ln.strip() and not re.match(r"^\s*[A-Z0-9]{10}\s", ln):
                rows[-1]["narrative"] += " | " + ln.strip()[:80]
            continue
        code, d, narr, status, tail = m.groups()
        if status == "Failed":
            continue
        nums = [abs(parse_amount(t)) for t, _, _ in [(x.group(1), x.group(2), 0) for x in AMT_RE.finditer(tail)]]
        if not nums:
            continue
        rows.append({"date": dt.date.fromisoformat(d), "narrative": narr + (" REVERSAL" if status == "Reversed" else ""),
                     "printed": nums[-2] if len(nums) > 1 else None, "balance": nums[-1], "line": code})
    return rows


def parse_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items()}
            d, _ = parse_date(r["date"])
            dr = float(r.get("debit") or 0 or 0) if r.get("debit") else 0.0
            cr = float(r.get("credit") or 0) if r.get("credit") else 0.0
            rows.append({"date": d, "narrative": r.get("narrative", ""),
                         "printed": cr or dr or None, "printed_signed": cr - dr,
                         "balance": float(r["balance"].replace(",", "")), "line": ""})
    return rows


def normalise_counterparty(n):
    n = n.upper()
    n = re.sub(r"\b[A-Z0-9]{10,}\b", "", n)  # refs
    n = re.sub(r"\d{6,}", "", n)  # phone and account numbers (never stored)
    n = re.sub(r"[^A-Z &]", " ", n)
    n = re.sub(r"\b(MPESA|M PESA|TRF|TRANSFER|FROM|TO|PAYMENT|FT|IFT|RTGS|EFT|PESALINK|B C|CR|DR)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()[:40] or "UNIDENTIFIED"


def analyse(rows, opening=None, closing=None, p_credits=None, p_debits=None, tol=0.011):
    out = {"rows": len(rows), "findings": []}
    F = out["findings"].append
    if len(rows) < 2:
        F(("critical", "Fewer than two transaction rows parsed. Check the format or supply CSV."))
        return out

    if rows[0]["date"] > rows[-1]["date"]:
        rows = rows[::-1]
        out["reversed"] = True
    dates = [r["date"] for r in rows]
    out_of_order = sum(1 for a, b in zip(dates, dates[1:]) if b < a)
    if out_of_order:
        F(("minor", f"{out_of_order} row(s) out of date order after orientation. Check for inserted rows."))
    out["period"] = [str(dates[0]), str(dates[-1])]

    # derive amounts from balances
    if opening is None:
        first = rows[0]
        if first.get("printed_signed") is not None:
            opening = first["balance"] - first["printed_signed"]
            out["opening_inferred"] = True
    prev = opening
    mism, residuals = [], []
    for i, r in enumerate(rows):
        if prev is None:
            r["amount"] = None
        else:
            r["amount"] = round(r["balance"] - prev, 2)
            if r["printed"] is not None and abs(abs(r["amount"]) - r["printed"]) > tol:
                mism.append({"i": i, "date": str(r["date"]), "printed": r["printed"],
                             "from_balances": r["amount"], "diff": round(abs(r["amount"]) - r["printed"], 2)})
        prev = r["balance"]
    out["row_mismatches"] = len(mism)
    out["row_mismatch_sample"] = mism[:15]

    # offset analysis: balance minus (opening + cumulative printed signed amounts)
    if opening is not None:
        cum = opening
        for r in rows:
            if r.get("printed_signed") is not None:
                s = r["printed_signed"]
            elif r["printed"] is not None and r["amount"] is not None:
                s = r["printed"] if r["amount"] >= 0 else -r["printed"]
            else:
                s = r["amount"] or 0
            cum += s
            residuals.append(round(r["balance"] - cum, 2))
        steps = [(i, residuals[i - 1], residuals[i]) for i in range(1, len(residuals))
                 if abs(residuals[i] - residuals[i - 1]) > tol]
        if residuals and all(abs(x - residuals[0]) <= tol for x in residuals) and abs(residuals[0]) > tol:
            F(("critical", f"Every running balance is offset by a constant {residuals[0]:,.2f} from the "
                           "opening balance plus printed amounts. Balances were shifted after issue (Statement_8 pattern)."))
        elif steps:
            F(("critical" if len(steps) <= 5 else "major",
               f"Running-balance offset changes at {len(steps)} point(s), first at row {steps[0][0]} "
               f"({rows[steps[0][0]]['date']}). Rows near these points were edited or are missing."))
        out["offset_steps"] = steps[:20]

    if mism and not out.get("offset_steps"):
        F(("major", f"{len(mism)} row(s) where the printed amount differs from the change in running balance."))

    credits = sum(r["amount"] for r in rows if r["amount"] and r["amount"] > 0)
    debits = -sum(r["amount"] for r in rows if r["amount"] and r["amount"] < 0)
    out["derived_credits"], out["derived_debits"] = round(credits, 2), round(debits, 2)
    last_bal = rows[-1]["balance"]
    out["last_running_balance"] = last_bal
    if closing is not None:
        if abs(last_bal - closing) > tol:
            F(("critical", f"Last running balance {last_bal:,.2f} does not equal printed closing {closing:,.2f} "
                           f"(difference {last_bal - closing:,.2f})."))
        if opening is not None and p_credits is not None and p_debits is not None:
            summ = opening + p_credits - p_debits
            if abs(summ - closing) > tol:
                F(("major", f"Printed summary does not add up: opening + credits - debits = {summ:,.2f} "
                            f"against closing {closing:,.2f}."))
            elif abs(last_bal - closing) > tol or mism:
                F(("critical", "Summary reconciles but the ledger does not. The ledger was altered after issue."))
        if p_credits is not None and abs(credits - p_credits) > max(1, 0.001 * p_credits):
            F(("major", f"Derived credits {credits:,.2f} differ from printed total credits {p_credits:,.2f}."))

    # classification
    def flag(rx, r):
        return re.search(rx, (r["narrative"] + " " + r.get("line", "")).upper()) is not None

    monthly = collections.OrderedDict()
    op_in = collections.OrderedDict()
    loans, returns, reversals, cash, xb, round_in, weekend = [], [], [], [], [], [], 0
    payers = collections.Counter()
    refs = collections.Counter()
    for r in rows:
        if r["amount"] is None:
            continue
        k = r["date"].strftime("%Y-%m")
        m = monthly.setdefault(k, {"in": 0.0, "out": 0.0, "n": 0})
        m["n"] += 1
        a = r["amount"]
        is_loan, is_rev = flag(LOAN_KW, r), flag(REVERSAL_KW, r)
        if a > 0:
            m["in"] += a
            if not (is_loan or is_rev):
                op_in[k] = op_in.get(k, 0) + a
                payers[normalise_counterparty(r["narrative"])] += a
            if a >= 1000 and a % 1000 == 0:
                round_in.append(a)
            if flag(CASH_KW, r):
                cash.append(a)
        else:
            m["out"] += -a
        if is_loan:
            loans.append({"date": str(r["date"]), "amount": a, "narr": r["narrative"][:70]})
        if flag(RETURN_KW, r):
            returns.append({"date": str(r["date"]), "amount": a, "narr": r["narrative"][:70]})
        if is_rev:
            reversals.append(a)
        if flag(XB_KW, r):
            xb.append(a)
        if r["date"].weekday() == 6:
            weekend += 1
        for ref in re.findall(r"\b[A-Z0-9]{10,}\b", r.get("line", "")):
            if re.search(r"[A-Z]", ref) and re.search(r"\d", ref):
                refs[ref] += 1

    out["monthly"] = {k: {"in": round(v["in"], 2), "out": round(v["out"], 2), "n": v["n"]} for k, v in monthly.items()}
    out["operating_inflows_by_month"] = {k: round(v, 2) for k, v in op_in.items()}
    tot_op = sum(op_in.values())
    months = len(monthly)
    out["operating_inflows_total"] = round(tot_op, 2)
    out["months_covered"] = months
    if months >= 6:
        out["annualised_operating_inflows"] = round(tot_op / months * 12, 2)
    else:
        F(("info", f"Only {months} month(s) of data. Do not annualise (CLAUDE.md: six or more months)."))

    vals = list(op_in.values())
    if len(vals) >= 4:
        peak = max(vals)
        last3 = statistics.mean(vals[-3:])
        out["peak_month_inflow"], out["last3_avg_inflow"] = round(peak, 2), round(last3, 2)
        if peak and last3 < 0.2 * peak:
            F(("major", f"Last three months average {last3:,.0f} is {last3 / peak:.0%} of the peak month {peak:,.0f}. "
                        "Activity has collapsed; ask why trading stopped."))

    # overdrawn days: carry balance forward day by day
    day_bal = {}
    for r in rows:
        day_bal[r["date"]] = r["balance"]
    d, end = dates[0], dates[-1]
    cur, neg_days, total_days = None, 0, 0
    while d <= end:
        cur = day_bal.get(d, cur)
        if cur is not None:
            total_days += 1
            neg_days += cur < 0
        d += dt.timedelta(days=1)
    out["share_days_overdrawn"] = round(neg_days / total_days, 3) if total_days else None
    if total_days and neg_days / total_days > 0.4:
        F(("major", f"Overdrawn {neg_days / total_days:.0%} of days."))

    if returns:
        F(("major", f"{len(returns)} returned or unpaid item(s)."))
    if loans:
        F(("major", f"{len(loans)} loan, digital-lender, SACCO or lien entries. Reconcile to the declared schedule of borrowings."))
    out["loan_entries"] = loans[:40]
    out["returned_items"] = returns[:20]
    out["reversals_total"] = round(sum(reversals), 2)

    top = payers.most_common(10)
    out["top_payers"] = [{"payer": p, "amount": round(v, 2), "share": round(v / tot_op, 3) if tot_op else None} for p, v in top]
    if tot_op and len(top) >= 2 and (top[0][1] + top[1][1]) / tot_op > 0.6:
        F(("major", f"Top two payers are {(top[0][1] + top[1][1]) / tot_op:.0%} of operating inflows."))
    if top and top[0][0] == "UNIDENTIFIED" and top[0][1] / (tot_op or 1) > 0.3:
        F(("minor", "Over 30% of inflows have no identifiable payer. Ask for a payer schedule."))

    if cash:
        share = sum(cash) / (tot_op or 1)
        out["cash_deposit_share"] = round(share, 3)
        if share > 0.3:
            F(("minor", f"Cash deposits are {share:.0%} of operating inflows. Inflows are harder to verify; ask for invoices."))
    if round_in and len(round_in) / max(1, sum(1 for r in rows if r['amount'] and r['amount'] > 0)) > 0.5:
        F(("minor", "Over half of credits are round thousands. Check for self-funding or window-dressing."))
    if xb:
        out["cross_border_entries"] = len(xb)
    dup = [k for k, v in refs.items() if v > 1]
    if dup:
        F(("major", f"{len(dup)} transaction reference(s) appear more than once. Possible copied rows."))
    out["sunday_postings"] = weekend

    order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    out["findings"] = [{"severity": s, "finding": t} for s, t in sorted(out["findings"], key=lambda f: order[f[0]])]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--opening", type=float)
    ap.add_argument("--closing", type=float)
    ap.add_argument("--printed-credits", type=float)
    ap.add_argument("--printed-debits", type=float)
    ap.add_argument("--currency", default="")
    ap.add_argument("--json")
    ap.add_argument("--dump-rows", action="store_true")
    ap.add_argument("--format", choices=["auto", "generic", "mpesa"], default="auto")
    a = ap.parse_args()
    ap_fmt = a.format
    if a.file.lower().endswith(".csv"):
        rows = parse_csv(a.file)
    else:
        rows = parse_mpesa(a.file) if ap_fmt == "mpesa" else parse_text(a.file)
        if ap_fmt == "auto" and len(rows) < 2:
            rows = parse_mpesa(a.file)
    res = analyse(rows, a.opening, a.closing, a.printed_credits, a.printed_debits)
    res["currency"] = a.currency
    if a.dump_rows:
        res["parsed_rows"] = [{k: (str(v) if k == "date" else v) for k, v in r.items() if k != "line"} for r in rows]
    s = json.dumps(res, indent=2, default=str)
    if a.json:
        open(a.json, "w").write(s)
    print(s)


if __name__ == "__main__":
    main()
