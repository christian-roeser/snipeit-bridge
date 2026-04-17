import time
import db

# Name of the Zammad ticket custom field that holds a Snipe-IT asset ID
ZAMMAD_ASSET_FIELD = "snipeit_asset_id"


def run(snipeit, zammad, run_id):
    items = 0
    try:
        tickets = zammad.get_tickets_with_asset_field(ZAMMAD_ASSET_FIELD)
        db.log(run_id, "INFO", f"Found {len(tickets)} Zammad tickets with asset references")
    except Exception as e:
        db.log(run_id, "ERROR", f"Failed to fetch Zammad tickets: {e}")
        raise

    for ticket in tickets:
        time.sleep(0.1)
        ticket_id = ticket.get("id")
        ticket_title = ticket.get("title", f"Ticket #{ticket_id}")
        asset_id = ticket.get(ZAMMAD_ASSET_FIELD)

        if not asset_id:
            continue

        try:
            asset_id = int(asset_id)
        except (TypeError, ValueError):
            db.log(run_id, "WARN", f"Ticket #{ticket_id}: invalid asset_id '{asset_id}', skipping")
            continue

        try:
            # marker (idempotency check) vs ticket_ref (human-readable line written to notes)
            ticket_ref = f"[Zammad #{ticket_id}] {ticket_title}"
            # Read existing notes to append (avoid duplicate entries)
            existing = snipeit.search_hardware(str(asset_id))
            current_notes = ""
            for hw in existing:
                if hw.get("id") == asset_id:
                    current_notes = hw.get("notes") or ""
                    break

            # The marker string is the idempotency key — if it's already in the
            # notes the ticket was linked in a previous sync run; skip to avoid duplicates.
            marker = f"[Zammad #{ticket_id}]"
            if marker not in current_notes:
                new_notes = (current_notes + "\n" + ticket_ref).strip()
                snipeit.update_hardware(asset_id, {"notes": new_notes})
                db.log(run_id, "INFO", f"Linked Zammad ticket #{ticket_id} to Snipe-IT asset #{asset_id}")
                items += 1
            else:
                db.log(run_id, "INFO", f"Ticket #{ticket_id} already linked to asset #{asset_id}, skipping")
        except Exception as e:
            db.log(run_id, "ERROR", f"Error linking ticket #{ticket_id} to asset #{asset_id}: {e}")

    return items
