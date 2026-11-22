
import os
import time
from collections.abc import Callable

import boto3
from botocore.config import Config
from pydantic import BaseModel, Field


class TextChunkTiming(BaseModel):
    text: str
    ms: float


class InferenceResult(BaseModel):
    text: str
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    stop_reason: str
    time_to_first_text_ms: float | None = None
    text_chunk_count: int = 0
    text_chunk_arrival_ms: list[TextChunkTiming] = Field(default_factory=list)
    text_chunk_intervals_ms: list[TextChunkTiming] = Field(default_factory=list)


class BedrockInferenceClient:
    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        runtime=None,   # intentional for testing purposes
    ):
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID",
            "amazon.nova-lite-v1:0",
        )

        self.runtime = runtime or boto3.client(
            "bedrock-runtime",
            region_name=region or os.getenv(
                "AWS_REGION", "us-east-1"
            ),
            config=Config(
                connect_timeout=5,
                read_timeout=60,
                retries={
                    "mode": "standard",
                    "max_attempts": 3,
                },
            ),
        )

    def generate(
        self,
        prompt: str,
        on_text: Callable[[str], None] | None = None,
    ) -> InferenceResult:
        """Consume a stream, measuring text arrivals before invoking the callback.

        Arrival times are relative to request start, measured at the client.
        Text chunks can contain multiple tokens. Callback work can delay
        consumption of subsequent chunks and contributes to total latency.
        Each interval is paired with the chunk arriving after that interval;
        the first nonempty chunk has no preceding chunk interval.
        """
        if not prompt.strip():
            raise ValueError("Prompt must not be empty")

        start = time.perf_counter()

        response = self.runtime.converse_stream(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={
                "maxTokens": 2048,
                "temperature": 0.5,
            },
        )

        stream = response["stream"]
        text_chunks = []
        text_arrivals_ms = []
        usage = None
        stop_reason = None
        try:
            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        if delta["text"]:
                            text_arrivals_ms.append((time.perf_counter() - start) * 1000)
                        text_chunks.append(delta["text"])
                        if on_text is not None:
                            on_text(delta["text"])
                elif "messageStop" in event:
                    stop_reason = event["messageStop"]["stopReason"]
                elif "metadata" in event:
                    usage = event["metadata"]["usage"]
        finally:
            stream.close()

        elapsed_ms = (time.perf_counter() - start) * 1000
        if usage is None or stop_reason is None:
            raise RuntimeError("Bedrock response stream ended without completion metadata")

        return InferenceResult(
            text="".join(text_chunks),
            model_id=self.model_id,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
            total_tokens=usage["totalTokens"],
            latency_ms=round(elapsed_ms, 2),
            stop_reason=stop_reason,
            time_to_first_text_ms=(
                round(text_arrivals_ms[0], 2) if text_arrivals_ms else None
            ),
            text_chunk_count=len(text_arrivals_ms),
            text_chunk_arrival_ms=[
                TextChunkTiming(text=text, ms=round(arrival, 2))
                for text, arrival in zip(
                    (chunk for chunk in text_chunks if chunk), text_arrivals_ms
                )
            ],
            text_chunk_intervals_ms=[
                TextChunkTiming(text=text, ms=round(current - previous, 2))
                for text, previous, current in zip(
                    [chunk for chunk in text_chunks if chunk][1:],
                    text_arrivals_ms,
                    text_arrivals_ms[1:],
                )
            ],
        )

