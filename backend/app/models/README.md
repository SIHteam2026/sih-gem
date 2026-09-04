# OPAL Tender Intelligence & Requirement Evaluation Contract Architecture

## Overview

In **OPAL** (SIH26100), the **Tender Intelligence** engine is responsible for parsing procurement tenders and transforming them into a structured, auditable understanding of tender requirements.

```
Tender PDF Document
        ↓
Tender Intelligence (PDF Parsing + Gemini Structured Extraction)
        ↓
TenderRequirement (Canonical Persisted Domain Model)
        ↓
RequirementEvaluationContract (Canonical Downstream Read Contract)
        ↓
Downstream Engines (Document Matching, Deterministic Compliance Rules,
External Registries, Contradiction Detection, Officer Review)
```

---

## Domain Models vs. Evaluation Contracts

| Object | Model File | Purpose | Persistence Layer | Mutability |
|---|---|---|---|---|
| **`TenderRequirement`** | [`tender.py`](file:///backend/app/models/tender.py) | Canonical representation of extracted tender clauses, conditions, provenance, and ambiguity. | Persisted in Supabase `public.tender_requirements` (linked to `public.tenders`). | Stored and versioned per tender. |
| **`RequirementEvaluationContract`** | [`tender_contract.py`](file:///backend/app/models/tender_contract.py) | Standardized, strongly typed downstream contract for automated rules, evidence extraction, and officer review. | Computed on read (`GET /api/tenders/{id}/evaluation-contract`). | Immutable read representation. |
| **`TenderEvaluationContract`** | [`tender_contract.py`](file:///backend/app/models/tender_contract.py) | Complete tender package aggregating all requirement contracts with verification mode distributions. | Computed on read. | Immutable read representation. |

---

## Evaluation Modes (`EvaluationMode`)

Every requirement in OPAL is deterministically classified into one or more execution modes:

1. **`DETERMINISTIC`**:
   - Exact mathematical or threshold comparison (e.g., Turnover $\ge$ INR 5.0 Cr, Local Content $\ge$ 20%, Warranty $\ge$ 24 Months, Past Contracts Count $\ge$ 2).
   - Executed deterministically by compliance rule engines without LLM hallucinations.
2. **`DOCUMENT_PRESENCE`**:
   - Verification that a mandatory statutory or technical document is attached (e.g., OEM MAF, PAN card, EMD receipts).
3. **`EXTERNAL_VERIFICATION`**:
   - Verification against authoritative government or statutory registries (e.g., GSTN portal for active GSTIN, Income Tax for PAN, Debarment/Holiday listings).
4. **`SEMANTIC`**:
   - Qualitative/semantic scope evaluation (e.g., verifying OEM authorization model coverage or technical specification compatibility).
5. **`HUMAN_REVIEW`**:
   - Subjective, vague, or underspecified clauses that lack objective numeric metrics and require procurement officer discretion.

---

## Canonical Evaluation Fields (`CanonicalEvaluationField`)

Standardized field identifiers allow downstream rule engines to evaluate parameters programmatically:

- `average_annual_turnover`: Financial turnover threshold in specified currency (e.g. `50000000.0 INR` over `3.0` years).
- `local_content_percentage`: Minimum local content percentage under Make in India guidelines (e.g. `20.0 PERCENT`).
- `warranty_months`: Comprehensive onsite warranty period in months (e.g. `24.0 MONTHS`).
- `similar_contract_count`: Count of past similar executed contracts within timeframe (e.g. `2.0 COUNT` in `5.0` years).
- `gst_status`: Statutory GST registration and return filing status (`ACTIVE`).
- `pan_validity`: PAN status issued by Income Tax Department (`VALID`).
- `oem_authorization`: Manufacturer Authorization Form status (`AUTHORIZED`).
- `debarment_status`: Non-blacklisting / non-holiday listing status (`CLEAR`).

---

## Statutory Applicability & Exemptions (`ApplicabilityContract`)

Tender Intelligence extracts and standardizes statutory exemptions:
- **`msme_exemption`**: True if Micro & Small Enterprises (MSEs) registered on Udyam are exempt (e.g., from turnover or experience requirements).
- **`startup_exemption`**: True if DPIIT-recognized startups are exempt.
- **`exemption_basis`**: Specific tender clause or Government order basis (e.g., GeM GTC / PPO 2017).

---

## Provenance Guarantees (`ProvenanceContract`)

Traceability is a core pillar of OPAL:
- **`page_number`**: 1-indexed page number in the original tender PDF.
- **`clause_number`**: Exact clause reference (e.g., `Clause 2.1`, `Section 3.4`).
- **`section_title`**: Section header in the RFP.
- **`verbatim_quote`**: Exact clause text extracted directly from the source PDF without AI paraphrasing.

---

## Ambiguity Radar (`AmbiguityContract`)

When tender clauses use subjective language (e.g., *"adequate experience"*, *"satisfactory reputation"*):
- `is_ambiguous`: Set to `True`.
- `ambiguity_type`: Categorized (e.g., `VAGUE_TERMINOLOGY`, `THRESHOLD_MISSING`).
- `ambiguity_reason`: Explains the missing metrics.
- `suggested_review_question`: Formulates actionable guidance for the procurement officer.
- **No false thresholds**: The contract never fabricates numeric values for vague requirements.

---

## What the Tender Intelligence Contract Does NOT Decide

In accordance with OPAL system boundaries:
- **No Bidder Evaluation**: Tender Intelligence does NOT evaluate whether a bidder passes or fails.
- **No Autonomous Decisions**: It does NOT make qualification/disqualification decisions.
- **No Contradiction Detection**: Cross-document reconciliation occurs downstream in the compliance engine.
- **No Mutation**: Converting `TenderRequirement` into `RequirementEvaluationContract` is a pure, idempotent read operation that never alters the underlying database state.
