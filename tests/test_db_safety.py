import importlib


def _load_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import config
    import db

    importlib.reload(config)
    importlib.reload(db)
    db.init_db()
    return db


def test_only_one_running_sync_per_source(tmp_path, monkeypatch):
    db = _load_db(tmp_path, monkeypatch)

    run_id = db.begin_run("unifi")
    assert run_id is not None

    second = db.begin_run("unifi")
    assert second is None

    db.end_run(run_id, "success", 0)

    third = db.begin_run("unifi")
    assert third is not None


def test_zammad_links_are_idempotent(tmp_path, monkeypatch):
    db = _load_db(tmp_path, monkeypatch)

    assert not db.has_zammad_link(101, 202)

    db.add_zammad_link(101, 202)
    assert db.has_zammad_link(101, 202)

    db.add_zammad_link(101, 202)
    assert db.has_zammad_link(101, 202)
