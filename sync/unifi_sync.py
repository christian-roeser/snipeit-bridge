import time
import db


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
        mac = (device.get("mac") or device.get("macAddress") or "").strip().lower()
        name = device.get("name") or device.get("hostname") or mac
        model_name = device.get("model") or device.get("productModel") or "Unifi Device"
        device_type = device.get("type") or "network"

        if not mac:
            db.log(run_id, "WARN", f"Skipping device '{name}' — no MAC address")
            continue

        asset_tag = f"UNIFI-{mac.replace(':', '').upper()}"

        try:
            category_id = snipeit.get_or_create_category(f"Unifi {device_type.capitalize()}")
            manufacturer_id = snipeit.get_or_create_manufacturer("Ubiquiti")
            model_id = snipeit.get_or_create_model(model_name, manufacturer_id, category_id)

            payload = {
                "name": name,
                "asset_tag": asset_tag,
                "model_id": model_id,
            }

            existing_id = db.get_mapping("unifi", mac)
            if existing_id is None:
                existing = snipeit.get_hardware_by_asset_tag(asset_tag)
                existing_id = existing["id"] if existing else None

            if existing_id:
                snipeit.update_hardware(existing_id, payload)
                db.set_mapping("unifi", mac, existing_id)
                db.log(run_id, "INFO", f"Updated Unifi device '{name}' (mac={mac}, id={existing_id})")
            else:
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
