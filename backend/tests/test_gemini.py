"""The Gemini adapter: request/response translation, errors, the free-tier guard, and the agent on top of it."""
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from services.ai import agent, extraction, llm, rag
from services.ai.gemini import GeminiClient, GeminiError, GeminiRateLimit, to_gemini_contents, to_gemini_schema
from services.database import db_service
from services.demo_data import seed
from services.in_memory_supabase import FakeSupabase


class FakeHttp:
    """Records POSTs and answers with scripted (status, json) pairs."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: List[Dict[str, Any]] = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "body": json, "headers": headers})
        status, data = self.replies.pop(0)
        return SimpleNamespace(status_code=status, json=lambda: data, text=str(data))


def reply(*parts, finish="STOP", prompt_tokens=10, output_tokens=5):
    return 200, {"candidates": [{"content": {"role": "model", "parts": list(parts)}, "finishReason": finish}],
                 "usageMetadata": {"promptTokenCount": prompt_tokens, "candidatesTokenCount": output_tokens}}


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def script(*replies):
        http = FakeHttp(*replies)
        llm.set_client(GeminiClient(api_key="test-key", http=http))
        return http

    yield script
    llm.set_client(None)


# --- translation ----------------------------------------------------------------

def test_schema_becomes_gemini_openapi_subset():
    schema = {"type": "object", "properties": {"q": {"type": "string", "description": "x"},
                                               "n": {"type": "integer"}},
              "required": ["q", "n"], "additionalProperties": False}
    assert to_gemini_schema(schema) == {
        "type": "OBJECT", "required": ["q", "n"], "propertyOrdering": ["q", "n"],
        "properties": {"q": {"type": "STRING", "description": "x"}, "n": {"type": "INTEGER"}}}


def test_conversation_translation():
    contents = to_gemini_contents([
        {"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "UERG"}},
            {"type": "text", "text": "Lies die Rechnung"}]},
        {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "", "signature": "anthropic-only"},
            {"type": "tool_use", "id": "c1", "name": "get_invoice", "input": {"invoice_id": "7"},
             "thought_signature": "sig"}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{\"ok\": 1}"}]},
    ])
    assert contents[0] == {"role": "user", "parts": [
        {"inline_data": {"mime_type": "application/pdf", "data": "UERG"}}, {"text": "Lies die Rechnung"}]}
    assert contents[1] == {"role": "model", "parts": [
        {"functionCall": {"name": "get_invoice", "args": {"invoice_id": "7"}}, "thoughtSignature": "sig"}]}
    assert contents[2]["parts"][0] == {"functionResponse": {"name": "get_invoice", "response": {"result": "{\"ok\": 1}"}}}


def test_request_body(gemini):
    http = gemini(reply({"text": "{}"}))
    llm.create("test", max_tokens=100, system="Sei kurz.",
               messages=[{"role": "user", "content": "Hallo"}],
               tools=agent.TOOLS[:1],
               output_config={"effort": "low", "format": {"type": "json_schema", "schema": {"type": "object", "properties": {}}}})
    call = http.calls[0]
    assert call["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert call["headers"]["x-goog-api-key"] == "test-key"
    body = call["body"]
    assert body["systemInstruction"] == {"parts": [{"text": "Sei kurz."}]}
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "search_invoices"
    assert "additionalProperties" not in str(body["tools"])
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "betas" not in body and "fallbacks" not in body


@pytest.mark.parametrize("parts, finish, stop_reason", [
    ([{"text": "Antwort"}], "STOP", "end_turn"),
    ([{"functionCall": {"name": "search_invoices", "args": {"query": "", "status": ""}}}], "STOP", "tool_use"),
    ([{"text": "abgeschnitt"}], "MAX_TOKENS", "max_tokens"),
    ([], "SAFETY", "refusal"),
])
def test_response_translation(parts, finish, stop_reason):
    http = FakeHttp(reply(*parts, finish=finish))
    response = GeminiClient(api_key="k", http=http).create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])
    assert response.stop_reason == stop_reason


def test_thoughts_are_skipped_and_usage_counted():
    http = FakeHttp((200, {"candidates": [{"content": {"parts": [{"text": "intern", "thought": True}, {"text": "Antwort"}]},
                                           "finishReason": "STOP"}],
                           "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3, "thoughtsTokenCount": 2}}))
    response = GeminiClient(api_key="k", http=http).create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])
    assert [b.text for b in response.content] == ["Antwort"]
    assert (response.usage.input_tokens, response.usage.output_tokens) == (7, 5)


def test_blocked_prompt_is_a_refusal():
    http = FakeHttp((200, {"promptFeedback": {"blockReason": "SAFETY"}}))
    response = GeminiClient(api_key="k", http=http).create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])
    assert response.stop_reason == "refusal"


@pytest.mark.parametrize("status, error", [(429, GeminiRateLimit), (400, GeminiError), (500, GeminiError)])
def test_http_errors(status, error):
    http = FakeHttp((status, {"error": {"message": "nope"}}))
    with pytest.raises(error):
        GeminiClient(api_key="k", http=http).create(model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])


# --- free-tier guard --------------------------------------------------------------

def test_free_gemini_key_only_goes_live_with_demo_data(monkeypatch):
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "free-key")
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("GEMINI_PAID_TIER", raising=False)
    assert llm.mode() == "offline" and "demo data" in llm.offline_reason()
    monkeypatch.setenv("DEMO_MODE", "true")
    assert llm.mode() == "live"
    monkeypatch.delenv("DEMO_MODE")
    monkeypatch.setenv("GEMINI_PAID_TIER", "true")
    assert llm.mode() == "live"


def test_gemini_needs_its_own_key(monkeypatch):
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    assert llm.offline_reason() == "no API key for gemini"


# --- features on Gemini -----------------------------------------------------------

@pytest.fixture
def demo_db(monkeypatch):
    monkeypatch.setattr(db_service, "_client", FakeSupabase())
    seed(db_service)
    return db_service


def test_agent_runs_on_gemini(gemini, demo_db):
    http = gemini(
        reply({"functionCall": {"name": "list_skonto_deadlines", "args": {"days": 14}}, "thoughtSignature": "s1"}),
        reply({"text": "Zwei Skonti laufen ab: Elektro Müller und Fliesen Schmidt."}),
    )
    result = agent.answer("Welches Skonto läuft ab?", [], demo_db)
    assert result["mode"] == "live"
    assert [t["tool"] for t in result["trace"]] == ["list_skonto_deadlines"]
    assert "Elektro Müller" in result["answer"]
    second = http.calls[1]["body"]["contents"]
    assert second[1]["parts"][0]["thoughtSignature"] == "s1"           # signature goes back with the call
    assert second[2]["parts"][0]["functionResponse"]["name"] == "list_skonto_deadlines"
    logged = demo_db.client.table("ai_requests").rows[-1]
    assert logged["model"] == "gemini-2.5-flash" and logged["cost_usd"] == 0


def test_rag_on_gemini_lists_sources_without_native_citations(gemini):
    gemini(reply({"text": "Ja, nach § 13b Abs. 2 UStG schuldet der Leistungsempfänger die Steuer."}))
    result = rag.ask("Muss bei Bauleistungen der Empfänger die Umsatzsteuer zahlen?")
    assert result["mode"] == "live"
    assert result["citations"][0]["citation"] == "§ 13b Abs. 2 UStG"


def test_extraction_on_gemini(gemini):
    import json
    empty = {name: {"value": "", "confidence": "none", "source_text": ""} for name in extraction.FIELDS}
    empty["rechnungsnummer"] = {"value": "RE-1", "confidence": "high", "source_text": "Rechnungsnummer: RE-1"}
    http = gemini(reply({"text": json.dumps({"fields": empty, "suspicious_instructions": ""})}))
    result = extraction.extract(b"%PDF-1.4 x")
    assert result["fields"]["rechnungsnummer"]["value"] == "RE-1"
    parts = http.calls[0]["body"]["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "application/pdf"


def test_api_reports_gemini_quota_clearly(client, auth_headers, gemini):
    gemini((429, {"error": {"message": "quota"}}))
    response = client.post("/api/ai/ask", json={"question": "Welche Angaben muss eine Rechnung enthalten?"},
                           headers=auth_headers)
    assert response.status_code == 503 and "Kontingent" in response.json()["detail"]


def test_status_shows_provider(client, auth_headers, gemini):
    gemini()
    status = client.get("/api/ai/status", headers=auth_headers).json()
    assert (status["provider"], status["model"], status["mode"]) == ("gemini", "gemini-2.5-flash", "live")
