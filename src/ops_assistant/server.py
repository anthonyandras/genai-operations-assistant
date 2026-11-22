"""Command-line server selection for the streaming API."""

import argparse
import asyncio
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the Bedrock streaming API")
    parser.add_argument("--http-version", choices=("1", "2", "3"), default="1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, help="Default: 8000 for HTTP/1, 8443 for HTTP/2 or HTTP/3")
    parser.add_argument("--certfile", type=Path, default=PROJECT_ROOT / ".certs/localhost-cert.pem")
    parser.add_argument("--keyfile", type=Path, default=PROJECT_ROOT / ".certs/localhost-key.pem")
    args = parser.parse_args(argv)
    if args.port is None:
        args.port = 8000 if args.http_version == "1" else 8443
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return parser, args


def tls_config(args):
    from hypercorn.config import Config

    config = Config()
    host = f"[{args.host}]" if ":" in args.host else args.host
    address = f"{host}:{args.port}"
    config.bind = [address]
    config.quic_bind = [address] if args.http_version == "3" else []
    config.certfile = str(args.certfile)
    config.keyfile = str(args.keyfile)
    config.alpn_protocols = ["h2", "http/1.1"]
    config.accesslog = "-"
    # Fail before starting lifespan tasks if TLS files are missing or invalid.
    config.create_ssl_context()
    return config


def main(app, argv=None):
    parser, args = parse_args(argv)
    if args.http_version == "1":
        import uvicorn

        uvicorn.run(app, host=args.host, port=args.port, http="h11")
        return

    try:
        from hypercorn.asyncio import serve

        if args.http_version == "3":
            import aioquic  # noqa: F401 - check the optional QUIC dependency
    except ImportError:
        parser.error("HTTP/2 and HTTP/3 require: uv sync --extra http3")

    try:
        config = tls_config(args)
    except (OSError, ValueError) as exc:
        parser.error(f"Unable to load TLS certificate/key: {exc}. See README.md for setup.")
    asyncio.run(serve(app, config))
