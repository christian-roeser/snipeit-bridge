import pytest

from connectors.unifi import Unifi


def test_get_devices_uses_host_ids_and_maps_site_metadata():
    unifi = Unifi("https://api.ui.com", "test-key")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {
                "data": [
                    {"siteId": "site-ok", "name": "OK", "hostId": "host-1"},
                    {"siteId": "site-ok-2", "name": "OK2", "meta": {"hostId": "host-2"}},
                ]
            }
        if path == "/v1/devices":
            assert params is not None
            assert set(params["hostIds[]"]) == {"host-1", "host-2"}
            return {
                "data": [
                    {"mac": "aa:bb:cc:dd:ee:ff", "hostId": "host-1"},
                    {"mac": "11:22:33:44:55:66", "hostId": "host-2"},
                ]
            }
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    devices = unifi.get_devices()

    assert len(devices) == 2
    assert devices[0]["_site_id"] == "site-ok"
    assert devices[1]["_site_id"] == "site-ok-2"
    errors = unifi.get_last_errors()
    assert len(errors) == 0


def test_get_devices_raises_when_device_endpoint_fails():
    unifi = Unifi("https://api.ui.com", "test-key")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {"data": [{"siteId": "site-a", "name": "A", "hostId": "host-a"}]}
        if path == "/v1/devices":
            raise RuntimeError("401 Client Error: Unauthorized")
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    with pytest.raises(RuntimeError, match="Failed to fetch Unifi devices"):
        unifi.get_devices()


def test_get_devices_raises_if_no_host_ids_present():
    unifi = Unifi("https://api.ui.com", "test-key")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {"data": [{"siteId": "site-a", "name": "A"}]}
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    with pytest.raises(RuntimeError, match="No valid UniFi hostIds"):
        unifi.get_devices()
    assert "Missing hostId for site site-a" in unifi.get_last_errors()[0]
