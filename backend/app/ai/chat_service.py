"""Procurement Q&A Chat Service using Groq Multi-Key Router.

Provides context-grounded Q&A assistance over tender and bidder documentation.
"""

import logging
import sys
from pathlib import Path

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from app.ai.prompts import PROCUREMENT_QA_PROMPT
    from app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import PROCUREMENT_QA_PROMPT
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import PROCUREMENT_QA_PROMPT
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


async def answer_procurement_question(question: str, context_text: str) -> str:
    """Answers a user inquiry strictly using the provided tender or bidder document context using Groq LLM.

    Args:
        question (str): The user's question regarding the document.
        context_text (str): Extracted text content from tender/bidder documents.

    Returns:
        str: Factual response grounded in context or an explicit missing info message.
    """
    if not question or not question.strip():
        return "Please provide a valid question."

    if not context_text or not context_text.strip():
        return "Information not found in the provided documents"

    prompt = (
        f"{PROCUREMENT_QA_PROMPT}\n\n"
        f"### Document Context:\n"
        f"{context_text}\n\n"
        f"### Question:\n"
        f"{question}\n\n"
        f"### Answer:"
    )

    try:
        response_text = await ai_router.generate_text(
            prompt=prompt,
            temperature=0.1,
        )

        if response_text and response_text.strip():
            return response_text.strip()
        else:
            return "Information not found in the provided documents"

    except Exception as err:
        logger.error("Error during Groq Q&A execution: %s", err)
        return "Error processing Q&A request."


if __name__ == "__main__":
    import asyncio

    sample_context = """
    TENDER DETAILS:
    Bid No: GEM/2026/B/77102
    Item: High-Performance Networking Switches
    Local Content Requirement: 50% under Make in India Class-I.
    EMD Amount: Rs. 1,50,000/- via Bank Guarantee.
    Turnover Criteria: Average annual turnover of Rs. 2.5 Crores over last 3 years.
    """

    print("Testing answer_procurement_question...")
    ans1 = asyncio.run(
        answer_procurement_question("What is the required local content percentage?", sample_context)
    )
    print("Q1 Answer:", ans1)

    ans2 = asyncio.run(
        answer_procurement_question("What is the penalty for late delivery?", sample_context)
    )
    print("Q2 (Unfound) Answer:", ans2)
