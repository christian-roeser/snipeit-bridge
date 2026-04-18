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
        self._last_errors = []

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

    @staticmethod
    def _extract_host_id(site):
        if not isinstance(site, dict):
            return None
        for key in ("hostId", "host_id"):
            if site.get(key):
                return site.get(key)
        meta = site.get("meta") if isinstance(site.get("meta"), dict) else {}
        for key in ("hostId", "host_id"):
            if meta.get(key):
                return meta.get(key)
        return None

    def get_devices(self):
        sites = self._get_sites()
        self._last_errors = []
        if not sites:
            return []

        host_ids = []
        host_to_site = {}
        for site in sites:
            host_id = self._extract_host_id(site)
            if host_id:
                host_ids.append(host_id)
                host_to_site[host_id] = {
                    "site_id": site.get("siteId") or site.get("id") or "",
                    "site_name": site.get("name") or (site.get("siteId") or site.get("id") or ""),
                }
            else:
                site_id = site.get("siteId") or site.get("id") or "unknown"
                self._last_errors.append(f"Missing hostId for site {site_id}")

        if not host_ids:
            raise RuntimeError("No valid UniFi hostIds found for selected sites")

        all_devices = []
        next_token = None
        while True:
            params = {
                "hostIds[]": host_ids,
                "pageSize": "200",
            }
            if next_token:
                params["nextToken"] = next_token

            try:
                data = self._get("/v1/devices", params=params)
            except Exception as e:
                raise RuntimeError(f"Failed to fetch Unifi devices: {e}") from e

            rows = data.get("data", []) if isinstance(data, dict) else []
            for device in rows:
                device_host_id = device.get("hostId") or device.get("host_id")
                site_info = host_to_site.get(device_host_id, {})
                device["_site_id"] = site_info.get("site_id") or device.get("siteId") or device.get("site_id") or ""
                device["_site_name"] = site_info.get("site_name") or device["_site_id"]
                all_devices.append(device)

            next_token = data.get("nextToken") if isinstance(data, dict) else None
            if not next_token:
                break

        return all_devices

    def get_last_errors(self):
        return list(self._last_errors)
