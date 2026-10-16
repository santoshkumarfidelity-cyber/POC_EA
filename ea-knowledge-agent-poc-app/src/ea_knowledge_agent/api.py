"""HTTP API + static hosting via http.server. JSON errors are always
{error: {code, message}}; API responses are no-store; static pages get
basic CSP headers; directory traversal is rejected."""

import base64
import hashlib
import json
import os
import posixpath
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .agent import KnowledgeAgent
from .auth import can_curate, get_persona, list_personas
from .claude_client import ClaudeClient
from .database import connect, initialize
from .file_extraction import extract_text
from .repository import KnowledgeRepository
from .seed import seed_if_empty
from .sharepoint_connector import SharePointConnector

_STATIC = {"/": "index.html", "/index.html": "index.html",
           "/styles.css": "styles.css", "/app.js": "app.js"}
_MIME = {".html": "text/html; charset=utf-8", ".css": "text/css",
         ".js": "text/javascript"}


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def make_handler(db_path: str, web_dir: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EAKnowledgePOC/0.1"

        # -------------------------------------------------- plumbing
        def log_message(self, *a):  # quiet but keep errors
            pass

        def _send_json(self, obj, status=200):
            body = json.dumps(obj, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status, code, message):
            self._send_json({"error": {"code": code, "message": message}},
                            status)

        def _persona(self, params):
            pid = params.get("persona", ["consumer"])[0]
            try:
                return get_persona(pid)
            except ValueError:
                raise ApiError("bad_persona", "unknown persona", 400)

        def _repo(self):
            conn = connect(db_path)
            return KnowledgeRepository(conn), conn

        def _body(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n > 5 * 1024 * 1024:
                raise ApiError("too_large", "body exceeds 5MB", 413)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise ApiError("bad_json", "request body must be JSON", 400)

        # -------------------------------------------------- routes
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            path = posixpath.normpath(urllib.parse.unquote(parsed.path))
            try:
                if path.startswith("/api/"):
                    return self._api_get(path, params)
                return self._static(path)
            except ApiError as e:
                return self._send_error(e.status, e.code, e.message)
            except PermissionError as e:
                return self._send_error(403, "forbidden", str(e))
            except Exception:
                return self._send_error(500, "internal",
                                        "unexpected server error")

        def _api_get(self, path, params):
            repo, conn = self._repo()
            try:
                if path == "/api/health":
                    return self._send_json({"status": "ok"})
                if path == "/api/personas":
                    return self._send_json({"personas": [
                        {"id": p.id, "display_name": p.display_name,
                         "role": p.role, "groups": list(p.groups)}
                        for p in list_personas()]})
                if path == "/api/integrations":
                    return self._send_json({
                        "claude_configured": ClaudeClient().configured,
                        "sharepoint_configured":
                            SharePointConnector().configured,
                        "mode": "local synthesis; SharePoint seam inactive"})
                if path == "/api/artifacts":
                    persona = self._persona(params)
                    items = repo.list_artifacts(
                        persona,
                        query=params.get("query", [""])[0],
                        tags=tuple(t for t in params.get("tags", [""])[0]
                                   .split(",") if t),
                        status=params.get("status", [""])[0],
                        audience=params.get("audience", [""])[0],
                        sort=params.get("sort", ["uploaded_desc"])[0])
                    return self._send_json({"artifacts": items})
                if path == "/api/tags":
                    persona = self._persona(params)
                    return self._send_json({"tags": repo.list_tags(persona)})
                if path == "/api/reports/quality":
                    persona = self._persona(params)
                    return self._send_json(repo.quality_report(persona))
                if path == "/api/audit/recent":
                    persona = self._persona(params)
                    if not can_curate(persona):
                        raise ApiError("forbidden",
                                       "audit log requires curator or admin",
                                       403)
                    return self._send_json(
                        {"events": repo.recent_audit(persona)})
                if path.startswith("/api/artifacts/"):
                    parts = path.split("/")
                    artifact_id = parts[3]
                    persona = self._persona(params)
                    if len(parts) == 5 and parts[4] == "versions":
                        item = repo.get_artifact(persona, artifact_id)
                        if not item:
                            raise ApiError("not_found", "artifact not found",
                                           404)
                        return self._send_json({
                            "versions": repo.get_family_versions(
                                persona, item["family_id"])})
                    item = repo.get_artifact(persona, artifact_id)
                    if not item:
                        raise ApiError("not_found", "artifact not found",
                                       404)
                    return self._send_json({"artifact": item})
                raise ApiError("not_found", "unknown endpoint", 404)
            finally:
                conn.close()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = posixpath.normpath(urllib.parse.unquote(parsed.path))
            try:
                return self._api_post(path, self._body())
            except ApiError as e:
                return self._send_error(e.status, e.code, e.message)
            except PermissionError as e:
                return self._send_error(403, "forbidden", str(e))
            except ValueError as e:
                return self._send_error(400, "bad_request", str(e))
            except KeyError:
                return self._send_error(404, "not_found", "not found")
            except Exception:
                return self._send_error(500, "internal",
                                        "unexpected server error")

        def _api_post(self, path, body):
            repo, conn = self._repo()
            try:
                if path == "/api/agent/query":
                    persona = get_persona(body.get("persona", "consumer"))
                    answer = KnowledgeAgent(conn).ask(
                        persona, body.get("question", ""),
                        body.get("conversation_id"))
                    return self._send_json({
                        "answer": answer.answer, "status": answer.status,
                        "provider": answer.provider,
                        "conversation_id": answer.conversation_id,
                        "audit_id": answer.audit_id,
                        "citations": [c.__dict__ for c in
                                      answer.citations]})
                if path == "/api/artifacts":
                    persona = get_persona(body.get("persona", ""))
                    payload = dict(body)
                    payload.pop("_server_content_hash", None)
                    warnings = []
                    if payload.get("file_base64"):
                        try:
                            data = base64.b64decode(
                                payload.pop("file_base64"))
                        except Exception:
                            raise ApiError("bad_file",
                                           "file_base64 is not valid "
                                           "base64", 400)
                        payload["_server_content_hash"] = hashlib.sha256(
                            data).hexdigest()
                        filename = payload.pop("filename", "")
                        text, warnings = extract_text(filename, data)
                        if text:
                            payload["content"] = text
                            payload["extraction_status"] = "EXTRACTED"
                        else:
                            safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_",
                                               filename) or "upload"
                            payload["content"] = (
                                f"[Extraction pending for {safe_name}; "
                                "body not indexed]")
                            payload["extraction_status"] = "PENDING"
                    result = repo.create_artifact(persona, payload)
                    result["warnings"] = warnings
                    return self._send_json(result, status=201)
                if path.startswith("/api/artifacts/") and \
                        path.endswith("/transition"):
                    artifact_id = path.split("/")[3]
                    persona = get_persona(body.get("persona", ""))
                    result = repo.transition_artifact(
                        persona, artifact_id,
                        body.get("target_status", ""),
                        body.get("note", ""))
                    return self._send_json(result)
                raise ApiError("not_found", "unknown endpoint", 404)
            finally:
                conn.close()

        # -------------------------------------------------- static
        def _static(self, path):
            if path in _STATIC:
                fname = _STATIC[path]
            elif path.startswith("/"):
                fname = path.lstrip("/")
            else:
                return self._send_error(404, "not_found", "not found")
            root = os.path.abspath(web_dir)
            fpath = os.path.abspath(os.path.join(root, fname))
            if not fpath.startswith(root + os.sep):
                return self._send_error(403, "forbidden", "forbidden")
            if not os.path.isfile(fpath):
                return self._send_error(404, "not_found", "not found")
            ext = os.path.splitext(fpath)[1]
            with open(fpath, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type",
                             _MIME.get(ext, "application/octet-stream"))
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' "
                             "'unsafe-inline'; script-src 'self'; "
                             "img-src 'self' data:; connect-src 'self'; "
                             "object-src 'none'; base-uri 'none'; "
                             "frame-ancestors 'none'; form-action 'self'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def create_server(host: str, port: int, db_path: str,
                  web_dir: str) -> ThreadingHTTPServer:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = connect(db_path)
    initialize(conn)
    seed_if_empty(conn)
    conn.close()
    return ThreadingHTTPServer((host, port), make_handler(db_path, web_dir))
