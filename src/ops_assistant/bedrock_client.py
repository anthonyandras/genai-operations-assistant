
import os
import time
from collections.abc import Callable

import boto3
from botocore.config import Config
from pydantic import BaseModel


class InferenceResult(BaseModel):
    text: str
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    stop_reason: str


class BedrockInferenceClient:
    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        runtime=None,   # intentional for testing purposes
    ):
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID",
            "amazon.nova-micro-v1:0",
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
        """Consume a response stream, optionally forwarding each text delta."""
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
        usage = None
        stop_reason = None
        try:
            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
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
        )

