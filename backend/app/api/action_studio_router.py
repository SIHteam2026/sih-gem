"""API Router for Action Studio endpoints.

Provides officer-controlled endpoints for creating, editing, regenerating,
versioning, and approving procurement decision documents grounded in canonical evidence.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Path, status

try:
    from app.models.action_studio import (
        ActionStudioDocument,
        ActionStudioDocumentVersion,
        ActionStudioListResponse,
        ApproveDraftRequest,
        CreateDraftRequest,
        UpdateDraftRequest,
    )
    from app.services.action_studio_service import ActionStudioService
except ImportError:
    from app.models.action_studio import (
        ActionStudioDocument,
        ActionStudioDocumentVersion,
        ActionStudioListResponse,
        ApproveDraftRequest,
        CreateDraftRequest,
        UpdateDraftRequest,
    )
    from app.services.action_studio_service import ActionStudioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Action Studio"])


@router.get(
    "/procurements/{procurement_id}/action-studio",
    response_model=ActionStudioListResponse,
    summary="List Action Studio Drafts",
    description="Retrieves all Action Studio document drafts created for a specific procurement workspace.",
)
async def list_procurement_action_studio_drafts(
    procurement_id: str = Path(..., description="Canonical procurement UUID."),
) -> ActionStudioListResponse:
    """Lists Action Studio document drafts for a procurement workspace."""
    try:
        return await ActionStudioService.list_procurement_drafts(procurement_id)
    except Exception as exc:
        logger.error("Failed to list Action Studio drafts for procurement '%s': %s", procurement_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error listing Action Studio drafts.",
        )


@router.post(
    "/procurements/{procurement_id}/action-studio/drafts",
    response_model=ActionStudioDocument,
    status_code=status.HTTP_201_CREATED,
    summary="Create Action Studio Draft",
    description="Generates an officer-controlled draft document from canonical technical and financial evidence context.",
)
async def create_action_studio_draft(
    request: CreateDraftRequest,
    procurement_id: str = Path(..., description="Canonical procurement UUID."),
) -> ActionStudioDocument:
    """Creates a new Action Studio document draft."""
    try:
        return await ActionStudioService.create_draft(procurement_id, request)
    except ValueError as val_err:
        logger.warning("Action Studio draft creation guard blocked request for '%s': %s", procurement_id, val_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to create Action Studio draft for procurement '%s': %s", procurement_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error creating Action Studio draft: {str(exc)}",
        )


@router.get(
    "/action-studio/drafts/{draft_id}",
    response_model=ActionStudioDocument,
    summary="Get Action Studio Draft Detail",
    description="Retrieves a specific Action Studio document draft including content and evidence references.",
)
async def get_action_studio_draft_detail(
    draft_id: str = Path(..., description="Action Studio draft UUID."),
) -> ActionStudioDocument:
    """Gets single Action Studio draft details."""
    try:
        doc = await ActionStudioService.get_draft(draft_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Action Studio draft with ID '{draft_id}' was not found.",
            )
        return doc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to retrieve Action Studio draft '%s': %s", draft_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error retrieving Action Studio draft detail.",
        )


@router.patch(
    "/action-studio/drafts/{draft_id}",
    response_model=ActionStudioDocument,
    summary="Update Action Studio Draft Content",
    description="Updates document content (human officer edit) and advances the document version without mutating evaluation results.",
)
async def update_action_studio_draft_content(
    request: UpdateDraftRequest,
    draft_id: str = Path(..., description="Action Studio draft UUID."),
) -> ActionStudioDocument:
    """Updates draft content and creates a new document version."""
    try:
        return await ActionStudioService.update_draft_content(draft_id, request)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to update Action Studio draft '%s': %s", draft_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error updating Action Studio draft: {str(exc)}",
        )


@router.post(
    "/action-studio/drafts/{draft_id}/regenerate",
    response_model=ActionStudioDocument,
    summary="Regenerate Action Studio Draft",
    description="Re-fetches canonical evidence context and regenerates draft content with a new version number.",
)
async def regenerate_action_studio_draft(
    draft_id: str = Path(..., description="Action Studio draft UUID."),
) -> ActionStudioDocument:
    """Regenerates draft content from evidence."""
    try:
        return await ActionStudioService.regenerate_draft(draft_id)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to regenerate Action Studio draft '%s': %s", draft_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error regenerating Action Studio draft: {str(exc)}",
        )


@router.get(
    "/action-studio/drafts/{draft_id}/versions",
    response_model=List[ActionStudioDocumentVersion],
    summary="List Draft Version History",
    description="Retrieves the full immutable version history snapshot entries for a draft document.",
)
async def list_action_studio_draft_versions(
    draft_id: str = Path(..., description="Action Studio draft UUID."),
) -> List[ActionStudioDocumentVersion]:
    """Lists draft document versions."""
    try:
        return await ActionStudioService.list_draft_versions(draft_id)
    except Exception as exc:
        logger.error("Failed to list versions for Action Studio draft '%s': %s", draft_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error retrieving draft version history.",
        )


@router.post(
    "/action-studio/drafts/{draft_id}/approve",
    response_model=ActionStudioDocument,
    summary="Approve Action Studio Draft",
    description="Formally approves a draft document under human officer authority and generates an audit event (without dispatch).",
)
async def approve_action_studio_draft(
    request: ApproveDraftRequest,
    draft_id: str = Path(..., description="Action Studio draft UUID."),
) -> ActionStudioDocument:
    """Approves an Action Studio draft."""
    try:
        return await ActionStudioService.approve_draft(draft_id, request)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to approve Action Studio draft '%s': %s", draft_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error approving Action Studio draft: {str(exc)}",
        )
