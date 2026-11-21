
import pytest

from ops_assistant.bedrock_client import (
    BedrockInferenceClient,
)


class FakeBedrockRuntime:
    def __init__(self):
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)

        return {
            "output": {
                "message": {
                    "content": [
                        {"text": "Inspect deployment changes."}
                    ]
                }
            },
            "usage": {
                "inputTokens": 20,
                "outputTokens": 8,
                "totalTokens": 28,
            },
            "stopReason": "end_turn",
        }


def test_generate_extracts_response():
    runtime = FakeBedrockRuntime()

    client = BedrockInferenceClient(
        model_id="test-model",
        runtime=runtime,
    )

    result = client.generate(
        "Diagnose an incident."
    )

    assert result.text == (
        "Inspect deployment changes."
    )
    assert result.input_tokens == 20
    assert result.output_tokens == 8
    assert result.total_tokens == 28
    assert result.stop_reason == "end_turn"
    assert result.latency_ms >= 0

    assert runtime.calls[0]["modelId"] == "test-model"


def test_empty_prompt_rejected():
    client = BedrockInferenceClient(
        model_id="test-model",
        runtime=FakeBedrockRuntime(),
    )

    with pytest.raises(ValueError):
        client.generate("   ")
