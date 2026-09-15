"""Provider-agnostic structured-JSON client.

The case compiler must not be welded to one vendor. Whichever key is present in .env is
detected and used; adding a different one later changes nothing above this file.

Every provider here is called over plain HTTPS with `requests`, so no vendor SDK has to
be installed on a machine that is already short on RAM and disk.

If no key at all is present, `NullExtractor` keeps the pipeline running on a rule-based
path. Quality is lower and it is labelled as such in the output, but a missing key
degrades the system instead of breaking it.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from app import config


@dataclass
class Provider:
    name: str
    env_key: str
    url: str
    default_model: str
    style: str  # "openai" | "anthropic" | "gemini"


# Ordered by preference. Anthropic first (native tool-use gives schema-guaranteed JSON),
# then OpenAI-compatible endpoints, then Gemini.
PROVIDERS: list[Provider] = [
    Provider("anthropic", "ANTHROPIC_API_KEY",
             "https://api.anthropic.com/v1/messages", "claude-sonnet-5", "anthropic"),
    Provider("openai", "OPENAI_API_KEY",
             "https://api.openai.com/v1/chat/completions", "gpt-4o-mini", "openai"),
    Provider("groq", "GROQ_API_KEY",
             "https://api.groq.com/openai/v1/chat/completions",
             "openai/gpt-oss-120b", "openai"),
    Provider("openrouter", "OPENROUTER_API_KEY",
             "https://openrouter.ai/api/v1/chat/completions",
             "google/gemini-2.5-flash", "openai"),
    Provider("deepseek", "DEEPSEEK_API_KEY",
             "https://api.deepseek.com/v1/chat/completions", "deepseek-chat", "openai"),
    Provider("mistral", "MISTRAL_API_KEY",
             "https://api.mistral.ai/v1/chat/completions", "magistral-medium-latest", "openai"),
    Provider("together", "TOGETHER_API_KEY",
             "https://api.together.xyz/v1/chat/completions",
             "meta-llama/Llama-3.3-70B-Instruct-Turbo", "openai"),
    Provider("gemini", "GEMINI_API_KEY",
             "https://generativelanguage.googleapis.com/v1beta/models", "gemini-2.5-flash",
             "gemini"),
]


def detect_provider() -> tuple[Provider, str] | None:
    """Return the first configured provider, honouring an explicit LLM_PROVIDER override."""
    forced = os.getenv("LLM_PROVIDER", "").strip().lower()
    candidates = PROVIDERS
    if forced:
        candidates = [p for p in PROVIDERS if p.name == forced] or PROVIDERS

    for provider in candidates:
        key = os.getenv(provider.env_key, "").strip()
        if key:
            return provider, key
    return None


def available() -> bool:
    return detect_provider() is not None


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of a model response that may be fenced or prefaced."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, depth = None, 0
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}" and start is not None:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    raise ValueError(f"no JSON object in response: {text[:200]}")


class LLMClient:
    """Thin structured-output wrapper over whichever provider is configured."""

    def __init__(self, provider: Provider | None = None, key: str | None = None,
                 model: str | None = None, timeout: int = 120):
        if provider is None:
            found = detect_provider()
            if found is None:
                raise RuntimeError(
                    "No LLM key found. Set one of: "
                    + ", ".join(p.env_key for p in PROVIDERS)
                )
            provider, key = found
        self.provider = provider
        self.key = key or os.getenv(provider.env_key, "")
        self.model = model or os.getenv("LLM_MODEL", "").strip() or provider.default_model
        self.timeout = timeout
        self._session = requests.Session()

    @property
    def label(self) -> str:
        return f"{self.provider.name}:{self.model}"

    def complete_json(self, system: str, user: str, schema: dict,
                      max_tokens: int = 3000) -> dict[str, Any]:
        style = self.provider.style
        if style == "anthropic":
            # Native tool-use already guarantees the shape.
            return self._anthropic(system, user, schema, max_tokens)

        # Everyone else gets the schema spelled out in the prompt. Plain JSON mode only
        # guarantees *valid* JSON, not *our* JSON: without this the model happily invents
        # its own key names and every extracted field silently lands as null.
        user = f"{user}\n\n{self._schema_instruction(schema)}"
        if style == "gemini":
            return self._gemini(system, user, schema, max_tokens)
        return self._openai(system, user, schema, max_tokens)

    @staticmethod
    def _schema_instruction(schema: dict) -> str:
        props = schema.get("properties", {})
        required = schema.get("required", [])
        lines = [
            "Return a single JSON object with EXACTLY these keys and no others:",
        ]
        for name, spec in props.items():
            kind = spec.get("type", "string")
            if isinstance(kind, list):
                kind = "/".join(k for k in kind)
            if spec.get("enum"):
                kind = "one of: " + ", ".join(str(e) for e in spec["enum"])
            note = spec.get("description", "")
            flag = " (required)" if name in required else ""
            lines.append(f'  "{name}": {kind}{flag}  - {note}')
        lines.append(
            "Use null for a scalar you cannot fill and [] for a list you cannot fill. "
            "Do not rename, nest, merge or add keys. Output JSON only, no prose."
        )
        return "\n".join(lines)

    # --- backends -------------------------------------------------------------------

    def _post(self, url: str, headers: dict, payload: dict, attempts: int = 5) -> dict:
        """POST with backoff on rate limits and transient server errors.

        Without this, a 429 partway through a benchmark run silently degrades the
        compiler to its rule-based path, and the resulting drop in case quality gets
        attributed to whichever ASR model happened to be next in the queue. An
        infrastructure hiccup must never be reportable as a model result.
        """
        last = ""
        for attempt in range(attempts):
            try:
                resp = self._session.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last = f"network error: {exc}"
                if attempt == attempts - 1:
                    break
                time.sleep(min(2 ** attempt, 30))
                continue

            if resp.status_code == 200:
                return resp.json()

            last = f"{self.provider.name} HTTP {resp.status_code}: {resp.text[:300]}"

            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after") or \
                    resp.headers.get("Retry-After") or ""
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = min(2 ** attempt, 30)
                time.sleep(min(max(wait, 1.0), 60.0) + 0.5)
                continue

            if 500 <= resp.status_code < 600:
                time.sleep(min(2 ** attempt, 30))
                continue

            raise RuntimeError(last)

        raise RuntimeError(last or "request failed after retries")

    def _anthropic(self, system, user, schema, max_tokens) -> dict:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [{
                "name": "emit_case",
                "description": "Emit the structured case.",
                "input_schema": schema,
            }],
            "tool_choice": {"type": "tool", "name": "emit_case"},
        }
        data = self._post(self.provider.url, {
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, payload)
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return block["input"]
        raise ValueError("anthropic returned no tool_use block")

    def _openai(self, system, user, schema, max_tokens) -> dict:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            data = self._post(self.provider.url,
                              {"Authorization": f"Bearer {self.key}"}, payload)
        except RuntimeError as exc:
            # Some OpenAI-compatible hosts reject json_object or max_tokens; retry plain.
            if "response_format" in str(exc) or "max_tokens" in str(exc):
                payload.pop("response_format", None)
                payload["max_completion_tokens"] = payload.pop("max_tokens", max_tokens)
                data = self._post(self.provider.url,
                                  {"Authorization": f"Bearer {self.key}"}, payload)
            else:
                raise
        return _extract_json(data["choices"][0]["message"]["content"])

    def _gemini(self, system, user, schema, max_tokens) -> dict:
        url = f"{self.provider.url}/{self.model}:generateContent?key={self.key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        data = self._post(url, {"content-type": "application/json"}, payload)
        parts = data["candidates"][0]["content"]["parts"]
        return _extract_json("".join(p.get("text", "") for p in parts))


def describe_setup() -> str:
    found = detect_provider()
    if found is None:
        return ("no LLM key configured - the compiler will fall back to rule-based "
                "extraction (lower quality, labelled as such in the output)")
    provider, _ = found
    model = os.getenv("LLM_MODEL", "").strip() or provider.default_model
    return f"LLM: {provider.name} ({model}) via {provider.env_key}"


def all_clients(timeout: int = 120) -> list["LLMClient"]:
    """One client per configured provider, in preference order.

    Used for failover: if the primary is rate-limited or down, the next key takes over
    rather than the pipeline silently dropping to rule-based extraction.
    """
    forced = os.getenv("LLM_PROVIDER", "").strip().lower()
    clients: list[LLMClient] = []
    for provider in PROVIDERS:
        key = os.getenv(provider.env_key, "").strip()
        if not key:
            continue
        if forced and provider.name != forced:
            continue
        try:
            clients.append(LLMClient(provider=provider, key=key, timeout=timeout))
        except Exception:
            continue
    return clients
