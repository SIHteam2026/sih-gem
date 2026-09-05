"""Procurement Processing Lifecycle & Orchestration Service.

Provides explicit state transition handling, stage boundary execution, idempotency,
retry policies, and failure isolation for procurement processing (IMPORTED -> PROCESSING -> READY/FAILED).
"""

import abc
import time
import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.models.procurement import (
    ProcurementStatus,
    ProcessingStage,
    ProcessingStageResult,
    ProcurementProcessingStatusResponse,
    StartProcessingResponse,
    ProcessingContext,
)
from backend.app.db.client import (
    get_procurement_hierarchy,
    update_procurement_status_db,
    get_procurement_processing_metadata_db,
)

logger = logging.getLogger(__name__)

# Global in-memory registry for processing execution state (fallback / mock / cache)
_IN_MEMORY_PROCESSING_STATE: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Processing Stage Abstract Boundary & Delegator Implementations
# ---------------------------------------------------------------------------
class ProcurementProcessingStage(abc.ABC):
    """Abstract interface for procurement processing pipeline stages."""

    @property
    @abc.abstractmethod
    def stage_name(self) -> ProcessingStage:
        """Returns the ProcessingStage enum for this stage."""
        pass

    @abc.abstractmethod
    async def execute(self, context: ProcessingContext) -> ProcessingStageResult:
        """Executes stage logic and returns stage result."""
        pass


class TenderIntelligenceStage(ProcurementProcessingStage):
    """Stage 1: Tender intelligence analysis (requirements extraction, classification)."""

    @property
    def stage_name(self) -> ProcessingStage:
        return ProcessingStage.TENDER_INTELLIGENCE

    async def execute(self, context: ProcessingContext) -> ProcessingStageResult:
        start_time = time.time()
        logger.info("Executing TenderIntelligenceStage for procurement '%s'", context.procurement_id)
        try:
            import os
            import asyncio
            from backend.app.services.tender_service import analyze_tender, save_tender_requirements
            from backend.app.models.tender_contract import RequirementEvaluationContract
            
            procurement = context.procurement
            procurement_id = context.procurement_id
            
            tenders = procurement.get("tenders", [])
            tender = procurement.get("tender") or (tenders[0] if tenders else {})
            tender_id = tender.get("tender_reference") or tender.get("id") or procurement_id
            
            documents = procurement.get("documents", [])
            tender_docs = [d for d in documents if "TENDER_SPECIFICATION" in str(d.get("document_type", ""))]
            if not tender_docs and tender:
                t_docs = tender.get("documents", [])
                tender_docs = [d for d in t_docs if "TENDER_SPECIFICATION" in str(d.get("document_type", ""))]
                
            if not tender_docs:
                raise Exception("No TENDER_SPECIFICATION document found for procurement.")
                
            tender_doc = tender_docs[0]
            
            storage_path = tender_doc.get("storage_path")
            file_bytes = None
            filename = tender_doc.get("filename", "tender.txt")
            if storage_path and os.path.exists(storage_path):
                with open(storage_path, "rb") as f:
                    file_bytes = f.read()
            elif tender_doc.get("content_text"):
                file_bytes = tender_doc.get("content_text").encode("utf-8")
                filename = "tender.txt" # Force txt extraction for mock strings
            else:
                raise Exception(f"Cannot retrieve document bytes for {tender_doc.get('id')}")
            
            # 4. Invoke Tender Intelligence service
            analysis_result = await analyze_tender(
                file_bytes=file_bytes, 
                tender_id=tender_id, 
                filename=filename
            )
            
            # 5 & 6. Persist canonical tender requirements
            reqs = analysis_result.requirements if hasattr(analysis_result, "requirements") else analysis_result.get("requirements", [])
            if not reqs:
                raise Exception("Tender intelligence extraction failed to produce any requirements.")
            
            await save_tender_requirements(tender_id, reqs)
            
            exec_time = (time.time() - start_time) * 1000.0
            return ProcessingStageResult(
                stage=self.stage_name,
                success=True,
                execution_time_ms=round(exec_time, 2),
                metadata={"requirements_extracted": len(reqs)},
            )
        except Exception as exc:
            exec_time = (time.time() - start_time) * 1000.0
            logger.error("TenderIntelligenceStage failed for '%s': %s", context.procurement_id, exc)
            return ProcessingStageResult(
                stage=self.stage_name,
                success=False,
                error_code="TENDER_INTELLIGENCE_FAILURE",
                error_message=f"Tender intelligence stage failed: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )


class DocumentIntelligenceStage(ProcurementProcessingStage):
    """Stage 2: Document intelligence analysis (OCR, layout parsing, table extraction)."""

    @property
    def stage_name(self) -> ProcessingStage:
        return ProcessingStage.DOCUMENT_INTELLIGENCE

    async def execute(self, context: ProcessingContext) -> ProcessingStageResult:
        start_time = time.time()
        logger.info("Executing DocumentIntelligenceStage for procurement '%s'", context.procurement_id)
        try:
            import os
            import asyncio
            from backend.app.services.document_processor import process_canonical_document
            
            procurement = context.procurement
            tenders = procurement.get("tenders", [])
            submissions = procurement.get("submissions", [])
            for t in tenders:
                submissions.extend(t.get("submissions", []))
            
            docs_processed = 0
            docs_failed = 0
            
            for sub in submissions:
                docs = sub.get("documents", [])
                for doc in docs:
                    doc_id = doc.get("id")
                    if not doc_id:
                        continue
                        
                    storage_path = doc.get("storage_path")
                    file_bytes = None
                    if storage_path and os.path.exists(storage_path):
                        with open(storage_path, "rb") as f:
                            file_bytes = f.read()
                    elif doc.get("content_text"):
                        file_bytes = doc.get("content_text").encode("utf-8")
                    else:
                        docs_failed += 1
                        logger.error(f"Cannot retrieve bytes for document {doc_id}")
                        continue
                        
                    try:
                        await process_canonical_document(doc_id, file_bytes)
                        docs_processed += 1
                    except Exception as e:
                        docs_failed += 1
                        logger.error(f"Failed to process document {doc_id}: {e}")
                        
            if docs_failed > 0 and docs_processed == 0:
                raise Exception("All documents failed to process.")
                
            exec_time = (time.time() - start_time) * 1000.0
            return ProcessingStageResult(
                stage=self.stage_name,
                success=True,
                execution_time_ms=round(exec_time, 2),
                metadata={
                    "documents_processed": docs_processed,
                    "documents_failed": docs_failed
                },
            )
        except Exception as exc:
            exec_time = (time.time() - start_time) * 1000.0
            logger.error("DocumentIntelligenceStage failed for '%s': %s", context.procurement_id, exc)
            return ProcessingStageResult(
                stage=self.stage_name,
                success=False,
                error_code="DOCUMENT_INTELLIGENCE_FAILURE",
                error_message=f"Document intelligence stage failed: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )


class EvidenceExtractionStage(ProcurementProcessingStage):
    """Stage 3: Evidence extraction & financial evaluation (GST, turnover, BoQ matching)."""

    @property
    def stage_name(self) -> ProcessingStage:
        return ProcessingStage.EVIDENCE_EXTRACTION

    async def execute(self, context: ProcessingContext) -> ProcessingStageResult:
        start_time = time.time()
        logger.info("Executing EvidenceExtractionStage for procurement '%s'", context.procurement_id)
        try:
            from backend.app.services.claim_extraction_service import process_document_evidence
            from backend.app.db.client import get_procurement_hierarchy
            from backend.app.services.tender_contract_service import get_tender_evaluation_contract
            from backend.app.models.procurement import Document
            
            procurement_id = context.procurement_id
            proc_full = await get_procurement_hierarchy(procurement_id)
            
            tenders = proc_full.get("tenders", [])
            tender = proc_full.get("tender") or (tenders[0] if tenders else {})
            tender_id = tender.get("tender_reference") or tender.get("id") or procurement_id
            
            try:
                tender_contract_pkg = await get_tender_evaluation_contract(tender_id)
                req_contracts = tender_contract_pkg.requirements
            except Exception as e:
                logger.warning(f"No tender requirements found or failed to load contract: {e}")
                req_contracts = []
                
            submissions = proc_full.get("submissions", [])
            for t in tenders:
                submissions.extend(t.get("submissions", []))
                
            claims_count = 0
            obs_count = 0
            
            for sub in submissions:
                docs = sub.get("documents", [])
                tender_context = {
                    "bidder_id": sub.get("bidder_id"),
                    "bid_submission_id": sub.get("id"),
                    "requirements": req_contracts
                }
                for doc in docs:
                    doc_model = Document(**doc) if isinstance(doc, dict) else doc
                    facts = process_document_evidence(doc_model, tender_context)
                    claims_count += len(facts.get("claims", []))
                    obs_count += len(facts.get("observations", []))
            
            exec_time = (time.time() - start_time) * 1000.0
            return ProcessingStageResult(
                stage=self.stage_name,
                success=True,
                execution_time_ms=round(exec_time, 2),
                metadata={
                    "claims_extracted": claims_count,
                    "observations_extracted": obs_count
                },
            )
        except Exception as exc:
            exec_time = (time.time() - start_time) * 1000.0
            logger.error("EvidenceExtractionStage failed for '%s': %s", context.procurement_id, exc)
            return ProcessingStageResult(
                stage=self.stage_name,
                success=False,
                error_code="EVIDENCE_EXTRACTION_FAILURE",
                error_message=f"Evidence extraction stage failed: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )


class ComplianceEvaluationStage(ProcurementProcessingStage):
    """Stage 4: Compliance evaluation (regulatory checks, deterministic scoring, fraud flags)."""

    @property
    def stage_name(self) -> ProcessingStage:
        return ProcessingStage.COMPLIANCE_EVALUATION

    async def execute(self, context: ProcessingContext) -> ProcessingStageResult:
        start_time = time.time()
        logger.info("Executing ComplianceEvaluationStage for procurement '%s'", context.procurement_id)
        try:
            from backend.app.services.master_pipeline import evaluate_canonical_submission_by_id
            from backend.app.db.client import get_procurement_hierarchy, insert_bid_evaluation
            from backend.app.models.evaluation import ComplianceState
            
            procurement_id = context.procurement_id
            proc_full = await get_procurement_hierarchy(procurement_id)
            
            tenders = proc_full.get("tenders", [])
            tender = proc_full.get("tender") or (tenders[0] if tenders else {})
            tender_id = tender.get("tender_reference") or tender.get("id") or procurement_id
            
            submissions = proc_full.get("submissions", [])
            for t in tenders:
                submissions.extend(t.get("submissions", []))
            
            if not submissions:
                logger.warning("No submissions found for evaluation.")
                
            subs_evaluated = 0
            pass_count = 0
            fail_count = 0
            review_count = 0
            unverified_count = 0
            na_count = 0
            
            for sub in submissions:
                sub_id = sub.get("id")
                
                # Use canonical pipeline
                eval_result_dict = await evaluate_canonical_submission_by_id(
                    submission_id=sub_id,
                    tender_id_or_ref=tender_id
                )
                
                # Extract requirement results for metadata stats
                req_results = eval_result_dict.get("requirement_results", [])
                for rr in req_results:
                    status = getattr(rr, "state", getattr(rr, "status", None))
                    if isinstance(status, ComplianceState):
                        status = status.value
                    elif hasattr(status, "value"):
                        status = status.value
                        
                    if status == "PASS": pass_count += 1
                    elif status == "FAIL": fail_count += 1
                    elif status == "REVIEW": review_count += 1
                    elif status == "UNVERIFIED": unverified_count += 1
                    elif status == "NOT_APPLICABLE": na_count += 1
                
                # Save bid evaluation
                await insert_bid_evaluation(tender_id, eval_result_dict)
                subs_evaluated += 1
                
            exec_time = (time.time() - start_time) * 1000.0
            return ProcessingStageResult(
                stage=self.stage_name,
                success=True,
                execution_time_ms=round(exec_time, 2),
                metadata={
                    "submissions_evaluated": subs_evaluated,
                    "PASS": pass_count,
                    "FAIL": fail_count,
                    "REVIEW": review_count,
                    "UNVERIFIED": unverified_count,
                    "NOT_APPLICABLE": na_count
                },
            )
        except Exception as exc:
            exec_time = (time.time() - start_time) * 1000.0
            logger.error("ComplianceEvaluationStage failed for '%s': %s", context.procurement_id, exc)
            return ProcessingStageResult(
                stage=self.stage_name,
                success=False,
                error_code="COMPLIANCE_EVALUATION_FAILURE",
                error_message=f"Compliance evaluation stage failed: {str(exc)}",
                execution_time_ms=round(exec_time, 2),
            )


# Default ordered pipeline stages
DEFAULT_PIPELINE_STAGES: List[ProcurementProcessingStage] = [
    TenderIntelligenceStage(),
    DocumentIntelligenceStage(),
    EvidenceExtractionStage(),
    ComplianceEvaluationStage(),
]


# ---------------------------------------------------------------------------
# Orchestration & Service Public Interface
# ---------------------------------------------------------------------------
async def get_procurement_processing_status(
    procurement_id: str,
) -> ProcurementProcessingStatusResponse:
    """Retrieves current processing lifecycle status for a procurement workspace.

    Args:
        procurement_id: Procurement UUID.

    Returns:
        ProcurementProcessingStatusResponse with current stage and completed results.

    Raises:
        HTTPException 404 if procurement does not exist.
    """
    procurement_data = await _get_procurement_or_raise(procurement_id)

    state = _IN_MEMORY_PROCESSING_STATE.get(procurement_id, {})
    db_meta_rec = await get_procurement_processing_metadata_db(procurement_id)
    db_meta = (db_meta_rec.get("processing_metadata") or {}) if db_meta_rec else {}

    raw_status = state.get("status") or db_meta.get("status") or procurement_data.get("status") or "IMPORTED"
    status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
    if "." in status_str:
        status_str = status_str.split(".")[-1]
    proc_status = ProcurementStatus(status_str.upper())

    current_stage = state.get("current_stage") or db_meta.get("current_stage")
    completed_stages = state.get("completed_stages") or db_meta.get("completed_stages") or []
    failed_stage = state.get("failed_stage") or db_meta.get("failed_stage")
    raw_results = state.get("stage_results") or db_meta.get("stage_results") or []
    retry_count = state.get("retry_count") or db_meta.get("retry_count") or 0
    last_error_code = state.get("last_error_code") or db_meta.get("last_error_code")
    last_error_message = state.get("last_error_message") or db_meta.get("last_error_message")

    stage_results = []
    for res in raw_results:
        if isinstance(res, dict):
            stage_results.append(ProcessingStageResult(**res))
        elif isinstance(res, ProcessingStageResult):
            stage_results.append(res)

    def _parse_stage(val: Any) -> Optional[ProcessingStage]:
        if not val:
            return None
        s = val.value if hasattr(val, "value") else str(val)
        if "." in s:
            s = s.split(".")[-1]
        return ProcessingStage(s.upper())

    return ProcurementProcessingStatusResponse(
        procurement_id=procurement_id,
        status=proc_status,
        current_stage=_parse_stage(current_stage),
        completed_stages=[_parse_stage(s) for s in completed_stages if _parse_stage(s)],
        failed_stage=_parse_stage(failed_stage),
        stage_results=stage_results,
        retry_count=retry_count,
        last_error_code=last_error_code,
        last_error_message=last_error_message,
        created_at=procurement_data.get("created_at"),
        updated_at=procurement_data.get("updated_at"),
    )



async def start_procurement_processing(
    procurement_id: str,
    force: bool = False,
    custom_pipeline: Optional[List[ProcurementProcessingStage]] = None,
) -> StartProcessingResponse:
    """Triggers procurement processing lifecycle orchestration.

    Transitions status from IMPORTED/FAILED -> PROCESSING -> READY/FAILED.
    Enforces idempotency and retry policies.

    Args:
        procurement_id: Procurement UUID.
        force: If True, forces re-processing even if status is READY.
        custom_pipeline: Optional custom processing pipeline stage list.

    Returns:
        StartProcessingResponse with updated status.

    Raises:
        HTTPException 404 if procurement does not exist.
    """
    procurement_data = await _get_procurement_or_raise(procurement_id)

    # Get existing processing state
    current_status_res = await get_procurement_processing_status(procurement_id)
    current_status = current_status_res.status

    # Idempotency check: currently PROCESSING
    if current_status == ProcurementStatus.PROCESSING and not force:
        return StartProcessingResponse(
            procurement_id=procurement_id,
            status=ProcurementStatus.PROCESSING,
            message="Procurement processing is currently in progress.",
            already_in_progress=True,
        )

    # Idempotency check: already READY
    if current_status == ProcurementStatus.READY and not force:
        return StartProcessingResponse(
            procurement_id=procurement_id,
            status=ProcurementStatus.READY,
            message="Procurement processing already completed successfully.",
            already_completed=True,
        )

    # Increment retry count if retrying from FAILED or forcing re-processing
    retry_count = current_status_res.retry_count
    if current_status in (ProcurementStatus.FAILED, ProcurementStatus.READY) or force:
        retry_count += 1

    # Transition status to PROCESSING
    pipeline = custom_pipeline if custom_pipeline is not None else DEFAULT_PIPELINE_STAGES

    state_entry: Dict[str, Any] = {
        "status": ProcurementStatus.PROCESSING.value,
        "current_stage": pipeline[0].stage_name.value if pipeline else None,
        "completed_stages": [],
        "failed_stage": None,
        "stage_results": [],
        "retry_count": retry_count,
        "last_error_code": None,
        "last_error_message": None,
    }
    _IN_MEMORY_PROCESSING_STATE[procurement_id] = state_entry
    await update_procurement_status_db(procurement_id, ProcurementStatus.PROCESSING.value, state_entry)

    # Build context for processing pipeline
    context = ProcessingContext(
        procurement_id=procurement_id,
        procurement=procurement_data,
        force=force,
        retry_count=retry_count,
    )

    completed_stages: List[str] = []
    stage_results: List[Dict[str, Any]] = []
    overall_success = True
    failed_stage_enum: Optional[str] = None
    error_code: Optional[str] = None
    error_msg: Optional[str] = None

    # Execute pipeline stages sequentially with failure isolation
    for stage_runner in pipeline:
        stage_enum = stage_runner.stage_name
        state_entry["current_stage"] = stage_enum.value
        await update_procurement_status_db(procurement_id, ProcurementStatus.PROCESSING.value, state_entry)

        stage_res = await stage_runner.execute(context)
        stage_results.append(stage_res.model_dump() if hasattr(stage_res, "model_dump") else stage_res.dict())
        state_entry["stage_results"] = stage_results


        if stage_res.success:
            completed_stages.append(stage_enum.value)
            state_entry["completed_stages"] = completed_stages
        else:
            overall_success = False
            failed_stage_enum = stage_enum.value
            error_code = stage_res.error_code or "STAGE_EXECUTION_ERROR"
            error_msg = stage_res.error_message or f"Stage '{stage_enum.value}' failed execution."
            break

    # Finalize status based on stage outcomes
    if overall_success:
        final_status = ProcurementStatus.READY
        state_entry["status"] = final_status.value
        state_entry["current_stage"] = None
        state_entry["failed_stage"] = None
        state_entry["last_error_code"] = None
        state_entry["last_error_message"] = None
        message = "Procurement processing completed successfully."
    else:
        final_status = ProcurementStatus.FAILED
        state_entry["status"] = final_status.value
        state_entry["current_stage"] = None
        state_entry["failed_stage"] = failed_stage_enum
        state_entry["last_error_code"] = error_code
        state_entry["last_error_message"] = error_msg
        message = f"Procurement processing failed at stage '{failed_stage_enum}': {error_msg}"

    _IN_MEMORY_PROCESSING_STATE[procurement_id] = state_entry
    await update_procurement_status_db(procurement_id, final_status.value, state_entry)

    return StartProcessingResponse(
        procurement_id=procurement_id,
        status=final_status,
        message=message,
        already_completed=False,
        already_in_progress=False,
    )


# ---------------------------------------------------------------------------
# Internal Helper Functions
# ---------------------------------------------------------------------------
async def _get_procurement_or_raise(procurement_id: str) -> Dict[str, Any]:
    """Internal helper to fetch procurement record or raise 404 HTTPException."""
    try:
        data = await get_procurement_hierarchy(procurement_id)
        if data:
            return data
    except ValueError:
        pass
    except Exception as exc:
        logger.warning("Error fetching procurement hierarchy for '%s': %s", procurement_id, exc)

    # Check read service fallback
    try:
        try:
            from backend.app.services.procurement_read_service import get_procurement_detail_service
        except ImportError:
            from app.services.procurement_read_service import get_procurement_detail_service
        detail = await get_procurement_detail_service(procurement_id)
        if detail:
            return detail.model_dump() if hasattr(detail, "model_dump") else detail.dict()
    except Exception as read_err:
        logger.warning("Read service lookup failed for '%s': %s", procurement_id, read_err)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Procurement with ID '{procurement_id}' not found.",
    )

