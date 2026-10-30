# Research: why accounts payable in Germany is changing, and what this project does about it

Status: October 2026. Regulatory dates were checked against the sources at the end. Where sources disagreed or a decision was still open, that is said explicitly.

## 1. The short version

German accounts payable is being pushed from "PDF in an inbox" to "structured data with an audit trail" by four overlapping rule sets:

| Rule | What it demands | Since / from |
|---|---|---|
| **E-Rechnungspflicht** (Wachstumschancengesetz, §14 UStG) | Every business must be able to *receive* structured e-invoices (EN 16931: XRechnung, ZUGFeRD/Factur-X). Issuing becomes mandatory in two steps | Receive: 1 Jan 2025 · Issue: 1 Jan 2027 if prior-year turnover > €800k, 1 Jan 2028 for all |
| **GoBD** + §147 AO | Records complete, unaltered and traceable; data access for tax auditors | Retention for receipts cut from 10 to **8 years** by BEG IV (promulgated 29 Oct 2024) |
| **DSGVO / GDPR** | Lawful basis, minimisation, storage limits, data subject rights, processors under contract | Since 2018; enforcement keeps tightening (e.g. LG München I on Google Fonts, 2022) |
| **ViDA** (EU "VAT in the Digital Age") | EN 16931 e-invoicing and near real-time digital reporting for intra-EU B2B | Adopted 11 Mar 2025 · mandatory from 1 Jul 2030 |

Open point: the trades association ZDH has asked since June 2026 to move the €800k step from 2027 to 2028. As of the sources checked, this was a demand, not a law. Check bundestag.de before relying on either date.

**What it means for a construction company's AP team:** every incoming invoice has to be checked against §14 UStG for input VAT, against §13b UStG (reverse charge on construction services) and §48 EStG (15 % construction withholding tax), approved by the right site manager, paid on time for the early-payment discount (Skonto), and then kept unaltered for eight years in a form a tax auditor can export.

## 2. What changes for invoice processing

1. **The PDF stops being the invoice.** In a ZUGFeRD/Factur-X hybrid the embedded XML is the legal invoice; an XRechnung has no visual at all. Tools built around OCR of the page image read the wrong thing. Parsing the XML is exact, needs no training data and makes OCR a fallback for paper.
2. **Validation moves left.** With structured data, §14 UStG checks (VAT ID check digit, net + VAT = gross, mandatory fields, duplicates) can run at upload instead of during a tax audit years later.
3. **Audit trail is a feature, not a log file.** GoBD requires that the original content of every change stays determinable. That needs an append-only, tamper-evident history per invoice plus an export auditors can import (Z3 data access).
4. **Privacy is part of the product.** The same system holds approvers' e-mails, IP addresses from approval links and sole traders' IBANs. DSGVO erasure has to be reconciled with GoBD retention (Art. 17(3)(b)) in software, not in a policy PDF.
5. **Cross-border comes next.** ViDA makes EN 16931 the EU-wide format for intra-community invoices from 2030, so building on EN 16931 now is not Germany-specific work.

## 3. Market landscape

Qualitative overview of tools German SMEs commonly use for incoming invoices. No market-share figures are given because none could be verified from primary sources.

| Product | Focus | Notes |
|---|---|---|
| **DATEV Unternehmen online** | Document exchange between companies and their tax advisor | The default destination for bookkeeping data in Germany; most AP tools integrate with it |
| **Candis** | AP automation: capture, approval workflows, payments | Official DATEV interface partner (DATEV Unternehmen online, Rechnungswesen) |
| **Lexware Office** (formerly lexoffice) | All-in-one bookkeeping for small businesses | Renamed in 2024; same product, Haufe-Lexware |
| **sevDesk** | Bookkeeping and invoicing for freelancers and small businesses | Broad SME tool rather than AP-specific |
| ERP AP modules (SAP, Microsoft Dynamics, …) | Large companies | Heavy, usually with dedicated e-invoicing add-ons |

**Gap this project explores:** generic tools optimise for the average SME. Construction is different. It has trade-specific approval (site manager signs off work done), reverse charge on construction services between builders (§13b), withholding tax without an exemption certificate (§48b), and KfW-funded costs that must be tracked separately. Those rules are the core of this platform, not settings in a generic tool.

## 4. How this repository maps to the research

| Need | Implementation | Where |
|---|---|---|
| Receive e-invoices | XRechnung (UBL, CII) and ZUGFeRD/Factur-X parsing by EN 16931 business term, XXE-safe | `backend/services/e_invoice.py` |
| Input VAT safety | §14 UStG, §33 UStDV, §13b UStG, §48 EStG checks with legal references; duplicate invoice numbers | `backend/services/invoice_compliance.py` |
| GoBD | Append-only hash-chained change log, retention-aware deletion, lock after approval, Z3 export | `backend/services/audit.py`, `gobd.py`, `api/routes/gobd.py` |
| DSGVO | Log redaction, IP retention, subject access/erasure with retention report, no third-party requests in the browser, Art. 13/30 docs | `backend/services/privacy_service.py`, `log_redaction.py`, `docs/compliance/dsgvo.md` |
| Accessibility | WCAG 2.1 AA fixes, axe-core audit with zero violations on the main pages | `docs/compliance/accessibility.md` |
| Security | Authentication on every data route, enforced by a test over all routes | `backend/tests/test_route_protection.py` |

## 5. What I would build next

1. **Booking export to DATEV** (EXTF/ASCII format or DATEV Rechnungsdatenservice): the step after approval that every German AP tool needs.
2. **Validation against the official KoSIT validator** for XRechnung, in addition to the business-rule checks here.
3. **Roles** (AP clerk, approver, privacy officer) instead of "every logged-in user can do everything".
4. **Transactional audit logging** via database trigger, so a change and its log entry commit together.
5. **VIES lookup** for foreign VAT IDs (currently format check only).

## Sources

- E-invoicing timeline and transition rules: [IHK Potsdam](https://www.ihk.de/potsdam/ihk-service-und-beratung/e-rechnungen-ab-2025-6223258), [PwC newsletter on the BMF letter](https://newsletter.pwc.de/umsatzsteuer/nl0029-2024-10-29/bmf-e-rechnung), [Gründerplattform guide](https://gruenderplattform.de/assets/indexable/documents/Leitfaden_E-Rechnungen.pdf)
- Postponement request for the 2027 step: [ZDH position](https://www.zdh.de/themen-und-positionen/zdh-positionen/zdh-kompakt/verschiebung-der-e-rechnungspflicht-auf-den-1-januar-2028/), [Bundestag lobby register entry](https://www.lobbyregister.bundestag.de/inhalte-der-interessenvertretung/regelungsvorhabensuche/RV0026674)
- 8-year retention (BEG IV): [Haufe](https://www.haufe.de/steuern/gesetzgebung-politik/viertes-buerokratieentlastungsgesetz_168_613390.html), [IHK Karlsruhe](https://www.ihk.de/karlsruhe/fachthemen/steuerrecht/aktuelles/neuer-inhalt4-buerokratieentlastungsgesetz-6347138), [iww](https://www.iww.de/pfb/steuern-und-recht-aktuell/abgabenordnung-verkuerzung-der-aufbewahrungsfrist-fuer-buchungsbelege-n163275)
- ViDA: [Deloitte](https://www.deloitte.com/be/en/services/tax/blogs/final-go-for-the-vida-package.html), [Norton Rose Fulbright](https://nortonrosefulbright.com/de-de/wissen/publications/7f7569e5/vat-in-the-digital-age-vida-package-finally-adopted), [European Commission](https://ec.europa.eu/newsroom/digital/items/877702)
- ZUGFeRD versions: [FeRD: ZUGFeRD 2.4](https://www.ferd-net.de/en/downloads/publications/details/zugferd-24-english), [FeRD: Factur-X 1.09 / ZUGFeRD 2.5 release](https://www.ferd-net.de/fileadmin/user_upload/FeRD/f%C3%BCr_FeRD-Meldungen/20260610_Factur-X_1_09_ZUGFeRD_2_5_Press_Release_EN.pdf)
- Market: [Lexware: lexoffice is now Lexware Office](https://www.lexware.de/lexoffice-index/), [Candis DATEV interface](https://www.candis.io/en/product-partner/datev)
- Google Fonts ruling: LG München I, judgment of 20 Jan 2022, 3 O 17493/20
