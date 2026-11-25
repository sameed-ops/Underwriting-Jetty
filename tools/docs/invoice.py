#!/usr/bin/env python3
"""Pro forma invoice generator for the Turkish entity (bilingual EN / TR).

Usage:
    python3 -I tools/docs/invoice.py deals/<CODE>/invoice.json [--out DIR]

Design basis (researched 25 Nov 2026, see playbook/invoicing.md):
  * A pro forma has no statutory form in Türkiye, but it mirrors the VUK
    art. 230 elements of the official invoice that follows it: date, number,
    both parties' names, addresses and tax identifiers, description,
    quantity, unit price, amount, plus a validity period and payment method.
  * Services exported to a foreign customer: KDV exempt under Law 3065
    art. 11/1-a; the official e-Arşiv invoice uses exemption code 302.
  * Kenyan withholding tax on professional fees to non-residents is shown as
    an explicit gross-up so that the net fee is never in dispute.
  * Wire instructions: beneficiary legal name, bank, bank address, IBAN,
    SWIFT, purpose of payment, reference, charges OUR. Intermediary bank
    only when the receiving bank names one.
Missing bank fields render as "To be completed" and block a final build
unless --draft is passed.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from letterhead import CSS, e, header, load_firm, render_pdf, statutory  # noqa: E402

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
TR1 = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
TR10 = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
CCY = {"USD": ("United States dollars", "cents", "ABD Doları", "sent"),
       "EUR": ("euros", "cents", "Avro", "sent"), "GBP": ("pounds sterling", "pence", "İngiliz Sterlini", "peni"),
       "TRY": ("Turkish lira", "kuruş", "Türk Lirası", "kuruş")}


def en_words(n):
    def h(n):
        if n < 20:
            return ONES[n]
        if n < 100:
            return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
        return ONES[n // 100] + " hundred" + (" and " + h(n % 100) if n % 100 else "")
    if n == 0:
        return "zero"
    parts = []
    for div, name in ((10**6, "million"), (1000, "thousand"), (1, "")):
        q, n = divmod(n, div)
        if q:
            parts.append(h(q) + (" " + name if name else ""))
    return " ".join(parts)


def tr_words(n):
    def h(n):
        s = ""
        if n >= 100:
            s += ("" if n // 100 == 1 else TR1[n // 100]) + "yüz"
        n %= 100
        return s + TR10[n // 10] + TR1[n % 10]
    if n == 0:
        return "sıfır"
    out = ""
    m, n = divmod(n, 10**6)
    if m:
        out += h(m) + "milyon"
    t, n = divmod(n, 1000)
    if t:
        out += ("" if t == 1 else h(t)) + "bin"
    return out + h(n)


def amount_words(x, ccy):
    big, small, tbig, tsmall = CCY.get(ccy, (ccy, "cents", ccy, "sent"))
    units, cents = int(round(x * 100)) // 100, int(round(x * 100)) % 100
    en = f"{en_words(units)} {big}" + (f" and {en_words(cents)} {small}" if cents else " only")
    tw = tr_words(units)
    tw = ("İ" if tw[0] == "i" else tw[0].upper()) + tw[1:]
    tr = f"Yalnız {tw} {tbig}" + (f" {tr_words(cents)} {tsmall}" if cents else "")
    return en[0].upper() + en[1:], tr


def money(x):
    return f"{x:,.2f}"


def build(inv, firm, draft):
    ccy = inv["currency"]
    issue = dt.date.fromisoformat(inv["issue_date"])
    valid = issue + dt.timedelta(days=inv.get("validity_days", 14))
    due = dt.date.fromisoformat(inv["due_date"]) if inv.get("due_date") else valid
    lines = inv["lines"]
    subtotal = sum(l["qty"] * l["unit_price"] for l in lines)
    vat_rate = inv.get("vat_rate", 0.0)
    vat = round(subtotal * vat_rate, 2)
    total = subtotal + vat
    w_en, w_tr = amount_words(total, ccy)
    b = firm["bank"]
    missing = [k for k in ("bank_name", "bank_address", "iban", "swift") if not b.get(k)]
    if missing and not draft:
        raise SystemExit(f"Bank fields missing: {missing}. Complete tools/docs/firm_tr.json or pass --draft.")
    tbc = '<span class="tbc">To be completed</span>'
    bank_rows = [("Beneficiary / Alıcı", e(b["beneficiary"])),
                 ("Bank / Banka", e(b.get("bank_name") or "") or tbc),
                 ("Branch / Şube", e(b.get("branch") or "") or tbc),
                 ("Bank address / Banka adresi", e(b.get("bank_address") or "") or tbc),
                 (f"IBAN ({e(b.get('account_currency', ccy))})", e(b.get("iban") or "") or tbc),
                 ("SWIFT / BIC", e(b.get("swift") or "") or tbc)]
    if b.get("intermediary"):
        bank_rows.append(("Intermediary bank / Muhabir banka", e(b["intermediary"])))
    bank_rows += [("Payment reference / Ödeme açıklaması", e(inv["payment_reference"])),
                  ("Purpose of payment / Ödeme amacı", e(inv["purpose_of_payment"])),
                  ("Charges / Masraflar", "OUR: all charges for the account of the remitter")]

    wht_html = ""
    if inv.get("wht"):
        r = inv["wht"]["rate"]
        gross = round(total / (1 - r), 2)
        wht_html = f"""
<div class="box"><b>Withholding tax gross-up / Stopaj</b><br>
{e(inv["wht"]["basis"])} If tax is withheld at {r:.0%}, the gross fee is <b>{ccy} {money(gross)}</b>:
{ccy} {money(gross - total)} is remitted to the {e(inv["wht"]["authority"])} and {ccy} {money(total)} to the Firm,
with the withholding certificate sent to the Firm. If no tax is withheld, the amount payable is {ccy} {money(total)}.</div>"""

    rows = "".join(
        f'<tr><td class="c">{i}</td><td><b>{e(l["title"])}</b>'
        + ("<ul>" + "".join(f"<li>{e(x)}</li>" for x in l.get("detail", [])) + "</ul>" if l.get("detail") else "")
        + f'</td><td class="c">{l["qty"]:g}</td><td class="c">{e(l.get("unit","Service"))}</td>'
          f'<td class="r">{money(l["unit_price"])}</td><td class="r">{money(l["qty"]*l["unit_price"])}</td></tr>'
        for i, l in enumerate(lines, 1))
    notes = "".join(f"<li>{e(n)}</li>" for n in inv["notes"])
    buyer = inv["buyer"]
    buyer_ids = "".join(f"{e(k)}: {e(v)}<br>" for k, v in buyer.get("ids", {}).items())

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}
body{{font-size:8.5pt;line-height:1.32}}
.title{{display:flex;justify-content:space-between;align-items:baseline;margin:2px 0 10px}}
.title h1{{font-size:14pt;letter-spacing:2px;margin:0}} .title .tr{{font-size:9pt;color:#555;letter-spacing:1px}}
.cols{{display:flex;gap:16px;margin-bottom:8px}} .cols>div{{flex:1}}
.k{{font-size:7.4pt;text-transform:uppercase;letter-spacing:1px;color:#555;margin-bottom:2px}}
table{{width:100%;border-collapse:collapse}}
.meta td{{padding:1px 0;vertical-align:top}} .meta td:first-child{{color:#555;white-space:nowrap;padding-right:8px}} .meta td{{white-space:nowrap}}
.items th,.items td{{border-bottom:1px solid #bbb;padding:4px 5px;vertical-align:top;text-align:left}}
.items th{{border-bottom:1.5px solid #111;background:#f2f2f2;font-size:8pt}}
.items .r{{text-align:right;white-space:nowrap}} .items .c{{text-align:center;white-space:nowrap}}
.items ul{{margin:2px 0 0;padding-left:14px}} .items li{{margin:0}}
.tot{{width:46%;margin-left:54%;margin-top:4px}} .tot td{{padding:2px 5px}} .tot td.r{{text-align:right;white-space:nowrap}}
.tot tr.g td{{border-top:1.5px solid #111;border-bottom:1.5px solid #111;font-weight:bold}}
.words{{margin:6px 0 8px;font-size:8.4pt}}
.box{{border:1px solid #999;padding:5px 8px;margin:6px 0;font-size:8.1pt}}
h2{{font-size:8.8pt;margin:7px 0 2px;text-transform:uppercase;letter-spacing:1px}}
.bank td{{padding:1.5px 0;vertical-align:top}} .bank td:first-child{{color:#555;width:36%}}
.tbc{{font-style:italic;color:#666}}
ol{{margin:0;padding-left:16px}} ol li{{margin-bottom:2px;text-align:justify}}
tr{{break-inside:avoid}}
</style></head><body>
{header(firm)}
<div class="title"><h1>PRO FORMA INVOICE</h1><span class="tr">PROFORMA FATURA</span></div>
<div class="cols">
<div><div class="k">Seller / Satıcı</div><b>{e(firm["legal_name"])}</b><br>{e(firm["address_one_line"])}<br>
{e(firm["tax_office"])} Vergi Dairesi, VKN: {e(firm["tax_no"])}<br>MERSİS No: {e(firm["mersis"])}<br>{e(firm["trade_registry"])}</div>
<div><div class="k">Buyer / Alıcı</div><b>{e(buyer["name"])}</b><br>{e(buyer["address"])}<br>{buyer_ids}
{("Attention: " + e(buyer["attention"])) if buyer.get("attention") else ""}</div>
<div style="flex:1.05"><table class="meta">
<tr><td>Number / Numara</td><td><b>{e(inv["number"])}</b></td></tr>
<tr><td>Date / Tarih</td><td>{issue:%d %B %Y}</td></tr>
<tr><td>Valid until / Geçerlilik</td><td>{valid:%d %B %Y}</td></tr>
<tr><td>Due / Vade</td><td>{due:%d %B %Y}</td></tr>
<tr><td>Currency / Döviz</td><td>{e(ccy)}</td></tr>
<tr><td>Engagement / Sözleşme</td><td>{e(inv["engagement_ref"])}</td></tr>
</table></div></div>

<table class="items"><tr><th class="c" style="width:5%">No</th><th>Description / Açıklama</th><th class="c" style="width:6%">Qty</th>
<th class="c" style="width:8%">Unit</th><th class="r" style="width:13%">Unit price</th><th class="r" style="width:13%">Amount ({e(ccy)})</th></tr>
{rows}</table>
<table class="tot">
<tr><td>Subtotal / Ara toplam</td><td class="r">{money(subtotal)}</td></tr>
<tr><td>VAT (KDV) {vat_rate:.0%}: {e(inv.get("vat_note",""))}</td><td class="r">{money(vat)}</td></tr>
<tr class="g"><td>Total payable / Ödenecek toplam</td><td class="r">{e(ccy)} {money(total)}</td></tr>
</table>
<div class="words"><b>Amount in words:</b> {e(w_en)}. <span style="color:#555">({e(w_tr)})</span></div>
{wht_html}
<h2>Payment instructions / Ödeme bilgileri</h2>
<table class="bank">{"".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in bank_rows)}</table>
<h2>Notes / Açıklamalar</h2><ol>{notes}</ol>
{statutory(firm)}
</body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out")
    ap.add_argument("--draft", action="store_true", help="allow missing bank fields")
    a = ap.parse_args()
    inv = json.load(open(a.spec, encoding="utf-8"))
    firm = load_firm()
    out = a.out or os.path.dirname(os.path.abspath(a.spec))
    stem = os.path.join(out, inv["file_stem"] + ("_DRAFT" if a.draft else ""))
    open(stem + ".html", "w", encoding="utf-8").write(build(inv, firm, a.draft))
    print("pages", render_pdf(stem + ".html", stem + ".pdf", firm, inv["number"], top="13mm", bottom="15mm"), stem + ".pdf")
