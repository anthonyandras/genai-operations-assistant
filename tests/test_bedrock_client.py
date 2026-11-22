import pytest
from botocore.exceptions import ClientError

from ops_assistant.bedrock_client import BedrockInferenceClient


class FakeBedrockRuntime:
    def __init__(self, content=None, error=None):
        self.calls = []
        self.content = content if content is not None else [
            {"text": "Inspect "},
            {"toolUse": {"toolUseId": "test", "name": "test", "input": {}}},
            {"text": "deployment changes."},
        ]
        self.error = error

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "output": {"message": {"role": "assistant", "content": self.content}},
            "usage": {"inputTokens": 20, "outputTokens": 8, "totalTokens": 28},
            "stopReason": "end_turn",
        }


def test_generate_extracts_complete_response(monkeypatch):
    clock = iter([10.0, 10.5])
    monkeypatch.setattr(
        "ops_assistant.bedrock_client.time.perf_counter", lambda: next(clock)
    )
    runtime = FakeBedrockRuntime()
    client = BedrockInferenceClient(model_id="test-model", runtime=runtime)

    result = client.generate("Diagnose an incident.")

    assert result.model_dump() == {
        "text": "Inspect deployment changes.",
        "model_id": "test-model",
        "input_tokens": 20,
        "output_tokens": 8,
        "total_tokens": 28,
        "stop_reason": "end_turn",
        "latency_ms": 500.0,
    }
    assert runtime.calls == [{
        "modelId": "test-model",
        "messages": [{"role": "user", "content": [{"text": "Diagnose an incident."}]}],
        "inferenceConfig": {"maxTokens": 2048, "temperature": 0.5},
    }]


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_empty_prompt_rejected(prompt):
    runtime = FakeBedrockRuntime()
    client = BedrockInferenceClient(runtime=runtime)
    with pytest.raises(ValueError, match="Prompt must not be empty"):
        client.generate(prompt)
    assert not runtime.calls


def test_service_error_propagates():
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}}, "Converse"
    )
    client = BedrockInferenceClient(runtime=FakeBedrockRuntime(error=error))
    with pytest.raises(ClientError) as exc:
        client.generate("Diagnose an incident.")
    assert exc.value is error


@pytest.mark.parametrize("content", [[], [{"text": ""}], [{"toolUse": {"input": {}}}]])
def test_response_without_text(content):
    client = BedrockInferenceClient(runtime=FakeBedrockRuntime(content=content))
    result = client.generate("Hello")
    assert result.text == ""
    assert result.total_tokens == 28
