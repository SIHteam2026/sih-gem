"""Canonical Layered Verification Engine for OPAL (SIH26100).

Orchestrates all 7 canonical verification layers:
1. INGESTION_AND_DOCUMENT_INTEGRITY
2. ADMINISTRATIVE_AND_IDENTITY
3. CORPORATE_EXISTENCE_AND_RISK
4. ANTI_COLLUSION_AND_RELATEDNESS
5. ADVERSARIAL_TECHNICAL
6. PAST_PERFORMANCE_AND_CAPACITY
7. FINANCIAL_AND_COMMERCIAL

Guarantees:
- Fault isolation: one failing verifier does not crash the pipeline.
- Provenance retention for all findings.
- Deterministic finding prioritization & severity scoring.
- Structured output consumable by procurement officers.
"""

from datetime import datetime, timezone
import logging
import traceback
from typing import Any, Dict, List, Optional

try:
    from app.models.evaluation import ComplianceState
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationEngineReport,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.layers.base import BaseVerifier
    from app.rules.layers.ingestion_integrity import DocumentIntegrityVerifier
    from app.rules.layers.administrative_identity import AdministrativeIdentityVerifier
    from app.rules.layers.corporate_risk import CorporateRiskVerifier
    from app.rules.layers.anti_collusion import AntiCollusionVerifier
    from app.rules.layers.adversarial_technical import AdversarialTechnicalVerifier
    from app.rules.layers.past_performance_capacity import PastPerformanceCapacityVerifier
    from app.rules.layers.financial_commercial import FinancialCommercialVerifier
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationEngineReport,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.layers.base import BaseVerifier
        from app.rules.layers.ingestion_integrity import DocumentIntegrityVerifier
        from app.rules.layers.administrative_identity import AdministrativeIdentityVerifier
        from app.rules.layers.corporate_risk import CorporateRiskVerifier
        from app.rules.layers.anti_collusion import AntiCollusionVerifier
        from app.rules.layers.adversarial_technical import AdversarialTechnicalVerifier
        from app.rules.layers.past_performance_capacity import PastPerformanceCapacityVerifier
        from app.rules.layers.financial_commercial import FinancialCommercialVerifier
    except ImportError:
        from models.evaluation import ComplianceState
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationEngineReport,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.layers.base import BaseVerifier
        from rules.layers.ingestion_integrity import DocumentIntegrityVerifier
        from rules.layers.administrative_identity import AdministrativeIdentityVerifier
        from rules.layers.corporate_risk import CorporateRiskVerifier
        from rules.layers.anti_collusion import AntiCollusionVerifier
        from rules.layers.adversarial_technical import AdversarialTechnicalVerifier
        from rules.layers.past_performance_capacity import PastPerformanceCapacityVerifier
        from rules.layers.financial_commercial import FinancialCommercialVerifier

logger = logging.getLogger(__name__)


class CanonicalVerificationEngine:
    """Master orchestrator for the 7-layer canonical verification system."""

    def __init__(self, verifiers: Optional[List[BaseVerifier]] = None):
        if verifiers is not None:
            self._verifiers = list(verifiers)
        else:
            # Default canonical 7-layer verification stack in strict execution order
            self._verifiers = [
                DocumentIntegrityVerifier(),
                AdministrativeIdentityVerifier(),
                CorporateRiskVerifier(),
                AntiCollusionVerifier(),
                AdversarialTechnicalVerifier(),
                PastPerformanceCapacityVerifier(),
                FinancialCommercialVerifier(),
            ]

    @property
    def verifiers(self) -> List[BaseVerifier]:
        return list(self._verifiers)

    def register_verifier(self, verifier: BaseVerifier) -> None:
        """Registers a custom or specialized verifier module."""
        self._verifiers.append(verifier)

    async def run_verification(self, context: VerificationContext) -> VerificationEngineReport:
        """Executes all registered verification layers sequentially with failure isolation.
        
        Args:
            context: Comprehensive verification context containing documents, claims, observations,
                     bidders, submissions, and requirements.
                     
        Returns:
            Structured VerificationEngineReport containing categorized findings, metrics,
            and review requirements.
        """
        all_findings: List[VerificationFinding] = []
        system_errors: List[VerificationFinding] = []
        findings_by_layer: Dict[str, List[VerificationFinding]] = {}
        findings_by_bidder: Dict[str, List[VerificationFinding]] = {}
        findings_by_requirement: Dict[str, List[VerificationFinding]] = {}
        collusion_findings: List[VerificationFinding] = []

        # Maintain cumulative context
        active_context = context.model_copy(deep=True)

        for verifier in self._verifiers:
            layer_name = verifier.layer.value if hasattr(verifier.layer, "value") else str(verifier.layer)
            logger.info("Executing verification layer '%s' via verifier '%s'", layer_name, verifier.verifier_id)
            
            try:
                active_context.previous_findings = list(all_findings)
                layer_findings = await verifier.verify(active_context)
                
                if layer_findings:
                    for f in layer_findings:
                        all_findings.append(f)
                        findings_by_layer.setdefault(layer_name, []).append(f)
                        
                        if f.bidder_id:
                            findings_by_bidder.setdefault(f.bidder_id, []).append(f)
                        if f.requirement_id:
                            findings_by_requirement.setdefault(f.requirement_id, []).append(f)
                        if f.verification_layer == VerificationLayer.ANTI_COLLUSION_AND_RELATEDNESS or "COLLUSION" in f.machine_readable_flags:
                            collusion_findings.append(f)

            except Exception as exc:
                # Failure Isolation: Catch exception, log it, record system error finding, and proceed safely
                error_trace = traceback.format_exc()
                logger.error("Verification error in layer '%s' (%s): %s\n%s", layer_name, verifier.verifier_id, exc, error_trace)
                
                err_finding = VerificationFinding(
                    verifier=verifier.verifier_id,
                    verification_layer=verifier.layer,
                    status=ComplianceState.UNVERIFIED,
                    severity=FindingSeverity.HIGH,
                    reason=f"Verifier execution error in '{verifier.verifier_id}': {str(exc)}",
                    confidence=0.0,
                    machine_readable_flags=["VERIFIER_EXECUTION_ERROR", "FAILURE_ISOLATED"],
                    metadata={"exception": str(exc), "traceback": error_trace},
                )
                system_errors.append(err_finding)
                all_findings.append(err_finding)
                findings_by_layer.setdefault(layer_name, []).append(err_finding)

        # Aggregate summary statistics
        summary_by_state: Dict[str, int] = {}
        summary_by_severity: Dict[str, int] = {}
        
        for f in all_findings:
            st = f.status.value if hasattr(f.status, "value") else str(f.status)
            sv = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            summary_by_state[st] = summary_by_state.get(st, 0) + 1
            summary_by_severity[sv] = summary_by_severity.get(sv, 0) + 1

        review_req = any(
            f.status == ComplianceState.REVIEW or f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            for f in all_findings
        )

        return VerificationEngineReport(
            procurement_id=context.procurement_id,
            tender_id=context.tender_id,
            executed_at=datetime.now(timezone.utc),
            total_findings=len(all_findings),
            findings_by_layer=findings_by_layer,
            findings_by_bidder=findings_by_bidder,
            findings_by_requirement=findings_by_requirement,
            collusion_findings=collusion_findings,
            system_errors=system_errors,
            summary_by_state=summary_by_state,
            summary_by_severity=summary_by_severity,
            review_required=review_req,
        )


# Global default canonical verification engine instance
canonical_verification_engine = CanonicalVerificationEngine()
