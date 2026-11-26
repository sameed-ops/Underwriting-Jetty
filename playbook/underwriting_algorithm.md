# The underwriting algorithm: from scan to verdict

This document describes how the Desk turns a pack of borrower documents into a credit verdict. It describes the method only. It contains no client names, figures or document contents.

The pipeline has eight stages. Stages 1 to 5 run once per document. Stages 6 to 8 run once per deal, and run again whenever new evidence arrives.

```
 1 Intake  ->  2 Provenance  ->  3 Extraction  ->  4 Internal consistency
                                                          |
 8 Outputs <-  7 Scoring     <-  6 Cross-checks <-  5 Cash-flow analysis
```

## Principles that govern every stage

1. **Every document is assumed wrong until the evidence agrees with it.**
2. **Order of authority when sources conflict:** bank-issued records, then registry and tax records, then audited accounts (only if verified), then management accounts, then the borrower's own statements.
3. **Tools find candidates; a person confirms.** Every critical finding is confirmed by eye on a page crop before it is reported.
4. **Size to cash flow, not to the request.**
5. **No figure is stated unless it was computed or sourced.** Every assumption, such as an interest rate or a margin, is disclosed next to the result that uses it.

## Stage 1: Intake

- Each deal gets a short code and a private working folder that is excluded from version control. Borrower files, account numbers, ID numbers and passwords never enter the repository.
- A password, if one is given, is passed through an environment variable for the one command that needs it. It is never written down.
- The file name is checked for words such as "unprotected", "unlock" or "edited". These show the file was handled after issue. That is acceptable for review, but a lender will want a copy direct from the issuer.
- Each document is classified by what a lender uses it to prove: identity, ownership, tax standing, trading activity, financial position, or the request itself.

## Stage 2: Provenance (`tools/pdf_forensics.py`)

The question at this stage: was this file produced by the system that claims to have issued it, and has it been touched since?

| Check | Method | Severity when it fails |
|---|---|---|
| Producer and creator | Read the PDF information dictionary and XMP metadata. Classify the software as an issuing system (report engines, core-banking exports, registry portals) or a desktop tool (office suites, online PDF editors, print-to-PDF drivers, phone scanners) | Major on a financial document. Never critical on its own, because a genuine file re-saved on a personal computer reads the same way |
| Title field | A title ending in a spreadsheet or document file extension means the PDF was printed from an office file | Major |
| Date gap | Modification more than one day after creation, or a modification date earlier than the creation date | Major |
| Edit history | XMP history entries that name an editing application | Major |
| Incremental saves | Count the end-of-file markers. An issuing system writes the file once | Minor at two; major at three or more, or at two with a desktop producer |
| Metadata disagreement | The information dictionary and the XMP metadata name different software or dates | Major |
| Font outliers | On each page, find numeric text set in a font that covers under 2% of the page's characters. This is the trace of an amount typed over the original | Major, then confirmed by eye |
| Cover boxes | Find white filled rectangles with digits drawn on top of them | Major, then confirmed by eye |
| Text layer | No extractable text on the first pages means a scan or a photograph | Minor; figures need extra care |
| Signatures, scripts, attachments | A valid issuer signature strongly supports authenticity; embedded scripts are unusual on a statement | Information |

The output is a provenance verdict per file: no concern, accepted with findings, or critical.

## Stage 3: Extraction

- **Text documents:** the text is extracted with the page layout preserved.
- **Image-only documents:** pages are rendered to images and read by eye. For identity documents, the printed fields are compared with the machine-readable zone on the same card.
- **Bank statements** are converted to a ledger: one row per transaction, with date, narrative, amount and running balance. Three parsers exist, tried in this order:
  1. **Generic:** a row starts with a date and ends with the running balance. The amount is derived from the change in balance, which is more reliable than reading the debit and credit columns.
  2. **Mobile money:** rows start with a receipt code and a timestamp, and carry a status. Failed transactions are dropped.
  3. **Coordinate-based:** when the text layout drifts between pages, or balances print only once per day, the parser reads each word's position on the page and assigns amounts to the debit, credit or balance column by x-coordinate.
- If the first date is later than the last, the rows are reversed before any calculation, or every sign inverts.
- A new statement format gets a new parser, and the format is added to the playbook.

## Stage 4: Internal consistency (`tools/statement_recon.py`)

The question at this stage: does the document agree with itself?

**For a bank statement, three tests run independently:**

1. **Row test.** For every row, the printed amount is compared with the change in running balance. Mismatched rows are listed.
2. **Offset test.** The series (running balance minus opening balance minus cumulative amounts) is computed for every row.
   - If it is zero throughout, the ledger is clean.
   - If it is a constant other than zero, every balance was shifted by the same amount after issue: **critical**.
   - If it steps from one value to another, rows near each step were edited or removed: **critical** for a few steps, major for many.
3. **Summary test.** Opening balance plus total credits less total debits must equal the printed closing balance, and the last running balance must equal the same figure. If the summary adds up but the ledger does not, the ledger was altered after issue: **critical**.

A tolerance of about one cent per row absorbs display rounding. A drift of a few cents over thousands of rows is rounding, not tampering.

**For a set of accounts, the tests are arithmetic and structural:**

- Total assets must equal equity plus liabilities.
- Profit in the directors' report must equal profit in the income statement.
- Retained earnings must roll forward: opening balance plus profit less distributions equals closing balance.
- The tax charge must have a matching liability or payment.
- Depreciation must agree with the fixed-asset note.
- Each expense line is divided by its prior-year figure. Several lines sharing an identical ratio means the figures were generated, not recorded.
- The audit report date must not precede the board's approval date.
- Margins are compared with what is plausible for the sector.

## Stage 5: Cash-flow analysis ("what the money says")

Every ledger row is classified by its narrative, using keyword families:

| Class | Purpose |
|---|---|
| Trading inflows (merchant settlements, mobile-money deposits, customer transfers) | The basis for turnover |
| Loan disbursements, reversals, refunds | Excluded from turnover |
| Loan repayments, digital-lender traffic, liens | Reveal borrowings, declared or not |
| Charges and duties | Excluded from operating outflows |
| Cash deposits and withdrawals | Inflows that are harder to verify; possible owner drawings |
| Returned or unpaid items | A conduct flag |
| Transfers to named persons or other banks | Related parties and accounts not supplied |

The following are then computed:

- **Monthly inflows and outflows**, and operating inflows net of loans and reversals.
- **Annualised turnover**, only when six or more months are present. Accounts are added together after transfers between them are removed.
- **Self-funding adjustment:** deposits from the account holder's own wallet or number are separated, because money moved in a circle is not revenue.
- **Trend:** the average of the last three months against the peak month. Under 20% of the peak is a major flag.
- **Days overdrawn:** the balance is carried forward day by day. Overdrawn more than 40% of days is a major flag.
- **Concentration:** payer names are normalised (references and long numbers stripped) and ranked. The top two above 60% of inflows is a major flag.
- **Loan schedule:** disbursements and repayments are grouped by loan reference to rebuild each facility: amount, start date, instalment, and whether repayments continue.
- **Pattern flags:** repeated transaction references (copied rows), many identical round transfers to one payee on one day, over half of credits in round thousands, cross-border phone prefixes, statutory payments (tax, social security) that are absent when staff are claimed.

## Stage 6: Cross-document checks

Each new document is tested against everything already on file.

| Test | Rule |
|---|---|
| Declared revenue against bank inflows **for the same period** | Above 1.5 times is major; above 2 times is critical |
| Directors and shareholders | Names on the registry extract, identity documents, tax certificates and accounts must agree |
| Share capital | The accounts must agree with the registry |
| Borrowings | Loans visible on statements must appear in the accounts and the declared schedule |
| Accounts supplied | Transfers to an account in the borrower's name that was not supplied mean the bank evidence is incomplete |
| Tax registrations | Declared turnover and payroll must be matched by the corresponding tax obligations |
| Projection against history | Projected revenue is compared with the bank run rate; projected pricing with the assumed market rate |
| Dates | Incorporation, account opening, first transactions and audit dates must be in a possible order |
| External facts | Auditors, lenders and registries are verified from public sources, with the source and its date recorded |

Each item on the nine-line document tracker is then marked Accepted, Accepted with findings, Rejected or Outstanding.

## Stage 7: Scoring (`tools/credit_model.py`)

### Inputs

The request (amount, instrument, tenor, currency), declared revenue, annualised bank inflows, bank inflows for the declared period, EBITDA, existing debt and its service cost, years trading, collateral by type, the share of the documentary standard supplied, and four evidence-based assessments from 0 to 100.

Where no reliable profit figure exists, EBITDA is an assumed sector margin applied to bank inflows, and the assumption is stated.

### Calculated tests

| Test | Rule |
|---|---|
| Revenue basis | The lower of declared revenue and bank inflows. Lenders believe the bank |
| Instrument | Working capital, trade, warehouse, receivables, purchase-order and revenue-based lines are short and tested on interest cover (minimum 1.5 times). Term loans are tested on debt service cover (minimum 1.25 times). Existing debt service is included in both |
| Scale | Short lines above 35% of turnover are major, above 75% critical. Term debt above 50% of revenue is major, above 100% critical |
| Leverage | (Existing debt plus new facility) divided by EBITDA. Above 4 times is major, above 6 times critical |
| Startups without profit | Runway after debt service: under 12 months is major, under 6 months critical. Debt is sized at 25% to 35% of equity raised |
| Collateral | Values are cut by type (property 60%, receivables 75%, stock 50%, equipment 40%, cash 95% retained). Cover below 50% of the facility is flagged |
| Interest rate | An assumed all-in rate per currency, stated in every output |

### Pillars

| Pillar | Weight | How it is scored |
|---|---|---|
| Document integrity | 15% | Assessed from stages 2, 4 and 6 |
| Identity and ownership | 10% | Assessed from registry, identity and tax documents |
| Track record | 10% | Half calculated from years trading (0 at none, 100 at five years), half assessed |
| Scale against request | 15% | 100 inside the limit, falling in a straight line to 0 at the critical threshold |
| Repayment capacity | 20% | A straight line: interest cover from 1.0 to 2.5 times, or debt service cover from 0.9 to 1.75 times, maps to 0 to 100 |
| Leverage | 10% | A straight line from 6 times (0) to 2 times (100) |
| Account conduct | 10% | Assessed from stage 5 |
| Security and structure | 10% | Assessed from the security offered |

An assessed pillar with no evidence scores 40 at most.

### Caps and bands

The weighted sum is the raw Index. Limiting conditions then cap it:

- a critical integrity finding: 34;
- arrears on existing debt: 34;
- under 40% of the documentary standard supplied: 34;
- repayment capacity not demonstrated: 50.

| Index | Band |
|---|---|
| 75 to 100 | Lender-ready |
| 55 to 74 | Fundable with remedies |
| 35 to 54 | Restructuring required |
| 0 to 34 | Not yet fundable |

### Indicative facility

The supportable amount is the smallest of these constraints, and never more than the request:

- **Scale:** 30% of the revenue basis for a short line, 50% for a term loan.
- **Cover:** the largest facility whose service the EBITDA covers at the minimum ratio, after existing debt service.
- **Leverage:** four times EBITDA less existing debt.
- **One peak monthly cycle:** for seasonal short lines only.

## Stage 8: Outputs

| Output | Audience | Content |
|---|---|---|
| Single-document review | Internal | Authenticity verdict, what the document proves, what it reveals, what to ask for next, the updated tracker |
| Financeability analysis | Internal | The request, the document table, the test table, the verdict at the requested size, the realistic structure, the class of lender that fits, and the conditions for reconsideration with integrity first |
| Credit screen (PDF) | Internal file, never sent to lenders | The same analysis in the firm's fixed eight-section format |
| Letters to the borrower | External | Inconsistencies are described precisely and never as accusations; issuer-direct copies are requested |

Two rules bind every external step:

1. A document believed to be inaccurate or altered is never passed to a lender.
2. Where the business is real but the request is not supportable, the reply declines the request and offers a smaller, controlled structure.

## The learning loop

After each deal:

- every new pattern is written into the red-flag library with its treatment;
- every new statement format gets a parser and a playbook entry;
- every tool miss is fixed in the tool and covered by a test;
- the deal log is updated with the facts and the status.

The synthetic self-test (`tests/selftest.py`) runs on invented data. It confirms that a clean statement passes, that a constant balance shift and a mid-statement shift are both caught, and that a weak case lands in the lowest band.

## Known limits

- Provenance checks detect careless edits. A careful forgery made at source will pass them; only confirmation from the issuer settles it.
- Narrative classification relies on keywords. Unfamiliar banks and languages need new keyword families.
- A bank statement proves flows through that account only. Turnover is understated when accounts are missing, and overstated when money circulates between the borrower's own accounts.
- An assumed EBITDA margin is a placeholder for management accounts that reconcile to the bank.
- The model scores evidence. It does not replace the judgement of a credit committee.
