# EA Knowledge Agent: Architecture Q&A

> **Note:** Some "why" answers are inferred from the architecture diagram, not from a written decision record. They are marked **(confirm with team)**.

## Contents

1. [What does each block do?](#1-what-does-each-block-do)
2. [Why did we pick these blocks?](#2-why-did-we-pick-these-blocks)
3. [Why Postgres for the audit log?](#3-why-postgres-for-the-audit-log)
4. [Why Google Vertex AI?](#4-why-google-vertex-ai)
5. [What tools are used in the Govern phase?](#5-what-tools-are-used-in-the-govern-phase)

---

## 1. What does each block do?

### Employees (React UI, role-based)
The front door. Everyone signs in and sees a view for their role. The screen shows only what that person is allowed to see.

### Microsoft 365
Where the company's documents and identity already live. The platform reads from it and does not replace it.

- **SharePoint (delta sync):** the source of the documents. Delta sync means we fetch only what changed (new, edited or deleted files) instead of copying everything again.
- **Entra ID (SSO and roles):** the company login system. It tells the platform who the person is and which roles and groups they belong to. No new passwords are needed.

### EA platform (hosted on Azure)
The core of the product. It runs in the client's own cloud and works in three ordered steps.

1. **Govern first:** every document is scanned for malware, its text is extracted, and it goes through the approval life cycle. Only one version is "current approved" at a time. Nothing reaches the AI before this step.
2. **Retrieve second:** when someone asks a question, the platform first filters to documents that are approved *and* that this person may see, and only then ranks them by relevance. Restricted content is removed before the search happens, so it cannot leak.
3. **Generate last:** the AI writes an answer using only the few excerpts it was given. The platform adds the citations itself. If no approved document supports an answer, the platform says so.

- **Governed store + audit log:** one place that holds documents, versions, permissions and search data, plus a record of who asked and accessed what.

### Google Cloud
The AI services. The platform calls them but does not depend on them for anything else.

- **Embeddings:** turn text into numbers so we can find documents by *meaning*, not just keywords. A search for "API strategy" can also find "Integration principles".
- **Gemini:** the language model. It only writes the answer from the excerpts it is handed. It stores nothing and decides nothing about access.

### The arrows in one sentence
SharePoint feeds documents into **Govern**, Entra ID feeds permissions into **Retrieve**, and **Retrieve** and **Generate** call Google for search and answer writing.

---

## 2. Why did we pick these blocks?

### Why three steps in this order?
The biggest risk with AI on internal documents is a confident wrong answer built from a draft, an outdated file, or something the person should not see. Putting the controls before the AI fixes that.

- **Govern first** means only approved, current, scanned content can ever be searched.
- **Retrieve second** means permissions are applied before ranking, so restricted content never reaches the AI.
- **Generate last** means the AI only phrases what it was given. The platform adds the citations, so the AI cannot invent them.

### Why SharePoint as the source?
The EA team already keeps documents there, so nobody has to move files or change habits. Delta sync keeps things current at low cost. Access is limited to one approved site (`Sites.Selected`), not the whole company, which is easier to get through security review.

### Why Entra ID for login and roles?
It is the company's existing identity system. Single sign-on means no new passwords, and permissions follow what IT already manages. It is also a trusted answer to "who is this person?", which the permission filtering depends on.

### Why one governed store and an audit log?
Keeping everything together makes it easy to enforce rules like "only one current approved version". The audit log gives security and compliance a record of who accessed what, and it stores hashes and IDs, not raw questions.

### Why host on Azure under client control?
The sensitive material (documents, permissions, audit trail) stays in the client's own environment, not a vendor's. This is usually the first thing a security team asks.

### Why Google for the AI, kept separate? **(confirm with team)**
The diagram labels it an "approved AI boundary", which suggests the client has already approved it. The design keeps its role narrow: embeddings for search and Gemini for writing answers. If the client wants another model later, only this block changes.

### Why not a simple chatbot over a shared drive?
It is faster to build, but it would answer from drafts, ignore permissions and leave no audit trail. For an EA team whose value is "the approved answer", those failures would lose trust.

---

## 3. Why Postgres for the audit log?

The design uses an **append-only Postgres table** that also **exports to the company's security monitoring system (SIEM)**. **(reasons inferred, confirm with team)**

| Reason | In simple words |
|---|---|
| Already there | The platform needs Postgres anyway, so there is no extra system to buy, run or secure. |
| Next to the data | Each audit entry can be linked to the exact document version and permissions at that moment. |
| Write-once | Postgres permissions and triggers can let the app add rows but never edit or delete them. |
| Easy to query | Compliance can ask plain SQL questions such as "who accessed this document last quarter?" |
| SIEM copy | A second copy outside the platform's control, so nobody can quietly change history. |
| Hashes and IDs only | We keep proof of what happened without storing the sensitive text of questions. |

**Honest trade-offs:**
- Postgres is not a purpose-built tamper-proof ledger. The SIEM export is what makes it defensible.
- Audit data grows fast, so it may need archiving later.
- For a PoC and pilot, this simple option is reasonable.

**One line for leadership:** *We keep the audit trail in the same database for simplicity, make it write-once, and copy it to the company's security system so it cannot be quietly altered.*

---

## 4. Why Google Vertex AI?

**(reasons inferred, confirm with team)**

- **Likely main reason, it is already approved.** The diagram calls Google Cloud an "Approved AI Boundary". Using a service the client already cleared avoids a slow new vendor review.
- **One provider for both AI jobs.** Vertex AI gives us embeddings and Gemini, with one contract and one set of controls.
- **Secure connection from Azure.** The platform uses workload identity federation, so Azure proves its identity to Google with no key files or stored passwords.
- **Business data terms.** Vertex AI is Google's enterprise service, and its terms generally say customer data is not used to train models. Confirm this against the client's actual agreement.
- **Replaceable.** Google holds no documents, makes no permission decisions and is not the source of truth. Swapping to another model only changes this block.

**If asked "why Google when we are on Azure?"** The platform is hosted where the client's identity and documents already are (Microsoft). The AI service is the one the client has approved. The connection is kept narrow and keyless to limit the added complexity. If the client has already approved Azure OpenAI, that would fit the same slot, so confirm which approval exists.

---

## 5. What tools are used in the Govern phase?

Listed in the order a document moves through the phase.

### 1. Getting documents in
- **Microsoft Graph API (msgraph SDK):** pulls files and permissions from SharePoint. Delta sync fetches only changes, including deletions.
- **SharePoint `Sites.Selected`:** limits access to the one approved site.

### 2. Ingestion worker (read and check the file)
- **python-docx, python-pptx, pypdf:** extract text from Word, PowerPoint and PDF files.
- **Malware scan:** checks each file first. The diagram does not name the scanner, so confirm which one is used.
- **Chunking:** splits text into searchable pieces.

### 3. Lifecycle engine (approval workflow)
- **State machine in the service layer (Python):** controls the path Draft → Review → Approved → Superseded → Archived and who can make each move.
- **Database rule:** only one current approved version of a document can exist. Enforcing this in the database means an app bug cannot break it.

### 4. Governed store (where it is kept)
- **PostgreSQL + pgvector:** document records, versions, permissions (ACLs) and search vectors.
- **Blob storage:** the original files.
- **Vertex AI embeddings:** create the vectors stored in pgvector. This is the one Google dependency in this phase.

### 5. Audit and quality
- **Append-only Postgres table, exported to SIEM:** records what happened.
- **Scheduled SQL quality reports:** flag stale, unowned and duplicate documents and broken links. This is the curator's to-do list.

### Supporting services
- **Azure Key Vault:** stores secrets.
- **OpenTelemetry:** monitoring.
- **CI/CD with Terraform or Bicep:** automated, repeatable deployment.

**One line for leadership:** *The Govern phase uses standard, mostly open-source tools (Python libraries and Postgres), so there is little vendor lock-in and little new licensing.*
