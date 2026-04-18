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
