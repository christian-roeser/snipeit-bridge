import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import urllib3


def _session(token_id, token_secret, verify_ssl):
    s = requests.Session()
    # Suppresses per-request warnings globally — acceptable because self-signed
    # certs are the norm in homelab/internal Proxmox setups.
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        # Proxmox API token auth uses a non-standard header value format:
        # PVEAPIToken=<user>@<realm>!<tokenname>=<secret>
        "Authorization": f"PVEAPIToken={token_id}={token_secret}",
        "Accept": "application/json",
    })
    s.verify = verify_ssl
    return s


class Proxmox:
    def __init__(self, url, token_id, token_secret, verify_ssl=False):
        self.base = url.rstrip("/") + "/api2/json"
        self.session = _session(token_id, token_secret, verify_ssl)

    def _get(self, path):
        r = self.session.get(f"{self.base}{path}", timeout=30)
        r.raise_for_status()
        # All Proxmox API responses wrap the payload in {"data": ...}.
        return r.json().get("data", [])

    def get_nodes(self):
        return self._get("/nodes")

    def get_vms(self, node):
        return self._get(f"/nodes/{node}/qemu")

    def get_containers(self, node):
        return self._get(f"/nodes/{node}/lxc")

    def get_all_assets(self):
        assets = []
        for node in self.get_nodes():
            node_name = node.get("node", "unknown")
            assets.append({
                "type": "node",
                "name": node_name,
                "source_id": node_name,
                "node": node_name,
                "status": node.get("status", "unknown"),
                "cpu": node.get("maxcpu"),
                "memory": node.get("maxmem"),
            })
            for vm in self.get_vms(node_name):
                vmid = vm.get("vmid")
                assets.append({
                    "type": "vm",
                    "name": vm.get("name", f"vm-{vmid}"),
                    "source_id": f"{node_name}/vm/{vmid}",
                    "node": node_name,
                    "status": vm.get("status", "unknown"),
                    "cpu": vm.get("maxcpu"),
                    "memory": vm.get("maxmem"),
                })
            for ct in self.get_containers(node_name):
                vmid = ct.get("vmid")
                assets.append({
                    "type": "container",
                    "name": ct.get("name", f"ct-{vmid}"),
                    "source_id": f"{node_name}/lxc/{vmid}",
                    "node": node_name,
                    "status": ct.get("status", "unknown"),
                    "cpu": ct.get("maxcpu"),
                    "memory": ct.get("maxmem"),
                })
        return assets
