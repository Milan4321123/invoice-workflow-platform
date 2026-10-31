"""The approval and Skonto links in e-mails, from sending to deciding."""
from html import unescape
import re

import pytest

from services.database import db_service
from services.demo_data import seed
from services.email_service import email_service
from services.in_memory_supabase import FakeSupabase


@pytest.fixture
def demo_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db_service, "_client", FakeSupabase())
    monkeypatch.setattr(email_service, "demo_mode", True)
    monkeypatch.setattr(email_service, "base_url", "http://api.test")
    monkeypatch.setenv("EMAIL_OUTBOX_DIR", str(tmp_path))
    seed(db_service)
    return db_service


def row(db, name):
    return next(r for r in db.client.table("invoices_clean").rows if name in r["file_name"])


def links(tmp_path):
    html = sorted(tmp_path.glob("*.html"))[-1].read_text(encoding="utf-8")
    return [unescape(u) for u in re.findall(r'href="(http://api\.test[^"]+)"', html)], html


async def send_approval(db):
    wagner = row(db, "Wagner")
    await email_service.send_bauleiter_approval_request(
        invoice_data=wagner, bauleiter_email="bau@example.com", editor_name="Prüfung", editor_email="p@example.com")
    return wagner


def path(url):
    return url.replace("http://api.test", "")


def decision_links(tmp_path):
    """(approve, reject) from the approval e-mail, in the template's order"""
    return [u for u in links(tmp_path)[0] if "/api/approval/" in u and not u.endswith("/pdf")]


@pytest.mark.asyncio
async def test_mail_links_point_at_the_api(demo_db, tmp_path):
    await send_approval(demo_db)
    urls, html = links(tmp_path)
    assert html.startswith("<!-- outbox {")
    approve = [u for u in urls if "/api/approval/" in u and not u.endswith("/pdf")]
    assert len(approve) == 2                                    # approve and reject
    assert any(u.endswith("/pdf") for u in urls)               # PDF via the token, not a 1-hour storage link


@pytest.mark.asyncio
async def test_opening_the_link_decides_nothing(client, demo_db, tmp_path):
    await send_approval(demo_db)
    approve_url = decision_links(tmp_path)[0]
    response = client.get(path(approve_url))
    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    assert "Rechnung freigeben" in response.text and "<iframe" in response.text
    assert row(demo_db, "Wagner")["status"] == "in_review_by_bauleiter"
    assert all(t.get("used_at") is None for t in demo_db.client.table("approval_tokens").rows)


@pytest.mark.asyncio
async def test_pdf_opens_from_the_mail(client, demo_db, tmp_path):
    await send_approval(demo_db)
    pdf_url = next(u for u in links(tmp_path)[0] if u.endswith("/pdf"))
    response = client.get(path(pdf_url))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["x-frame-options"] == "SAMEORIGIN"      # may be framed by the approval page
    assert client.get(path(decision_links(tmp_path)[0])).headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_approve_once(client, demo_db, tmp_path):
    await send_approval(demo_db)
    approve_url = decision_links(tmp_path)[0]
    pdf_url = next(u for u in links(tmp_path)[0] if u.endswith("/pdf"))
    response = client.post(path(approve_url), data={"comment": "Leistung abgenommen"})
    assert response.status_code == 200 and "freigegeben" in response.text
    wagner = row(demo_db, "Wagner")
    assert (wagner["status"], wagner["approval_method"], wagner["review_notes"]) == (
        "approved_by_bauleiter", "email_link", "Leistung abgenommen")
    assert demo_db.client.table("invoice_audit_log").rows[-1]["actor"] == "E-Mail-Link bau@example.com"

    assert client.post(path(approve_url), data={}).status_code == 410            # single use
    assert "Bereits entschieden" in client.get(path(approve_url)).text
    assert client.get(path(pdf_url)).status_code == 200                       # viewing still works


@pytest.mark.asyncio
async def test_reject_needs_a_reason(client, demo_db, tmp_path):
    await send_approval(demo_db)
    reject_url = decision_links(tmp_path)[1]
    assert client.post(path(reject_url), data={"comment": " "}).status_code == 400
    assert row(demo_db, "Wagner")["status"] == "in_review_by_bauleiter"
    client.post(path(reject_url), data={"comment": "Montage fehlt"})
    assert (row(demo_db, "Wagner")["status"], row(demo_db, "Wagner")["review_notes"]) == (
        "rejected_by_bauleiter", "Montage fehlt")


@pytest.mark.asyncio
async def test_approve_and_reject_links_share_one_decision(client, demo_db, tmp_path):
    await send_approval(demo_db)
    approve_url, reject_url = decision_links(tmp_path)[:2]
    client.post(path(approve_url), data={})
    response = client.post(path(reject_url), data={"comment": "zu spät"})
    assert "Bereits entschieden" in response.text
    assert row(demo_db, "Wagner")["status"] == "approved_by_bauleiter"


@pytest.mark.asyncio
async def test_fails_closed_when_tokens_cant_be_checked(client, demo_db, tmp_path, monkeypatch):
    await send_approval(demo_db)
    approve_url = decision_links(tmp_path)[0]
    original = demo_db.client.table

    def broken(name):
        if name == "approval_tokens":
            raise RuntimeError("database down")
        return original(name)

    monkeypatch.setattr(demo_db.client, "table", broken)
    assert client.post(path(approve_url), data={}).status_code == 410
    monkeypatch.setattr(demo_db.client, "table", original)
    assert row(demo_db, "Wagner")["status"] == "in_review_by_bauleiter"


def test_forged_and_expired_links_are_refused(client, demo_db):
    assert client.get("/api/approval/not-a-token").status_code == 410
    import jwt
    forged = jwt.encode({"invoice_id": row(demo_db, "Wagner")["id"], "action": "approve", "user_email": "x"},
                        "wrong-secret", algorithm="HS256")
    assert client.post(f"/api/approval/{forged}", data={}).status_code == 410


@pytest.mark.asyncio
async def test_expired_record_is_refused(client, demo_db, tmp_path):
    await send_approval(demo_db)
    for token in demo_db.client.table("approval_tokens").rows:
        token["expires_at"] = "2020-01-01T00:00:00"
    assert client.get(path(decision_links(tmp_path)[0])).status_code == 410


@pytest.mark.asyncio
async def test_supplier_text_is_escaped(client, demo_db, tmp_path):
    wagner = row(demo_db, "Wagner")
    wagner["rechnungssteller"] = "<script>alert(1)</script>"
    await send_approval(demo_db)
    page = client.get(path(decision_links(tmp_path)[0])).text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


@pytest.mark.asyncio
async def test_skonto_link_shows_then_decides(client, demo_db, tmp_path):
    mueller = row(demo_db, "Mueller")
    await email_service.send_skonto_reminder(invoice_data=mueller, recipient_email="buchhaltung@example.com")
    take_url = next(u for u in links(tmp_path)[0] if "decision=taken" in u)
    page = client.get(path(take_url))
    assert page.status_code == 200 and "Skonto nehmen" in page.text
    assert row(demo_db, "Mueller")["skonto_decision"] == "pending"
    client.post(path(take_url))
    assert row(demo_db, "Mueller")["skonto_decision"] == "taken"
    assert client.post(path(take_url)).status_code == 410
