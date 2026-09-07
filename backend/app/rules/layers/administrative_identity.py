"""Layer 2: Administrative and Identity Verifier.

Integrates:
- PAN structural regex validation (FORMAT_VALID / INVALID)
- GSTIN structural regex & state code validation (FORMAT_VALID / INVALID)
- Central Debarment & Blacklist registry checks (PASS / FAIL)
- External government/sandbox verification integration (EXTERNALLY_VERIFIED / SERVICE_UNAVAILABLE / UNVERIFIED)
- Prevents external API failures from silently becoming false PASS or false FAIL.
"""

from difflib import SequenceMatcher
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import ProvenanceRecord
    from app.models.verification import (
        FindingSeverity,
        IdentityVerificationStatus,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.debarment import is_entity_blacklisted
    from app.rules.layers.base import BaseVerifier
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import ProvenanceRecord
        from app.models.verification import (
            FindingSeverity,
            IdentityVerificationStatus,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.debarment import is_entity_blacklisted
        from app.rules.layers.base import BaseVerifier
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import ProvenanceRecord
        from models.verification import (
            FindingSeverity,
            IdentityVerificationStatus,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.debarment import is_entity_blacklisted
        from rules.layers.base import BaseVerifier

logger = logging.getLogger(__name__)

# Valid Indian State/UT GST State codes (01 to 38, plus special codes 97, 99)
VALID_GST_STATE_CODES = {
    f"{i:02d}" for i in range(1, 39)
}.union({"97", "99"})

PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class AdministrativeIdentityVerifier(BaseVerifier):
    """Verifier for Layer 2: Administrative and Identity."""

    @property
    def verifier_id(self) -> str:
        return "ADMINISTRATIVE_IDENTITY_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.ADMINISTRATIVE_AND_IDENTITY

    def _validate_pan_format(self, pan: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validates structural syntax of an Indian PAN number."""
        if not pan:
            return False, "PAN is missing or empty."
        pan_clean = str(pan).strip().upper()
        if len(pan_clean) != 10:
            return False, f"PAN '{pan_clean}' is {len(pan_clean)} characters (expected exactly 10)."
        if not PAN_REGEX.match(pan_clean):
            return False, f"PAN '{pan_clean}' does not match standard 10-character alphanumeric structure (AAAAA9999A)."
        return True, None

    def _validate_gstin_format(self, gstin: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validates structural syntax and state code of an Indian GSTIN."""
        if not gstin:
            return False, "GSTIN is missing or empty."
        gst_clean = str(gstin).strip().upper()
        if len(gst_clean) != 15:
            return False, f"GSTIN '{gst_clean}' is {len(gst_clean)} characters (expected exactly 15)."
        if not GSTIN_REGEX.match(gst_clean):
            return False, f"GSTIN '{gst_clean}' does not match standard 15-character GSTIN format."
        state_code = gst_clean[:2]
        if state_code not in VALID_GST_STATE_CODES:
            return False, f"GSTIN '{gst_clean}' contains invalid Indian State/UT code '{state_code}'."
        return True, None

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        bidders = context.bidders or []
        
        # Build bidder profile map
        for b in bidders:
            bidder_id = str(b.get("id") or b.get("bidder_id") or "")
            legal_name = str(b.get("legal_name") or "")
            pan = b.get("pan")
            gstin = b.get("gstin")
            
            # 1. PAN Structural Validation
            if pan:
                is_valid_pan, pan_err = self._validate_pan_format(pan)
                if not is_valid_pan:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            bidder_id=bidder_id,
                            status=ComplianceState.FAIL,
                            severity=FindingSeverity.CRITICAL,
                            claim={"pan": pan},
                            observation=IdentityVerificationStatus.INVALID.value,
                            reason=f"Structural PAN Validation Failed for {legal_name}: {pan_err}",
                            confidence=1.0,
                            machine_readable_flags=["INVALID_PAN_FORMAT", "IDENTITY_VALIDATION_FAIL"],
                            metadata={"pan": pan, "identity_status": IdentityVerificationStatus.INVALID.value},
                        )
                    )
                else:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            bidder_id=bidder_id,
                            status=ComplianceState.PASS,
                            severity=FindingSeverity.INFO,
                            claim={"pan": pan},
                            observation=IdentityVerificationStatus.FORMAT_VALID.value,
                            reason=f"PAN '{pan}' is structurally valid (10-character alphanumeric syntax verified).",
                            confidence=1.0,
                            machine_readable_flags=["VALID_PAN_FORMAT", "FORMAT_VALID"],
                            metadata={"pan": pan, "identity_status": IdentityVerificationStatus.FORMAT_VALID.value},
                        )
                    )

            # 2. GSTIN Structural Validation
            if gstin:
                is_valid_gst, gst_err = self._validate_gstin_format(gstin)
                if not is_valid_gst:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            bidder_id=bidder_id,
                            status=ComplianceState.FAIL,
                            severity=FindingSeverity.CRITICAL,
                            claim={"gstin": gstin},
                            observation=IdentityVerificationStatus.INVALID.value,
                            reason=f"Structural GSTIN Validation Failed for {legal_name}: {gst_err}",
                            confidence=1.0,
                            machine_readable_flags=["INVALID_GSTIN_FORMAT", "IDENTITY_VALIDATION_FAIL"],
                            metadata={"gstin": gstin, "identity_status": IdentityVerificationStatus.INVALID.value},
                        )
                    )
                else:
                    # Check PAN-GST consistency: Characters 3-12 of GSTIN must match PAN
                    gst_pan = str(gstin)[2:12].upper()
                    if pan and str(pan).strip().upper() != gst_pan:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                bidder_id=bidder_id,
                                status=ComplianceState.FAIL,
                                severity=FindingSeverity.CRITICAL,
                                claim={"pan": pan, "gstin": gstin},
                                observation=f"GSTIN PAN '{gst_pan}' does not match declared PAN '{pan}'",
                                reason=f"PAN/GSTIN Identity Mismatch: Declared PAN '{pan}' conflicts with embedded PAN '{gst_pan}' inside GSTIN '{gstin}'.",
                                confidence=1.0,
                                machine_readable_flags=["PAN_GSTIN_MISMATCH", "IDENTITY_CROSS_CHECK_FAIL"],
                                metadata={"pan": pan, "gst_pan": gst_pan, "gstin": gstin},
                            )
                        )
                    else:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                bidder_id=bidder_id,
                                status=ComplianceState.PASS,
                                severity=FindingSeverity.INFO,
                                claim={"gstin": gstin},
                                observation=IdentityVerificationStatus.FORMAT_VALID.value,
                                reason=f"GSTIN '{gstin}' is structurally valid (State code {str(gstin)[:2]}, valid checksum format).",
                                confidence=1.0,
                                machine_readable_flags=["VALID_GSTIN_FORMAT", "FORMAT_VALID"],
                                metadata={"gstin": gstin, "identity_status": IdentityVerificationStatus.FORMAT_VALID.value},
                            )
                        )

            # 3. Central Government Debarment / Blacklist Check
            for id_to_check, id_type in [(pan, "PAN"), (gstin, "GSTIN")]:
                if id_to_check:
                    if is_entity_blacklisted(id_to_check):
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                bidder_id=bidder_id,
                                status=ComplianceState.FAIL,
                                severity=FindingSeverity.CRITICAL,
                                claim={id_type.lower(): id_to_check},
                                observation="BLACKLISTED_IN_CENTRAL_REGISTRY",
                                reason=f"Debarment Kill-Switch Triggered: {id_type} '{id_to_check}' ({legal_name}) is actively debarred/blacklisted on CPPP/GeM registry.",
                                confidence=1.0,
                                machine_readable_flags=["DEBARRED_ENTITY", "STATUTORY_DISQUALIFICATION_SIGNAL"],
                                metadata={"entity_id": id_to_check, "id_type": id_type},
                            )
                        )
                    else:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                bidder_id=bidder_id,
                                status=ComplianceState.PASS,
                                severity=FindingSeverity.INFO,
                                claim={id_type.lower(): id_to_check},
                                observation="NOT_BLACKLISTED",
                                reason=f"Debarment Registry check clear for {id_type} '{id_to_check}'.",
                                confidence=1.0,
                                machine_readable_flags=["DEBARMENT_CLEAR"],
                                metadata={"entity_id": id_to_check, "id_type": id_type},
                            )
                        )

            # 4. External Authoritative / Sandbox Verification
            ext_verifs = context.external_verifications or {}
            # Match by bidder_id, gstin, pan, or requirement_id
            matched_ext = ext_verifs.get(bidder_id) or (ext_verifs.get(gstin) if gstin else None) or (ext_verifs.get(pan) if pan else None)
            
            if matched_ext:
                ext_status = str(matched_ext.get("status", "")).upper()
                ext_gov_name = str(matched_ext.get("legal_name") or matched_ext.get("taxpayer_name") or "").strip().upper()
                
                if ext_status in ("ACTIVE", "VERIFIED", "SUCCESS", "EXTERNALLY_VERIFIED"):
                    # Check name match
                    score = SequenceMatcher(None, legal_name.upper(), ext_gov_name).ratio() if ext_gov_name else 1.0
                    if score < 0.85 and ext_gov_name:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                bidder_id=bidder_id,
                                status=ComplianceState.REVIEW,
                                severity=FindingSeverity.HIGH,
                                claim={"legal_name": legal_name},
                                observation={"government_legal_name": ext_gov_name, "match_score": round(score, 2)},
                                reason=f"Authoritative Registry Name Discrepancy: Bidder profile name '{legal_name}' differs from government record '{ext_gov_name}' (match score {score:.2f} < 0.85).",
                                confidence=0.95,
                                machine_readable_flags=["REGISTRY_NAME_MISMATCH", "IDENTITY_REVIEW_REQUIRED"],
                                metadata={"declared_name": legal_name, "registry_name": ext_gov_name, "score": score},
                            )
                        )
                    else:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                bidder_id=bidder_id,
                                status=ComplianceState.PASS,
                                severity=FindingSeverity.INFO,
                                claim={"gstin": gstin, "legal_name": legal_name},
                                observation=IdentityVerificationStatus.EXTERNALLY_VERIFIED.value,
                                reason=f"Authoritative Registry Verification Succeeded: GSTIN '{gstin}' is active and matches '{ext_gov_name or legal_name}'.",
                                confidence=1.0,
                                machine_readable_flags=["EXTERNALLY_VERIFIED", "ACTIVE_REGISTRATION"],
                                metadata={"gstin": gstin, "registry_data": matched_ext},
                            )
                        )
                elif ext_status in ("CANCELLED", "SUSPENDED", "INACTIVE", "FAILED"):
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            bidder_id=bidder_id,
                            status=ComplianceState.FAIL,
                            severity=FindingSeverity.CRITICAL,
                            claim={"gstin": gstin},
                            observation=f"REGISTRY_STATUS_{ext_status}",
                            reason=f"Authoritative Registry Invalidation: Government registration for '{gstin}' is '{ext_status}'.",
                            confidence=1.0,
                            machine_readable_flags=["REGISTRY_STATUS_INACTIVE", "STATUTORY_DISQUALIFICATION_SIGNAL"],
                            metadata={"gstin": gstin, "registry_status": ext_status},
                        )
                    )
                elif ext_status in ("UNAVAILABLE", "ERROR", "SERVICE_UNAVAILABLE", "TIMEOUT"):
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            bidder_id=bidder_id,
                            status=ComplianceState.UNVERIFIED,
                            severity=FindingSeverity.HIGH,
                            claim={"gstin": gstin},
                            observation=IdentityVerificationStatus.SERVICE_UNAVAILABLE.value,
                            reason=f"Authoritative Registry Service Unavailable: External portal timeout or gateway error for '{gstin}'. Verification incomplete.",
                            confidence=0.8,
                            machine_readable_flags=["EXTERNAL_SERVICE_UNAVAILABLE", "UNVERIFIED_STATUTORY_RECORD"],
                            metadata={"gstin": gstin, "error": matched_ext.get("error")},
                        )
                    )

        return findings
