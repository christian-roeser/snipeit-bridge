import importlib


def test_security_defaults_are_hardened(monkeypatch):
    monkeypatch.delenv("PROXMOX_VERIFY_SSL", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)

    import config

    module = importlib.reload(config)

    assert module.config.PROXMOX_VERIFY_SSL is True
    assert module.config.SESSION_COOKIE_SECURE is True
