from connectors.snipeit import SnipeIT


def test_update_hardware_raises_on_api_error_status(monkeypatch):
    snipeit = SnipeIT("https://example.invalid", "token")

    def fake_patch(path, payload):
        assert path == "/hardware/42"
        assert payload == {"name": "AP-1"}
        return {"status": "error", "messages": "Asset not found"}

    monkeypatch.setattr(snipeit, "_patch", fake_patch)

    try:
        snipeit.update_hardware(42, {"name": "AP-1"})
        assert False, "Expected RuntimeError"
    except RuntimeError as e:
        assert "rejected hardware update" in str(e)


def test_update_hardware_accepts_success_status(monkeypatch):
    snipeit = SnipeIT("https://example.invalid", "token")

    def fake_patch(path, payload):
        assert path == "/hardware/7"
        assert payload == {"name": "AP-2"}
        return {"status": "success"}

    monkeypatch.setattr(snipeit, "_patch", fake_patch)

    snipeit.update_hardware(7, {"name": "AP-2"})
