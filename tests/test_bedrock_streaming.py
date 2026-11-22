from ops_assistant.resilient_stream import generate_resilient


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
    events = list(generate_resilient(FakeRuntime(), "test-model", "Say hello"))

    assert events[0].kind == "start"
    assert [event.text for event in events if event.kind == "text"] == ["Hello ", "world"]
    assert events[-1].kind == "complete"
    assert events[-1].input_tokens == 12
    assert events[-1].output_tokens == 3
    assert events[-1].stop_reason == "end_turn"
