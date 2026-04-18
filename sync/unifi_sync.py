import time
import db


def _extract_mac(device):
    candidates = [
        device.get("mac"),
        device.get("macAddress"),
        device.get("primaryMac"),
        device.get("reportedMac"),
        (device.get("uidb") or {}).get("mac") if isinstance(device.get("uidb"), dict) else None,
        (device.get("system") or {}).get("mac") if isinstance(device.get("system"), dict) else None,
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def _device_name(device):
    name = device.get("name") or device.get("hostname") or device.get("displayName")
    if isinstance(name, str) and name.strip():
        return name.strip()
    site_name = device.get("_site_name") or device.get("_site_id") or "unknown-site"
    host_id = device.get("hostId") or device.get("host_id") or "unknown-host"
    return f"unknown-device ({site_name}/{host_id})"


def run(snipeit, unifi, run_id):
    items = 0
    try:
        devices = unifi.get_devices()
        for msg in unifi.get_last_errors():
            db.log(run_id, "WARN", msg)
        db.log(run_id, "INFO", f"Fetched {len(devices)} devices from Unifi")
    except Exception as e:
        db.log(run_id, "ERROR", f"Failed to fetch Unifi devices: {e}")
        raise

    for device in devices:
        time.sleep(0.1)
        mac = _extract_mac(device)
        name = _device_name(device)
        model_name = device.get("model") or device.get("productModel") or "Unifi Device"
        device_type = device.get("type") or "network"

        if not mac:
            db.log(run_id, "WARN", f"Skipping device '{name}' — no MAC address")
            continue

        serial = mac.upper()

        try:
            category_id = snipeit.get_or_create_category(f"Unifi {device_type.capitalize()}")
            manufacturer_id = snipeit.get_or_create_manufacturer("Ubiquiti")
            model_id = snipeit.get_or_create_model(model_name, manufacturer_id, category_id)

            payload = {
                "name": name,
                "serial": serial,
                "model_id": model_id,
            }

            existing_id = db.get_mapping("unifi", mac)
            if existing_id is None:
                existing = snipeit.get_hardware_by_serial(serial)
                existing_id = existing["id"] if existing else None

            if existing_id:
                try:
                    snipeit.update_hardware(existing_id, payload)
                    db.set_mapping("unifi", mac, existing_id)
                    db.log(run_id, "INFO", f"Updated Unifi device '{name}' (mac={mac}, id={existing_id})")
                except Exception:
                    # Mapping may reference an asset that was deleted in Snipe-IT.
                    existing_id = None

            if not existing_id:
                new_id = snipeit.create_hardware({**payload, "status_id": 1})
                if new_id:
                    db.set_mapping("unifi", mac, new_id)
                    db.log(run_id, "INFO", f"Created Unifi device '{name}' (mac={mac}, id={new_id})")
                else:
                    db.log(run_id, "WARN", f"Failed to create Unifi device '{name}'")
                    continue

            items += 1
        except Exception as e:
            db.log(run_id, "ERROR", f"Error processing Unifi device '{name}' (mac={mac}): {e}")

    return items
