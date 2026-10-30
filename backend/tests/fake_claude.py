"""
A scripted stand-in for the Anthropic client: returns prepared responses in
order and records every request, so tests can check what was sent without
a key, network or cost.
"""
import json
from types import SimpleNamespace
from typing import Any, Dict, List


class Block(SimpleNamespace):
    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        data = {k: v for k, v in vars(self).items() if not (exclude_none and v is None)}
        if "citations" in data and data["citations"] is not None:
            data["citations"] = [vars(c) for c in data["citations"]]
        return data


def text(value: str, citations=None) -> Block:
    return Block(type="text", text=value, citations=citations)


def citation(document_index: int, cited_text: str) -> SimpleNamespace:
    return SimpleNamespace(type="char_location", document_index=document_index, cited_text=cited_text)


def tool_use(name: str, arguments: Dict[str, Any], id: str) -> Block:
    return Block(type="tool_use", id=id, name=name, input=arguments)


def response(*content: Block, stop_reason: str = "end_turn", input_tokens: int = 100, output_tokens: int = 50,
             explanation: str = None) -> SimpleNamespace:
    return SimpleNamespace(
        content=list(content), stop_reason=stop_reason, model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_details=SimpleNamespace(explanation=explanation) if stop_reason == "refusal" else None,
    )


def json_response(data: Dict[str, Any]) -> SimpleNamespace:
    return response(text(json.dumps(data, ensure_ascii=False)))


class FakeClaude:
    def __init__(self, *responses: SimpleNamespace):
        self.responses: List[SimpleNamespace] = list(responses)
        self.requests: List[Dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **params: Any) -> SimpleNamespace:
        # deep-ish copy so later mutation of `messages` by the caller doesn't change what we recorded
        self.requests.append(json.loads(json.dumps(params, default=lambda o: o.model_dump()
                                                   if hasattr(o, "model_dump") else vars(o))))
        if not self.responses:
            raise AssertionError("FakeClaude ran out of scripted responses")
        return self.responses.pop(0)
