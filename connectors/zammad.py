import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


def _session(token):
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update({
        "Authorization": f"Token token={token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    return s


class Zammad:
    def __init__(self, url, token):
        self.base = url.rstrip("/") + "/api/v1"
        self.session = _session(token)

    def _get(self, path, params=None):
        r = self.session.get(f"{self.base}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_tickets(self, page=1, per_page=100):
        return self._get("/tickets", params={"page": page, "per_page": per_page, "expand": True})

    def get_ticket(self, ticket_id):
        return self._get(f"/tickets/{ticket_id}", params={"expand": True})

    def get_tickets_with_asset_field(self, field_name):
        """Return tickets where field_name is set (non-null, non-empty)."""
        tickets = []
        page = 1
        while True:
            batch = self.get_tickets(page=page, per_page=100)
            if not batch:
                break
            found_any = False
            for ticket in batch:
                val = ticket.get(field_name)
                if val:
                    tickets.append(ticket)
                    found_any = True
            if len(batch) < 100:
                break
            page += 1
        return tickets
