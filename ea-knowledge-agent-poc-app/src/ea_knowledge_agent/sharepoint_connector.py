"""Optional SharePoint / Microsoft Graph connector seam.

NOT wired into the demo flow: the API exposes only a `configured` status
boolean via /api/integrations. Production should:
  * use certificate or workload-identity client credentials (not a
    client secret),
  * request application scope Sites.Selected on the approved site only,
  * drive sync via Graph delta links (list_delta below),
  * synchronize ACLs so retrieval stays permission-aware,
  * route tokens through OBO/delegated flows where per-user context is
    required.
Secrets are never logged; failures raise internal exceptions and the
caller must fail closed.
"""

import json
import urllib.parse
import urllib.request

from .config import load_settings

_TOKEN_URL = ("https://login.microsoftonline.com/{tenant}/oauth2/v2.0/"
              "token")
_GRAPH = "https://graph.microsoft.com/v1.0"
_TIMEOUT = 15


def _validate_graph_url(url: str) -> None:
    """Only absolute HTTPS URLs on graph.microsoft.com, default port, no
    userinfo — prevents bearer tokens leaking to an arbitrary host."""
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or p.hostname != "graph.microsoft.com" \
            or p.username or p.password or (p.port not in (None, 443)):
        raise RuntimeError(f"refusing non-Graph URL: {url!r}")


class SharePointConnector:
    def __init__(self, settings=None):
        self._s = settings or load_settings()

    @property
    def configured(self) -> bool:
        s = self._s
        return bool(s.graph_tenant_id and s.graph_client_id
                    and s.graph_client_secret and s.sharepoint_site_id
                    and s.sharepoint_drive_id)

    def get_access_token(self) -> str:
        """Client-credentials token for Graph. Raises RuntimeError when
        not configured or on any HTTP error (fail closed)."""
        if not self.configured:
            raise RuntimeError("Graph/SharePoint not configured")
        body = urllib.parse.urlencode({
            "client_id": self._s.graph_client_id,
            "client_secret": self._s.graph_client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }).encode()
        req = urllib.request.Request(
            _TOKEN_URL.format(tenant=self._s.graph_tenant_id),
            data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())["access_token"]
        except Exception as exc:
            raise RuntimeError("token request failed") from exc

    def list_delta(self, delta_url: str | None = None) -> dict:
        """Graph delta query for the configured drive. Pass the previous
        deltaLink to receive only changes since the last sync."""
        url = delta_url or (f"{_GRAPH}/drives/{self._s.sharepoint_drive_id}"
                            "/root/delta")
        _validate_graph_url(url)
        return self._get(url)

    def download_item(self, drive_id: str, item_id: str) -> bytes:
        url = (f"{_GRAPH}/drives/"
               f"{urllib.parse.quote(drive_id, safe='')}/items/"
               f"{urllib.parse.quote(item_id, safe='')}/content")
        _validate_graph_url(url)
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.get_access_token()}"})
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.read()
        except Exception as exc:
            raise RuntimeError("download failed") from exc

    def _get(self, url: str) -> dict:
        _validate_graph_url(url)
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.get_access_token()}"})
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            raise RuntimeError("graph request failed") from exc
