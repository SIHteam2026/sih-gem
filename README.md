# 🏛️ SIH26100 — OPAL: AI-Powered Integrated Bid Compliance Verification Platform for GeM

**Team:** IShowSolution  
**Problem Statement:** SIH26100 — AI-Powered Decision Support Layer for GeM Public Procurement Compliance Verification  
**Core Philosophy:** *"We don't simply scan documents. We verify bidder claims against tender requirements with complete provenance and deterministic gatekeeping."*

---

## 📌 Executive Summary

**OPAL** is an enterprise-grade, decision-support compliance intelligence platform designed for the **Government e-Marketplace (GeM)** and Indian Public Procurement under **GFR 2017**.

The platform automates the time-consuming and error-prone evaluation of multi-hundred-page technical and financial bids. It extracts tender clauses into strict JSON condition schemas, verifies claims against live government registries (GST / PAN), executes a **7-Layer Deterministic Rule Engine**, detects cross-bidder **Anti-Collusion / Cartel Rings**, and manages the **Two-Cover (Cover-1 Technical / Cover-2 Financial)** lifecycle through the **Action Studio** officer workbench.

```
Tender & Bid Ingestion (PDF / OCR / ZIP)
  └──> Clause Decomposition (Bounded Gemini 2.0 Flash & Groq Schemas)
        └──> Statutory Grounding (ChromaDB RAG — GFR 2017 & GeM GTC)
              └──> 7-Layer Deterministic Engine & Anti-Collusion Forensics
                    └──> Clarification Desk (Shortfall Notices & Technical Freeze)
                          └──> Cover-2 Financial Gatekeeper (BOQ Arithmetic & L1 Ranking)
                                └──> Action Studio (Human-in-the-Loop Decision & Immutable Audit Trail)
```

---

## 🏗️ System Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│               1. Opal Web Console (Next.js 14 / React 19 / Tailwind)   │
│  • Workspace Navigation           • 7-Layer Technical Scrutiny Matrix │
│  • Action Studio (Officer Bench)  • Financial Scrutiny (Cover-2 / BOQ) │
│  • Side-by-Side Evidence Drawer   • Immutable Audit Trail & LOA Export │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ REST API (Pydantic v2 Contracts)
┌───────────────────────────────────▼────────────────────────────────────┐
│               2. Application Backend (FastAPI / Python 3.11)           │
│  • Multi-Format Ingestion (PyMuPDF + Tesseract OCR + Safe ZIP Sandbox) │
│  • Bounded AI Router (Gemini 2.0 Flash & Groq LLM Inference Pool)      │
│  • 7-Layer Deterministic Rule Engine & Cross-Bidder Forensics Aggregator│
│  • Clarification Desk, Shortfall Engine & Technical Freeze Gatekeeper  │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────┐ ┌──────────────────────────────────┐
│  3. Data & Storage Layer         │ │  4. External Verification Adapters│
│  • Supabase (PostgreSQL + RLS)   │ │  • Sandbox.co.in GSTIN API (Live) │
│  • ChromaDB (GFR 2017 Vector DB) │ │  • Central PAN / MCA Verifiers    │
│  • Document & OCR Layout Cache   │ │  • Central Debarment / Blacklists │
└──────────────────────────────────┘ └──────────────────────────────────┘
```

---

## 🛡️ The 7-Layer Deterministic Verification Engine

Our system enforces a strict boundary between **AI semantic understanding** and **deterministic compliance gatekeeping** (zero LLM math/threshold hallucinations):

| Layer | Verification Scope | Core Technology |
| :--- | :--- | :--- |
| **Layer 1: Identity & Admin** | Live GSTIN active status, 10-character PAN syntax, EMD exemptions. | **Sandbox.co.in APIs + `httpx` + Regex** |
| **Layer 2: Document Integrity** | SHA-256 cryptographic hashes, page-tree corruption, missing mandatory files. | **PyMuPDF (`fitz`) + `hashlib`** |
| **Layer 3: Financial & Commercial** | 3-year turnover threshold, net worth math, CA 18-digit UDIN syntax check. | **Python 3.11 `Decimal` + Regex** |
| **Layer 4: Past Performance** | Similar contract values (80%/50%/40% rules), completion certificate recency. | **Pydantic v2 + `datetime` (UTC)** |
| **Layer 5: Corporate Risk** | Central debarment lists, blacklist registries, evasive legal declarations. | **Supabase PostgreSQL + Pattern Scanner** |
| **Layer 6: Technical Specs** | Technical parameter matching, upper/lower engineering tolerance bounds. | **Gemini 2.0 Flash + Python Comparator** |
| **Layer 7: Collusion Forensics** | PDF metadata collisions, creation timestamps, shared CA UDINs, text clones. | **PyMuPDF Metadata + `difflib`** |

---

## 📂 Repository File Structure & Key Modules

```
sih-gem/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── ai_router.py              # Multi-key LLM fallback (Gemini / Groq)
│   │   │   ├── prompts.py                # Bounded system prompts & JSON schemas
│   │   │   └── llm_evaluator_service.py  # LLM compliance reasoning service
│   │   ├── api/
│   │   │   ├── procurement_router.py     # Core procurement lifecycle API
│   │   │   ├── action_studio_router.py   # Officer decision workbench router
│   │   │   └── mock_gem_router.py        # GeM portal integration mock/sandbox
│   │   ├── db/
│   │   │   ├── client.py                 # Unified database client & persistence mode
│   │   │   └── supabase_client.py        # Supabase PostgreSQL client
│   │   ├── models/
│   │   │   ├── tender_contract.py        # RequirementEvaluationContract schemas
│   │   │   ├── verification.py           # VerificationFinding & Layer models
│   │   │   ├── evidence.py               # BidderClaim, ProvenanceRecord models
│   │   │   └── financial.py              # BOQ item evaluation & ALB models
│   │   ├── rules/
│   │   │   ├── layers/                   # 7 Deterministic Rule Verifiers
│   │   │   │   ├── administrative_identity.py
│   │   │   │   ├── ingestion_integrity.py
│   │   │   │   ├── financial_commercial.py
│   │   │   │   ├── past_performance_capacity.py
│   │   │   │   ├── corporate_risk.py
│   │   │   │   ├── adversarial_technical.py
│   │   │   │   └── anti_collusion.py
│   │   │   └── forensics/                # Cross-Bidder Cartel Detection
│   │   │       ├── metadata_collision.py
│   │   │       ├── formatting_clones.py
│   │   │       ├── financial_overlap.py
│   │   │       └── aggregator.py
│   │   └── services/
│   │       ├── multi_format_extractor.py # PDF / OCR / Spreadsheet extraction
│   │       ├── claim_extraction_service.py
│   │       ├── contradiction_service.py  # Intra-bidder document reconciliation
│   │       ├── financial_evaluation_service.py # Cover-2 BOQ gatekeeper & L1
│   │       ├── clarification_service.py  # Shortfall notice generation
│   │       └── rag_service.py            # ChromaDB GFR legal vector store
│   └── tests/                            # 20+ Automated Unit & E2E Test Suites
│
├── frontend/
│   └── src/
│       ├── app/                          # Next.js 14 App Router Pages
│       │   ├── procurements/             # Procurement cases & dashboards
│       │   └── workspace/                # Active officer workspace
│       ├── components/
│       │   └── procurement/
│       │       ├── ActionStudio/         # Human-in-the-loop decision center
│       │       ├── TechnicalScrutiny/    # 7-Layer compliance matrix
│       │       ├── FinancialScrutiny/    # Cover-2 BOQ scrutiny table
│       │       └── EvidenceComparison.tsx# Side-by-Side discrepancy viewer
│       └── lib/ & types/                 # Shared TypeScript models & API clients
│
└── dfd_simplified_presentation.png       # Presentation Architecture Diagram
```

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
* Python 3.11+
* Node.js 18+ / npm
* Tesseract OCR installed on PATH
* Supabase Account & Sandbox.co.in API Key (Optional for offline mock mode)

### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.api.main:app --reload --port 8000
```
* API Docs available at: `http://localhost:8000/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
* Web Console available at: `http://localhost:3000`

### 4. Running Verification Test Suites
```bash
cd backend
pytest tests/ -v
```

---

## 🌟 Key Innovations & Compliance Standards

1. **GFR 2017 & GeM Policy Aligned**: Fully respects two-cover procurement guidelines; financial Cover-2 remains sealed until Cover-1 is frozen.
2. **Deterministic Gatekeeping**: Math, turnover benchmarks, expiry dates, and debarment checks are evaluated in code, not left to LLM discretion.
3. **Cartel & Collusion Radar**: Identifies shared PDF authors, creation timestamps ($< 120\text{s}$), cloned text layouts, and shared CA UDINs across competing bidders.
4. **Human-in-the-Loop Action Studio**: Generates auditable Shortfall Notices and Draft Award Memos with immutable cryptographic logging.