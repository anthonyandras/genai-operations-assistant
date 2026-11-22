import pytest
from botocore.exceptions import EventStreamError

from ops_assistant.bedrock_client import BedrockInferenceClient


class FakeStream:
    def __init__(self, events):
        self.events = events
        self.closed = False

    def __iter__(self):
        for event in self.events:
            if isinstance(event, Exception):
                raise event
            yield event

    def close(self):
        self.closed = True


class FakeBedrockRuntime:
    def __init__(self, events=None):
        self.calls = []
        self.stream = FakeStream(events if events is not None else [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Inspect "}}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "deployment changes."}}},
            {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"toolUse": {"input": "{}"}}}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 20, "outputTokens": 8, "totalTokens": 28}}},
        ])

    def converse_stream(self, **kwargs):
        self.calls.append(kwargs)
        return {"stream": self.stream}


def test_generate_extracts_response():
    runtime = FakeBedrockRuntime()
    client = BedrockInferenceClient(model_id="test-model", runtime=runtime)
    result = client.generate("Diagnose an incident.")

    assert result.text == "Inspect deployment changes."
    assert result.model_id == "test-model"
    assert result.input_tokens == 20
    assert result.output_tokens == 8
    assert result.total_tokens == 28
    assert result.stop_reason == "end_turn"
    assert result.latency_ms >= 0
    assert runtime.stream.closed
    assert runtime.calls == [{
        "modelId": "test-model",
        "messages": [{"role": "user", "content": [{"text": "Diagnose an incident."}]}],
        "inferenceConfig": {"maxTokens": 2048, "temperature": 0.5},
    }]


def test_generate_forwards_text_as_it_arrives():
    runtime = FakeBedrockRuntime()
    client = BedrockInferenceClient(runtime=runtime)
    chunks = []

    def on_text(text):
        print(f"Received text chunk: {text}")
        assert not runtime.stream.closed
        chunks.append(text)

    result = client.generate("Diagnose an incident.", on_text=on_text)
    assert chunks == ["Inspect ", "deployment changes."]
    assert result.text == "".join(chunks)


def test_empty_prompt_rejected():
    runtime = FakeBedrockRuntime()
    client = BedrockInferenceClient(runtime=runtime)
    with pytest.raises(ValueError):
        client.generate("   ")
    assert not runtime.calls


def test_stream_error_propagates_and_closes_stream():
    error = EventStreamError(
        {"Error": {"Code": "modelStreamErrorException", "Message": "Stream failed"}},
        "ConverseStream",
    )
    runtime = FakeBedrockRuntime([error])
    client = BedrockInferenceClient(runtime=runtime)
    with pytest.raises(EventStreamError):
        client.generate("Diagnose an incident.")
    assert runtime.stream.closed


@pytest.mark.parametrize("events", [
    [],
    [{"messageStop": {"stopReason": "end_turn"}}],
    [{"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}}}],
])
def test_incomplete_stream_rejected(events):
    runtime = FakeBedrockRuntime(events)
    client = BedrockInferenceClient(runtime=runtime)
    with pytest.raises(RuntimeError, match="completion metadata"):
        client.generate("Diagnose an incident.")
    assert runtime.stream.closed


def test_callback_error_closes_stream():
    runtime = FakeBedrockRuntime()
    client = BedrockInferenceClient(runtime=runtime)

    def on_text(text):
        raise ValueError("Callback failed")

    with pytest.raises(ValueError, match="Callback failed"):
        client.generate("Diagnose an incident.", on_text=on_text)
    assert runtime.stream.closed


def test_text_arrival_measurements(monkeypatch):
    clock = iter([10.0, 10.125, 10.375, 10.5])
    monkeypatch.setattr(
        "ops_assistant.bedrock_client.time.perf_counter", lambda: next(clock)
    )
    client = BedrockInferenceClient(runtime=FakeBedrockRuntime())

    result = client.generate("Diagnose an incident.")

    assert result.time_to_first_text_ms == 125.0
    assert result.text_chunk_count == 2
    metrics = result.model_dump(exclude={"text"})
    assert metrics["text_chunk_arrival_ms"] == [
        {"text": "Inspect ", "ms": 125.0},
        {"text": "deployment changes.", "ms": 375.0},
    ]
    assert metrics["text_chunk_intervals_ms"] == [
        {"text": "deployment changes.", "ms": 250.0},
    ]
    assert result.latency_ms == 500.0


@pytest.mark.parametrize("texts", [[], [""], ["", "Hello"]])
def test_empty_and_single_text_chunk_measurements(texts):
    events = [
        {"contentBlockDelta": {"delta": {"text": text}}}
        for text in texts
    ] + [
        {"messageStop": {"stopReason": "end_turn"}},
        {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}}},
    ]
    client = BedrockInferenceClient(runtime=FakeBedrockRuntime(events))

    result = client.generate("Hello")

    assert result.text_chunk_count == sum(bool(text) for text in texts)
    assert len(result.text_chunk_arrival_ms) == result.text_chunk_count
    assert [chunk.text for chunk in result.text_chunk_arrival_ms] == [
        text for text in texts if text
    ]
    assert result.text_chunk_intervals_ms == []
    if any(texts):
        assert result.time_to_first_text_ms is not None
        assert result.time_to_first_text_ms >= 0
    else:
        assert result.time_to_first_text_ms is None
