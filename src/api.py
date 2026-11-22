
import json
import os
from dataclasses import asdict
from functools import lru_cache

import anyio
import boto3
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from ops_assistant.resilient_stream import generate_resilient

app = FastAPI()

@lru_cache
def get_runtime():
    return boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )

MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon.nova-micro-v1:0",
)
STREAM_EVENT_METADATA = os.getenv("STREAM_EVENT_METADATA", "false").lower() == "true"


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000, pattern=r"\S")


def sse(event):
    payload = json.dumps(asdict(event))

    return (
        f"event: {event.kind}\n"
        f"data: {payload}\n\n"
    )


@app.post(
    "/generate",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/plain": {}, "text/event-stream": {}}}},
)
def generate(request: GenerateRequest, runtime=Depends(get_runtime)):
    async def events():
        # Boto3 blocks, so advance its iterator in a worker thread.
        stream = generate_resilient(runtime, MODEL_ID, request.prompt)
        try:
            async for event in iterate_in_threadpool(stream):
                if STREAM_EVENT_METADATA:
                    yield sse(event)
                elif event.kind == "text":
                    yield event.text
                elif event.kind == "error":
                    # Fail the transfer rather than mixing errors into model text.
                    raise RuntimeError(f"Generation failed: {event.code}")
        finally:
            # Also release the Bedrock stream if the HTTP client disconnects.
            with anyio.CancelScope(shield=True):
                await run_in_threadpool(stream.close)

    return StreamingResponse(
        events(),
        media_type="text/event-stream" if STREAM_EVENT_METADATA else "text/plain",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    from ops_assistant.server import main

    main(app)
