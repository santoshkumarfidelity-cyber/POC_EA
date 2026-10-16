"""Knowledge agent: retrieve authorized evidence, sanitize, synthesize,
cite or abstain. Audit events never contain the raw question."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from .claude_client import ClaudeClient
from .guardrails import detect_prompt_injection, sanitize_evidence, \
    validate_answer
from .models import AgentAnswer, Citation, Persona
from .retrieval import PermissionAwareRetriever

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class KnowledgeAgent:
    def __init__(self, conn, claude: ClaudeClient | None = None):
        self.conn = conn
        self.retriever = PermissionAwareRetriever(conn)
        self.claude = claude or ClaudeClient()

    def ask(self, persona: Persona, question: str,
            conversation_id: str | None = None) -> AgentAnswer:
        question = (question or "").strip()
        if not question:
            raise ValueError("question must not be empty")
        conv_id = conversation_id or uuid.uuid4().hex
        evidence = self.retriever.search(persona, question)
        evidence, warnings = sanitize_evidence(evidence)
        if not evidence:
            answer = AgentAnswer(
                answer="I could not find current, approved EA content you "
                       "are authorized to see that answers this question. "
                       "Try rephrasing, checking tags, or asking a content "
                       "owner.",
                status="insufficient_evidence", citations=(),
                conversation_id=conv_id, provider="local",
                audit_id=self._audit(persona, question, "local",
                                     "insufficient_evidence", (),
                                     len(warnings)))
            self._persist_conversation(conv_id, persona, question, answer)
            return answer

        provider = "local"
        if self.claude.configured:
            try:
                text = self.claude.synthesize(question, evidence)
                provider = "claude"
            except Exception:
                provider = "local-fallback"
                text = self._local_synthesis(question, evidence)
        else:
            text = self._local_synthesis(question, evidence)

        citations = tuple(
            Citation(artifact_id=e["artifact_id"], title=e["title"],
                     version=e["version"], source_url=e["source_url"],
                     excerpt=e["excerpt"])
            for e in evidence[:3])
        grounded = validate_answer(text, citations)
        answer = AgentAnswer(
            answer=text if grounded else
            "The retrieved material did not support a defensible cited "
            "answer, so I am abstaining.",
            status="grounded" if grounded else "insufficient_evidence",
            citations=citations if grounded else (),
            conversation_id=conv_id, provider=provider,
            audit_id=self._audit(persona, question, provider,
                                 "grounded" if grounded
                                 else "insufficient_evidence",
                                 citations, len(warnings)))
        self._persist_conversation(conv_id, persona, question, answer)
        return answer

    # ---------------------------------------------------------- internals
    def _local_synthesis(self, question: str, evidence: list[dict]) -> str:
        top = evidence[0]
        sentences = _SENTENCE_RE.split(top["content_text"].strip())
        q_tokens = {t.lower() for t in re.findall(r"[A-Za-z]{3,}",
                                                  question)}
        relevant = [s for s in sentences
                    if {w.lower() for w in re.findall(r"[A-Za-z]{3,}", s)}
                    & q_tokens]
        picked = (relevant or sentences)[:2]
        body = " ".join(s.strip().rstrip(".") + "." for s in picked)
        others = [f"{e['title']} v{e['version']}" for e in evidence[1:3]]
        related = (f" Related approved material: {'; '.join(others)}."
                   if others else "")
        return (f"Per the governing source {top['title']} v{top['version']}: "
                f"{body}{related}")

    def _persist_conversation(self, conv_id, persona, question, answer):
        cited = json.dumps([c.artifact_id for c in answer.citations])
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO conversations
               (id, persona, last_question, last_status, cited_ids_json,
                updated_at) VALUES (?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET last_question=excluded.
               last_question, last_status=excluded.last_status,
               cited_ids_json=excluded.cited_ids_json,
               updated_at=excluded.updated_at""",
            (conv_id, persona.id, question, answer.status, cited, now))
        self.conn.commit()

    def _audit(self, persona, question, provider, status, citations,
               warning_count):
        aid = uuid.uuid4().hex
        details = {
            "question_hash":
                hashlib.sha256(question.encode()).hexdigest()[:16],
            "provider": provider, "status": status,
            "citation_ids": [c.artifact_id for c in citations],
            "warnings": warning_count,
        }
        self.conn.execute(
            "INSERT INTO audit_events (id, persona, action, resource_id, "
            "details_json, at) VALUES (?,?,?,?,?,?)",
            (aid, persona.id, "agent_query", "",
             json.dumps(details),
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.conn.commit()
        return aid


# keep injection detector importable for callers/tests
_ = detect_prompt_injection
