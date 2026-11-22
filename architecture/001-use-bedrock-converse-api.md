# ADR 001: Use the Bedrock Converse API for model inference

- Status: Accepted; the original shared-client inference mode was changed by [ADR 002](002-consume-bedrock-response-streams.md) and restored for the CLI by [ADR 006](006-separate-cli-converse-from-api-streaming.md).
- Decision date: 2026-11-21
- Source commit: `cae29c9` — initial revision

## Context

The initial application needed a Python client that could submit an operations
prompt to Amazon Bedrock and return usable text together with inference metrics.
The initial commit has no explanatory body; this context is reconstructed from
its implementation rather than an explicitly recorded rationale.

## Decision

Use Boto3's `bedrock-runtime.converse` operation behind `BedrockInferenceClient`.
Return a Pydantic `InferenceResult` containing text, model ID, input/output/total
token counts, elapsed client latency, and stop reason. Reject blank prompts.

Resolve the model and Region from constructor arguments or environment settings.
Initially default to Nova Micro in `us-east-1`, with 2,048 maximum output tokens
and temperature 0.5. Configure SDK connection/read timeouts and standard retries.
Accept an injected runtime so tests do not require AWS access.

## Consequences

Callers receive one completed response and wait for the request to finish.
AWS SDK details stay inside the client, while tests can use a fake runtime.
Client latency includes the request's network and SDK behavior, not just model
compute. The initial implementation does not retrieve operational evidence or
execute actions.

## Subsequent changes

ADR 002 temporarily replaces Converse with streaming. ADR 003 changes the client
default to Nova Lite. ADR 006 restores Converse for the CLI while the HTTP API
continues streaming.
