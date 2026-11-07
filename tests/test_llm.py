"""Tests for the optional LLM theming step against a fake local endpoint."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kindle_clippings_tidy.llm import LLMConfig, LLMError, chat, theme_clippings
from kindle_clippings_tidy.parser import Clipping
from kindle_clippings_tidy.tidy import group_by_book

FAKE_REPLY = "### Theme: Asking better questions\n- Prompting is just asking a better question.\n"


class FakeOpenAIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        assert payload["model"] == "fake-model"
        assert payload["stream"] is False
        assert isinstance(payload["messages"], list)
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": FAKE_REPLY}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence test output
        pass


@pytest.fixture()
def fake_endpoint():
    server = HTTPServer(("127.0.0.1", 0), FakeOpenAIHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/v1/chat/completions"
    server.shutdown()


def make_section():
    from kindle_clippings_tidy.tidy import group_by_book as _group

    clippings = [
        Clipping(book="B", author="A", kind="highlight", text="Prompting is just asking a better question.", page="12"),
        Clipping(book="B", author="A", kind="bookmark", text="", page="20"),
    ]
    return _group(clippings)[0]


def test_chat_round_trip(fake_endpoint):
    result = chat(LLMConfig(endpoint=fake_endpoint, model="fake-model", timeout_seconds=10), "hi")
    assert result == FAKE_REPLY.strip()


def test_theme_clippings_skips_bookmarks(fake_endpoint):
    section = make_section()
    themes = theme_clippings(section, LLMConfig(endpoint=fake_endpoint, model="fake-model", timeout_seconds=10))
    assert themes is not None
    assert themes.startswith("## Themes")
    assert FAKE_REPLY in themes


def test_theme_clippings_returns_none_without_text(fake_endpoint):
    section = group_by_book(
        [Clipping(book="B", author="A", kind="bookmark", text="")]
    )[0]
    assert theme_clippings(section, LLMConfig(endpoint=fake_endpoint, model="fake-model")) is None


def test_unreachable_endpoint_raises_llm_error():
    config = LLMConfig(endpoint="http://127.0.0.1:1/v1/chat/completions", timeout_seconds=2)
    with pytest.raises(LLMError):
        chat(config, "hello")


def test_http_4xx_maps_to_llm_error():
    class Fake400Handler(FakeOpenAIHandler):
        def do_POST(self):
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = HTTPServer(("127.0.0.1", 0), Fake400Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = LLMConfig(endpoint=f"http://127.0.0.1:{port}/v1/chat/completions", timeout_seconds=10)
        with pytest.raises(LLMError) as excinfo:
            chat(config, "hello")
        assert "400" in str(excinfo.value)
    finally:
        server.shutdown()
