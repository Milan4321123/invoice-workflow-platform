# Invoice Workflow Platform: one-pager

**Accounts payable for German construction companies that is compliant by design: e-invoices in, audit-proof records out.**

## The problem

Since January 2025 every German business must be able to receive e-invoices; from 2027/2028 they must issue them too. At the same time an AP team in construction checks every invoice against rules generic tools barely know: reverse charge on construction services (§13b UStG), 15 % construction withholding tax without an exemption certificate (§48 EStG), approvals by the site manager who saw the work, and eight years of unalterable retention under the GoBD. Mistakes surface years later, in a tax audit, as lost input VAT.

## What the platform does

| | |
|---|---|
| **Reads e-invoices** | XRechnung (UBL and CII) and ZUGFeRD/Factur-X are parsed from the XML, the legally binding part. Amounts, VAT IDs, IBAN and Skonto terms arrive exact, without retyping. |
| **Checks before paying** | Live §14 UStG check while editing: mandatory details, VAT ID check digit, net + VAT = gross, §13b, §48 EStG, duplicate invoice numbers. Every finding cites its paragraph. |
| **Approves securely** | Site managers approve via signed, single-use links. Early-payment discount reminders go to accounting before the deadline. |
| **Keeps records audit-proof** | Every change is logged with old and new value in a hash-chained, append-only log. Approved invoices are locked; deletion is refused during retention. One click exports the year for the tax auditor. |
| **Respects privacy** | No trackers or third-party requests; e-mail addresses and IBANs masked in logs; IP addresses removed after 30 days; access and erasure requests handled in the app, with a clear report of what retention law requires to keep. |
| **Works for everyone** | German and English UI; WCAG 2.1 AA with zero automated violations on the main screens. |

## Why now

- E-invoice receiving obligation since 1 Jan 2025; issuing obligation from 2027 (turnover > €800k) and 2028 (everyone).
- Retention for receipts cut to 8 years (BEG IV), so retention logic in old systems is wrong.
- EU ViDA makes EN 16931 e-invoicing mandatory for intra-EU B2B from July 2030.

## Try it

```bash
./start-demo.sh
```

Open http://localhost:3000 and log in as `demo` / `Demo-2026!`. Six fictional invoices show each feature; nothing is saved and no e-mail leaves the machine.

## Under the hood

FastAPI · Next.js 15 · Supabase (Postgres, EU) · 230 automated tests · CI on every pull request · every route authenticated and verified by a test.
