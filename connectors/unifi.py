import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


def _session(api_key):
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({
        "X-API-KEY": api_key,
        "Accept": "application/json",
    })
    return s


class Unifi:
    def __init__(self, url, api_key, sites="ALL"):
        self.base = url.rstrip("/")
        self.session = _session(api_key)
        # sites: "ALL" or comma-separated site IDs
        self.site_filter = None if sites.upper() == "ALL" else [s.strip() for s in sites.split(",")]

    def _get(self, path, params=None):
        r = self.session.get(f"{self.base}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _get_sites(self):
        data = self._get("/v1/sites")
        sites = data.get("data", [])
        if self.site_filter:
            sites = [s for s in sites if s.get("siteId") in self.site_filter or s.get("name") in self.site_filter]
        return sites

    def get_devices(self):
        sites = self._get_sites()
        all_devices = []
        for site in sites:
            site_id = site.get("siteId") or site.get("id")
            try:
                data = self._get(f"/v1/sites/{site_id}/devices")
                for device in data.get("data", []):
                    device["_site_id"] = site_id
                    device["_site_name"] = site.get("name", site_id)
                    all_devices.append(device)
            except Exception as e:
                # log-friendly: caller handles errors
                raise RuntimeError(f"Failed to fetch devices for site {site_id}: {e}") from e
        return all_devices
