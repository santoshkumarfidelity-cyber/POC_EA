"""Demo personas and lifecycle authorization.

This is a demo persona switch, NOT authentication. Production uses Entra ID
SSO + RBAC through an identity adapter seam; see README and
`api.py` for where that seam is applied.
"""

from .models import LifecycleStatus, Persona

PERSONAS: dict[str, Persona] = {
    "consumer": Persona(
        id="consumer", display_name="EA Consumer", role="EA Consumer",
        groups=("EA_ALL", "EA_INSURANCE"),
    ),
    "contributor": Persona(
        id="contributor", display_name="EA Contributor",
        role="EA Contributor",
        groups=("EA_ALL", "EA_INSURANCE", "EA_CONTRIBUTORS"),
    ),
    "owner": Persona(
        id="owner", display_name="Content Owner", role="Content Owner",
        groups=("EA_ALL", "EA_INSURANCE", "EA_OWNERS"),
    ),
    "approver": Persona(
        id="approver", display_name="Governance Approver",
        role="Governance Approver",
        groups=("EA_ALL", "EA_INSURANCE", "EA_APPROVERS"),
    ),
    "curator": Persona(
        id="curator", display_name="Repository Curator",
        role="Repository Curator",
        groups=("EA_ALL", "EA_INSURANCE", "EA_CURATORS"),
    ),
    "admin": Persona(
        id="admin", display_name="Platform Administrator",
        role="Platform Administrator",
        groups=("EA_ALL", "EA_INSURANCE", "EA_CONTRIBUTORS", "EA_OWNERS",
                "EA_APPROVERS", "EA_CURATORS", "EA_ADMINS", "EA_AI",
                "EA_ARCHITECTS"),
    ),
}

# Allowed lifecycle transitions by persona id.
_TRANSITIONS: dict[tuple[LifecycleStatus, LifecycleStatus], frozenset[str]] = {
    (LifecycleStatus.DRAFT, LifecycleStatus.REVIEW):
        frozenset({"contributor", "owner", "admin"}),
    (LifecycleStatus.REVIEW, LifecycleStatus.APPROVED):
        frozenset({"approver", "admin"}),
    (LifecycleStatus.APPROVED, LifecycleStatus.SUPERSEDED):
        frozenset({"owner", "approver", "admin"}),
    (LifecycleStatus.SUPERSEDED, LifecycleStatus.ARCHIVED):
        frozenset({"curator", "admin"}),
}


def get_persona(persona_id: str) -> Persona:
    try:
        return PERSONAS[persona_id]
    except KeyError:
        raise ValueError(f"unknown persona: {persona_id!r}")


def list_personas() -> list[Persona]:
    return list(PERSONAS.values())


def can_transition(persona: Persona, source: LifecycleStatus,
                   target: LifecycleStatus) -> bool:
    allowed = _TRANSITIONS.get((source, target))
    return bool(allowed) and persona.id in allowed


def can_contribute(persona: Persona) -> bool:
    return persona.id in {"contributor", "owner", "admin"}


def can_curate(persona: Persona) -> bool:
    return persona.id in {"curator", "admin"}


def can_view_working_content(persona: Persona) -> bool:
    """Whether the persona may see DRAFT/REVIEW working content.
    Consumers are limited to approved (plus authorized history)."""
    return persona.id in {"contributor", "owner", "approver", "curator",
                          "admin"}
