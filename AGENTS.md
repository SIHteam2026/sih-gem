# AGENTS.md — IShowSolution Shared Project Rules

## Project
SIH26100 — AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement.

**Team:** IShowSolution

**Core principle:** We don't simply verify documents. We verify bidder claims against tender requirements.

The product is a decision-support layer around procurement workflow. It does not replace the procurement officer and must never autonomously make the final qualification/disqualification decision.

## Intended architecture
Tender
→ Tender Intelligence
→ Requirement Decomposition
→ Applicability
→ Required Evidence
→ Bidder Document Ingestion
→ Document Classification
→ OCR / Extraction
→ Normalization
→ Entity Resolution
→ Government / Authoritative Verification
→ Evidence Graph
→ Cross-Evidence Reconciliation
→ Deterministic Compliance Rules
→ Contradiction / Ambiguity / Risk Analysis
→ Human Review
→ Human Decision
→ Audit Trail

Conceptual engines:
1. Tender Intelligence
2. Requirement & Applicability
3. Document Intelligence
4. Evidence / Normalization
5. Entity Resolution
6. Compliance Rules
7. Contradiction / Ambiguity / Risk
8. Human Review / Audit / Feedback

External government services are evidence providers/adapters, not the intelligence core.

## Expected stack
Inspect the repository before assuming anything is implemented.

- Frontend: Next.js / React / Tailwind CSS
- Backend: Python / FastAPI
- Database: PostgreSQL / Supabase
- Vector search: pgvector where useful
- Document processing: PDF/image ingestion, OCR, layout/table extraction
- AI: LLMs with structured outputs
- External integrations: adapter-based
- Object storage: S3-compatible where needed
- Async jobs: Redis + Celery/RQ only if justified

## Evidence-first design
Important findings should be traceable through:

Tender clause
→ requirement
→ applicability
→ bidder claim
→ supporting evidence
→ authoritative verification
→ rule
→ finding
→ human decision

Record source, document/page, extracted claim, timestamp, rule/version, confidence, and verification status where available.

Never create an unsupported "verified" result.

## Compliance states
Prefer:
- PASS — sufficient evidence establishes compliance
- FAIL — reliable evidence establishes non-compliance
- REVIEW — conflicting/ambiguous evidence or human interpretation required
- UNVERIFIED — verification could not be completed
- NOT_APPLICABLE — requirement does not apply

An unavailable external service must not become PASS.

## AI vs deterministic logic
Use LLMs for:
- tender-language understanding
- extraction/classification
- semantic matching
- ambiguity identification
- explanations

Use deterministic rules for:
- thresholds
- dates/expiry
- numerical comparisons
- required/optional logic
- eligibility criteria
- scoring
- compliance-state transitions

Do not let an LLM silently decide deterministic procurement conditions. Validate and schema-constrain LLM outputs.

## Government integrations
Use official, authorized APIs, gateways, or sandboxes.

Never:
- bypass CAPTCHA
- scrape protected portals against their rules
- use undocumented/private endpoints
- hard-code credentials
- expose secrets in frontend code
- fabricate live verification responses

Connector failures should normally result in UNVERIFIED or REVIEW, not false compliance.

## Security
The system may handle sensitive bidder/business data.

At minimum:
- validate upload type/size
- safely isolate document parsing
- consider malware scanning
- protect secrets
- authentication/RBAC as appropriate
- minimize sensitive-data retention
- audit important actions
- never commit .env, API keys, tokens, certificates, or credentials

Do not claim government security certification unless actually obtained.

## Engineering workflow
Before changing code:

1. Read this file.
2. Inspect git status and repository structure.
3. Inspect relevant existing code/configuration.
4. Verify whether the requested feature already exists.
5. Make the smallest coherent change.
6. Preserve working functionality and unrelated work.
7. Run relevant tests, lint, type checks, and/or build where practical.
8. Inspect the actual result.
9. Report what changed, what was tested, and what remains.

Do not rebuild existing functionality merely because another agent implemented it.

## Codex + Antigravity collaboration
Both agents work in the same repository.

Before editing:
- inspect git status
- inspect recent commits
- inspect the relevant implementation
- avoid overwriting another agent's uncommitted work
- avoid broad formatting/rewrite changes

If another agent changed the same area, reconcile deliberately rather than blindly overwriting.

Keep commits focused when committing is appropriate.

## Current milestone guidance
A first GST verification slice has historically been implemented, including FastAPI, Next.js, GST verification, Sandbox.co.in integration, deterministic GST rules, Supabase history, and status badges.

This is historical guidance only. **Verify the current repository before relying on it.**

The next major milestone is a complete:
Tender → Requirements → Evidence → Verification → Contradiction → Human Review path.

Target:
- one full tender
- 5–7 requirement classes
- 3–5 document types
- GST integration appropriately live/sandboxed
- one additional meaningful verification source
- cross-document matching
- basic contradiction detection
- evidence traceability
- basic human-review workflow

## What not to build
Avoid:
- generic chatbot over PDFs
- generic RAG without compliance reasoning
- dashboard-only green/red checking
- autonomous qualification/disqualification
- fake government integrations
- unsupported fraud-detection claims
- unauthorized scraping/CAPTCHA bypass
- unnecessary microservices
- custom OCR/ML training when existing components suffice
- AI features added only for appearance

Keep extraction, normalization, verification, rules, reasoning, and presentation modular.

Do not bury compliance rules in UI code or prompts when they can be explicit.

## Demo target
A strong demo should show:

Tender: local content >=20%
Bidder declaration: 27%
Supporting evidence: 14%

Expected result:
- identify the requirement
- identify the claim/evidence
- detect the contradiction
- show provenance
- mark REVIEW
- leave final decision to the officer

## Product north star
> Does this feature help a procurement officer make a faster, more reliable, more explainable compliance decision from the available evidence?

Priority:
Correctness > evidence traceability > deterministic logic > security > reliability > explainability > maintainability > polish > novelty.
