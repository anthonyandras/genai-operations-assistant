# ADR 004: Provide a streaming API with selectable HTTP protocols

- Status: Accepted
- Decision date: 2026-11-22
- Source commit: `4583218` — Add streaming API with selectable HTTP protocols

## Context

The commit message introduces a streaming API, optional event metadata, retries
before output, and selectable HTTP protocols. A client-facing stream requires
explicit response serialization, failure handling, and transport configuration.

## Decision

Expose FastAPI `POST /generate`, validating a nonblank prompt of 1–8,000
characters. Use a cached Boto3 runtime and a separate `generate_resilient`
generator calling ConverseStream. Advance its blocking iterator in worker
threads and close it when the HTTP iterator finishes or is closed.

Stream plain model text by default. With `STREAM_EVENT_METADATA=true`, serialize
server-sent events containing `start`, `text`, `complete`, or `error` generation
events. Completion carries input/output token usage and stop reason. Plain-text
failures terminate the transfer; SSE failures produce an error event.

Permit up to three application attempts for selected transient failures, with
exponential backoff and jitter, only before any model text has been emitted.
After text, report interruption instead of silently replaying the answer.

Default to loopback HTTP/1.1 using Uvicorn. Support HTTP/2 over TLS/TCP through
Hypercorn and HTTP/3 over QUIC/UDP through its optional HTTP/3 dependencies.
Retain TCP fallback in TLS modes, validate TLS files before startup, and keep
local certificates out of Git. The launcher accepts protocol, host, port, and
certificate options; `hypercorn.toml` also supports direct Hypercorn launches.

The API defaults to Nova Micro, 300 maximum output tokens, and temperature 0.2.

## Consequences

HTTP clients receive incremental text without adopting SSE unless they need
structured lifecycle events. After headers are sent, stream errors cannot change
the HTTP status. There is no generation resume mechanism.

HTTP/1.1 needs no local TLS setup; HTTP/2 and HTTP/3 require certificates and extra
dependencies. QUIC additionally requires a compatible client and reachable UDP.
Selecting a client transport does not change the Boto3-to-Bedrock connection.

The local prototype has no API authentication or application rate/concurrency
limits. Loopback binding is the default, not a substitute for access controls
when externally deployed. Blocking reads may delay disconnect cleanup, and SDK
retries are separate from the application retry loop.

## Subsequent changes

[ADR 006](006-separate-cli-converse-from-api-streaming.md) preserves this streaming
API while changing only the CLI inference interface.
