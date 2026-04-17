import time
import db


def run(snipeit, proxmox, run_id):
    items = 0
    try:
        assets = proxmox.get_all_assets()
        db.log(run_id, "INFO", f"Fetched {len(assets)} assets from Proxmox")
    except Exception as e:
        db.log(run_id, "ERROR", f"Failed to fetch Proxmox assets: {e}")
        raise

    for asset in assets:
        time.sleep(0.1)
        source_id = asset["source_id"]
        name = asset["name"]
        asset_type = asset["type"]

        asset_tag = f"PVE-{source_id.replace('/', '-').upper()}"

        try:
            if asset_type == "node":
                category_id = snipeit.get_or_create_category("Proxmox Node")
            elif asset_type == "vm":
                category_id = snipeit.get_or_create_category("Proxmox VM")
            else:
                category_id = snipeit.get_or_create_category("Proxmox Container")

            manufacturer_id = snipeit.get_or_create_manufacturer("Proxmox")
            model_id = snipeit.get_or_create_model(
                f"Proxmox {asset_type.capitalize()}", manufacturer_id, category_id
            )

            payload = {
                "name": name,
                "asset_tag": asset_tag,
                "model_id": model_id,
            }

            existing_id = db.get_mapping("proxmox", source_id)
            if existing_id is None:
                existing = snipeit.get_hardware_by_asset_tag(asset_tag)
                existing_id = existing["id"] if existing else None

            if existing_id:
                snipeit.update_hardware(existing_id, payload)
                db.set_mapping("proxmox", source_id, existing_id)
                db.log(run_id, "INFO", f"Updated Proxmox {asset_type} '{name}' (id={existing_id})")
            else:
                new_id = snipeit.create_hardware({**payload, "status_id": 1})
                if new_id:
                    db.set_mapping("proxmox", source_id, new_id)
                    db.log(run_id, "INFO", f"Created Proxmox {asset_type} '{name}' (id={new_id})")
                else:
                    db.log(run_id, "WARN", f"Failed to create Proxmox {asset_type} '{name}'")
                    continue

            items += 1
        except Exception as e:
            db.log(run_id, "ERROR", f"Error processing Proxmox {asset_type} '{name}': {e}")

    return items
