# Datenschutz (DSGVO): Verarbeitungsverzeichnis, TOM und Löschkonzept

Vorlage für das Unternehmen, das die Plattform betreibt. Was die Software umsetzt, ist beschrieben; was das Unternehmen selbst festlegen muss, ist als **[zu ergänzen]** markiert.

Stand: Oktober 2026.

## 1. Verzeichnis von Verarbeitungstätigkeiten (Art. 30 Abs. 1 DSGVO)

| | Eingangsrechnungsbearbeitung |
|---|---|
| Verantwortlicher | **[Firma, Anschrift, Vertretung]**; Datenschutzkontakt **[Name/E-Mail]** |
| Zwecke | Erfassung, Prüfung, Freigabe, Zahlung und Aufbewahrung von Eingangsrechnungen |
| Betroffene | Beschäftigte der Rechnungsprüfung und Buchhaltung, Bauleitungen (Freigabe), Lieferanten (insbesondere Einzelunternehmer) |
| Datenkategorien | Name, geschäftliche E-Mail-Adresse, Benutzername, Passwort-Hash; Lieferantenname, Anschrift, Steuernummer/USt-IdNr., IBAN; Rechnungsbeträge; Zeitpunkte von Bearbeitung und Freigabe; IP-Adresse beim Aufruf eines Freigabe-Links |
| Rechtsgrundlagen | Art. 6 Abs. 1 lit. b (Vertrag), lit. c (§§ 146, 147 AO, § 257 HGB), lit. f (Sicherheit des Freigabeverfahrens) |
| Empfänger | Interne Fachabteilungen; Auftragsverarbeiter (Abschnitt 3); Finanzverwaltung bei Außenprüfung (§ 147 Abs. 6 AO) |
| Drittlandübermittlung | Nur über den E-Mail-Versanddienst, falls dieser außerhalb der EU sitzt (Abschnitt 3) |
| Löschfristen | Abschnitt 4 |
| TOM | Abschnitt 2 |

## 2. Technische und organisatorische Maßnahmen (Art. 32 DSGVO)

### In der Software umgesetzt

| Ziel | Maßnahme | Wo |
|---|---|---|
| Zugriffskontrolle | Jede API-Route mit Rechnungsdaten erfordert eine Anmeldung; ein Test prüft alle Routen gegen eine Liste bewusst öffentlicher Routen | `backend/main.py`, `tests/test_route_protection.py` |
| Zugriffskontrolle | Datenbank nur über die API erreichbar (Row Level Security ohne Policies, kein Datenbankschlüssel im Browser) | `COMPLETE_SUPABASE_SETUP.sql` |
| Freigabe-Links | Signiert, befristet, einmal verwendbar; Verwendung mit IP-Adresse protokolliert | `services/email_service.py` |
| Integrität | Änderungsprotokoll nur fortschreibbar, Hash-Kette mit Prüfroute | `services/audit.py`, Migration 006 |
| Datenminimierung | Keine Rechnungsdatensätze in Logs; E-Mail-Adressen und IBANs werden in allen Logzeilen maskiert | `services/log_redaction.py` |
| Speicherbegrenzung | IP-Adressen werden nach 30 Tagen automatisch entfernt | `services/privacy_service.py` |
| Keine Drittanbieter im Browser | Schrift (next/font) und PDF.js-Worker werden selbst ausgeliefert; keine Analyse- oder Tracking-Dienste | `frontend/src/app/layout.tsx`, `PDFViewerClean.tsx` |
| Sichere XML-Verarbeitung | E-Rechnungen werden mit `defusedxml` geparst (Schutz vor XXE) | `services/e_invoice.py` |
| Transport | HSTS in Produktion, Sicherheits-Header auf allen Antworten | `backend/main.py` |
| Passwörter | bcrypt-Hash, Mindestlänge und Blockliste für das Admin-Passwort beim Start | `services/auth_service.py`, `main.py` |

### Vom Unternehmen festzulegen

- Berechtigungskonzept (wer erhält ein Konto) und Prozess zum Entzug bei Austritt **[zu ergänzen]**
- Datensicherung und Wiederherstellungstests **[zu ergänzen]**
- Verpflichtung der Beschäftigten auf Vertraulichkeit **[zu ergänzen]**

### Bekannte Punkte für die nächste Ausbaustufe

- Das Sitzungstoken gilt 30 Tage und liegt im `localStorage`. Kürzere Laufzeit mit Refresh-Token in einem `HttpOnly`-Cookie würde das Risiko bei einer XSS-Lücke senken.
- Es gibt noch keine Rollen; jeder angemeldete Benutzer kann Datenschutz-Anfragen bearbeiten. Ausbaustufe: Rolle „Datenschutz“ bzw. „Admin“.

## 3. Auftragsverarbeiter (Art. 28 DSGVO)

| Dienst | Zweck | Sitz / Region | Grundlage | Status |
|---|---|---|---|---|
| Supabase | Datenbank, Dateiablage | Projekt-Region wählbar; **EU (Frankfurt) verwenden** | AVV (DPA) des Anbieters | **[AVV abschließen, Region prüfen]** |
| Render | Hosting von API und Oberfläche | Region wählbar; **Frankfurt verwenden** | AVV (DPA) des Anbieters | **[AVV abschließen, Region prüfen]** |
| SendGrid (Twilio Inc.) | E-Mail-Versand | USA | AVV; EU-US Data Privacy Framework bzw. Standardvertragsklauseln (Art. 45/46) | **[AVV abschließen; EU-Anbieter als Alternative prüfen]** |

Die Anwendung kann E-Mails statt zu versenden in einen lokalen Ordner schreiben (`EMAIL_DEMO_MODE`). Das ist nützlich für Tests, ohne echte Adressen an einen Versanddienst zu geben.

## 4. Löschkonzept

| Datenkategorie | Frist | Auslöser | Umsetzung |
|---|---|---|---|
| Rechnungen (Buchungsbelege) inkl. beteiligter Personen | 8 Jahre ab Ende des Eingangsjahres (§ 147 Abs. 3, 4 AO) | Fristablauf | Löschen vor Fristende wird abgelehnt; danach bewusste Löschung **[Prozess festlegen]** |
| Änderungsprotokoll | wie die zugehörigen Rechnungen | Fristablauf | nur fortschreibbar; Archivierung/Löschung nach Fristende **[Prozess festlegen]** |
| Fälschlich hochgeladene Dateien | sofort | Feststellung | Löschen im Dashboard, wird protokolliert |
| IP-Adressen (Freigabe-Links, Sicherheitsereignisse) | 30 Tage | täglich automatisch | `remove_old_ip_addresses` |
| E-Mail-Versandprotokoll | **[z. B. 2 Jahre]** | Löschantrag oder Frist | Pseudonymisierung über Datenschutz-Anfrage |
| Benutzerkonten | Austritt | Antrag | Deaktivierung, Name und E-Mail entfernt; Benutzername bleibt im Änderungsprotokoll |
| Server-Logs | **[Aufbewahrung beim Hoster einstellen, z. B. 14 Tage]** | Frist | E-Mail-Adressen und IBANs sind bereits maskiert |

## 5. Ablauf bei Anfragen betroffener Personen (Art. 12 bis 22)

1. Anfrage annehmen, Identität prüfen, Frist notieren (ein Monat, Art. 12 Abs. 3).
2. In der Anwendung unter **Datenschutz** die E-Mail-Adresse eingeben.
3. Auskunft: JSON herunterladen und der Person übermitteln. Die Datei enthält alle Tabellen, in denen die Adresse vorkommt, und die Aktionen der Person im Änderungsprotokoll, nie den Passwort-Hash.
4. Löschung: bestätigen. Die Anwendung pseudonymisiert Benutzerkonto, Versandprotokoll, Freigabe-Links und Sicherheitsereignisse und meldet, was aus Aufbewahrungsgründen bleibt und bis wann. Diese Begründung der Person mitteilen (Art. 17 Abs. 3 lit. b).
5. Die Bearbeitung wird automatisch in `security_events` festgehalten, mit einem Hash der Adresse statt der Adresse selbst (Rechenschaftspflicht, Art. 5 Abs. 2).
