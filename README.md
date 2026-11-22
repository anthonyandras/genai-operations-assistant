# GenAI Operations Assistant

Run commands from the repository root. Configure AWS credentials normally;
`AWS_REGION` defaults to `us-east-1` and `BEDROCK_MODEL_ID` defaults to
`amazon.nova-micro-v1:0` for the API.

## Select the HTTP protocol

The API launcher accepts `--http-version 1`, `2`, or `3`. HTTP/1.1 is the
default and needs no certificate. HTTP/2 and HTTP/3 use HTTPS and require TLS
certificates plus the optional server dependencies:

```sh
uv sync --extra http3
```

The `http3` extra includes Hypercorn for both HTTP/2 and HTTP/3.

| Option | Server | Default address | Transport |
| --- | --- | --- | --- |
| `1` (default) | Uvicorn | `http://127.0.0.1:8000` | HTTP/1.1 over TCP |
| `2` | Hypercorn | `https://127.0.0.1:8443` | HTTP/2 over TLS/TCP, HTTP/1.1 fallback |
| `3` | Hypercorn | `https://127.0.0.1:8443` | HTTP/3 over QUIC/UDP, HTTP/2 and HTTP/1.1 over TLS/TCP fallback |

Choose one launch command below. Stop the previous server before changing
modes on the same port. Use `--host` and `--port` to override the address.
These options select the client-to-API transport; Boto3's connection to
Bedrock and model chunk sizes are unaffected.

### HTTP/1.1 (default)

```sh
.venv/bin/python src/api.py
```

Equivalent explicit selection:

```sh
.venv/bin/python src/api.py --http-version 1
```

Test streaming from a second terminal:

```sh
curl --http1.1 -N http://127.0.0.1:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Give three safe diagnostic steps for elevated HTTP 500 errors."}'
```

### TLS setup for HTTP/2 and HTTP/3

Create a self-signed certificate for local development (requires OpenSSL).
Run once; rerunning replaces the key and certificate:

```sh
mkdir -p .certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout .certs/localhost-key.pem \
  -out .certs/localhost-cert.pem \
  -days 30 -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
chmod 600 .certs/localhost-key.pem
```

The launcher finds the default certificate files relative to the project
root. To use different files, pass `--certfile /path/to/cert.pem` and
`--keyfile /path/to/key.pem`. Missing or invalid TLS files produce a startup
error with setup guidance. Keep private keys out of Git; `.certs/` is ignored.

### HTTP/2

```sh
.venv/bin/python src/api.py --http-version 2
```

Request HTTP/2 and display the negotiated version after the streamed text:

```sh
curl --http2 --cacert .certs/localhost-cert.pem -N \
  https://127.0.0.1:8443/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Give three safe diagnostic steps for elevated HTTP 500 errors."}' \
  -w '\nHTTP version: %{http_version}\n'
```

Check that the printed version is `2`; `--http2` permits fallback.

### HTTP/3 over QUIC

```sh
.venv/bin/python src/api.py --http-version 3
```

Use an HTTP/3-capable curl build to require QUIC:

```sh
/opt/homebrew/opt/curl/bin/curl --http3-only \
  --cacert .certs/localhost-cert.pem -N \
  https://127.0.0.1:8443/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Give three safe diagnostic steps for elevated HTTP 500 errors."}' \
  -w '\nHTTP version: %{http_version}\n'
```

On macOS, `brew install curl` provides a separate curl installation; check
`/opt/homebrew/opt/curl/bin/curl --version` for `HTTP3`. The system curl may
lack it. Adjust the executable path if Homebrew is installed elsewhere.

The curl certificate paths above are relative to your terminal's current
directory. Run from the project root or pass an absolute certificate path.
For browser use, trust the development certificate locally or use a trusted
certificate. External hosting requires an appropriate bind address, a trusted
certificate, and TCP access; HTTP/3 additionally requires UDP access on the
chosen port. Hypercorn advertises QUIC availability using `Alt-Svc`.

The earlier `hypercorn.toml` remains available for direct Hypercorn launches;
it is independent of the launcher options:

```sh
.venv/bin/python -m hypercorn --config hypercorn.toml src/api.py:app
```

## Model text and optional SSE metadata

All protocol modes stream only model output as `text/plain` by default,
without event names, JSON wrappers, or metadata. To include server-sent
events (SSE), set `STREAM_EVENT_METADATA=true` at launch, for example:

```sh
STREAM_EVENT_METADATA=true .venv/bin/python src/api.py
STREAM_EVENT_METADATA=true .venv/bin/python src/api.py --http-version 2
STREAM_EVENT_METADATA=true .venv/bin/python src/api.py --http-version 3
```

Choose one of these commands. The option is read at startup; restart after
changing it. SSE mode returns `text/event-stream` with `start`, `text`, and
`complete` events, or an `error` event if generation fails. Each `text` event
contains an incremental chunk in its JSON `text` field. The `complete` event
includes token usage and the stop reason. Errors after streaming starts are
reported as SSE events rather than a new HTTP status.

In default text-only mode, generation failures terminate the transfer and
are logged on the server; error metadata is not appended to model output.
Once response headers have been sent, the HTTP status cannot be changed.

Clients must consume responses incrementally. `curl -N` disables output
buffering. Browser clients should use `fetch()` with a response body reader
and decode incoming bytes incrementally; in SSE mode, also parse frames
separated by a blank line. Calling `response.text()` or `response.json()`
waits for the complete response. Native `EventSource` uses GET and cannot
directly call this POST endpoint.

## Tests

Run without live AWS calls:

```sh
.venv/bin/python -m pytest
```
