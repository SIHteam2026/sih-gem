# .repobrain/rules.md

## IShowSolution — Compact Shared Rules

### Mission
Build SIH26100 as an evidence-reconciliation and compliance-reasoning system for GeM procurement.

> We don't simply verify documents. We verify bidder claims against tender requirements.

The procurement officer remains the final decision-maker.

### Architecture
Tender → Requirements → Applicability → Evidence → Claims → Verification → Rules → Contradictions/Ambiguity → Review → Human Decision → Audit

Keep these concerns modular:
- Tender Intelligence
- Requirement & Applicability
- Document Intelligence
- Evidence/Normalization
- Entity Resolution
- Compliance Rules
- Contradiction/Ambiguity/Risk
- Human Review/Audit/Feedback

Government systems are evidence adapters, not the reasoning core.

### AI policy
LLMs: semantic understanding, extraction, classification, matching, ambiguity detection, explanations.

Deterministic code: thresholds, dates, expiry, numerical logic, eligibility, scoring, state transitions.

Never allow an LLM to silently decide deterministic compliance conditions.

### Evidence policy
Important findings must be traceable to source evidence:

clause → requirement → claim → evidence → verification → rule → finding

Use explicit states:
PASS / FAIL / REVIEW / UNVERIFIED / NOT_APPLICABLE

Unavailable verification is not compliance.

### Government/API policy
Use official/authorized APIs, gateways, and sandboxes only.

Never bypass CAPTCHA, use private/undocumented endpoints, unauthorized scraping, hard-coded credentials, or fabricated live results.

### Security
Protect sensitive bidder/business data. Validate uploads, isolate parsing, protect secrets, use auth/RBAC where appropriate, minimize retention, audit important actions, and keep secrets out of git/logs/frontend bundles.

### Agent workflow
Before editing:
1. Read AGENTS.md.
2. Inspect git status and repository structure.
3. Inspect relevant implementation.
4. Verify the feature is not already implemented.
5. Make the smallest coherent change.
6. Preserve unrelated work.
7. Test/lint/type-check/build where practical.
8. Review the actual result.
9. Report changes, tests, and limitations.

### Codex + Antigravity
Both agents share this repository. Never blindly overwrite another agent's work. Avoid broad refactors and formatting churn. Reconcile conflicts deliberately.

### Product priority
Correctness > evidence traceability > deterministic logic > security > reliability > explainability > maintainability > polish > novelty.

### Demo target
Tender local content >=20%; bidder declares 27%; evidence indicates 14%.

The system should identify the requirement, map the evidence, detect the contradiction, show provenance, mark REVIEW, and leave the final decision to the officer.

### North star
> Does this feature help a procurement officer make a faster, more reliable, more explainable compliance decision?
