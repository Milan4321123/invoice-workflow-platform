# LinkedIn post draft

Edit before posting; it's written in the first person for the author.

---

Since January 2025 every company in Germany has to be able to receive e-invoices. I wanted to understand what that really means for the people who process invoices, so I rebuilt my invoice workflow project around it.

What I learned and built:

📄 A ZUGFeRD PDF isn't "a PDF". The embedded XML is the legal invoice. My platform now reads XRechnung and ZUGFeRD directly, so amounts, VAT IDs and IBANs arrive exact instead of being typed in. (And the XML is parsed safely: external input, so no XXE.)

✅ Validation belongs before payment. A live check against §14 UStG flags missing details, wrong VAT ID check digits and duplicate invoice numbers while you edit. For construction it also knows reverse charge (§13b) and the 15 % construction withholding tax (§48 EStG).

🔒 GoBD means "never silently change a record". Every edit is logged with old and new value in a hash-chained, append-only log; approved invoices are locked; deletion respects the 8-year retention period; and tax auditors get a one-click export.

🛡️ DSGVO in code, not only in a policy: no third-party requests (I found and removed a CDN script that sent every user's IP address to a third party), emails and IBANs masked in logs, and erasure requests that explain exactly what tax law requires to keep.

♿ WCAG 2.1 AA, checked with axe-core: zero violations on the main screens, plus a German/English UI.

Everything is in small, reviewable pull requests with 230 automated tests, and there's a demo mode you can run with one command.

Repo: https://github.com/Milan4321123/invoice-workflow-platform

#EInvoicing #XRechnung #ZUGFeRD #GoBD #DSGVO #FinTech #Python #NextJS
