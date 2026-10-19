"""Configuration: environment variables only, no secrets stored in code."""

import os
from dataclasses import dataclass

_APP_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir))


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    db_path: str = "data/poc.db"
    web_dir: str = os.path.join(_APP_ROOT, "web")

    anthropic_api_key: str | None = None
    claude_model: str | None = None

    graph_tenant_id: str | None = None
    graph_client_id: str | None = None
    graph_client_secret: str | None = None
    sharepoint_site_id: str | None = None
    sharepoint_drive_id: str | None = None


def load_settings() -> Settings:
    env = os.environ
    return Settings(
        host=env.get("POC_HOST", "127.0.0.1"),
        port=int(env.get("POC_PORT", "8765")),
        db_path=env.get("POC_DB", "data/poc.db"),
        web_dir=env.get("POC_WEB_DIR") or os.path.join(_APP_ROOT, "web"),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        claude_model=env.get("CLAUDE_MODEL") or None,
        graph_tenant_id=env.get("GRAPH_TENANT_ID") or None,
        graph_client_id=env.get("GRAPH_CLIENT_ID") or None,
        graph_client_secret=env.get("GRAPH_CLIENT_SECRET") or None,
        sharepoint_site_id=env.get("SHAREPOINT_SITE_ID") or None,
        sharepoint_drive_id=env.get("SHAREPOINT_DRIVE_ID") or None,
    )
