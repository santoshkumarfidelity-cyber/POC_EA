# EA / ATLAS — Knowledge Agent POC (first vertical slice)

A runnable, offline, standard-library-only proof of the governed knowledge
journey described in `../requirements_summary.md` and the V2 deck:
**discover → contribute → govern → reuse**, with a grounded, permission-
aware AI experience on top.

This is a POC increment, **not** a production system. Persona switching is
a demo convenience, not authentication. SQLite, local keyword retrieval and
stdlib file extraction stand in for managed storage, hybrid/vector search
and production parsers. Claude and SharePoint/Graph are adapter seams,
inactive by default. **Never load real client data.**

## Architecture

```
web/ (HTML/CSS/JS, no build)  ── same process ──  api.py (http.server)
                                                     │
              ┌──────────────┬───────────────────────┤
        repository.py   retrieval.py           agent.py ── claude_client.py (opt)
        (ACL + audit,   (approved/current      (sanitize → synthesize
         lifecycle)      evidence only)         → cite or abstain)
              │                 │
        database.py ── seed.py ── guardrails.py (injection, validation)
              │
        SQLite data/poc.db   +  seams: auth.py (Entra seam),
        sharepoint_connector.py (Sites.Selected/delta seam),
        file_extraction.py (parser seam)
```

Trust model: every repository/retrieval query applies group ACLs; only
`APPROVED` current versions are agent evidence; Claude output returns
through validation; audit events store hashes/IDs, never raw prompts or
bodies.

## Quick start

```bash
cd ea-knowledge-agent-poc-app
make run          # serves http://127.0.0.1:8765 (seeds data/poc.db once)
make test         # 25 unittest acceptance checks
make reset-demo   # deletes data/poc.db only
make check        # compileall + tests
```

No virtualenv or packages needed — Python 3.10+ standard library only.
Copy `.env.example` to `.env` is *not* required; env vars are read directly.

## Demo walkthrough (mapped to acceptance criteria)

1. **Ask** (AC-007/008): try `Show the latest Insurance technology
   strategy` → grounded answer citing *Insurance Technology Strategy
   v4.2*. Then `What is our policy on quantum computing hardware?` → safe
   abstention.
2. **Permissions** (AC-006/GR): `What is the approved API strategy?` as
   *consumer* answers only from authorized artifacts — the restricted
   *Enterprise API Strategy* never appears in citations or the Discover
   list. Switch persona to *admin* → the answer cites it directly.
3. **Discover** (AC-003/004): tag chips, lifecycle/audience filters, sort
   newest-first; open a card → drawer shows source link, versions,
   lifecycle history (v4.1 superseded under v4.2's family).
4. **Contribute** (AC-001): fill the form (or attach TXT/DOCX/PPTX) →
   artifact created as DRAFT; duplicates and missing metadata are
   rejected with clear errors.
5. **Govern** (AC-009): as contributor submit the draft for review; as
   approver approve it (prior approved version in the family is
   superseded automatically); consumer sees read-only explanation.
6. **Reports** (AC-010): curator/admin see item-level stale, unowned,
   superseded, duplicate and broken-link rows; other personas see counts
   and the permission note.
7. **Audit** (GR): `GET /api/audit/recent?persona=curator` lists sanitized
   events — question hashes, never raw prompts.

## Configuration

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | Optional Claude adapter (generation only, after ACL/policy checks; fails closed to local synthesis) |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `SHAREPOINT_SITE_ID`, `SHAREPOINT_DRIVE_ID` | SharePoint/Graph seam — **not called** by the demo; `/api/integrations` reports status only |
| `POC_HOST`, `POC_PORT`, `POC_DB`, `POC_WEB_DIR` | Server overrides |

## Security limitations (explicit)

- Persona dropdown is **not authentication** — production requires Entra
  ID SSO/RBAC at the identity seam.
- Retrieval is deterministic keyword/metadata ranking; embeddings/vector
  search are a seam, not implemented.
- PDF, XLSX, Visio and image extraction are pending production parsers;
  such uploads register metadata as `PENDING`, but they cannot be
  approved and are never used as agent evidence until extraction
  succeeds.
- SQLite is single-node demo storage; managed storage/search products
  remain client architecture decisions.
- Audit is append-only JSON rows; production needs immutable/WORM audit.
- Synthetic data only; no PII/PHI and no automated decisions.

## Next increments

Entra adapter behind `auth.py`; SharePoint `Sites.Selected` + delta sync
via `sharepoint_connector.py`; embedding index behind `retrieval.py`;
contextual follow-up retrieval; production extractors; transcript ingestion;
external-publication workflow; curator bulk operations.
