# Underwriting Desk: Chapra & Co. and Jetty Credit

This is the working toolkit behind the credit screens. The operating brief is `CLAUDE.md`. Everything in `playbook/` extends it and is subordinate to it.

## Intake runbook (one document at a time)

1. Save the file to `deals/<CODE>/`, which is git-ignored. If it is password-protected, pass the password through an environment variable (`--password-env`). It is never written down.
2. Check provenance: `python3 -I tools/pdf_forensics.py deals/<CODE>/file.pdf`
3. Extract the text: `pdftotext -layout deals/<CODE>/file.pdf deals/<CODE>/file.txt`
4. Rebuild the ledger: `python3 -I tools/statement_recon.py deals/<CODE>/file.txt --opening X --closing Y --printed-credits C --printed-debits D`
   Add `--format mpesa` for Safaricom statements, or supply a CSV with the columns `date,narrative,debit,credit,balance`.
5. Score the file: fill in `deal.json` (run `python3 -I tools/credit_model.py` with no arguments to see the template), then run `python3 -I tools/credit_model.py deals/<CODE>/deal.json`.
6. Report in the format of CLAUDE.md section 9.1, and update the tracker.

The tools find candidates. The verdict remains a judgement on the evidence, and every critical finding is confirmed by eye on a page crop before it is reported.

## Contents

| Path | Purpose |
|---|---|
| `tools/pdf_forensics.py` | Metadata, producer class, date gaps, incremental saves, XMP history, font outliers, white-box overlays |
| `tools/statement_recon.py` | Ledger rebuilt from running balances, constant and step offsets, summary reconciliation, monthly flows, conduct flags, hidden loans, concentration. Generic, M-Pesa and CSV formats |
| `tools/credit_model.py` | Eight-pillar Index, caps, bands, calculated tests and indicative facility (CLAUDE.md section 5) |
| `tools/docs/` | Turkish entity letterhead, statutory footer and bilingual pro forma invoice generator (`invoice.py deals/<CODE>/invoice.json`) |
| `playbook/underwriting_algorithm.md` | The full pipeline from scan to verdict, with no client information |
| `playbook/invoicing.md` | Invoicing rules: pro forma vs e-Arşiv, VAT exemption for service exports, Kenyan withholding gross-up, wire details |
| `tests/selftest.py` | Synthetic, Illustrative tests: clean statement, +600 constant shift, mid-statement step, and a case like Blossom |
| `playbook/rates.md` | Market check of the assumed rates (25 Nov 2026), proposed for approval |
| `playbook/advanced_red_flags.md` | Forensic, cash-flow and structural patterns beyond section 6, plus sector cycles |
| `playbook/jurisdictions.md` | File conventions for Nigeria, Türkiye, Brazil, Pakistan, the UAE, Saudi Arabia, Ghana, Uganda and Tanzania |

Setup: `pip install -r requirements.txt`. This also needs poppler-utils, and Playwright for PDF output.
