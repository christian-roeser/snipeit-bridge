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


def test_get_devices_flattens_wrapped_host_payload():
    unifi = Unifi("https://api.ui.com", "test-key")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {"data": [{"siteId": "site-a", "name": "A", "hostId": "host-a"}]}
        if path == "/v1/devices":
            return {
                "data": [
                    {
                        "hostId": "host-a",
                        "siteId": "site-a",
                        "devices": [
                            {"uidb": {"mac": "AA:AA:AA:AA:AA:01"}},
                            {"uidb": {"mac": "AA:AA:AA:AA:AA:02"}},
                        ],
                    }
                ]
            }
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    devices = unifi.get_devices()

    assert len(devices) == 2
    assert devices[0]["hostId"] == "host-a"
    assert devices[0]["_site_id"] == "site-a"


def test_site_filter_name_matching_is_case_insensitive_and_trimmed():
    unifi = Unifi("https://api.ui.com", "test-key", sites=" office  , 'warehouse' ")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {
                "data": [
                    {"siteId": "site-1", "name": "Office", "hostId": "host-1"},
                    {"siteId": "site-2", "name": "Warehouse", "hostId": "host-2"},
                    {"siteId": "site-3", "name": "Lab", "hostId": "host-3"},
                ]
            }
        if path == "/v1/devices":
            assert set(params["hostIds[]"]) == {"host-1", "host-2"}
            return {"data": []}
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    devices = unifi.get_devices()

    assert devices == []
    assert unifi.get_last_errors() == []


def test_site_filter_warns_when_no_sites_match():
    unifi = Unifi("https://api.ui.com", "test-key", sites="DoesNotExist")

    def fake_get(path, params=None):
        if path == "/v1/sites":
            return {"data": [{"siteId": "site-1", "name": "Office", "hostId": "host-1"}]}
        raise AssertionError(f"Unexpected path: {path}")

    unifi._get = fake_get

    devices = unifi.get_devices()

    assert devices == []
    assert "UNIFI_SITES filter matched no sites" in unifi.get_last_errors()
