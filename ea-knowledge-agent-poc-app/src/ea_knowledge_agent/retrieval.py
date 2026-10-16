"""Permission-aware deterministic retrieval. Only APPROVED current
versions of artifacts the persona's groups can see are eligible evidence.
Vector/embedding search is a documented seam — this slice uses keyword and
metadata overlap so the demo is deterministic and offline."""

from .models import Persona
from .repository import tokenize

MIN_SCORE = 2.0  # below this the agent abstains


class PermissionAwareRetriever:
    def __init__(self, conn):
        self.conn = conn

    def search(self, persona: Persona, question: str,
               limit: int = 4) -> list[dict]:
        groups = ",".join("?" for _ in persona.groups)
        rows = self.conn.execute(
            f"""SELECT v.*, f.title, f.segment, f.domain, f.content_type,
                       f.audience, f.owner
                FROM artifact_versions v
                JOIN artifact_families f ON f.id = v.family_id
                WHERE v.is_current_approved = 1
                  AND v.lifecycle_status = 'APPROVED'
                  AND v.id IN (SELECT version_id FROM artifact_acl_groups
                               WHERE grp IN ({groups}))""",
            list(persona.groups)).fetchall()
        q_tokens = tokenize(question)
        results = []
        for r in rows:
            tags = [t[0] for t in self.conn.execute(
                "SELECT tag FROM artifact_tags WHERE version_id=?",
                (r["id"],))]
            doc_tokens = tokenize(" ".join([
                r["title"], r["description"], r["content_text"],
                r["segment"], r["domain"], " ".join(tags)]))
            overlap = q_tokens & doc_tokens
            if not overlap:
                continue
            title_tokens = tokenize(r["title"])
            tag_tokens = {t.lower() for t in tags}
            score = float(len(overlap))
            score += 2.0 * len(q_tokens & title_tokens)   # title boost
            score += 1.5 * len(q_tokens & tag_tokens)     # tag boost
            score += 1.0                                  # current approved
            results.append({
                "artifact_id": r["id"],
                "family_id": r["family_id"],
                "title": r["title"],
                "version": r["version"],
                "lifecycle_status": r["lifecycle_status"],
                "audience": r["audience"],
                "owner": r["owner"],
                "segment": r["segment"],
                "domain": r["domain"],
                "source_url": r["source_url"],
                "tags": tags,
                "score": round(score, 2),
                "excerpt": _excerpt(r["content_text"], q_tokens),
                "content_text": r["content_text"],
            })
        results.sort(key=lambda e: (-e["score"], e["title"]))
        return [e for e in results if e["score"] >= MIN_SCORE][:limit]


def _excerpt(text: str, q_tokens: set[str], width: int = 260) -> str:
    """Return a snippet around the first sentence containing a query term."""
    sentences = [s.strip() for s in text.replace("\n", " ").split(". ")
                 if s.strip()]
    for s in sentences:
        if tokenize(s) & q_tokens:
            return (s[:width] + "…") if len(s) > width else s
    return text[:width] + ("…" if len(text) > width else "")
