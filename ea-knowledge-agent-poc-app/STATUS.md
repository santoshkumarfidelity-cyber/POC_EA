# POC status — acceptance criteria coverage

Verdicts are conservative: *Implemented* only where the current UI/API can
demonstrate the behaviour end-to-end on seeded synthetic data.

| AC | Criterion | Status | Evidence route |
|----|-----------|--------|----------------|
| AC-001 | Upload a supported file, complete metadata and tags, submit for review | Implemented | Contribute page → POST /api/artifacts creates DRAFT, then Govern transition to REVIEW |
| AC-002 | Register a video/document link with metadata and source location | Partial | Links supported via `source_url` + `registered_links`; dedicated link-registration UX is thin |
| AC-003 | Display authorized active tags and retrieve artifacts for a tag | Implemented | Discover page tag chips → GET /api/tags, /api/artifacts?tags= |
| AC-004 | Sort search results by upload date, newest first by default | Implemented | Discover sort control (`uploaded_desc` default) |
| AC-005 | Distinguish Internal/External and enforce approval/access | Partial | Audience stored, displayed and filterable; no External artifacts seeded, and External-publication workflow is not built |
| AC-006 | Identify latest approved artifact; expose authorized prior versions | Implemented | `is_current_approved` badge; detail drawer version list; `test_current_approved_version_is_preferred` |
| AC-007 | Answer from authorized content and show sources | Implemented | Ask page → POST /api/agent/query; grounded answers carry citation cards |
| AC-008 | State when authoritative information cannot be found | Implemented | Abstain path → `insufficient_evidence` status, empty citations |
| AC-009 | Move artifacts through Draft→Review→Approved→Superseded→Archived per permissions | Implemented | Govern page transitions; role-gated via `can_transition`; lifecycle history shown |
| AC-010 | Report stale, unowned, superseded, duplicate, broken-link content | Implemented | Reports page → GET /api/reports/quality (item detail curator/admin only) |

Known gaps for next increments: conversation IDs are persisted but
contextual follow-up retrieval is not yet implemented; real Entra auth,
SharePoint sync,
embeddings/vector search, PDF/XLSX/Visio/image extraction, external
publication workflow, bulk curator operations, transcript ingestion.
