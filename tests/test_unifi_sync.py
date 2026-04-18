from sync import unifi_sync
from sync.unifi_sync import _extract_mac, _device_name


def test_extract_mac_from_top_level_fields():
    assert _extract_mac({"mac": "AA:BB:CC:DD:EE:FF"}) == "aa:bb:cc:dd:ee:ff"
    assert _extract_mac({"macAddress": "11:22:33:44:55:66"}) == "11:22:33:44:55:66"


def test_extract_mac_from_nested_fields():
    assert _extract_mac({"uidb": {"mac": "AA:00:00:00:00:01"}}) == "aa:00:00:00:00:01"
    assert _extract_mac({"system": {"mac": "AA:00:00:00:00:02"}}) == "aa:00:00:00:00:02"


def test_device_name_fallback_is_never_empty():
    name = _device_name({"_site_name": "SiteA", "hostId": "host-1"})
    assert name.startswith("unknown-device")
    assert "SiteA" in name
    assert "host-1" in name


def test_run_sets_mac_as_serial_on_create(monkeypatch):
    class FakeUnifi:
        def get_devices(self):
            return [{"mac": "aa:bb:cc:dd:ee:ff", "name": "AP-1", "model": "U7"}]

        def get_last_errors(self):
            return []

    class FakeSnipeit:
        def get_or_create_category(self, _):
            return 1

        def get_or_create_manufacturer(self, _):
            return 2

        def get_or_create_model(self, *_):
            return 3

        def get_hardware_by_serial(self, _):
            return None

        def create_hardware(self, payload):
            self.payload = payload
            return 123

        def update_hardware(self, *_):
            raise AssertionError("update_hardware should not be called")

    monkeypatch.setattr(unifi_sync.time, "sleep", lambda _: None)
    monkeypatch.setattr(unifi_sync.db, "log", lambda *args, **kwargs: None)
    monkeypatch.setattr(unifi_sync.db, "get_mapping", lambda *args, **kwargs: None)
    monkeypatch.setattr(unifi_sync.db, "set_mapping", lambda *args, **kwargs: None)

    snipeit = FakeSnipeit()
    items = unifi_sync.run(snipeit, FakeUnifi(), run_id=1)

    assert items == 1
    assert snipeit.payload["serial"] == "AA:BB:CC:DD:EE:FF"
    assert "asset_tag" not in snipeit.payload


def test_run_uses_serial_lookup_fallback(monkeypatch):
    class FakeUnifi:
        def get_devices(self):
            return [{"mac": "aa:bb:cc:dd:ee:ff", "name": "AP-1", "model": "U7"}]

        def get_last_errors(self):
            return []

    class FakeSnipeit:
        def __init__(self):
            self.updated = False

        def get_or_create_category(self, _):
            return 1

        def get_or_create_manufacturer(self, _):
            return 2

        def get_or_create_model(self, *_):
            return 3

        def get_hardware_by_serial(self, serial):
            assert serial == "AA:BB:CC:DD:EE:FF"
            return {"id": 777}

        def create_hardware(self, _):
            raise AssertionError("create_hardware should not be called")

        def update_hardware(self, asset_id, payload):
            self.updated = True
            assert asset_id == 777
            assert payload["serial"] == "AA:BB:CC:DD:EE:FF"

    monkeypatch.setattr(unifi_sync.time, "sleep", lambda _: None)
    monkeypatch.setattr(unifi_sync.db, "log", lambda *args, **kwargs: None)
    monkeypatch.setattr(unifi_sync.db, "get_mapping", lambda *args, **kwargs: None)
    monkeypatch.setattr(unifi_sync.db, "set_mapping", lambda *args, **kwargs: None)

    snipeit = FakeSnipeit()
    items = unifi_sync.run(snipeit, FakeUnifi(), run_id=1)

    assert items == 1
    assert snipeit.updated is True
