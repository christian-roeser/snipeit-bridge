import importlib
import pytest


def _load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-password")
    monkeypatch.setenv("SNIPEIT_URL", "https://example.invalid")
    monkeypatch.setenv("SNIPEIT_TOKEN", "test-token")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("WEB_CONCURRENCY", "1")

    import config
    import db
    import app

    importlib.reload(config)
    importlib.reload(db)
    app_module = importlib.reload(app)

    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["RATELIMIT_ENABLED"] = False
    return app_module


def test_sync_returns_warning_if_already_running(tmp_path, monkeypatch):
    app_module = _load_app(tmp_path, monkeypatch)

    monkeypatch.setattr(app_module.db, "begin_run", lambda source: None)

    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    response = client.post("/sync/intune", follow_redirects=True)

    assert response.status_code == 200
    assert b"already running" in response.data


def test_public_asset_api_hides_internal_errors(tmp_path, monkeypatch):
    app_module = _load_app(tmp_path, monkeypatch)

    def _fail():
        raise RuntimeError("sensitive backend error")

    monkeypatch.setattr(app_module, "_snipeit", _fail)

    client = app_module.app.test_client()
    response = client.get("/api/assets?search=laptop")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Asset search failed"}


def test_public_asset_api_rejects_too_long_query(tmp_path, monkeypatch):
    app_module = _load_app(tmp_path, monkeypatch)
    monkeypatch.setenv("ASSET_API_MAX_SEARCH_LENGTH", "10")

    import config
    importlib.reload(config)
    app_module.config.ASSET_API_MAX_SEARCH_LENGTH = 10

    client = app_module.app.test_client()
    response = client.get("/api/assets?search=12345678901")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Search query too long"}


def test_multi_worker_requires_non_memory_rate_limit_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app-multi.db"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-password")
    monkeypatch.setenv("SNIPEIT_URL", "https://example.invalid")
    monkeypatch.setenv("SNIPEIT_TOKEN", "test-token")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")

    import config
    import db
    import app

    importlib.reload(config)
    importlib.reload(db)
    with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI"):
        importlib.reload(app)
