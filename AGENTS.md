# Project guidance

This project is a Python operations assistant using Amazon Bedrock.

## Layout

- Application code lives in `src/ops_assistant/`.
- The command-line example lives in `src/main.py`.
- Tests live in `tests/`.
- Dependencies are declared in `pyproject.toml` and locked in `uv.lock`.

## Validation

Run the test suite from the repository root:

```sh
.venv/bin/python -m pytest
```

## Bedrock conventions

- Use `converse_stream` for inference.
- Close response streams on success and failure.
- Preserve token usage and stop reasons in completed results.
- Propagate inference and callback failures; reject incomplete streams.
- Keep optional text callbacks usable for displaying text as it arrives.

## Testing and scope

- Inject fake Bedrock runtimes in unit tests; do not make live AWS calls.
- Make fake streams reflect the event structure and cleanup behavior expected by the client.
- Preserve existing public interfaces unless the requested task requires a change.
- Keep changes focused on the requested work.
