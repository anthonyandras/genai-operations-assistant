# ADR 002: Consume Bedrock response streams with optional text callbacks

- Status: Superseded for `BedrockInferenceClient` by [ADR 006](006-separate-cli-converse-from-api-streaming.md).
- Decision date: 2026-11-21
- Source commit: `88bf929` — Update application to handle streaming responses from the model
- Builds on: [ADR 001](001-use-bedrock-converse-api.md)

## Context

The application was extended to handle incremental model output. The commit
subject records this intent; its diff defines the callback, aggregation, and
cleanup behavior. It contains no separate design rationale.

## Decision

Replace the client's `converse` call with `converse_stream`. Consume text deltas,
collect the message stop reason and usage metadata, and retain the completed
`InferenceResult` return value. Provide an optional `on_text` callback that is
invoked as text arrives.

Close the stream in `finally`, including when iteration or a callback fails.
Propagate failures and reject streams missing usage or stop metadata rather than
returning a seemingly successful partial result.

## Consequences

Callers can observe output before the full response finishes, while existing
callers can still request a completed result. They now depend on event iteration
and stream lifecycle handling. Callback work can delay subsequent consumption.
An interrupted request can already have delivered partial text to its callback.

## Subsequent changes

ADR 006 removes this interface from the CLI client. The separate HTTP streaming
path introduced by [ADR 004](004-provide-a-streaming-api-with-selectable-http-protocols.md)
continues to use ConverseStream with its own generation-event interface.
