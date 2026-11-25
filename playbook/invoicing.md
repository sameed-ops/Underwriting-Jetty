# Invoicing from the Turkish entity (researched 25 November 2026)

This note sits behind `tools/docs/invoice.py`. Have the accountant (*mali müşavir*) confirm every rule here before the first live invoice.

## 1. Documents and their roles
| Document | Legal status | Role |
|---|---|---|
| Engagement letter | Contract, signed by Aarifah Loonat (Müdür) and the client | Holds the terms: scope, fees, gross-up, no guarantee of finance, authority to verify, KVKK, governing law |
| Pro forma invoice (*proforma fatura*) | No statutory form; not a tax invoice; creates no accounting entry | Requests payment. Unsigned. Refers to the engagement letter |
| e-Arşiv invoice | The official tax invoice (VUK art. 229 and 230) | Issued by the accountant on receipt of payment |

## 2. Contents of the pro forma
It mirrors VUK art. 230, so the official invoice that follows matches it line for line.
- **Number and dates:** number, issue date, validity date (14 days by default) and due date.
- **Seller:** full legal name, address, tax office and tax number (VKN), MERSİS number, and trade registry number.
- **Buyer:** legal name, address, company number and tax PIN, and an attention line.
- **Lines:** description, quantity, unit, unit price and amount; then subtotal, VAT and total.
- **Amount in words:** in English, and in Turkish ("Yalnız ...").
- **Payment instructions:**
  - beneficiary legal name, bank, branch, bank address, IBAN and SWIFT;
  - an intermediary bank only when the receiving bank names one;
  - a specific purpose of payment and a reference built on the invoice number;
  - charges: OUR (all charges for the remitter).
- **Statutory line (TTK art. 39):** trade name, registered office, trade registry and number, MERSİS number. The full legal name also appears in the header.

## 3. VAT on services to foreign clients
- **Exemption:** export of services, Law 3065 art. 11/1-a and 12/2.
- **Conditions:**
  - the service is performed for a customer abroad;
  - the invoice is issued in that customer's name;
  - the customer benefits from the service abroad;
  - payment is in foreign currency into a Turkish account. This was a condition under older rules; whether it still is, is unconfirmed.
- **The official invoice:** an e-Arşiv invoice (a foreign buyer is not an e-Fatura user), exemption code 302 per practice sources, and buyer VKN field 2222222222.
- **Returns and refunds:** declare the sale on the monthly VAT return. VAT paid on the company's own costs can be reclaimed against exempt export sales.
- **Evidence file:** engagement letter, the client's registration certificate, the bank credit advice for the receipt, and the delivered report.

## 4. Withholding tax in the client's country
- **Kenya:** 20% on management and professional fees paid to non-residents, and it is final tax for the recipient (KRA guidance).
  - The Kenyan National Treasury lists the Kenya and Türkiye tax treaty as "concluded, not signed", so it gives no relief.
  - The gross-up is gross = net / (1 - rate). For a net fee of USD 2,000 the gross is USD 2,500, of which USD 500 goes to KRA.
  - Always ask for the withholding certificate. It supports the firm's Turkish tax position.
- **Other countries:** check the domestic rate and treaty status before each new country (CLAUDE.md section 12.3).

## 5. Things not to do
- Do not describe the fee as being for "obtaining" or "securing" a loan.
- Do not accept payment from a third party, in cash, or into a personal account.
- Do not show an intermediary bank unless your own bank names one.
- Do not sign the pro forma. The signed engagement letter carries the authority.

## Sources
- Paraşüt, pro forma invoices: https://www.parasut.com/blog/proforma-fatura-nedir-nasil-duzenlenir
- Alomaliye, invoices under the VUK: https://www.alomaliye.com/2006/08/10/vergi-usul-kanununda-fatura
- Alomaliye, information required on commercial documents under the TTK: https://www.alomaliye.com/2013/11/23/yeni-turk-ticaret-kanununa-gore-ticari-belgelerde-1-ocak-2014-tarihinden-itibaren-yer-almasi-gereken-zorunlu-bilgiler
- Paraşüt, service export invoice and code 302: https://www.parasut.com/blog/hizmet-ihracati-faturasi
- Muhasebe News, services to foreign customers: https://www.muhasebenews.com/yurt-disindaki-musteriler-icin-yapilan-hizmetler-kdvden-istisna-edilmistir/
- Xe, payment details and intermediary banks: https://www.xe.com/blog/business/vendor-payment-intake-form-that-prevents-failed-transfers
- KRA withholding tax rates: https://www.kra.go.ke/helping-tax-payers/faqs/more-about-withholding-tax
- PwC tax summaries, Kenya withholding taxes: https://taxsummaries.pwc.com/kenya/corporate/withholding-taxes
- Kenyan National Treasury, double taxation agreements: https://treasury.go.ke/?p=166
