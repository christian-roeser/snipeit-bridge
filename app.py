from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify,
)
from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo

import db
import config as cfg
from config import config
from connectors.snipeit import SnipeIT
from connectors.intune import Intune
from connectors.unifi import Unifi
from connectors.proxmox import Proxmox
from connectors.zammad import Zammad
from sync import intune_sync, unifi_sync, proxmox_sync, zammad_sync

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

LOCAL_TZ = ZoneInfo("Europe/Berlin")


@app.template_filter("localtime")
def _localtime(iso):
    if not iso:
        return ""
    return datetime.fromisoformat(iso).astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")


@app.template_filter("duration")
def _duration(start_iso, end_iso):
    if not start_iso or not end_iso:
        return ""
    delta = datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    return f"{secs // 60}m {secs % 60}s"


db.init_db()

SOURCES = ["intune", "unifi", "proxmox", "zammad"]


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def _snipeit():
    # Factory instead of a module-level singleton — ensures a fresh requests.Session
    # per sync call and avoids stale connections across requests.
    return SnipeIT(config.SNIPEIT_URL, config.SNIPEIT_TOKEN)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (request.form.get("username") == config.DASHBOARD_USER and
                request.form.get("password") == config.DASHBOARD_PASSWORD):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    connector_status = {}
    for source in SOURCES:
        run = db.get_last_run(source)
        last_success = db.get_last_successful_run(source) if (run and run["status"] != "success") else None
        connector_status[source] = {
            "last_run": dict(run) if run else None,
            "last_success": dict(last_success) if last_success else None,
            "configured": _is_configured(source),
        }
    return render_template("dashboard.html", connector_status=connector_status)


def _is_configured(source):
    if source == "intune":
        return bool(config.INTUNE_TENANT_ID and config.INTUNE_CLIENT_ID and config.INTUNE_CLIENT_SECRET)
    if source == "unifi":
        return bool(config.UNIFI_URL and config.UNIFI_API_KEY)
    if source == "proxmox":
        return bool(config.PROXMOX_URL and config.PROXMOX_TOKEN_ID and config.PROXMOX_TOKEN_SECRET)
    if source == "zammad":
        return bool(config.ZAMMAD_URL and config.ZAMMAD_TOKEN)
    return False


@app.route("/sync/<source>", methods=["POST"])
@login_required
def sync(source):
    if source not in SOURCES:
        flash(f"Unknown source: {source}", "danger")
        return redirect(url_for("dashboard"))

    if not config.SNIPEIT_URL or not config.SNIPEIT_TOKEN:
        flash("Snipe-IT is not configured", "danger")
        return redirect(url_for("dashboard"))

    run_id = db.begin_run(source)
    items = 0
    error = None

    try:
        snipeit = _snipeit()
        if source == "intune":
            intune = Intune(config.INTUNE_TENANT_ID, config.INTUNE_CLIENT_ID, config.INTUNE_CLIENT_SECRET)
            items = intune_sync.run(snipeit, intune, run_id)
        elif source == "unifi":
            unifi = Unifi(config.UNIFI_URL, config.UNIFI_API_KEY, config.UNIFI_SITES)
            items = unifi_sync.run(snipeit, unifi, run_id)
        elif source == "proxmox":
            proxmox = Proxmox(
                config.PROXMOX_URL, config.PROXMOX_TOKEN_ID,
                config.PROXMOX_TOKEN_SECRET, config.PROXMOX_VERIFY_SSL
            )
            items = proxmox_sync.run(snipeit, proxmox, run_id)
        elif source == "zammad":
            zammad = Zammad(config.ZAMMAD_URL, config.ZAMMAD_TOKEN)
            items = zammad_sync.run(snipeit, zammad, run_id)

        db.end_run(run_id, "success", items)
    except Exception as e:
        error = str(e)
        db.log(run_id, "ERROR", f"Unhandled error: {e}")
        db.end_run(run_id, "error", items, error)

    return redirect(url_for("dashboard"))


@app.route("/history")
@login_required
def history():
    runs = db.get_runs()
    return render_template("history.html", runs=runs)


@app.route("/history/<int:run_id>/logs")
@login_required
def run_logs(run_id):
    logs = db.get_logs(run_id)
    return render_template("logs.html", logs=logs, run_id=run_id)


@app.route("/config")
@login_required
def show_config():
    def mask(val):
        if not val:
            return "(not set)"
        if len(val) <= 8:
            return "***"
        return val[:4] + "***" + val[-4:]

    items = {
        "Snipe-IT URL": config.SNIPEIT_URL or "(not set)",
        "Snipe-IT Token": mask(config.SNIPEIT_TOKEN),
        "Intune Tenant ID": config.INTUNE_TENANT_ID or "(not set)",
        "Intune Client ID": config.INTUNE_CLIENT_ID or "(not set)",
        "Intune Client Secret": mask(config.INTUNE_CLIENT_SECRET),
        "Unifi URL": config.UNIFI_URL or "(not set)",
        "Unifi API Key": mask(config.UNIFI_API_KEY),
        "Unifi Sites": config.UNIFI_SITES or "ALL",
        "Proxmox URL": config.PROXMOX_URL or "(not set)",
        "Proxmox Token ID": config.PROXMOX_TOKEN_ID or "(not set)",
        "Proxmox Token Secret": mask(config.PROXMOX_TOKEN_SECRET),
        "Proxmox Verify SSL": str(config.PROXMOX_VERIFY_SSL),
        "Zammad URL": config.ZAMMAD_URL or "(not set)",
        "Zammad Token": mask(config.ZAMMAD_TOKEN),
        "Dashboard User": config.DASHBOARD_USER,
        "DB Path": config.DB_PATH,
    }
    return render_template("config.html", items=items)


@app.route("/api/assets")
# No @login_required — Zammad's External Data Source feature calls this without
# session cookies. Keep it read-only (search only, no writes).
def api_assets():
    """Public endpoint consumed by Zammad as External Data Source."""
    query = request.args.get("search", "").strip()
    if not query or not config.SNIPEIT_URL or not config.SNIPEIT_TOKEN:
        return jsonify([])
    try:
        snipeit = _snipeit()
        results = snipeit.search_hardware(query)
        payload = []
        for hw in results[:50]:
            label_parts = [hw.get("name") or ""]
            serial = hw.get("serial") or ""
            if serial:
                label_parts.append(f"SN: {serial}")
            model = (hw.get("model") or {}).get("name") if isinstance(hw.get("model"), dict) else hw.get("model")
            if model:
                label_parts.append(model)
            payload.append({
                "value": hw["id"],
                "label": " | ".join(filter(None, label_parts)),
            })
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT)
