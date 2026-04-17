import msal
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPE = ["https://graph.microsoft.com/.default"]


def _session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


class Intune:
    def __init__(self, tenant_id, client_id, client_secret):
        self.app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        self.session = _session()

    def _token(self):
        # Try in-memory cache first; only hits the network if the token is expired or missing.
        result = self.app.acquire_token_silent(SCOPE, account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise RuntimeError(f"Intune auth failed: {result.get('error_description')}")
        return result["access_token"]

    def _get(self, url, params=None):
        token = self._token()
        r = self.session.get(
            url, params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def get_users(self):
        # Only active accounts; $select limits payload size.
        url = f"{GRAPH_BASE}/users"
        users = []
        while url:
            data = self._get(
                url,
                params={
                    "$filter": "accountEnabled eq true",
                    "$select": "id,displayName,givenName,surname,userPrincipalName,mail,employeeId",
                    "$top": 999,
                } if "?" not in url else None,
            )
            users.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return users

    def get_devices(self):
        url = f"{GRAPH_BASE}/deviceManagement/managedDevices"
        devices = []
        while url:
            # nextLink already contains all query params — don't add $top again.
            data = self._get(url, params={"$top": 999} if "?" not in url else None)
            devices.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return devices
