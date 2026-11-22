import pytest

from ops_assistant.server import main, parse_args, tls_config


@pytest.mark.parametrize("argv, version, port", [
    ([], "1", 8000),
    (["--http-version", "1"], "1", 8000),
    (["--http-version", "2"], "2", 8443),
    (["--http-version", "3", "--port", "9443"], "3", 9443),
])
def test_protocol_defaults(argv, version, port):
    _, args = parse_args(argv)
    assert args.http_version == version
    assert args.port == port


def test_default_uses_http1_without_tls(monkeypatch):
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    app = object()
    main(app, [])
    assert calls == [((app,), {"host": "127.0.0.1", "port": 8000, "http": "h11"})]


@pytest.mark.parametrize("version, quic", [("2", []), ("3", ["127.0.0.1:8443"])])
def test_tls_protocol_configuration(monkeypatch, version, quic):
    config_module = pytest.importorskip("hypercorn.config")
    monkeypatch.setattr(config_module.Config, "create_ssl_context", lambda self: None)
    _, args = parse_args(["--http-version", version])
    config = tls_config(args)
    assert config.bind == ["127.0.0.1:8443"]
    assert config.quic_bind == quic
    assert config.alpn_protocols == ["h2", "http/1.1"]


def test_missing_certificate_has_actionable_error(tmp_path, capsys):
    pytest.importorskip("hypercorn")
    with pytest.raises(SystemExit) as exc:
        main(object(), ["--http-version", "2", "--certfile", str(tmp_path / "missing.pem")])
    assert exc.value.code == 2
    assert "Unable to load TLS certificate/key" in capsys.readouterr().err
