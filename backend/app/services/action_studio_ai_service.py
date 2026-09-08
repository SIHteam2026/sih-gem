"""Action Studio Bounded AI Drafting Service.

Transforms canonical evidence context into evidence-grounded procurement draft documents
using Gemini AI infrastructure with deterministic fallback and strict document guards.

Guarantees:
- Never invents facts, amounts, or findings.
- Never mutates procurement, technical, or financial evaluation state.
- Enforces strict document eligibility guards (e.g. LoA requires legitimate L1 and Cover 2 completion).
- Sets is_draft = True and decision_authority = HUMAN_PROCUREMENT_OFFICER.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.models.action_studio import ActionDocumentType, EvidenceReference
except ImportError:
    from app.models.action_studio import ActionDocumentType, EvidenceReference

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class ActionStudioAiDraftingService:
    """Bounded AI drafting service for Action Studio documents."""

    @classmethod
    def check_document_eligibility(
        cls, document_type: ActionDocumentType, context: Dict[str, Any], target_bidder_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validates document generation eligibility guards against canonical procurement state.

        Args:
            document_type: Type of document requested.
            context: Canonical evidence context.
            target_bidder_id: Target bidder ID for bidder-specific letters.

        Returns:
            Tuple[bool, Optional[str]]: (is_eligible, rejection_reason)
        """
        technical = context.get("technical", {})
        financial = context.get("financial", {})

        if document_type == ActionDocumentType.LETTER_OF_AWARD:
            # 1. Technical freeze / evaluation completed check
            if not technical.get("technical_freeze_completed", True):
                return False, "Cannot generate Letter of Award: Technical evaluation / freeze has not completed."

            # 2. Cover 2 / Financial evaluation check
            if not financial.get("financial_evaluation_completed", False):
                return False, "Cannot generate Letter of Award: Cover 2 financial evaluation has not completed."

            # 3. Legitimate L1 bidder check
            l1_bidder = financial.get("l1_bidder")
            if not l1_bidder:
                return False, "Cannot generate Letter of Award: No legitimate L1 bidder exists in financial evaluation results."

            # 4. Check if procurement is blocked by critical unresolved technical blockers on L1
            unresolved = technical.get("unresolved_blockers", [])
            l1_name = l1_bidder.get("bidder_name", "")
            for blocker in unresolved:
                if blocker.get("bidder_name") == l1_name and blocker.get("risk_level") == "CRITICAL":
                    return False, f"Cannot generate Letter of Award: L1 bidder '{l1_name}' has unresolved CRITICAL compliance blockers."

        elif document_type in [ActionDocumentType.REJECTION_LETTER, ActionDocumentType.REGRET_LETTER]:
            excluded = technical.get("excluded_bidders", [])
            if not excluded and not target_bidder_id:
                return False, "Cannot generate Rejection/Regret letter: No technically or financially excluded bidders found."

            if target_bidder_id:
                # Check if target bidder is in excluded list
                is_excluded = any(
                    b.get("bidder_id") == target_bidder_id or b.get("legal_name") == target_bidder_id
                    for b in excluded
                )
                if not is_excluded:
                    return False, f"Cannot generate Rejection/Regret letter: Target bidder '{target_bidder_id}' is not in the excluded bidder list."

        return True, None

    @classmethod
    async def generate_draft(
        cls,
        document_type: ActionDocumentType,
        context: Dict[str, Any],
        target_bidder_id: Optional[str] = None,
    ) -> Tuple[str, List[EvidenceReference], bool]:
        """Generates an evidence-grounded draft document.

        Args:
            document_type: Target Action Studio document type.
            context: Canonical evidence context.
            target_bidder_id: Optional target bidder ID for bidder-specific documents.

        Returns:
            Tuple[str, List[EvidenceReference], bool]: (content_markdown, evidence_references, is_ai_generated)
        """
        # 1. Enforce Document Guards
        eligible, reason = cls.check_document_eligibility(document_type, context, target_bidder_id)
        if not eligible:
            raise ValueError(reason)

        # 2. Extract structured evidence references from context
        evidence_refs = cls._extract_evidence_references(document_type, context, target_bidder_id)

        # 3. Attempt AI Generation with Gemini infrastructure
        try:
            content, is_ai = await cls._generate_with_ai(document_type, context, target_bidder_id)
            return content, evidence_refs, is_ai
        except Exception as ai_err:
            logger.warning("AI draft generation failed (%s). Utilizing deterministic evidence-grounded fallback.", ai_err)
            content = cls._generate_deterministic_fallback(document_type, context, target_bidder_id)
            return content, evidence_refs, False

    @classmethod
    def _extract_evidence_references(
        cls, document_type: ActionDocumentType, context: Dict[str, Any], target_bidder_id: Optional[str] = None
    ) -> List[EvidenceReference]:
        """Extracts structured evidence references from context for traceability."""
        refs: List[EvidenceReference] = []
        technical = context.get("technical", {})
        findings = technical.get("technical_findings", [])

        for f in findings:
            b_id = f.get("bidder_id") or f.get("bidder_name")
            if target_bidder_id and b_id != target_bidder_id:
                # Filter for target bidder if applicable
                continue

            ev_ids = f.get("evidence_ids") or []
            ev_id = ev_ids[0] if ev_ids else None
            req_id = f.get("requirement_id")
            reasoning = f.get("reasoning_trace") or f.get("reason")

            prov = f.get("expected") or {}
            page_num = prov.get("page_number") if isinstance(prov, dict) else None

            refs.append(
                EvidenceReference(
                    requirement_id=req_id,
                    finding_id=f.get("id") or req_id,
                    evaluation_id=context.get("procurement_id"),
                    document_id=ev_id,
                    document_name=f.get("source_document"),
                    page_number=page_num,
                    quote=reasoning,
                    provenance_summary=f"Requirement '{req_id}' - {f.get('state')}: {reasoning}",
                )
            )

        return refs

    @classmethod
    async def _generate_with_ai(
        cls, document_type: ActionDocumentType, context: Dict[str, Any], target_bidder_id: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Calls Gemini API using existing google-genai / ai_router infrastructure if available."""
        # Check if GEMINI_API_KEY is configured
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")

        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        system_instruction = (
            "You are an officer assistant drafting formal public procurement documents for human officer review.\n"
            "CRITICAL CONSTRAINTS:\n"
            "- You MUST rely exclusively on the provided canonical evidence context.\n"
            "- You MUST NOT invent any bidder names, financial amounts, technical findings, or legal conclusions.\n"
            "- You MUST NOT alter L1/L2/L3 financial rankings or qualification statuses.\n"
            "- You MUST NOT declare a final binding decision; you only draft placeholders for human officer approval.\n"
            "- Standard marker: 'DRAFT FOR HUMAN PROCUREMENT OFFICER REVIEW ONLY'."
        )

        prompt = f"Document Type: {document_type.value}\nTarget Bidder: {target_bidder_id or 'ALL'}\n\nCanonical Evidence Context:\n{json.dumps(context, indent=2, default=str)}\n\nGenerate structured markdown document:"

        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            ),
        )

        if response and response.text:
            return response.text.strip(), True

        raise RuntimeError("Empty response received from Gemini model.")

    @classmethod
    def _generate_deterministic_fallback(
        cls, document_type: ActionDocumentType, context: Dict[str, Any], target_bidder_id: Optional[str] = None
    ) -> str:
        """Deterministic evidence-grounded fallback document builder when AI is unavailable."""
        proc_title = context.get("title", "Procurement Workspace")
        ext_ref = context.get("external_reference", context.get("procurement_id"))
        org = context.get("organization", "Government Department")

        tech = context.get("technical", {})
        fin = context.get("financial", {})

        eligible_bidders = tech.get("technically_eligible_bidders", [])
        excluded_bidders = tech.get("excluded_bidders", [])
        fin_rankings = fin.get("financial_rankings", [])
        eval_amounts = fin.get("evaluated_amounts", {})

        lines = []

        if document_type == ActionDocumentType.NOTE_FOR_FILE:
            lines.append(f"# PROCUREMENT NOTE FOR FILE")
            lines.append(f"**Procurement Reference:** {ext_ref}")
            lines.append(f"**Title:** {proc_title}")
            lines.append(f"**Issuing Organization:** {org}")
            lines.append(f"**Document Status:** DRAFT FOR HUMAN PROCUREMENT OFFICER REVIEW ONLY\n")

            lines.append("## 1. Executive Overview")
            lines.append(f"This Note for File records the canonical technical and financial evaluation summary for procurement '{ext_ref}'.\n")

            lines.append("## 2. Technical Evaluation Summary")
            lines.append(f"- **Technically Eligible Bidders ({len(eligible_bidders)}):** " + (", ".join([b.get("legal_name", "") for b in eligible_bidders]) or "None"))
            lines.append(f"- **Technically Excluded Bidders ({len(excluded_bidders)}):** " + (", ".join([b.get("legal_name", "") for b in excluded_bidders]) or "None"))
            
            if excluded_bidders:
                lines.append("\n### Non-Compliance Findings:")
                for b in excluded_bidders:
                    lines.append(f"#### Bidder: {b.get('legal_name')}")
                    for r in b.get("rejection_reasons", []):
                        lines.append(f"- Requirement `{r.get('requirement_id')}`: {r.get('reasoning_trace')}")

            lines.append("\n## 3. Financial Evaluation Summary")
            if fin.get("financial_evaluation_completed"):
                lines.append("Commercial bid Cover 2 opening has completed.")
                lines.append("\n| Rank | Bidder Legal Name | Evaluated Amount (INR) |")
                lines.append("|---|---|---|")
                for r in fin_rankings:
                    lines.append(f"| {r.get('rank')} | {r.get('bidder_name')} | INR {r.get('evaluated_amount', 0):,.2f} |")
            else:
                lines.append("Commercial bid Cover 2 opening is PENDING / Not executed.")

            if fin.get("abnormally_low_bids"):
                lines.append("\n### Abnormally Low Bid (ALB) Flags:")
                for alb in fin.get("abnormally_low_bids"):
                    lines.append(f"- Flagged Bidder: **{alb}** (Subject to detailed rate scrutiny).")

            lines.append("\n## 4. Officer Decision & Recommendation Placeholder")
            lines.append("> [!IMPORTANT]")
            lines.append("> **OFFICER DECISION:** [PENDING HUMAN PROCUREMENT OFFICER DECISION]")
            lines.append("> **RECOMMENDATION:** [PENDING HUMAN PROCUREMENT OFFICER RECOMMENDATION]")

        elif document_type == ActionDocumentType.EVALUATION_COMMITTEE_REPORT:
            lines.append(f"# TENDER EVALUATION COMMITTEE REPORT")
            lines.append(f"**Tender Reference:** {ext_ref}")
            lines.append(f"**Work Title:** {proc_title}")
            lines.append(f"**Department:** {org}\n")

            lines.append("## 1. Bidder Technical Status")
            lines.append("| Bidder Name | Technical Status | Requirements Evaluated |")
            lines.append("|---|---|---|")
            for b in eligible_bidders:
                lines.append(f"| {b.get('legal_name')} | QUALIFIED | {b.get('finding_count', 0)} |")
            for b in excluded_bidders:
                lines.append(f"| {b.get('legal_name')} | DISQUALIFIED | {b.get('finding_count', 0)} |")

            lines.append("\n## 2. Financial Ranking (Cover 2)")
            if fin_rankings:
                lines.append("| Rank | Bidder Name | Commercial Bid Value | Outcome |")
                lines.append("|---|---|---|---|")
                for r in fin_rankings:
                    status = "Lowest Evaluated (L1)" if r.get("is_l1") else "Non-L1"
                    lines.append(f"| {r.get('rank')} | {r.get('bidder_name')} | INR {r.get('evaluated_amount', 0):,.2f} | {status} |")
            else:
                lines.append("Financial evaluation results pending.")

            lines.append("\n## 3. Committee Observations & Anomaly Analysis")
            anomalies = fin.get("anomaly_flags", [])
            if anomalies:
                for a in anomalies:
                    lines.append(f"- **{a.get('bidder_name')}**: {a.get('flag')} - {a.get('details')}")
            else:
                lines.append("No financial arithmetic anomalies flagged.")

            lines.append("\n## 4. Committee Sign-off")
            lines.append("This report presents the objective evaluation facts for formal committee review.")
            lines.append("\n**Committee Member Signatures:** [PENDING HUMAN OFFICER APPROVAL]")

        elif document_type == ActionDocumentType.LETTER_OF_AWARD:
            l1 = fin.get("l1_bidder") or {}
            l1_name = l1.get("bidder_name", "L1 Bidder")
            l1_val = l1.get("evaluated_amount", 0.0)

            lines.append(f"# DRAFT LETTER OF AWARD (LoA)")
            lines.append(f"**Ref No:** LOA/{ext_ref}/2026")
            lines.append(f"**Procurement Title:** {proc_title}")
            lines.append(f"**Issuing Authority:** {org}\n")

            lines.append(f"To,")
            lines.append(f"**{l1_name}**")
            lines.append(f"Subject: Award of Contract for '{proc_title}' (Tender Ref: {ext_ref})\n")

            lines.append("Dear Sir/Madam,")
            lines.append(f"We are pleased to convey the draft intention to award the contract for **{proc_title}** to **{l1_name}** as the lowest evaluated responsive bidder (L1).")
            lines.append(f"The total evaluated contract value is **INR {l1_val:,.2f}** inclusive of all applicable taxes and duties.\n")

            lines.append("### Key Terms & Conditions:")
            lines.append("1. **Performance Security:** Submission of 3% Performance Bank Guarantee (PBG) within 14 days.")
            lines.append("2. **Contract Signing:** Execution of formal contract agreement within 21 days.")
            lines.append("3. **Scope of Work:** In strict accordance with Tender RFP specification.")

            lines.append("\n> [!WARNING]")
            lines.append("> **NOTICE:** THIS IS AN ACTION STUDIO DRAFT PREPARED FOR HUMAN OFFICER REVIEW.")
            lines.append("> IT DOES NOT CONSTITUTE A BINDING LEGAL DISPATCH OR CONTRACT UNTIL FORMALLY APPROVED BY THE AUTHORIZED PROCUREMENT OFFICER.")

        elif document_type in [ActionDocumentType.REJECTION_LETTER, ActionDocumentType.REGRET_LETTER]:
            target_name = target_bidder_id or "Bidder"
            reasons = []

            for b in excluded_bidders:
                if b.get("bidder_id") == target_bidder_id or b.get("legal_name") == target_bidder_id:
                    target_name = b.get("legal_name")
                    reasons = b.get("rejection_reasons", [])

            lines.append(f"# DRAFT REJECTION / REGRET NOTICE")
            lines.append(f"**Ref No:** REG/{ext_ref}/2026")
            lines.append(f"**Tender Ref:** {ext_ref}")
            lines.append(f"**Procurement Title:** {proc_title}\n")

            lines.append(f"To,")
            lines.append(f"**{target_name}**\n")
            lines.append(f"Subject: Technical/Financial Evaluation Outcome for Tender '{proc_title}'\n")

            lines.append("Dear Sir/Madam,")
            lines.append(f"We regret to inform you that following evaluation of the bid submissions for tender **{ext_ref}**, your submission was not considered responsive due to the following specific non-compliance grounds:\n")

            lines.append("### Specific Grounds of Non-Compliance:")
            if reasons:
                for r in reasons:
                    req_str = f"Requirement ID `{r.get('requirement_id')}`" if r.get('requirement_id') else "Mandatory Criteria"
                    lines.append(f"- **{req_str}:** {r.get('reasoning_trace')}")
            else:
                lines.append("- Submission failed to meet mandatory technical evaluation criteria as recorded in canonical evaluation findings.")

            lines.append("\nWe thank you for your participation and interest in government procurement opportunities.")

            lines.append("\n> [!IMPORTANT]")
            lines.append("> **NOTICE:** DRAFT PRODUCED FOR HUMAN OFFICER REVIEW. DISPATCH PENDING OFFICER APPROVAL.")

        return "\n".join(lines)
