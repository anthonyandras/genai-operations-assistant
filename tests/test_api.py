import asyncio
import json
import threading

import pytest

import api


@pytest.mark.parametrize("metadata", [False, True])
def test_endpoint_sends_text_before_generation_completes(monkeypatch, metadata):
    monkeypatch.setattr(api, "STREAM_EVENT_METADATA", metadata)
    release = threading.Event()
    closed = threading.Event()
    chunks = []

    class Runtime:
        def converse_stream(self, **kwargs):
            def events():
                try:
                    yield {"contentBlockDelta": {"delta": {"text": "Hello "}}}
                    assert release.wait(timeout=2), "HTTP layer buffered the first text"
                    yield {"contentBlockDelta": {"delta": {"text": "world"}}}
                    yield {"messageStop": {"stopReason": "end_turn"}}
                    yield {"metadata": {"usage": {"inputTokens": 2, "outputTokens": 3}}}
                finally:
                    closed.set()
            return {"stream": events()}

    async def run():
        sent_request = False

        async def receive():
            nonlocal sent_request
            if not sent_request:
                sent_request = True
                return {"type": "http.request", "body": json.dumps({"prompt": "Hello"}).encode()}
            await asyncio.Event().wait()

        async def send(message):
            if message["type"] == "http.response.start":
                assert message["status"] == 200
                media_type = b"text/event-stream" if metadata else b"text/plain"
                assert dict(message["headers"])[b"content-type"].startswith(media_type)
            elif message["type"] == "http.response.body" and message.get("body"):
                text = message["body"].decode()
                chunks.append(text)
                if "Hello " in text:
                    assert not closed.is_set()
                    release.set()

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/generate", "raw_path": b"/generate", "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "server": ("test", 80), "client": ("test", 1234),
        }
        await asyncio.wait_for(api.app(scope, receive, send), timeout=5)

    api.app.dependency_overrides[api.get_runtime] = Runtime
    try:
        asyncio.run(run())
    finally:
        release.set()
        api.app.dependency_overrides.clear()

    if metadata:
        assert [chunk.splitlines()[0] for chunk in chunks] == [
            "event: start", "event: text", "event: text", "event: complete"
        ]
        assert json.loads(chunks[-1].split("data: ")[1])["output_tokens"] == 3
    else:
        assert chunks == ["Hello ", "world"]
    assert closed.is_set()
