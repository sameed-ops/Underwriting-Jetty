# Advanced red flags and lender practice (beyond CLAUDE.md)

These patterns extend section 6 of CLAUDE.md. They come from general credit and document-forensics practice, not from Chapra & Co. live files. Promote a pattern into section 6 only once it appears in a live file.

## A. Document forensics

1. **Incremental saves.** A bank export is normally written once, with one `%%EOF`. Two markers can be a bank signature or linearisation. Three or more, or two with a desktop producer, means the file was opened and saved again. `pdf_forensics.py` counts them.
2. **Info and XMP mismatch.** When an editor rewrites one metadata store but not the other, Producer or ModDate disagree between them. XMP `xmpMM:History` entries name the editing application outright.
3. **Font outliers.** An amount set in a font or size that appears nowhere else on the page is the typical cover-and-retype edit. Confirm it by cropping the region with `pdftoppm -r 300 -x -y -W -H` and putting the crop in the exhibit.
4. **White boxes under figures.** A filled white rectangle with digits drawn on top of it is the same edit done in a PDF editor.
5. **Scanned statements.** Statements are digital-native almost everywhere now. An image-only "statement" removes the ability to test the text layer, so treat it as a request for a bank-direct copy.
6. **Kerning and alignment.** Edited digits often break the column's decimal alignment by a fraction of a point. Compare the x-coordinates of the right edge of every amount in a column: genuine exports align to within 0.1pt.
7. **Arithmetic in totals rows.** Fabricators edit the rows and forget the page subtotals, or edit the summary and forget the rows. The statement engine tests rows, offsets and summary independently for this reason.
8. **Sequence gaps.** Cheque numbers, M-Pesa receipt codes and transaction IDs that run out of order, repeat, or skip in blocks suggest inserted or deleted rows.
9. **Calendar sanity.** Check for postings on bank holidays where the bank does not post, value dates before transaction dates, and an account-opening date later than the earliest transaction.
10. **Template audits.** Look for identical wording across unrelated clients, an audit opinion dated before the year end, an unsigned or unnamed engagement partner, or a firm missing from the professional body register. A trial balance that balances to the shilling with no rounding note is another sign.

## B. What the money says

1. **Round-tripping.** Money leaves to a related party and returns as "sales" within days, inflating turnover. Match outflows to inflows of similar size within 1 to 10 days and with similar names.
2. **Window-dressing.** Large credits in the last weeks before the statement date, reversed soon after, or a sudden lift in the average balance in the month before application.
3. **Cheque kiting.** Two of the borrower's own accounts pay each other repeatedly, creating float. This shows as matched in-and-out pairs across accounts on adjacent days.
4. **Salary and tax absence.** A business with claimed staff but no PAYE, NSSF, SHIF (Kenya) or equivalent payments either runs payroll in cash or overstates its scale.
5. **Undisclosed lenders by fingerprint.** Look for regular equal debits on the same day each month, debits to known lender paybills or names, and "standing order" narratives. An unexplained credit followed by equal debits is a loan.
6. **Digital-lender stacking.** Several Fuliza, M-Shwari, Tala or Branch draws in one month indicates liquidity stress, even when each is small.
7. **Supplier prepayment claims.** "Paid supplier upfront" with no outflow to that supplier on any statement. Ask for the supplier's acknowledgement on its letterhead.
8. **Sanctions and geography.** Payments to or through high-risk jurisdictions, or a counterparty name matching a listed entity, stop the file until screening clears.

## C. Structural and legal

1. **Security that cannot be perfected.** This includes stock pledged to one lender already, unregistered land, family land without spousal consent where the law requires it, and receivables from a buyer whose contracts forbid assignment.
2. **FX mismatch.** A USD facility repaid from local-currency revenue takes the devaluation risk onto the borrower. Stress the cover at a 20% to 30% depreciation for the frontier currencies.
3. **Related-party guarantees.** A guarantor whose only assets are shares in the borrower adds nothing.
4. **Beneficial ownership through nominees.** When the CR12 shows a nominee or a holding company, trace it to natural persons with 25% or more, and screen each one.
5. **Change of control near application.** Directors or shareholders changed in the last six months, a new company formed to receive a facility, or a name change. Ask why.

## D. Sector cycles for sizing (starting points, to be evidenced per file)

| Sector | Cycle and typical days | Short-line sizing guide |
|---|---|---|
| Grain trading (maize, wheat) | Harvest buying Aug to Dec (Kenya long rains) and Feb to Mar; stock 60 to 120 days | One peak monthly cycle, against certified warehouse receipts at a 50% advance |
| Coffee and tea | Auction or export cycle; receivables 30 to 60 days | Pre-export finance against contracts, repaid from export proceeds paid to the lender |
| FMCG distribution | Stock 20 to 45 days, receivables 15 to 45 days | 25% to 30% of turnover, against a borrowing base |
| Construction contractors | Certificates 60 to 120 days, retention 5% to 10% | Against certified IPCs from creditworthy employers only |
| Agri cooperatives (Brazil) | Safra cycle; CPR instruments | Against CPR registered with an authorised registrar and off-take |
| SaaS and venture | No inventory; recurring revenue | Revenue-based lines at 3 to 6 times MRR, with runway as the test |

## E. Questions that separate real businesses from staged ones

1. Name your five largest customers, what they buy and how often. Then check that the names appear in the inflows.
2. Which account do you use for wages, rent and tax? It must appear among the statements supplied.
3. Show the last three supplier invoices and the payment for each.
4. Who else has lent to you in the last 24 months, and what is outstanding today?
5. Why this amount, and why now?
