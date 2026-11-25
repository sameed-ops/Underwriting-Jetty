# Assumed rates: market check of 25 November 2026

**Status: proposal for Sameed's approval.** The model (`tools/credit_model.py`) and CLAUDE.md section 5.8 still carry the original assumptions. Neither changes until Sameed confirms.

**Sourcing caveat:** these figures come from web search results that quote central bank releases and the financial press. The central bank pages were not opened directly, because the session's network allowlist blocked direct fetches. Each figure shall be re-checked at source before it appears in any external document.

| Ccy | Policy rate (decision date) | Observed lending rate | Current assumption | Proposed | Direction |
|---|---|---|---|---|---|
| USD | Fed funds 3.75 to 4.00% (28 Oct 2026) | Prime about 7% (derived) | 10% | 8% | Down |
| EUR | ECB deposit 2.50% (29 Oct 2026) | NFC cost of borrowing 3.77% (Aug 2026) | 8% | 6% | Down |
| GBP | Bank Rate 4.00% (5 Nov 2026) | New SME loans 6.18% (May 2026) | 9% | 8% | Down |
| AED | CBUAE base 3.90% (28 Oct 2026) | unverified | 9% | 8% | Down |
| SAR | SAMA repo 4.50% (17 Sep 2026) | unverified | 9% | 8% | Down |
| TRY | One-week repo 36% (22 Oct 2026) | TL commercial about 50.5% (month unconfirmed) | 48% | 50% | Up |
| KES | CBR 8.75% (7 Oct 2026) | Average 14.4% (Sep 2026) | 16% | 16% | Hold |
| NGN | MPR 23.0% (24 Nov 2026) | Maximum average 32.62% (Sep 2026) | 30% | 33% | Up |
| GHS | MPR 11.0% (18 Nov 2026) | Average 15.8% (Oct 2026) | 30% | 18% | Down sharply |
| ZAR | Repo 7.25% (19 Nov 2026) | Prime 10.75% | 13% | 14% | Up |
| EGP | Overnight lending 21.0% (29 Oct 2026) | unverified | 30% | 24% | Down |
| PKR | Policy 12.0% (26 Oct 2026) | 11.02% (Feb 2026, stale) | 18% | 16% | Down |
| INR | Repo 5.50% (7 Oct 2026) | WALR fresh loans 8.51% (Sep 2026) | 12% | 11% | Down |
| UGX | CBR 12.0% (9 Nov 2026) | 16.93% (Jun 2026, before hike) | 20% | 20% | Hold |
| TZS | CBR 6.25% (Q4 2026, date unverified) | About 15% (Feb 2026) | 18% | 17% | Down |
| BRL | Selic 13.75% (4 Nov 2026) | unverified; check BCB SGS series 20715 | 18% | 25% | Up sharply |

**Method:** the proposed rate is the policy rate plus a typical SME spread, or the observed lending rate plus 2 to 3 points of stress, rounded to the nearest whole percent.

**Material for live files:**
- **Ghana:** the 30% assumption now overstates the cost and understates capacity.
- **Brazil (COTRISEL):** at 18%, the assumption is probably light. Cooperative refinancing in BRL with Selic at 13.75% is unlikely to price below the low twenties all-in. Capacity tests on COTRISEL shall be rerun at the approved rate.

**Upcoming decisions that can move these:** RBI on 2 to 4 Dec, Fed on 8 to 9 Dec, CBRT on 10 Dec and BoE on 17 Dec.
