import time
import secrets
import db


def run(snipeit, intune, run_id):
    items = 0
    items += _sync_users(snipeit, intune, run_id)
    items += _sync_devices(snipeit, intune, run_id)
    return items


def _sync_devices(snipeit, intune, run_id):
    items = 0
    try:
        devices = intune.get_devices()
        db.log(run_id, "INFO", f"Fetched {len(devices)} devices from Intune")
    except Exception as e:
        db.log(run_id, "ERROR", f"Failed to fetch Intune devices: {e}")
        raise

    for device in devices:
        time.sleep(0.1)
        serial = device.get("serialNumber", "").strip()
        name = device.get("deviceName") or device.get("displayName") or serial
        manufacturer = device.get("manufacturer") or "Unknown"
        model_name = device.get("model") or "Unknown"

        if not serial:
            db.log(run_id, "WARN", f"Skipping device '{name}' — no serial number")
            continue

        try:
            category_id = snipeit.get_or_create_category("Intune Device")
            manufacturer_id = snipeit.get_or_create_manufacturer(manufacturer)
            model_id = snipeit.get_or_create_model(model_name, manufacturer_id, category_id)

            payload = {
                "name": name,
                "serial": serial,
                "model_id": model_id,
            }

            # Check local DB cache first; fall back to Snipe-IT API only on first
            # encounter to avoid one extra API call per device on every sync run.
            existing_id = db.get_mapping("intune", serial)
            if existing_id is None:
                existing = snipeit.get_hardware_by_serial(serial)
                existing_id = existing["id"] if existing else None

            if existing_id:
                snipeit.update_hardware(existing_id, payload)
                db.set_mapping("intune", serial, existing_id)
                db.log(run_id, "INFO", f"Updated asset '{name}' (serial={serial}, id={existing_id})")
            else:
                new_id = snipeit.create_hardware({**payload, "status_id": 1})
                if new_id:
                    db.set_mapping("intune", serial, new_id)
                    db.log(run_id, "INFO", f"Created asset '{name}' (serial={serial}, id={new_id})")
                else:
                    db.log(run_id, "WARN", f"Failed to create asset '{name}' — no ID returned")
                    continue

            items += 1
        except Exception as e:
            db.log(run_id, "ERROR", f"Error processing '{name}' (serial={serial}): {e}")

    return items


def _sync_users(snipeit, intune, run_id):
    items = 0
    try:
        users = intune.get_users()
        db.log(run_id, "INFO", f"Fetched {len(users)} active users from Intune")
    except Exception as e:
        db.log(run_id, "ERROR", f"Failed to fetch Intune users: {e}")
        raise

    for user in users:
        time.sleep(0.1)
        upn = (user.get("userPrincipalName") or "").strip().lower()
        if not upn:
            db.log(run_id, "WARN", "Skipping user — no userPrincipalName")
            continue

        display = user.get("displayName") or upn
        first = user.get("givenName") or display.split()[0]
        last = user.get("surname") or (display.split()[-1] if " " in display else "")
        email = user.get("mail") or upn
        employee_num = user.get("employeeId") or ""

        try:
            existing = snipeit.get_user_by_username(upn)

            payload = {
                "first_name": first,
                "last_name": last,
                "username": upn,
                "email": email,
                "employee_num": employee_num,
                "locale": "de-DE",
                # activated=false: user exists for asset assignment but cannot log in.
                "activated": False,
            }

            if existing:
                snipeit.update_user(existing["id"], payload)
                db.log(run_id, "INFO", f"Updated user '{upn}' (id={existing['id']})")
            else:
                # Snipe-IT requires a password even for inactive accounts.
                payload["password"] = secrets.token_urlsafe(24)
                payload["password_confirmation"] = payload["password"]
                new_id = snipeit.create_user(payload)
                if new_id:
                    db.log(run_id, "INFO", f"Created user '{upn}' (id={new_id})")
                else:
                    db.log(run_id, "WARN", f"Failed to create user '{upn}' — no ID returned")
                    continue

            items += 1
        except Exception as e:
            db.log(run_id, "ERROR", f"Error processing user '{upn}': {e}")

    return items
