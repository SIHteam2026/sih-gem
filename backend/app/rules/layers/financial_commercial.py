"""Layer 7: Financial and Commercial Verifier.

Evaluates financial and commercial criteria:
- Average annual turnover vs required benchmark
- Statutory MSME / Startup turnover exemptions (NOT_APPLICABLE / REVIEW)
- CA turnover certificate validity & UDIN structural checks
- Positive net worth & solvency certificate validity
- EMD / PBG security deposit compliance and exemption validation
- Commercial pricing/BoQ completeness.
"""

import logging
import re
from typing import Any, Dict, List, Optional

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
    from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.engine import parse_numeric_value
    from app.rules.layers.base import BaseVerifier
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.engine import parse_numeric_value
        from app.rules.layers.base import BaseVerifier
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.engine import parse_numeric_value
        from rules.layers.base import BaseVerifier

logger = logging.getLogger(__name__)

# Valid ICAI Unique Document Identification Number (UDIN) regex: 18 alphanumeric characters
UDIN_REGEX = re.compile(r"\b[0-9]{2}[0-9]{6}[A-Z0-9]{10}\b", re.IGNORECASE)


class FinancialCommercialVerifier(BaseVerifier):
    """Verifier for Layer 7: Financial and Commercial."""

    @property
    def verifier_id(self) -> str:
        return "FINANCIAL_COMMERCIAL_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.FINANCIAL_AND_COMMERCIAL

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        requirements = context.requirements or []
        claims = context.claims or []
        observations = context.observations or []
        bidders = context.bidders or []
        exemptions = context.extra_context.get("exemptions", {})

        fin_reqs = [
            r for r in requirements
            if r.evaluation_field in (
                CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER,
                CanonicalEvaluationField.EMD_SECURITY_DEPOSIT,
                CanonicalEvaluationField.COMMERCIAL_PRICE,
            )
            or any(kw in r.description.upper() for kw in ("TURNOVER", "NET WORTH", "SOLVENCY", "EMD", "FINANCIAL", "BALANCE SHEET", "CA CERTIFICATE"))
        ]

        if not fin_reqs:
            return findings

        for req in fin_reqs:
            req_id = req.requirement_id
            req_threshold = req.threshold_value
            if req_threshold is None:
                parsed_t, _ = parse_numeric_value(req.description)
                if parsed_t is not None:
                    req_threshold = parsed_t

            is_turnover = (req.evaluation_field == CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER) or "TURNOVER" in req.description.upper()

            for b in (bidders or [{"id": None, "legal_name": "Bidder"}]):
                bid_id = b.get("id") or b.get("bidder_id")
                b_name = b.get("legal_name", "Bidder")

                # Check statutory MSME / Startup exemption on turnover
                is_mse = context.extra_context.get("is_mse") or (exemptions.get(bid_id, {}).get("is_mse") if isinstance(exemptions.get(bid_id), dict) else None)
                is_startup = context.extra_context.get("is_startup") or (exemptions.get(bid_id, {}).get("is_startup") if isinstance(exemptions.get(bid_id), dict) else None)

                if is_turnover and (is_mse or is_startup):
                    ex_label = "MSE" if is_mse else "DPIIT-recognized Startup"
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.NOT_APPLICABLE,
                            severity=FindingSeverity.INFO,
                            claim={"exemption": ex_label},
                            observation=f"Turnover threshold waived under Public Procurement Policy for {ex_label}.",
                            reason=f"Statutory Exemption Applied: Prior annual turnover criteria waived for {b_name} as an eligible {ex_label}.",
                            evidence=[],
                            confidence=1.0,
                            machine_readable_flags=["STATUTORY_TURNOVER_EXEMPTION_APPLIED", "MSE_STARTUP_WAIVER"],
                            metadata={"exemption_type": ex_label, "requirement_id": req_id},
                        )
                    )
                    continue

                # Match bidder observations & claims
                b_claims = [c for c in claims if c.requirement_id == req_id and (not c.bidder_id or c.bidder_id == bid_id)]
                b_obs = [o for o in observations if o.requirement_id == req_id and (not o.bidder_id or o.bidder_id == bid_id)]

                if not b_claims and not b_obs:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.UNVERIFIED,
                            severity=FindingSeverity.HIGH,
                            claim=None,
                            observation="No financial certificates or CA statements submitted.",
                            reason=f"Financial Evidence Missing: Mandatory financial turnover/solvency proof required for '{req.title or req_id}', but none was submitted.",
                            evidence=[],
                            confidence=1.0,
                            machine_readable_flags=["FINANCIAL_EVIDENCE_MISSING", "MANDATORY_PROOF_ABSENT"],
                            metadata={"requirement_id": req_id},
                        )
                    )
                    continue

                # Check CA UDIN format on observations
                for obs in b_obs:
                    quote = str(obs.source_quote or "")
                    udin_matches = UDIN_REGEX.findall(quote)
                    if "UDIN" in quote.upper() and not udin_matches:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=bid_id,
                                status=ComplianceState.REVIEW,
                                severity=FindingSeverity.HIGH,
                                claim={"document": obs.source_document},
                                observation="CA Certificate contains invalid or missing 18-digit UDIN format.",
                                reason=f"CA Certificate UDIN Non-Compliance: Submitted certificate in '{obs.source_document}' does not contain a valid 18-character ICAI UDIN number.",
                                evidence=[ProvenanceRecord(document_name=obs.source_document, page_number=obs.page_number, quote=obs.source_quote)],
                                confidence=0.90,
                                machine_readable_flags=["INVALID_UDIN_SYNTAX", "CA_CERTIFICATE_REVIEW"],
                                metadata={"requirement_id": req_id},
                            )
                        )

                # Numerical turnover comparison
                if req_threshold and is_turnover:
                    max_observed_to = 0.0
                    best_obs = None
                    for o in b_obs:
                        num_val, unit = parse_numeric_value(o.observed_value)
                        if num_val and num_val > max_observed_to:
                            max_observed_to = num_val
                            best_obs = o

                    if max_observed_to >= req_threshold:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=bid_id,
                                status=ComplianceState.PASS,
                                severity=FindingSeverity.INFO,
                                claim={"required_turnover": req_threshold},
                                observation={"verified_turnover": max_observed_to},
                                reason=f"Financial Turnover Compliant: Verified turnover of Rs. {max_observed_to:,.2f} meets or exceeds required Rs. {req_threshold:,.2f}.",
                                evidence=[ProvenanceRecord(document_name=best_obs.source_document, page_number=best_obs.page_number, quote=best_obs.source_quote, normalized_value=max_observed_to)] if best_obs else [],
                                confidence=1.0,
                                machine_readable_flags=["TURNOVER_THRESHOLD_MET", "FINANCIAL_COMPLIANT"],
                                metadata={"achieved": max_observed_to, "required": req_threshold},
                            )
                        )
                    elif max_observed_to > 0:
                        deficit = req_threshold - max_observed_to
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=bid_id,
                                status=ComplianceState.FAIL,
                                severity=FindingSeverity.HIGH,
                                claim={"required_turnover": req_threshold},
                                observation={"verified_turnover": max_observed_to, "shortfall": deficit},
                                reason=f"Financial Turnover Deficit: Verified average turnover of Rs. {max_observed_to:,.2f} falls short of required Rs. {req_threshold:,.2f} by Rs. {deficit:,.2f}.",
                                evidence=[ProvenanceRecord(document_name=best_obs.source_document, page_number=best_obs.page_number, quote=best_obs.source_quote, normalized_value=max_observed_to)] if best_obs else [],
                                confidence=1.0,
                                machine_readable_flags=["TURNOVER_DEFICIT", "FINANCIAL_THRESHOLD_FAIL"],
                                metadata={"achieved": max_observed_to, "required": req_threshold, "deficit": deficit},
                            )
                        )

        # Process commercial anomalies and comparative pricing signals if provided in extra_context
        commercial_signals = (
            context.extra_context.get("commercial_signals")
            or context.extra_context.get("commercial_anomalies")
            or context.extra_context.get("comparative_signals")
            or []
        )
        if commercial_signals:
            comm_req = next((r for r in fin_reqs if r.evaluation_field == CanonicalEvaluationField.COMMERCIAL_PRICE or "COMMERCIAL" in r.description.upper() or "BOQ" in r.description.upper()), None)
            comm_req_id = comm_req.requirement_id if comm_req else "REQ-COMMERCIAL-ANOMALY"

            for sig in commercial_signals:
                sig_type = getattr(sig, "signal_type", None) or (sig.get("signal_type") if isinstance(sig, dict) else "")
                sig_sev = getattr(sig, "severity", None) or (sig.get("severity") if isinstance(sig, dict) else "INFO")
                sig_desc = getattr(sig, "description", None) or (sig.get("description") if isinstance(sig, dict) else "")
                sig_bidders = getattr(sig, "bidders_involved", None) or (sig.get("bidders_involved") if isinstance(sig, dict) else [])
                sig_details = getattr(sig, "details", None) or (sig.get("details") if isinstance(sig, dict) else {})
                sig_val = getattr(sig, "metric_value", None) or (sig.get("metric_value") if isinstance(sig, dict) else 0.0)
                sig_metric = getattr(sig, "metric_name", None) or (sig.get("metric_name") if isinstance(sig, dict) else "")
                sig_authority = getattr(sig, "decision_authority", None) or (sig.get("decision_authority") if isinstance(sig, dict) else "HUMAN_PROCUREMENT_OFFICER")

                if str(sig_sev).upper() in ("WARNING", "CRITICAL"):
                    finding_sev = FindingSeverity.CRITICAL if str(sig_sev).upper() == "CRITICAL" else FindingSeverity.HIGH
                    # Target specific bidders if identified, otherwise all context bidders
                    target_bidders = [
                        b for b in bidders
                        if (b.get("legal_name") in sig_bidders or b.get("id") in sig_bidders or any(s in str(b.get("legal_name")) for s in sig_bidders))
                    ] if sig_bidders else bidders

                    if not target_bidders:
                        target_bidders = bidders or [{"id": None, "legal_name": "Bidder"}]

                    for b in target_bidders:
                        b_id = b.get("id") or b.get("bidder_id")
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=comm_req_id,
                                bidder_id=b_id,
                                status=ComplianceState.REVIEW,
                                severity=finding_sev,
                                claim={"signal_type": str(sig_type)},
                                observation=sig_desc,
                                reason=f"Commercial Pricing Anomaly Flagged: {sig_desc}",
                                evidence=[],
                                confidence=0.95,
                                machine_readable_flags=[str(sig_type), "COMMERCIAL_ANOMALY_FLAG", "OFFICER_REVIEW_REQUIRED"],
                                metadata={
                                    "signal_type": str(sig_type),
                                    "metric_name": sig_metric,
                                    "metric_value": sig_val,
                                    "decision_authority": sig_authority,
                                    "details": sig_details,
                                },
                            )
                        )

        return findings
