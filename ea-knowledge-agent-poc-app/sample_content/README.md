# Sample content

The POC seeds its corpus automatically into `data/poc.db` on first run —
see `src/ea_knowledge_agent/seed.py`. All content is synthetic EA material
(strategy, templates, standards, playbooks) with fictional `example.invalid`
source URLs. **Do not place real client data in this directory or corpus.**

To exercise file upload from the Contribute page, use any local TXT, MD,
DOCX or PPTX file. PDF/XLSX/Visio/images register metadata but return an
explicit "extraction pending" warning rather than pretending to parse.
