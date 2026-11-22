# ADR 006: Use Converse for the CLI and preserve streaming for the API

- Status: Accepted
- Decision date: 2026-11-22
- Source commit: `a797c88` — Use Converse for CLI inference while preserving API streaming
- Supersedes: [ADR 002](002-consume-bedrock-response-streams.md) for the CLI client and the streaming measurement/display portions of [ADR 003](003-measure-streaming-latency-and-display-live-output.md)

## Context

The commit explicitly separates complete CLI responses from API streaming.
The CLI previously exposed callbacks and chunk timing fields, while the HTTP API
already had its own resilient streaming generator. No additional rationale for
reversing CLI streaming is recorded in the commit message.

## Decision

Return `BedrockInferenceClient.generate(prompt)` to Boto3 Converse. Assemble text
from the completed message's text blocks and retain model ID, input/output/total
tokens, total client latency, and stop reason. Remove the callback parameter,
first-text latency, chunk timing model, arrival lists, and chunk counts.

Make `src/main.py` print the complete response once after generation returns,
then print metrics excluding response text. Keep the client's Nova Lite default,
existing inference parameters, SDK timeouts, retries, and runtime injection.
Propagate SDK inference failures.

Leave the API's ConverseStream path unchanged. Adapt CLI tests to complete
responses and keep streaming tests on the resilient API generator. Update project
guidance and document that Converse needs `bedrock:InvokeModel`, while API
streaming needs `bedrock:InvokeModelWithResponseStream`.

## Consequences

The CLI has a simpler completed-result interface and waits until generation
finishes before displaying text. It cannot measure first-token or chunk delivery
latency. The API retains incremental delivery, optional SSE metadata, and its
separate retry policy.

Both paths still expose token usage and stop reasons, but differ in model defaults,
inference parameters, resilience behavior, and result shape. Consumers using the
removed callback or chunk fields must adapt to the completed-result interface.
