from ops_assistant.bedrock_client import BedrockInferenceClient


class FakeRuntime:
    def converse_stream(self, **kwargs):
        return {"stream": self.events()}

    @staticmethod
    def events():
        yield {"contentBlockDelta": {"delta": {"text": "Hello "}}}
        yield {"contentBlockDelta": {"delta": {"text": "world"}}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": 12,
                    "outputTokens": 3,
                    "totalTokens": 15,
                }
            }
        }


def test_stream_assembles_text_and_usage():
    client = BedrockInferenceClient(
        model_id="test-model",
        runtime=FakeRuntime(),
    )
    chunks = []

    result = client.generate("Say hello", on_text=chunks.append)

    assert chunks == ["Hello ", "world"]
    assert result.text == "".join(chunks) == "Hello world"
    assert result.input_tokens == 12
    assert result.output_tokens == 3
    assert result.total_tokens == 15
    assert result.stop_reason == "end_turn"
