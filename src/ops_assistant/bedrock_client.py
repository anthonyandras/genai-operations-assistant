
import os
import time

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

    def generate(self, prompt: str) -> InferenceResult:
        if not prompt.strip():
            raise ValueError("Prompt must not be empty")

        start = time.perf_counter()

        response = self.runtime.converse(
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

        elapsed_ms = (
            time.perf_counter() - start
        ) * 1000

        content = response["output"]["message"]["content"]

        text = "".join(
            block.get("text", "")
            for block in content
        )

        usage = response["usage"]

        return InferenceResult(
            text=text,
            model_id=self.model_id,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
            total_tokens=usage["totalTokens"],
            latency_ms=round(elapsed_ms, 2),
            stop_reason=response["stopReason"],
        )

