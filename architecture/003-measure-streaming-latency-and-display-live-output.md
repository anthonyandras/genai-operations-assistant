# ADR 003: Measure streaming latency and display live CLI output

- Status: Partially superseded by [ADR 006](006-separate-cli-converse-from-api-streaming.md); the Nova Lite default and separate metrics output remain.
- Decision date: 2026-11-22
- Source commit: `5525f71` — Add streaming latency metrics and live CLI output
- Builds on: [ADR 002](002-consume-bedrock-response-streams.md)

## Context

The commit message calls for live CLI output and measurements of first-text
latency, chunk counts, arrivals, and intervals. Total request latency alone does
not describe when text is observed during a stream.

## Decision

Default the client to Nova Lite while retaining explicit model and environment
overrides. Print text through the callback as it arrives. Print inference metrics
afterward, excluding the complete response text to avoid repeating it.

Record nonempty text chunk arrival times relative to request start, time to the
first nonempty text chunk, chunk count, and intervals between arrivals. Associate
each timing with its text; an interval belongs to the later arriving chunk.
Use a monotonic client clock and deterministic fake-clock tests.

## Consequences

The CLI exposes observable delivery timing and supports examining model response
patterns. These are chunk measurements, not individual token timings or isolated
model compute measurements. Network delivery and callback execution affect them.
Recording text alongside timings also retains generated content in metrics.

## Subsequent changes

ADR 006 removes live CLI callbacks and all chunk metrics when returning to
Converse. Total latency, token metrics, the Nova Lite default, and excluding text
from the final printed metrics remain in effect.
