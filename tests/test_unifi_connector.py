import pytest

from connectors.unifi import Unifi


def test_get_devices_skips_failing_sites_when_others_succeed():
    unifi = Unifi("https://api.ui.com", "test-key")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {
                "data": [
                    {"siteId": "site-ok", "name": "OK"},
                    {"siteId": "site-404", "name": "Broken"},
                ]
            }
        if path == "/v1/sites/site-ok/devices":
            return {"data": [{"mac": "aa:bb:cc:dd:ee:ff"}]}
        if path == "/v1/sites/site-404/devices":
            raise RuntimeError("404 Client Error: Not Found")
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    devices = unifi.get_devices()

    assert len(devices) == 1
    assert devices[0]["_site_id"] == "site-ok"
    errors = unifi.get_last_errors()
    assert len(errors) == 1
    assert "site-404" in errors[0]


def test_get_devices_raises_when_all_sites_fail():
    unifi = Unifi("https://api.ui.com", "test-key")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {"data": [{"siteId": "site-404", "name": "Broken"}]}
        if path == "/v1/sites/site-404/devices":
            raise RuntimeError("404 Client Error: Not Found")
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    with pytest.raises(RuntimeError, match="Failed to fetch devices for site site-404"):
        unifi.get_devices()
