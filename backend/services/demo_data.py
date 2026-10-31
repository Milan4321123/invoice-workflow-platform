"""
Fictional data for demo mode (DEMO_MODE=true).

Seven invoices from a made-up construction company, each showing one part of
the workflow: a complete invoice, a ZUGFeRD PDF and a bare XRechnung that
fill themselves in, an invoice with §14 UStG errors, an approved (locked)
one, one waiting for the site manager, and a likely double payment. Companies, VAT IDs and people are
invented; the VAT IDs have valid check digits but belong to nobody, and the
IBANs are the usual published test numbers.
"""
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import uuid

from services.e_invoice import parse_pdf, parse_xml

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
DEMO_USER = "demo"
DEMO_PASSWORD = "Demo-2026!"


def simple_pdf(lines) -> bytes:
    """A one-page A4 PDF with text lines: [(size, bold, x, y, text), ...]"""
    def escape(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "".join(
        f"BT /{'F2' if bold else 'F1'} {size} Tf {x} {y} Td ({escape(text)}) Tj ET\n"
        for size, bold, x, y, text in lines
    ).encode("cp1252")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def invoice_pdf(supplier, address, number, issued, items, net, rate, vat, gross, notes=()) -> bytes:
    euro = lambda value: f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    lines = [
        (16, True, 50, 790, supplier),
        (9, False, 50, 774, address),
        (9, False, 50, 720, "Muster Bau AG · Baustraße 7 · 10115 Berlin"),
        (20, True, 50, 670, "Rechnung"),
        (10, False, 50, 645, f"Rechnungsnummer: {number}"),
        (10, False, 50, 630, f"Rechnungsdatum: {issued:%d.%m.%Y}"),
    ]
    y = 590
    for description, amount in items:
        lines += [(10, False, 50, y, description), (10, False, 430, y, euro(amount))]
        y -= 18
    lines += [
        (10, False, 300, y - 20, "Nettobetrag"), (10, False, 430, y - 20, euro(net)),
        (10, False, 300, y - 38, f"Umsatzsteuer {rate:g} %"), (10, False, 430, y - 38, euro(vat)),
        (11, True, 300, y - 60, "Gesamtbetrag"), (11, True, 430, y - 60, euro(gross)),
    ]
    for offset, note in enumerate(notes):
        lines.append((9, False, 50, y - 110 - offset * 14, note))
    lines.append((8, False, 50, 60, "Fiktive Demo-Rechnung · keine echte Firma"))
    return simple_pdf(lines)


def _attach(pdf: bytes, name: str, xml: bytes) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    writer.add_attachment(name, xml)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def seed(db) -> None:
    """Fill the in-memory database behind db (a DatabaseService) with the demo data."""
    client = db.client
    today = date.today()
    now = datetime.now(timezone.utc)

    for field, options in {
        "projekt": [("omega", "Wohnanlage Omega"), ("hafen", "Bürohaus Hafenkante")],
        "gewerk": [("elektro", "Elektroinstallation"), ("sanitaer", "Sanitärinstallation"), ("heizung", "Heizungsbau"),
                   ("maler", "Malerarbeiten"), ("fliesen", "Fliesenarbeiten"), ("trockenbau", "Trockenbau")],
        "rechnungsempfaenger": [("muster_bau", "Muster Bau AG")],
        "weiter_berechnen_an": [("keine", "Keine Weiterberechnung"), ("bauherr", "Bauherr")],
    }.items():
        for order, (value, label) in enumerate(options, start=1):
            client.table("dropdown_options").insert({
                "id": len(client.table("dropdown_options").rows) + 1, "field_name": field, "value": value,
                "label": label, "is_default": order == 1, "sort_order": order, "is_active": True, "metadata": {},
            }).execute()

    def add(file_name, content, status, fields, bucket="invoices", mime="application/pdf"):
        invoice_id = str(uuid.uuid4())
        client.storage.from_(bucket).upload(file_name, content)
        row = {
            "id": invoice_id, "file_name": file_name, "file_path": file_name, "file_size": len(content),
            "mime_type": mime, "status": status, "created_at": now.isoformat(), "updated_at": now.isoformat(),
            "approval_status": "pending", "skonto_decision": "pending", "reverse_charge_13b": False,
            "kfw_anrechenbare_kosten": False, "rechnungsempfaenger": "muster_bau", **fields,
        }
        client.table(db.table_name).insert(row).execute()
        db.audit.record(invoice_id, "created", {k: {"old": None, "new": v} for k, v in fields.items()},
                        actor="demo-import")
        return invoice_id

    complete = dict(
        rechnungssteller="Elektro Müller GmbH", lieferant_ust_id="DE123456788", lieferant_iban="DE89370400440532013000",
        projekt="omega", gewerk="elektro", rechnungsnummer="RE-2026-0815",
        rechnungsdatum=(today - timedelta(days=15)).isoformat(), leistungsdatum=(today - timedelta(days=20)).isoformat(),
        rechnungseingang=(today - timedelta(days=13)).isoformat(), nettobetrag=1000.0, ust_satz=19.0, ust_betrag=190.0,
        rechnungsbetrag=1190.0, faelligkeit=(today + timedelta(days=15)).isoformat(),
        skonto_datum=(today + timedelta(days=2)).isoformat(), skonto_prozent=2.0,
        freistellung_48b_gueltig_bis=(today + timedelta(days=240)).isoformat(),
        rechnungspruefung="pruefung@muster-bau.example",
    )
    add("20261015_OMEGA_ELEKTRO_Mueller.pdf", invoice_pdf(
        "Elektro Müller GmbH", "Lindenweg 4 · 12043 Berlin · USt-IdNr. DE123456788", "RE-2026-0815",
        today - timedelta(days=15), [("Elektroinstallation 2. OG, 20 Std.", 1000.0)], 1000, 19, 190, 1190,
        ["Zahlbar innerhalb 30 Tagen, bei Zahlung innerhalb 17 Tagen 2 % Skonto.",
         "IBAN DE89 3704 0044 0532 0130 00"]), "edited", complete)

    # ZUGFeRD: the XML inside the PDF fills in the fields
    factur_x = (DEMO_DIR / "fliesen_schmidt_factur-x.xml").read_bytes()
    pdf = _attach(invoice_pdf(
        "Fliesen Schmidt KG", "Kachelstraße 12 · 20095 Hamburg · USt-IdNr. DE987654328", "2026-4711",
        date(2026, 10, 20), [("Fliesen 30x60, Lieferung und Verlegung", 2500.0)], 2500, 19, 475, 2975,
        ["Zahlbar innerhalb 30 Tagen netto, 3 % Skonto innerhalb 14 Tagen.",
         "Diese Rechnung enthält eine maschinenlesbare ZUGFeRD-Datei (EN 16931)."]), "factur-x.xml", factur_x)
    e_invoice = parse_pdf(pdf)
    add("20261020_OMEGA_FLIESEN_Schmidt.pdf", pdf, "uploaded",
        {**e_invoice.invoice_fields(), "projekt": "omega", "gewerk": "fliesen", "e_rechnung_format": e_invoice.format})

    # Bare XRechnung: no page to show, §13b reverse charge credit note
    xrechnung = (DEMO_DIR / "trockenbau_weber_xrechnung.xml").read_bytes()
    e_invoice = parse_xml(xrechnung)
    add("20261001_HAFEN_TROCKENBAU_Weber.xml", xrechnung, "uploaded",
        {**e_invoice.invoice_fields(), "projekt": "hafen", "gewerk": "trockenbau", "e_rechnung_format": e_invoice.format},
        mime="application/xml")

    # Gaps and mistakes the compliance check points out
    add("20261005_HAFEN_SANITAER_Becker.pdf", invoice_pdf(
        "Sanitär Becker", "Rohrgasse 3 · 10997 Berlin", "", today - timedelta(days=12),
        [("Sanitärinstallation EG", 840.0)], 840, 19, 159.6, 1009.6, ["IBAN DE02 1203 0000 0000 2020 51"]),
        "edited", dict(
            rechnungssteller="Sanitär Becker", lieferant_ust_id="DE123456789", projekt="hafen", gewerk="sanitaer",
            rechnungsdatum=(today - timedelta(days=12)).isoformat(), nettobetrag=840.0, ust_satz=19.0,
            ust_betrag=159.6, rechnungsbetrag=1090.6, lieferant_iban="DE02120300000000202051",
            rechnungseingang=(today - timedelta(days=10)).isoformat(),
        ))

    # Approved: booking-relevant fields are locked
    approved = dict(
        rechnungssteller="Malerbetrieb Klein", lieferant_steuernummer="21/815/08150", projekt="omega", gewerk="maler",
        rechnungsnummer="MK-2026-117", rechnungsdatum="2026-09-08", leistungsdatum="2026-09-01",
        rechnungseingang="2026-09-10", nettobetrag=3200.0, ust_satz=19.0, ust_betrag=608.0, rechnungsbetrag=3808.0,
        faelligkeit="2026-10-08", freistellung_48b_gueltig_bis="2027-03-31", lieferant_iban="DE89370400440532013000",
        bauleiter_email="bauleitung@muster-bau.example",
    )
    approved_id = add("20260910_OMEGA_MALER_Klein.pdf", invoice_pdf(
        "Malerbetrieb Klein", "Farbenweg 9 · 14193 Berlin · St.-Nr. 21/815/08150", "MK-2026-117", date(2026, 9, 8),
        [("Malerarbeiten Treppenhaus", 3200.0)], 3200, 19, 608, 3808), "uploaded", approved)
    client.table(db.table_name).update({"status": "approved_by_bauleiter", "approval_status": "approved",
                                        "approved_at": "2026-09-15T09:30:00+00:00"}).eq("id", approved_id).execute()
    db.audit.record(approved_id, "approval_decided",
                    {"status": {"old": "uploaded", "new": "approved_by_bauleiter"}},
                    actor="E-Mail-Link bauleitung@muster-bau.example")

    # Waiting for the site manager's approval (Bauleiter dashboard)
    add("20261022_OMEGA_HEIZUNG_Wagner.pdf", invoice_pdf(
        "Heizungsbau Wagner GmbH", "Thermenweg 2 · 13353 Berlin · USt-IdNr. DE987654328", "HW-2026-204",
        today - timedelta(days=8), [("Fußbodenheizung 1. OG, Material und Montage", 6400.0)], 6400, 19, 1216, 7616,
        ["IBAN DE02 1203 0000 0000 2020 51"]), "in_review_by_bauleiter", dict(
            rechnungssteller="Heizungsbau Wagner GmbH", lieferant_ust_id="DE987654328", projekt="omega", gewerk="heizung",
            rechnungsnummer="HW-2026-204", rechnungsdatum=(today - timedelta(days=8)).isoformat(),
            leistungsdatum=(today - timedelta(days=12)).isoformat(), rechnungseingang=(today - timedelta(days=6)).isoformat(),
            nettobetrag=6400.0, ust_satz=19.0, ust_betrag=1216.0, rechnungsbetrag=7616.0,
            faelligkeit=(today + timedelta(days=22)).isoformat(), lieferant_iban="DE02120300000000202051",
            freistellung_48b_gueltig_bis=(today + timedelta(days=180)).isoformat(),
            bauleiter_email="bauleitung@muster-bau.example", rechnungspruefung="pruefung@muster-bau.example",
        ))

    # Same supplier and number again: probably the same invoice sent twice
    add("20261028_OMEGA_MALER_Klein.pdf", invoice_pdf(
        "Malerbetrieb Klein", "Farbenweg 9 · 14193 Berlin · St.-Nr. 21/815/08150", "MK-2026-117", date(2026, 9, 8),
        [("Malerarbeiten Treppenhaus", 3200.0)], 3200, 19, 608, 3808, ["ZWEITSCHRIFT"]), "uploaded",
        {**approved, "rechnungseingang": (today - timedelta(days=2)).isoformat(), "bauleiter_email": None})
