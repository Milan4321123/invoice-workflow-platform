# Accessibility statement (Erklärung zur Barrierefreiheit)

**Target:** WCAG 2.1 level AA, the standard behind EN 301 549 and the European Accessibility Act (in Germany: BFSG, in force since 28 June 2025).

**Scope note:** the BFSG applies mainly to products and services for consumers. An internal B2B accounts payable tool is generally outside it. The platform follows WCAG 2.1 AA anyway: employees with disabilities use it every day, and a fintech's own customer-facing products are in scope.

## How it was checked

- Automated: [axe-core](https://github.com/dequelabs/axe-core) 4.10 with the WCAG 2.0/2.1 A and AA rule sets, run in the browser against the app in demo mode (`./start-demo.sh`), on 30 Oct 2026.
- Manual spot checks: clicking a label focuses its field; tab order on the login form; the language switch updates `lang`. A full keyboard-only and 200 % zoom review is still to do.

| Page | Violations before fixes¹ | Violations after | Rules passed |
|---|---|---|---|
| Login | – | 0 | 23 |
| Dashboard | – | 0 | – |
| Invoice editor (incl. change history) | 2 (contrast, unreachable scroll area) | 0 | 32 |

¹ – = not measured before the fixes.

Automated tools catch only part of accessibility problems, so "0 violations" means "no known automated failures", not "fully accessible".

## What was fixed

| WCAG | Issue | Fix |
|---|---|---|
| 3.1.1 | Page language was `en` on a German UI | `lang` follows the selected language; legal pages always `de` |
| 1.4.4 | Pinch zoom disabled (`user-scalable=0`) | Removed |
| 2.4.1 | No way to skip the navigation | Skip link |
| 2.4.7 | Focus not always visible | Global `:focus-visible` outline |
| 2.3.3 | Constant animations | Respect `prefers-reduced-motion` |
| 1.3.1, 4.1.2 | Form fields without linked labels; icon-only links without names; dropdowns without state | Labels linked, `aria-expanded`, `aria-current`, named buttons |
| 2.1.1 | Delete buttons only visible on mouse hover; scrollable PDF not reachable | Visible on focus; focusable region |
| 1.4.3 | Low-contrast secondary text | Darker grey |
| 4.1.3 | Live check results not announced | `role="status"` live region |

## Known limitations

- The older parts of the dashboard (Bauleiter dashboard, folder watcher, Prüfbericht) were not part of this pass.
- Compliance findings come from the API in German; in the English UI they keep German text with the legal reference.
- Browser `alert()`/`confirm()` dialogs are still used in places; they are accessible but not styled or translated.

Feedback: please open an issue in the repository.
