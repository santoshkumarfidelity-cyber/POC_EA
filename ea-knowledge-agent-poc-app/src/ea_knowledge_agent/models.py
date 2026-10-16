"""Core dataclasses and enumerations shared across the POC."""

from dataclasses import dataclass
from enum import Enum


class LifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class Audience(str, Enum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class Persona:
    id: str
    display_name: str
    role: str
    groups: tuple[str, ...]


@dataclass(frozen=True)
class Citation:
    artifact_id: str
    title: str
    version: str
    source_url: str
    excerpt: str


@dataclass(frozen=True)
class AgentAnswer:
    answer: str
    status: str  # grounded | insufficient_evidence
    citations: tuple[Citation, ...]
    conversation_id: str
    provider: str
    audit_id: str
