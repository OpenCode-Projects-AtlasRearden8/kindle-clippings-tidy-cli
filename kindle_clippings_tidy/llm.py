"""Optional theme grouping via a local OpenAI-compatible chat endpoint.

Works with Ollama (``http://localhost:11434/v1/chat/completions``), llama.cpp
server, LM Studio, LocalAI, vLLM, or anything else that speaks the OpenAI
chat-completions shape. No API key is required for local endpoints; if the
endpoint needs one, read it from the ``OPENAI_API_KEY`` environment variable
at runtime (never stored in files).
"""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_ENDPOINT = "http://localhost:11434/v1/chat/completions"
DEFAULT_MODEL = "llama3.2"

MAX_CHARS_PER_CLIPPING = 400
MAX_CHARS_PER_PROMPT = 12000

SYSTEM_PROMPT = (
    "You are a friendly reading assistant. You organize Kindle highlights into "
    "themes. Reply with Markdown only: a short intro line, then one '### Theme "
    "Name' section per theme, each listing the matching quotes (shortened with "
    "leading/trailing ellipses if needed) under '- ' bullets. Never invent "
    "quotes that are not in the input. Plain, warm language."
)


@dataclass
class LLMConfig:
    endpoint: str = DEFAULT_ENDPOINT
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 120.0


@dataclass
class LLMError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _clip_line(clip) -> str:
    detail = []
    if clip.page:
        detail.append(f"page {clip.page}")
    if clip.location:
        detail.append(f"location {clip.location}")
    tail = f" ({', '.join(detail)})" if detail else ""
    text = " ".join(clip.text.split())
    if len(text) > MAX_CHARS_PER_CLIPPING:
        text = text[: MAX_CHARS_PER_CLIPPING - 1].rstrip() + "\u2026"
    return f"[{clip.kind}] {text}{tail}"


def build_prompt(geo_title: str, clippings: list) -> str:
    items: list[str] = []
    total = 0
    for clip in clippings:
        line = _clip_line(clip)
        if total + len(line) > MAX_CHARS_PER_PROMPT:
            items.append("... (more highlights omitted to fit the model context)")
            break
        items.append(line)
        total += len(line)
    listing = "\n".join(items) if items else "(no text clippings)"
    return (
        f"Group the following clippings from the book '{geo_title}' into 3-6 "
        "themes. Use the exact quote text for bullets.\n\n" + listing
    )


def chat(config: LLMConfig, user_prompt: str) -> str:
    """POST one chat completion to an OpenAI-compatible local endpoint."""
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    request = urllib.request.Request(
        config.endpoint, data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(
            f"LLM endpoint returned HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMError(
            f"Could not reach LLM endpoint {config.endpoint}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM endpoint returned non-JSON output: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {body!r}"[:300]) from exc
    if not isinstance(content, str):
        raise LLMError("LLM response 'content' was not a string")
    return content.strip()


def theme_clippings(section, config: LLMConfig) -> str | None:
    """Generate a '## Themes' Markdown section for one book's clippings."""
    textful = [c for c in section.clippings if c.kind in ("highlight", "note") and c.text]
    if not textful:
        return None
    prompt = build_prompt(section.title, textful)
    reply = chat(config, prompt)
    return "## Themes\n\n" + reply + "\n"
