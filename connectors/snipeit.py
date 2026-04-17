import time
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


def _session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


class SnipeIT:
    def __init__(self, url, token):
        self.base = url.rstrip("/") + "/api/v1"
        self.session = _session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        # Per-instance cache for get_or_create_* — IDs are stable within one sync run.
        self._cache = {}

    def _request(self, method, path, **kwargs):
        url = f"{self.base}{path}"
        for _ in range(6):
            r = self.session.request(method, url, timeout=30, **kwargs)
            if r.status_code == 429:
                # Respect Retry-After header; default to 60s if missing.
                wait = int(r.headers.get("Retry-After", 60))
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    def _get(self, path, params=None):
        return self._request("GET", path, params=params)

    def _post(self, path, payload):
        return self._request("POST", path, json=payload)

    def _patch(self, path, payload):
        return self._request("PATCH", path, json=payload)

    def get_hardware_by_serial(self, serial):
        data = self._get("/hardware", params={"search": serial, "limit": 5})
        for item in data.get("rows", []):
            if item.get("serial") == serial:
                return item
        return None

    def get_hardware_by_asset_tag(self, tag):
        data = self._get("/hardware", params={"search": tag, "limit": 5})
        for item in data.get("rows", []):
            if item.get("asset_tag") == tag:
                return item
        return None

    def search_hardware(self, query):
        data = self._get("/hardware", params={"search": query, "limit": 50})
        return data.get("rows", [])

    def create_hardware(self, payload):
        result = self._post("/hardware", payload)
        return result.get("payload", {}).get("id")

    def update_hardware(self, asset_id, payload):
        self._patch(f"/hardware/{asset_id}", payload)

    def get_or_create_category(self, name, category_type="asset"):
        key = ("category", name)
        if key not in self._cache:
            data = self._get("/categories", params={"search": name, "limit": 10})
            for cat in data.get("rows", []):
                if cat["name"] == name:
                    self._cache[key] = cat["id"]
                    break
            else:
                result = self._post("/categories", {"name": name, "category_type": category_type})
                self._cache[key] = result.get("payload", {}).get("id")
        return self._cache[key]

    def get_or_create_manufacturer(self, name):
        key = ("manufacturer", name)
        if key not in self._cache:
            data = self._get("/manufacturers", params={"search": name, "limit": 10})
            for m in data.get("rows", []):
                if m["name"] == name:
                    self._cache[key] = m["id"]
                    break
            else:
                result = self._post("/manufacturers", {"name": name})
                self._cache[key] = result.get("payload", {}).get("id")
        return self._cache[key]

    def get_or_create_company(self, name):
        key = ("company", name)
        if key not in self._cache:
            data = self._get("/companies", params={"search": name, "limit": 10})
            for c in data.get("rows", []):
                if c["name"] == name:
                    self._cache[key] = c["id"]
                    break
            else:
                result = self._post("/companies", {"name": name})
                self._cache[key] = result.get("payload", {}).get("id")
        return self._cache[key]

    def get_user_by_username(self, username):
        data = self._get("/users", params={"search": username, "limit": 10})
        for user in data.get("rows", []):
            if user.get("username") == username:
                return user
        return None

    def create_user(self, payload):
        result = self._post("/users", payload)
        return result.get("payload", {}).get("id")

    def update_user(self, user_id, payload):
        self._patch(f"/users/{user_id}", payload)

    def get_or_create_model(self, name, manufacturer_id, category_id):
        key = ("model", name)
        if key not in self._cache:
            data = self._get("/models", params={"search": name, "limit": 10})
            for m in data.get("rows", []):
                if m["name"] == name:
                    self._cache[key] = m["id"]
                    break
            else:
                result = self._post("/models", {
                    "name": name,
                    "manufacturer_id": manufacturer_id,
                    "category_id": category_id,
                })
                self._cache[key] = result.get("payload", {}).get("id")
        return self._cache[key]
