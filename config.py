import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SNIPEIT_URL = os.getenv("SNIPEIT_URL", "")
    SNIPEIT_TOKEN = os.getenv("SNIPEIT_TOKEN", "")

    INTUNE_TENANT_ID = os.getenv("INTUNE_TENANT_ID", "")
    INTUNE_CLIENT_ID = os.getenv("INTUNE_CLIENT_ID", "")
    INTUNE_CLIENT_SECRET = os.getenv("INTUNE_CLIENT_SECRET", "")

    UNIFI_URL = os.getenv("UNIFI_URL", "https://api.ui.com")
    UNIFI_API_KEY = os.getenv("UNIFI_API_KEY", "")
    UNIFI_SITES = os.getenv("UNIFI_SITES", "ALL")

    PROXMOX_URL = os.getenv("PROXMOX_URL", "")
    PROXMOX_TOKEN_ID = os.getenv("PROXMOX_TOKEN_ID", "")
    PROXMOX_TOKEN_SECRET = os.getenv("PROXMOX_TOKEN_SECRET", "")
    PROXMOX_VERIFY_SSL = os.getenv("PROXMOX_VERIFY_SSL", "false").lower() == "true"

    ZAMMAD_URL = os.getenv("ZAMMAD_URL", "")
    ZAMMAD_TOKEN = os.getenv("ZAMMAD_TOKEN", "")

    DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
    DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    DB_PATH = os.getenv("DB_PATH", "snipeit_bridge.db")

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))


config = Config()
