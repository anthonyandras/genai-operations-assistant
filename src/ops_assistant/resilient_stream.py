
import random
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ReadTimeoutError,
)


@dataclass(frozen=True)
class GenerationEvent:
    kind: Literal["start", "text", "complete", "error"]
    attempt_id: str
    text: str = ""
    code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None


RETRYABLE_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelNotReadyException",
    "ModelTimeoutException",
    "ModelStreamErrorException",
}


def retryable(exc: Exception) -> bool:
    if isinstance(
        exc, (ReadTimeoutError, ConnectionClosedError)
    ):
        return True

    if isinstance(exc, ClientError):
        return (
            exc.response.get("Error", {}).get("Code")
            in RETRYABLE_CODES
        )

    return False


def generate_resilient(
    runtime,
    model_id: str,
    prompt: str,
    max_attempts: int = 3,
) -> Iterator[GenerationEvent]:
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")

    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    attempt_id = str(uuid4())
    emitted_text = False

    yield GenerationEvent("start", attempt_id)

    for attempt in range(max_attempts):
        stream = None
        stop_reason = None
        usage = {}

        try:
            response = runtime.converse_stream(
                modelId=model_id,
                messages=[{
                    "role": "user",
                    "content": [{"text": prompt}],
                }],
                inferenceConfig={
                    "maxTokens": 300,
                    "temperature": 0.2,
                },
            )

            stream = response["stream"]

            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    text = delta.get("text", "")

                    if text:
                        emitted_text = True
                        yield GenerationEvent(
                            "text", attempt_id, text=text
                        )

                elif "messageStop" in event:
                    stop_reason = event["messageStop"].get(
                        "stopReason"
                    )

                elif "metadata" in event:
                    usage = event["metadata"].get(
                        "usage", {}
                    )

            if stop_reason is None:
                raise RuntimeError(
                    "Stream ended without messageStop"
                )

            yield GenerationEvent(
                "complete",
                attempt_id,
                input_tokens=usage.get("inputTokens"),
                output_tokens=usage.get("outputTokens"),
                stop_reason=stop_reason,
            )
            return

        except Exception as exc:
            can_retry = (
                not emitted_text
                and retryable(exc)
                and attempt < max_attempts - 1
            )

            if can_retry:
                delay = min(0.5 * (2 ** attempt), 4)
                delay += random.uniform(0, 0.25)
                time.sleep(delay)
                continue

            yield GenerationEvent(
                "error",
                attempt_id,
                code=(
                    "GENERATION_INTERRUPTED"
                    if emitted_text
                    else "GENERATION_FAILED"
                ),
            )
            return

        finally:
            if stream is not None:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()
