"""
Gemini as an alternative AI provider (AI_PROVIDER=gemini).

The AI features are written against the shape of the Anthropic Messages API.
This adapter accepts the subset they use (system prompt, text / PDF /
tool_use / tool_result blocks, tools, JSON-schema output) and translates it
to Gemini's generateContent REST API, then translates the answer back. So
the features, their guardrails and their tests stay provider-neutral.

Plain HTTP via httpx rather than the google-genai SDK: the SDK needs a newer
httpx than the Supabase client allows.

What Gemini doesn't have here: document citations (RAG falls back to listing
the retrieved passages) and server-side refusal fallback (a blocked answer
becomes a refusal).
"""
from dataclasses import dataclass
from itertools import count
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import httpx

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"

BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}


class GeminiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Gemini API {status}: {message}")
        self.status = status


class GeminiRateLimit(GeminiError):
    """429: on the free tier this usually means the per-minute or daily quota is used up."""


@dataclass
class Block:
    """A content block in the shape the features read (type, text / id, name, input)."""
    type: str
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    thought_signature: Optional[str] = None
    citations: Optional[list] = None

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        data = dict(self.__dict__)
        return {k: v for k, v in data.items() if v is not None} if exclude_none else data


# ---------------------------------------------------------------------------
# Request translation
# ---------------------------------------------------------------------------

_TYPES = {"string": "STRING", "number": "NUMBER", "integer": "INTEGER", "boolean": "BOOLEAN",
          "array": "ARRAY", "object": "OBJECT"}


def to_gemini_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """JSON Schema -> the OpenAPI subset Gemini accepts (no additionalProperties, upper-case types)."""
    out: Dict[str, Any] = {}
    if "type" in schema:
        out["type"] = _TYPES[schema["type"]]
    for key in ("description", "enum", "required", "format"):
        if key in schema:
            out[key] = schema[key]
    if "properties" in schema:
        out["properties"] = {name: to_gemini_schema(sub) for name, sub in schema["properties"].items()}
        out["propertyOrdering"] = list(schema["properties"])
    if "items" in schema:
        out["items"] = to_gemini_schema(schema["items"])
    return out


def _as_dict(block: Any) -> Dict[str, Any]:
    return block if isinstance(block, dict) else block.model_dump(exclude_none=True)


def to_gemini_contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tool_names: Dict[str, str] = {}   # tool_use id -> function name, which functionResponse needs
    contents = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        blocks = message["content"]
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        parts = []
        for block in map(_as_dict, blocks):
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                parts.append({"text": block["text"]})
            elif kind == "document":
                source = block["source"]
                if source["type"] == "base64":
                    parts.append({"inline_data": {"mime_type": source["media_type"], "data": source["data"]}})
                else:  # plain-text document, e.g. a retrieved passage
                    parts.append({"text": f"<document title=\"{block.get('title', '')}\">\n{source['data']}\n</document>"})
            elif kind == "tool_use":
                tool_names[block["id"]] = block["name"]
                part: Dict[str, Any] = {"functionCall": {"name": block["name"], "args": block.get("input") or {}}}
                if block.get("thought_signature"):
                    part["thoughtSignature"] = block["thought_signature"]
                parts.append(part)
            elif kind == "tool_result":
                content = block.get("content")
                if isinstance(content, list):
                    content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
                key = "error" if block.get("is_error") else "result"
                parts.append({"functionResponse": {"name": tool_names.get(block["tool_use_id"], "tool"),
                                                   "response": {key: content}}})
            # thinking blocks from another provider and unknown types carry nothing Gemini can use
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GeminiClient:
    """Exposes beta.messages.create(...) like the Anthropic client, backed by Gemini."""

    def __init__(self, api_key: Optional[str] = None, http: Any = None, timeout: float = 120.0):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.http = http or httpx.Client(timeout=timeout)
        self._ids = count(1)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, *, model: str, max_tokens: int, messages: List[Dict[str, Any]], system: Optional[str] = None,
               tools: Optional[List[Dict[str, Any]]] = None, output_config: Optional[Dict[str, Any]] = None,
               **_anthropic_only: Any) -> SimpleNamespace:
        body: Dict[str, Any] = {"contents": to_gemini_contents(messages),
                                "generationConfig": {"maxOutputTokens": max_tokens}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t["name"], "description": t["description"], "parameters": to_gemini_schema(t["input_schema"])}
                for t in tools]}]
        output_format = (output_config or {}).get("format")
        if output_format:
            body["generationConfig"]["responseMimeType"] = "application/json"
            body["generationConfig"]["responseSchema"] = to_gemini_schema(output_format["schema"])

        response = self.http.post(API_URL.format(model=model), json=body,
                                  headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"})
        if response.status_code == 429:
            raise GeminiRateLimit(429, "quota exceeded")
        if response.status_code >= 400:
            try:
                message = response.json().get("error", {}).get("message", response.text)
            except ValueError:
                message = response.text
            raise GeminiError(response.status_code, message[:300])
        return self._translate(response.json(), model)

    def _translate(self, data: Dict[str, Any], model: str) -> SimpleNamespace:
        usage_data = data.get("usageMetadata", {})
        usage = SimpleNamespace(input_tokens=usage_data.get("promptTokenCount", 0),
                                output_tokens=usage_data.get("candidatesTokenCount", 0)
                                + usage_data.get("thoughtsTokenCount", 0))
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "blocked")
            return SimpleNamespace(content=[], stop_reason="refusal", usage=usage, model=model,
                                   stop_details=SimpleNamespace(explanation=f"Gemini: {reason}"))

        candidate = candidates[0]
        blocks: List[Block] = []
        for part in (candidate.get("content") or {}).get("parts", []):
            if part.get("thought"):
                continue
            if "functionCall" in part:
                call = part["functionCall"]
                blocks.append(Block(type="tool_use", id=call.get("id") or f"gemini_call_{next(self._ids)}",
                                    name=call["name"], input=call.get("args") or {},
                                    thought_signature=part.get("thoughtSignature")))
            elif part.get("text"):
                blocks.append(Block(type="text", text=part["text"]))

        finish = candidate.get("finishReason", "STOP")
        if finish in BLOCKED:
            stop_reason = "refusal"
        elif any(b.type == "tool_use" for b in blocks):
            stop_reason = "tool_use"
        elif finish == "MAX_TOKENS":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"
        details = SimpleNamespace(explanation=f"Gemini: {finish}") if stop_reason == "refusal" else None
        return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=usage, model=model, stop_details=details)
