"""Base Verifier Interface for Canonical Verification Engine Layers."""

import abc
from typing import List

try:
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
except ImportError:
    try:
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
    except ImportError:
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )


class BaseVerifier(abc.ABC):
    """Abstract base class for all canonical verification layer modules."""

    @property
    @abc.abstractmethod
    def verifier_id(self) -> str:
        """Unique identifier of this verifier module."""
        pass

    @property
    @abc.abstractmethod
    def layer(self) -> VerificationLayer:
        """Canonical named verification layer this module belongs to."""
        pass

    @abc.abstractmethod
    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        """Executes verification analysis against the provided context.
        
        Args:
            context: The comprehensive procurement, tender, bidder, and evidence context.
            
        Returns:
            List of structured VerificationFinding objects.
        """
        pass
