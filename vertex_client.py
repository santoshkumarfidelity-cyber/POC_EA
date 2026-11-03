"""Google Vertex AI (Gemini) answer generation. Same contract as
ClaudeClient: disabled unless VERTEX_PROJECT and VERTEX_MODEL are set, and
any failure raises so the caller falls back to local synthesis. Auth uses
VERTEX_ACCESS_TOKEN if set, otherwise the developer's gcloud login
(`gcloud auth print-access-token`). Tokens and error bodies are never
returned to the browser."""

import json
import re
import subprocess
import time
import urllib.error
import urllib.request

from .claude_client import SYSTEM_PROMPT, build_evidence_text
from .config import load_settings

_TIMEOUT = 30
_TOKEN_TTL = 45 * 60
_SAFE = re.compile(r"[A-Za-z0-9_.-]+")


class VertexClient:
    _token_cache: tuple[str, float] | None = None  # shared across requests

    def __init__(self, settings=None):
        self._s = settings or load_settings()

    @property
    def configured(self) -> bool:
        s = self._s
        return bool(s.vertex_project and s.vertex_model)

    @property
    def model(self) -> str:
        return self._s.vertex_model or ""

    def _access_token(self) -> str:
        if self._s.vertex_access_token:
            return self._s.vertex_access_token
        cached = VertexClient._token_cache
        if cached and cached[1] > time.time():
            return cached[0]
        try:
            out = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True, text=True, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                "no Vertex credentials: run `gcloud auth login` or set "
                "VERTEX_ACCESS_TOKEN") from exc
        token = out.stdout.strip()
        if not token:
            raise RuntimeError("gcloud returned an empty access token")
        VertexClient._token_cache = (token, time.time() + _TOKEN_TTL)
        return token

    def _url(self) -> str:
        s = self._s
        for v in (s.vertex_project, s.vertex_location, s.vertex_model):
            if not _SAFE.fullmatch(v or ""):
                raise RuntimeError("invalid Vertex project/location/model")
        host = ("aiplatform.googleapis.com" if s.vertex_location == "global"
                else f"{s.vertex_location}-aiplatform.googleapis.com")
        return (f"https://{host}/v1/projects/{s.vertex_project}/locations/"
                f"{s.vertex_location}/publishers/google/models/"
                f"{s.vertex_model}:generateContent")

    def synthesize(self, question: str, evidence: list[dict]) -> str:
        if not self.configured:
            raise RuntimeError("Vertex adapter not configured")
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text":
                f"Authorized evidence:\n{build_evidence_text(evidence)}"
                f"\n\nQuestion: {question}"}]}],
            "generationConfig": {"temperature": 0.2,
                                 "maxOutputTokens": 1024},
        }
        req = urllib.request.Request(
            self._url(), data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._access_token()}"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Vertex request failed: HTTP {exc.code} "
                               f"{_google_error(exc)}") from exc
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:
            # Server-log only: says whether DNS, proxy, firewall or SSL
            # stopped the call (never contains the token).
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(f"Vertex request failed: "
                               f"{type(reason).__name__}: {reason}") from exc
        cands = body.get("candidates") or []
        parts = (cands[0].get("content", {}).get("parts", [])
                 if cands else [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise RuntimeError("Vertex returned empty content")
        return text


def _google_error(exc) -> str:
    """Google's own error message (e.g. 'Permission denied on resource
    project …'), for the server log only."""
    try:
        err = json.loads(exc.read().decode("utf-8")).get("error", {})
        return f"{err.get('status', '')}: {err.get('message', '')}"[:300]
    except Exception:
        return ""
