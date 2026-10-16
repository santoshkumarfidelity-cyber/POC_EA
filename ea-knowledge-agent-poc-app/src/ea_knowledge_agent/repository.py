"""Knowledge repository: ACL-filtered artifact access, lifecycle
transitions, quality reporting and sanitized audit events."""

import hashlib
import json
import re
import urllib.parse
import uuid
from datetime import datetime, timezone

from .auth import can_contribute, can_curate, can_transition, \
    can_view_working_content
from .models import LifecycleStatus, Persona

REQUIRED_FIELDS = ("title", "description", "owner", "version", "segment",
                   "domain", "content_type", "audience", "review_date",
                   "source_url", "content", "tags", "allowed_groups")

_DEFAULT_VISIBLE = (LifecycleStatus.DRAFT.value, LifecycleStatus.REVIEW.value,
                    LifecycleStatus.APPROVED.value)


class KnowledgeRepository:
    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------- audit
    def record_audit(self, persona: Persona, action: str,
                     resource_id: str, details: dict) -> str:
        """Write a sanitized audit event. `details` must already be
        sanitized (no full prompts or content bodies)."""
        aid = uuid.uuid4().hex
        safe = {k: (v if not isinstance(v, str) or len(v) < 200
                    else hashlib.sha256(v.encode()).hexdigest()[:16])
                for k, v in details.items()}
        self.conn.execute(
            "INSERT INTO audit_events (id, persona, action, resource_id, "
            "details_json, at) VALUES (?,?,?,?,?,?)",
            (aid, persona.id, action, resource_id, json.dumps(safe),
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.conn.commit()
        return aid

    # ------------------------------------------------------------ access
    def _authorized_sql(self, persona: Persona):
        groups = ",".join("?" for _ in persona.groups)
        sql = f"""v.id IN (SELECT version_id FROM artifact_acl_groups
                           WHERE grp IN ({groups}))"""
        return sql, list(persona.groups)

    def _row_to_dict(self, row, include_content=False):
        d = dict(row)
        d["tags"] = [r[0] for r in self.conn.execute(
            "SELECT tag FROM artifact_tags WHERE version_id=?",
            (d["id"],))]
        d["allowed_groups"] = [r[0] for r in self.conn.execute(
            "SELECT grp FROM artifact_acl_groups WHERE version_id=?",
            (d["id"],))]
        if not include_content:
            d.pop("content_text", None)
        return d

    def _family_meta(self, family_id):
        return dict(self.conn.execute(
            "SELECT * FROM artifact_families WHERE id=?",
            (family_id,)).fetchone())

    # ------------------------------------------------------------ query
    def list_artifacts(self, persona, *, query="", tags=(), status="",
                       audience="", sort="uploaded_desc"):
        acl, params = self._authorized_sql(persona)
        where = [acl]
        working = can_view_working_content(persona)
        if status:
            st = status.upper()
            if not working and st in ("DRAFT", "REVIEW"):
                self.record_audit(persona, "search", "", {
                    "query_hash": _hash_text(query), "status": st,
                    "result_count": 0, "blocked": "working_content"})
                return []
            where.append("v.lifecycle_status = ?")
            params.append(st)
            if not working and st == "APPROVED":
                where.append("v.is_current_approved = 1")
        elif not working:
            where.append("v.lifecycle_status = 'APPROVED'")
            where.append("v.is_current_approved = 1")
        else:
            where.append("v.lifecycle_status IN ("
                         + ",".join("?" for _ in _DEFAULT_VISIBLE) + ")")
            params.extend(_DEFAULT_VISIBLE)
        if audience:
            where.append("f.audience = ?")
            params.append(audience.upper())
        if query:
            where.append("(f.title LIKE ? OR v.description LIKE ? "
                         "OR v.content_text LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        for t in tags:
            where.append("v.id IN (SELECT version_id FROM artifact_tags "
                         "WHERE tag = ?)")
            params.append(t.upper())
        order = {
            "uploaded_desc": "v.uploaded_at DESC",
            "uploaded_asc": "v.uploaded_at ASC",
            "updated_desc": "v.updated_at DESC",
            "title_asc": "f.title ASC",
        }.get(sort, "v.uploaded_at DESC")
        rows = self.conn.execute(
            f"""SELECT v.*, f.title, f.segment, f.domain, f.content_type,
                       f.audience, f.owner, f.contributor
                FROM artifact_versions v
                JOIN artifact_families f ON f.id = v.family_id
                WHERE {' AND '.join(where)}
                ORDER BY v.is_current_approved DESC, {order}""",
            params).fetchall()
        items = [self._row_to_dict(r) for r in rows]
        for it in items:
            fm = self._family_meta(it["family_id"])
            it["current_version_id"] = fm["current_version_id"]
        self.record_audit(persona, "search", "", {
            "query_hash": _hash_text(query), "tags": list(tags),
            "status": status, "result_count": len(items)})
        return items

    def get_artifact(self, persona, artifact_id: str):
        acl, params = self._authorized_sql(persona)
        row = self.conn.execute(
            f"""SELECT v.*, f.title, f.segment, f.domain, f.content_type,
                       f.audience, f.owner, f.contributor
                FROM artifact_versions v
                JOIN artifact_families f ON f.id = v.family_id
                WHERE v.id = ? AND {acl}""",
            [artifact_id] + params).fetchone()
        if not row:
            return None
        if not can_view_working_content(persona) and \
                row["lifecycle_status"] in ("DRAFT", "REVIEW"):
            return None
        item = self._row_to_dict(row, include_content=True)
        fm = self._family_meta(item["family_id"])
        item["current_version_id"] = fm["current_version_id"]
        item["lifecycle_events"] = [dict(r) for r in self.conn.execute(
            "SELECT from_status, to_status, actor_persona, note, at "
            "FROM lifecycle_events WHERE version_id=? ORDER BY at",
            (artifact_id,))]
        self.record_audit(persona, "read", artifact_id, {})
        return item

    def get_family_versions(self, persona, family_id: str):
        acl, params = self._authorized_sql(persona)
        rows = self.conn.execute(
            f"""SELECT v.*, f.title, f.owner, f.audience
                FROM artifact_versions v
                JOIN artifact_families f ON f.id = v.family_id
                WHERE v.family_id = ? AND {acl}
                ORDER BY v.uploaded_at DESC""",
            [family_id] + params).fetchall()
        if not can_view_working_content(persona):
            rows = [r for r in rows
                    if r["lifecycle_status"] not in ("DRAFT", "REVIEW")]
        items = [self._row_to_dict(r) for r in rows]
        for it in items:
            it.pop("content_text", None)
        return items

    def list_tags(self, persona):
        acl, params = self._authorized_sql(persona)
        status_clause = ("v.is_current_approved = 1 AND "
                         "v.lifecycle_status = 'APPROVED'"
                         if not can_view_working_content(persona) else
                         "v.lifecycle_status IN ('DRAFT','REVIEW','APPROVED')")
        rows = self.conn.execute(
            f"""SELECT t.tag, COUNT(*) AS n FROM artifact_tags t
                JOIN artifact_versions v ON v.id = t.version_id
                WHERE {acl.replace('v.id', 't.version_id')}
                  AND {status_clause}
                GROUP BY t.tag ORDER BY t.tag""", params).fetchall()
        return [{"tag": r["tag"], "count": r["n"]} for r in rows]

    # ----------------------------------------------------------- create
    def create_artifact(self, persona, payload: dict):
        if not can_contribute(persona):
            raise PermissionError("persona cannot contribute content")
        pending = payload.get("extraction_status") == "PENDING"
        missing = [f for f in REQUIRED_FIELDS
                   if not (f == "content" and pending)
                   and not payload.get(f)]
        if missing:
            raise ValueError("missing required fields: " + ", ".join(missing))
        parsed = urllib.parse.urlparse(payload["source_url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(
                "source_url must be an absolute HTTPS URL")
        content = payload.get("content", "")
        if payload.get("_server_content_hash"):
            chash = payload["_server_content_hash"]
        else:
            chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        dup_url = self.conn.execute(
            "SELECT id FROM artifact_versions WHERE source_url=?",
            (payload["source_url"],)).fetchone()
        dup_hash = self.conn.execute(
            "SELECT id FROM artifact_versions WHERE content_hash=?",
            (chash,)).fetchone()
        if (dup_url or dup_hash) and not (
                payload.get("duplicate_override") and can_curate(persona)):
            raise ValueError("duplicate source URL or content detected")
        fam_id = uuid.uuid4().hex
        vid = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO artifact_families
               (id, title, segment, domain, content_type, audience, owner,
                contributor, created_at, current_version_id)
               VALUES (?,?,?,?,?,?,?,?,?,NULL)""",
            (fam_id, payload["title"], payload["segment"].upper(),
             payload["domain"].upper(), payload["content_type"].upper(),
             payload["audience"].upper(), payload["owner"], persona.id,
             now))
        self.conn.execute(
            """INSERT INTO artifact_versions
               (id, family_id, version, description, lifecycle_status,
                review_date, uploaded_at, updated_at, source_url,
                content_hash, content_text, extraction_status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vid, fam_id, payload["version"], payload["description"],
             LifecycleStatus.DRAFT.value, payload["review_date"], now, now,
             payload["source_url"], chash, content,
             payload.get("extraction_status", "TEXT")))
        for tag in payload["tags"]:
            self.conn.execute(
                "INSERT INTO artifact_tags (version_id, tag) VALUES (?,?)",
                (vid, str(tag).upper()))
        for grp in payload["allowed_groups"]:
            self.conn.execute(
                "INSERT INTO artifact_acl_groups (version_id, grp) "
                "VALUES (?,?)", (vid, grp))
        self.conn.execute(
            """INSERT INTO lifecycle_events
               (id, version_id, from_status, to_status, actor_persona,
                note, at) VALUES (?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, vid, None, LifecycleStatus.DRAFT.value,
             persona.id, "submitted", now))
        try:
            self.conn.execute(
                "INSERT INTO artifact_fts (version_id, title, description, "
                "content_text, tags_text) VALUES (?,?,?,?,?)",
                (vid, payload["title"], payload["description"], content,
                 " ".join(payload["tags"])))
        except Exception:
            pass
        self.conn.commit()
        self.record_audit(persona, "create", vid,
                          {"family_id": fam_id, "title": payload["title"]})
        return {"artifact_id": vid, "family_id": fam_id,
                "status": LifecycleStatus.DRAFT.value}

    # -------------------------------------------------------- transition
    def transition_artifact(self, persona, artifact_id: str,
                            target_status: str, note: str):
        row = self.conn.execute(
            "SELECT * FROM artifact_versions WHERE id=?",
            (artifact_id,)).fetchone()
        if not row:
            raise KeyError("artifact not found")
        # ACL check still applies — cannot transition invisible artifacts
        acl, params = self._authorized_sql(persona)
        if not self.conn.execute(
                f"SELECT 1 FROM artifact_versions v WHERE v.id=? AND {acl}",
                [artifact_id] + params).fetchone():
            raise PermissionError("not authorized for this artifact")
        source = LifecycleStatus(row["lifecycle_status"])
        try:
            target = LifecycleStatus(target_status.upper())
        except ValueError:
            raise ValueError(f"invalid status {target_status!r}")
        if not can_transition(persona, source, target):
            raise PermissionError(
                f"{persona.role} cannot move {source.value} -> "
                f"{target.value}")
        if target == LifecycleStatus.APPROVED:
            if row["extraction_status"] == "PENDING":
                raise ValueError("cannot approve: extraction pending")
            for field, val in (("owner", self._family_meta(
                    row["family_id"])["owner"]),
                    ("version", row["version"]),
                    ("review_date", row["review_date"]),
                    ("audience", self._family_meta(
                        row["family_id"])["audience"])):
                if not val:
                    raise ValueError(
                        f"cannot approve: missing {field}")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE artifact_versions SET lifecycle_status=?, updated_at=? "
            "WHERE id=?", (target.value, now, artifact_id))
        if target == LifecycleStatus.APPROVED:
            # supersede prior approved versions; exactly one current
            others = self.conn.execute(
                "SELECT id FROM artifact_versions WHERE family_id=? "
                "AND is_current_approved=1 AND id!=?",
                (row["family_id"], artifact_id)).fetchall()
            for o in others:
                self.conn.execute(
                    "UPDATE artifact_versions SET lifecycle_status=?, "
                    "is_current_approved=0, updated_at=? WHERE id=?",
                    (LifecycleStatus.SUPERSEDED.value, now, o["id"]))
                self.conn.execute(
                    """INSERT INTO lifecycle_events
                       (id, version_id, from_status, to_status,
                        actor_persona, note, at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (uuid.uuid4().hex, o["id"], LifecycleStatus.APPROVED.value,
                     LifecycleStatus.SUPERSEDED.value, persona.id,
                     "superseded by new approved version", now))
            self.conn.execute(
                "UPDATE artifact_versions SET is_current_approved=1 "
                "WHERE id=?", (artifact_id,))
            self.conn.execute(
                "UPDATE artifact_families SET current_version_id=? "
                "WHERE id=?", (artifact_id, row["family_id"]))
        self.conn.execute(
            """INSERT INTO lifecycle_events
               (id, version_id, from_status, to_status, actor_persona,
                note, at) VALUES (?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, artifact_id, source.value, target.value,
             persona.id, note[:200] if note else "", now))
        if target == LifecycleStatus.SUPERSEDED and \
                row["is_current_approved"]:
            self.conn.execute(
                "UPDATE artifact_versions SET is_current_approved=0 "
                "WHERE id=?", (artifact_id,))
            fam = self._family_meta(row["family_id"])
            if fam["current_version_id"] == artifact_id:
                self.conn.execute(
                    "UPDATE artifact_families SET current_version_id=NULL "
                    "WHERE id=?", (row["family_id"],))
        self.conn.commit()
        self.record_audit(persona, "transition", artifact_id,
                          {"from": source.value, "to": target.value})
        return {"artifact_id": artifact_id, "status": target.value}

    # ---------------------------------------------------------- quality
    def quality_report(self, persona):
        acl, params = self._authorized_sql(persona)
        today = datetime.now(timezone.utc).date().isoformat()
        overdue = self.conn.execute(
            f"""SELECT v.id, f.title, v.version, v.review_date
                FROM artifact_versions v JOIN artifact_families f
                  ON f.id=v.family_id
                WHERE {acl} AND v.review_date IS NOT NULL
                  AND v.review_date < ?
                  AND v.lifecycle_status IN ('REVIEW','APPROVED')""",
            params + [today]).fetchall()
        unowned = self.conn.execute(
            f"""SELECT v.id, f.title, v.version
                FROM artifact_versions v JOIN artifact_families f
                  ON f.id=v.family_id
                WHERE {acl} AND (f.owner IS NULL OR f.owner='')
                  AND v.lifecycle_status IN ('REVIEW','APPROVED')""",
            params).fetchall()
        superseded = self.conn.execute(
            f"""SELECT v.id, f.title, v.version
                FROM artifact_versions v JOIN artifact_families f
                  ON f.id=v.family_id
                WHERE {acl} AND v.lifecycle_status='SUPERSEDED'""",
            params).fetchall()
        hashes = self.conn.execute(
            f"""SELECT v.content_hash, COUNT(*) AS n
                FROM artifact_versions v WHERE {acl}
                GROUP BY v.content_hash HAVING n>1""", params).fetchall()
        lg = ",".join("?" for _ in persona.groups)
        broken = self.conn.execute(
            f"""SELECT l.id, l.title, l.url FROM registered_links l
                WHERE l.link_status='BROKEN'
                  AND l.id IN (SELECT link_id FROM
                               registered_link_acl_groups
                               WHERE grp IN ({lg}))""",
            list(persona.groups)).fetchall()
        detailed = can_curate(persona)
        report = {
            "counts": {
                "review_overdue": len(overdue),
                "unowned": len(unowned),
                "superseded": len(superseded),
                "duplicate_candidates": len(hashes),
                "broken_links": len(broken),
            },
            "details_visible": detailed,
        }
        if detailed:
            report["items"] = {
                "review_overdue": [dict(r) for r in overdue],
                "unowned": [dict(r) for r in unowned],
                "superseded": [dict(r) for r in superseded],
                "duplicate_candidates": [dict(r) for r in hashes],
                "broken_links": [dict(r) for r in broken],
            }
        self.record_audit(persona, "report", "quality",
                          {"details": detailed})
        return report

    def recent_audit(self, persona, limit=25):
        if not can_curate(persona):
            raise PermissionError("audit log requires curator or admin")
        rows = self.conn.execute(
            "SELECT * FROM audit_events ORDER BY at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def tokenize(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "")}
