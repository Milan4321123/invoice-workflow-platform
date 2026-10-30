# Verfahrensdokumentation Eingangsrechnungen (GoBD)

Diese Dokumentation beschreibt, wie die Plattform Eingangsrechnungen erfasst, prüft, freigibt und aufbewahrt. Sie folgt dem Aufbau aus GoBD Rz. 151 ff. (allgemeine Beschreibung, Anwender-, technische System- und Betriebsdokumentation) und ist die Vorlage, die ein Unternehmen beim Einsatz um seine organisatorischen Angaben ergänzt (Verantwortliche, internes Kontrollsystem, Datensicherung).

Stand: Oktober 2026. Rechtsgrundlagen: §§ 146, 147 AO, §§ 14, 14a, 13b UStG, § 48 EStG, BMF-Schreiben zu den GoBD vom 28.11.2019 mit Änderungen zur E-Rechnung.

## 1. Allgemeine Beschreibung

| | |
|---|---|
| Zweck | Erfassung, sachliche und rechnerische Prüfung, Freigabe und Aufbewahrung von Eingangsrechnungen eines Bauunternehmens |
| Belegarten | Papierrechnung als Scan (PDF), E-Rechnung als XRechnung (UBL/CII) oder ZUGFeRD/Factur-X (PDF/A-3 mit XML) |
| Beteiligte | Rechnungsprüfung (Erfassung, Kontierung), Bauleitung (sachliche Freigabe per E-Mail-Link), Buchhaltung (Skonto, Zahlung) |
| Systeme | Web-Oberfläche (Next.js), API (FastAPI), Datenbank und Dateiablage (Supabase, Postgres, Region EU) |

## 2. Ablauf (Anwenderdokumentation)

1. **Eingang.** Die Rechnung kommt per Upload oder über einen überwachten Ordner ins System. Dateiname: `EINGANGSDATUM_PROJEKT_GEWERK_LIEFERANT.pdf` oder `.xml`. Doppelte Dateinamen werden abgewiesen.
2. **E-Rechnung.** Enthält die Datei strukturierte Rechnungsdaten (EN 16931), übernimmt das System Rechnungsnummer, Datum, Lieferant, Steuer-IDs, IBAN, Beträge und Skonto aus dem XML. Bei hybriden Formaten ist das XML maßgeblich, nicht die Bilddarstellung.
3. **Prüfung.** Die Rechnungsprüfung ergänzt Projekt, Gewerk und Prüfer. Die Pflichtangabenprüfung (§ 14 Abs. 4 UStG, § 33 UStDV, § 13b UStG, § 48 EStG) zeigt fehlende oder widersprüchliche Angaben sowie bereits erfasste Rechnungsnummern desselben Lieferanten an.
4. **Freigabe.** Die Bauleitung erhält einen signierten, befristeten, einmal verwendbaren Link und gibt frei oder lehnt ab.
5. **Festschreibung.** Ab der Freigabe sind die buchungsrelevanten Angaben gesperrt (siehe 3.3). Korrekturen erfolgen über eine Gutschrift oder Rechnungskorrektur des Lieferanten, die als neuer Beleg erfasst wird.
6. **Zahlung und Skonto.** Das System erinnert die Buchhaltung vor Ablauf der Skontofrist und hält die Entscheidung fest.

## 3. Technische Systemdokumentation

### 3.1 Unveränderbarkeit und Protokollierung (Rz. 58–60, 107 ff.)

- Alle Änderungen an Rechnungen laufen über eine einzige Methode (`DatabaseService._write_invoice`). Sie protokolliert jedes geänderte Feld mit altem und neuem Wert, Benutzer (bzw. E-Mail-Adresse bei Freigabe-Links), Zeitpunkt und Art der Änderung in der Tabelle `invoice_audit_log`.
- Die Tabelle ist nur fortschreibbar: Datenbank-Trigger lehnen `UPDATE`, `DELETE` und `TRUNCATE` ab (Migration 006).
- Jeder Eintrag enthält den SHA-256-Hash seines Inhalts zusammen mit dem Hash des vorherigen Eintrags. `GET /api/audit/verify` berechnet die Kette neu und meldet den ersten veränderten oder fehlenden Eintrag. So bleibt eine Manipulation auch durch jemanden mit direktem Datenbankzugriff erkennbar.
- Der Originalbeleg (PDF oder XML) wird unverändert in einem nicht öffentlichen Speicher abgelegt.

### 3.2 Aufbewahrung und Löschung (§ 147 Abs. 3, 4 AO)

- Aufbewahrungsfrist für Buchungsbelege: **8 Jahre** (seit dem Bürokratieentlastungsgesetz IV, ab 1.1.2025), beginnend mit dem Schluss des Kalenderjahres des Eingangs. Beispiel: Eingang 03/2026 → Aufbewahrung bis 31.12.2034.
- Löschbar sind nur Uploads, die noch niemand bearbeitet hat (falsche Datei, Dublette). Auch diese Löschung wird protokolliert.
- Bearbeitete oder freigegebene Rechnungen lehnt das System beim Löschen bis Fristende ab (HTTP 409 mit Begründung). „Alle löschen“ entfernt nur unbearbeitete Uploads.

### 3.3 Festschreibung nach Freigabe

Nach Status `approved_by_bauleiter` oder `completed` sind gesperrt: Beteiligte, Projekt, Gewerk, alle Beträge und Steuerangaben, Datumsangaben, Rechnungsart und Dateiverweis. Die Freigabe selbst kann nicht durch erneutes Speichern zurückgesetzt werden. Änderbar bleiben Arbeitsablauf-Felder (Skonto-Entscheidung, Erinnerungen, E-Mail-Protokoll).

### 3.4 Zugriffsschutz

- Jede API-Route mit Rechnungsdaten erfordert eine Anmeldung. Ein automatischer Test prüft alle registrierten Routen gegen eine Liste bewusst öffentlicher Routen.
- Freigabe-Links sind signiert (JWT), befristet und nur einmal verwendbar. Jede Verwendung wird mit IP-Adresse in `security_events` festgehalten.
- Datenbankzugriff nur über die API (Row Level Security ohne Policies, kein Datenbankschlüssel im Browser).

### 3.5 Datenzugriff der Finanzverwaltung (§ 147 Abs. 6 AO)

`GET /api/exports/gobd?year=JJJJ` (Schaltfläche „GoBD-Export“ im Dashboard) liefert ein ZIP mit
- `rechnungen.csv`: alle Eingangsrechnungen des Jahres mit Steuerangaben,
- `aenderungsprotokoll.csv`: alle Änderungen an diesen Rechnungen samt Hash-Kette,
- `beschreibung.txt`: Beschreibung aller Dateien und Spalten, Zeichensatz, Trennzeichen und Ergebnis der Kettenprüfung.

Format: UTF-8, Semikolon als Trennzeichen, Punkt als Dezimaltrennzeichen. Damit lassen sich die Dateien in Prüfsoftware wie IDEA importieren (Datenträgerüberlassung, Z3).

## 4. Betriebsdokumentation

| Thema | Umsetzung | Vom Unternehmen festzulegen |
|---|---|---|
| Datensicherung | Tägliche Supabase-Backups, Point-in-Time-Recovery als Option | Sicherungsintervall, Wiederherstellungstests |
| Verfügbarkeit | Health-Check `/api/health` | Monitoring, Bereitschaft |
| Schemaänderungen | Versionierte SQL-Migrationen in `database/migrations/` | Freigabe vor Einspielen |
| Codeänderungen | Git-Historie, Pull Requests, CI mit Tests | Vier-Augen-Prinzip |

## 5. Bekannte Grenzen

- Die Änderung an der Rechnung und der Protokolleintrag werden nacheinander geschrieben, nicht in einer Datenbanktransaktion. Schlägt das Protokollieren fehl, wird das als Fehler geloggt. Ausbaustufe: Protokollierung per Datenbank-Trigger in derselben Transaktion, mit dem Benutzer als Session-Variable.
- Die Hash-Kette erkennt Manipulationen, verhindert sie aber nicht. Wer Wert auf externe Bestätigung legt, kann den jeweils letzten Hash täglich bei einem Zeitstempeldienst (RFC 3161) hinterlegen.
- Belege, deren Frist abgelaufen ist, werden nicht automatisch gelöscht. Das erfordert eine bewusste Entscheidung und ist mit der Datenschutz-Löschfrist abzustimmen (siehe DSGVO-Dokumentation).
