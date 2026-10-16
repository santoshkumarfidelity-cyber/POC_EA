"""Synthetic seed content. All artifacts are fictional EA material — no
client data. Idempotent: safe to call on an already-seeded database."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from .models import LifecycleStatus

NOW = datetime.now(timezone.utc)


def _ts(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Each entry: (title, [(version, status, review_offset_days, body)], tags,
#              groups, segment, domain, ctype, audience, owner, source_url)
SEED = [
    {
        "title": "Insurance Technology Strategy",
        "segment": "INSURANCE", "domain": "PLATFORM",
        "content_type": "STRATEGY", "audience": "INTERNAL",
        "owner": "EA Insurance", "contributor": "ea.demo",
        "groups": ["EA_INSURANCE"],
        "tags": ["INSURANCE", "STRATEGY", "CLOUD", "APPROVED"],
        "source_url":
            "https://example.invalid/sharepoint/insurance-strategy-v4-2",
        "versions": [
            ("4.1", LifecycleStatus.SUPERSEDED, 120,
             "Prior iteration of the Insurance technology strategy. "
             "Emphasized datacenter consolidation and selective SaaS. "
             "Superseded by v4.2 which adopts API-first integration and "
             "zero-trust controls across the Insurance segment."),
            ("4.2", LifecycleStatus.APPROVED, 45,
             "The Insurance technology strategy prioritizes API-first "
             "integration, zero-trust controls, governed cloud adoption, "
             "and reusable data products. All new Insurance capabilities "
             "must expose governed APIs, authenticate workload identity, "
             "and publish data products through the enterprise catalog. "
             "Cloud workloads adopt the landing-zone standard and are "
             "reviewed at the ARB before external exposure."),
        ],
    },
    {
        "title": "ARB Submission Template",
        "segment": "ENTERPRISE", "domain": "PLATFORM",
        "content_type": "TEMPLATE", "audience": "INTERNAL",
        "owner": "EA Governance", "contributor": "ea.demo",
        "groups": ["EA_ALL"],
        "tags": ["ARB", "TEMPLATE", "GOVERNANCE"],
        "source_url": "https://example.invalid/sharepoint/arb-template-v3",
        "versions": [
            ("3.0", LifecycleStatus.APPROVED, 90,
             "Standard Architecture Review Board submission template. "
             "Sections: context, decision, options, security assessment, "
             "data classification, operational impact. Submit two weeks "
             "before the target board session."),
        ],
    },
    {
        "title": "Enterprise API Strategy",
        "segment": "ENTERPRISE", "domain": "API",
        "content_type": "STRATEGY", "audience": "INTERNAL",
        "owner": "EA Platform", "contributor": "ea.demo",
        "groups": ["EA_ARCHITECTS"],
        "tags": ["API", "STRATEGY", "INTERNAL"],
        "source_url": "https://example.invalid/sharepoint/api-strategy-v21",
        "versions": [
            ("2.1", LifecycleStatus.APPROVED, 30,
             "Enterprise API strategy: all integrations expose versioned, "
             "documented APIs through the central gateway. REST is "
             "default; event streams for domain events. API products have "
             "named owners, SLAs and retirement plans. Restricted to the "
             "architecture community while gateway consolidation runs."),
        ],
    },
    {
        "title": "AI Reference Architecture",
        "segment": "ENTERPRISE", "domain": "AI",
        "content_type": "REFERENCE_ARCHITECTURE", "audience": "INTERNAL",
        "owner": "EA Emerging Tech", "contributor": "ea.demo",
        "groups": ["EA_AI"],
        "tags": ["AI", "REFERENCE_ARCHITECTURE", "DRAFT"],
        "source_url": "https://example.invalid/sharepoint/ai-refarch-v08",
        "versions": [
            ("0.8", LifecycleStatus.DRAFT, None,
             "Working draft of the AI reference architecture. Covers "
             "permission-aware retrieval, model isolation behind an "
             "approved boundary, output validation and audit. Not yet "
             "approved for reuse."),
        ],
    },
    {
        "title": "EA Onboarding Playbook",
        "segment": "ENTERPRISE", "domain": "PLATFORM",
        "content_type": "PLAYBOOK", "audience": "INTERNAL",
        "owner": "EA Practice", "contributor": "ea.demo",
        "groups": ["EA_ALL"],
        "tags": ["ONBOARDING", "PLAYBOOK", "APPROVED"],
        "source_url": "https://example.invalid/sharepoint/onboarding-v2",
        "versions": [
            ("2.0", LifecycleStatus.APPROVED, 60,
             "Onboarding playbook for new enterprise architects. Week one: "
             "governance model, segment map, artifact catalog walkthrough. "
             "Week two: ARB process, templates, domain communities. "
             "Includes checklist and mentor assignment."),
        ],
    },
    {
        "title": "Cloud Security Standard",
        "segment": "INSURANCE", "domain": "SECURITY",
        "content_type": "STANDARD", "audience": "INTERNAL",
        "owner": "", "contributor": "ea.demo",
        "groups": ["EA_INSURANCE"],
        "tags": ["CLOUD", "SECURITY", "REVIEW"],
        "source_url": "https://example.invalid/sharepoint/cloud-sec-v5",
        "versions": [
            ("5.0", LifecycleStatus.REVIEW, -15,
             "Cloud security standard under review. Covers encryption, "
             "key custody, workload identity, egress control and landing "
             "zone guardrails. Review date has passed; pending approver "
             "decision."),
        ],
    },
    {
        "title": "Data Governance Pattern",
        "segment": "INSURANCE", "domain": "DATA",
        "content_type": "PATTERN", "audience": "INTERNAL",
        "owner": "EA Data", "contributor": "ea.demo",
        "groups": ["EA_INSURANCE"],
        "tags": ["DATA", "PATTERN", "APPROVED"],
        "source_url": "https://example.invalid/sharepoint/data-gov-v13",
        "versions": [
            ("1.3", LifecycleStatus.APPROVED, 75,
             "Pattern for governed data products: named owner, published "
             "schema, quality rules, access via entitlement, and "
             "classification metadata. Insurance data products register "
             "in the catalog before consumption."),
        ],
    },
    {
        "title": "Legacy Integration Standard",
        "segment": "ENTERPRISE", "domain": "INTEGRATION",
        "content_type": "STANDARD", "audience": "INTERNAL",
        "owner": "EA Integration", "contributor": "ea.demo",
        "groups": ["EA_ALL"],
        "tags": ["INTEGRATION", "STANDARD", "SUPERSEDED"],
        "source_url": "https://example.invalid/sharepoint/legacy-int-v1",
        "versions": [
            ("1.0", LifecycleStatus.SUPERSEDED, 200,
             "Legacy point-to-point integration standard. Retained in "
             "history for traceability; superseded by the Enterprise API "
             "Strategy pattern. Do not apply to new integrations."),
        ],
    },
]


def seed_if_empty(conn) -> None:
    if conn.execute("SELECT COUNT(*) FROM artifact_families").fetchone()[0]:
        return
    try:
        fts = conn.execute("SELECT * FROM artifact_fts LIMIT 0") or True
        has_fts = True
    except Exception:
        has_fts = False
    for item in SEED:
        fam_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO artifact_families
               (id, title, segment, domain, content_type, audience, owner,
                contributor, created_at, current_version_id)
               VALUES (?,?,?,?,?,?,?,?,?,NULL)""",
            (fam_id, item["title"], item["segment"], item["domain"],
             item["content_type"], item["audience"], item["owner"],
             item["contributor"], _ts(90)))
        versions = item["versions"]
        for v_idx, (ver, status, review_off, body) in enumerate(versions):
            vid = uuid.uuid4().hex
            review_date = None
            if review_off is not None:
                review_date = (NOW + timedelta(days=review_off)).date() \
                    .isoformat() if review_off >= 0 else \
                    (NOW - timedelta(days=-review_off)).date().isoformat()
            conn.execute(
                """INSERT INTO artifact_versions
                   (id, family_id, version, description, lifecycle_status,
                    review_date, uploaded_at, updated_at, source_url,
                    content_hash, content_text, is_current_approved)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (vid, fam_id, ver,
                 f"{item['title']} {item['content_type'].lower()} "
                 f"for the EA repository.",
                 status.value, review_date, _ts(30 + v_idx * 60), _ts(30),
                 item["source_url"], _hash(body), body,
                 1 if status == LifecycleStatus.APPROVED
                 and v_idx == len(versions) - 1 else 0))
            for tag in item["tags"]:
                conn.execute(
                    "INSERT INTO artifact_tags (version_id, tag) "
                    "VALUES (?,?)", (vid, tag))
            for grp in item["groups"]:
                conn.execute(
                    "INSERT INTO artifact_acl_groups (version_id, grp) "
                    "VALUES (?,?)", (vid, grp))
            conn.execute(
                """INSERT INTO lifecycle_events
                   (id, version_id, from_status, to_status, actor_persona,
                    note, at)
                   VALUES (?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, vid, None, status.value, "seed",
                 "seeded", _ts(30 + v_idx * 60)))
            if has_fts:
                conn.execute(
                    "INSERT INTO artifact_fts (version_id, title, "
                    "description, content_text, tags_text) "
                    "VALUES (?,?,?,?,?)",
                    (vid, item["title"], item["content_type"], body,
                     " ".join(item["tags"])))
            if status == LifecycleStatus.APPROVED and \
                    v_idx == len(versions) - 1:
                conn.execute(
                    "UPDATE artifact_families SET current_version_id=? "
                    "WHERE id=?", (vid, fam_id))
    # broken registered links for reporting demos — ACL-scoped
    links = [
        ("https://example.invalid/video/architecture-overview-removed",
         "Broken Architecture Video Link", ["EA_ALL"]),
        ("https://example.invalid/stream/ai-recording-removed",
         "Restricted AI Recording Link", ["EA_AI"]),
    ]
    for url, title_, groups in links:
        lid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO registered_links
               (id, family_id, url, title, link_status, created_at)
               VALUES (?,?,?,?,?,?)""",
            (lid, None, url, title_, "BROKEN", _ts(20)))
        for grp in groups:
            conn.execute(
                "INSERT INTO registered_link_acl_groups (link_id, grp) "
                "VALUES (?,?)", (lid, grp))
    conn.commit()
