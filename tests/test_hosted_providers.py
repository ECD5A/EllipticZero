from __future__ import annotations

import json

from app.llm.providers import http_utils
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.openrouter_provider import OpenRouterProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_openai_provider_builds_responses_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"output_text": "hosted-openai-text"})

    monkeypatch.setattr(http_utils.urllib_request, "urlopen", fake_urlopen)

    provider = OpenAIProvider(api_key="openai-test-key")
    text = provider.generate(
        model="gpt-test",
        timeout_seconds=17,
        max_request_tokens=256,
        system_prompt="system",
        user_prompt="user",
        metadata={"agent": "math_agent"},
    )

    assert text == "hosted-openai-text"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 17
    assert captured["auth"] == "Bearer openai-test-key"
    assert captured["body"] == {
        "model": "gpt-test",
        "instructions": "system",
        "input": "user",
        "metadata": {"agent": "math_agent"},
    }


def test_gemini_provider_builds_generate_content_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "hosted-gemini-text"},
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(http_utils.urllib_request, "urlopen", fake_urlopen)

    provider = GeminiProvider(api_key="gemini-test-key")
    text = provider.generate(
        model="gemini-test",
        timeout_seconds=19,
        max_request_tokens=384,
        system_prompt="system",
        user_prompt="user",
        metadata={"agent": "critic_agent"},
    )

    assert text == "hosted-gemini-text"
    assert captured["timeout"] == 19
    assert "models/gemini-test:generateContent?key=gemini-test-key" in str(captured["url"])
    assert captured["body"] == {
        "system_instruction": {"parts": [{"text": "system"}]},
        "contents": [{"role": "user", "parts": [{"text": "user"}]}],
    }


def test_openrouter_provider_builds_chat_completions_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["auth"] = request.get_header("Authorization")
        header_items = dict(request.header_items())
        captured["referer"] = header_items.get("Http-referer")
        captured["title"] = header_items.get("X-title")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "hosted-openrouter-text",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(http_utils.urllib_request, "urlopen", fake_urlopen)

    provider = OpenRouterProvider(api_key="openrouter-test-key")
    text = provider.generate(
        model="openai/gpt-4.1-mini",
        timeout_seconds=21,
        max_request_tokens=320,
        system_prompt="system",
        user_prompt="user",
        metadata={"agent": "report_agent"},
    )

    assert text == "hosted-openrouter-text"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["timeout"] == 21
    assert captured["auth"] == "Bearer openrouter-test-key"
    assert captured["referer"] == "https://github.com/ECD5A/EllipticZero"
    assert captured["title"] == "EllipticZero Research Lab"
    assert captured["body"] == {
        "model": "openai/gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        "max_tokens": 320,
    }


def test_anthropic_provider_builds_messages_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["api_key"] = request.get_header("X-api-key")
        captured["version"] = request.get_header("Anthropic-version")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "content": [
                    {"type": "text", "text": "hosted-anthropic-text"},
                ]
            }
        )

    monkeypatch.setattr(http_utils.urllib_request, "urlopen", fake_urlopen)

    provider = AnthropicProvider(api_key="anthropic-test-key")
    text = provider.generate(
        model="claude-test",
        timeout_seconds=23,
        max_request_tokens=512,
        system_prompt="system",
        user_prompt="user",
        metadata={"agent": "strategy_agent"},
    )

    assert text == "hosted-anthropic-text"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["timeout"] == 23
    assert captured["api_key"] == "anthropic-test-key"
    assert captured["version"] == "2023-06-01"
    assert captured["body"] == {
        "model": "claude-test",
        "max_tokens": 512,
        "system": "system",
        "messages": [{"role": "user", "content": "user"}],
    }
