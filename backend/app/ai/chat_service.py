"""Procurement Q&A Chat Service.

Provides context-grounded Q&A assistance over tender and bidder documentation.
"""

import logging
import os
import sys
from pathlib import Path

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import find_dotenv, load_dotenv
import google.generativeai as genai

try:
    from backend.app.ai.prompts import PROCUREMENT_QA_PROMPT
except ImportError:
    try:
        from app.ai.prompts import PROCUREMENT_QA_PROMPT
    except ImportError:
        from prompts import PROCUREMENT_QA_PROMPT

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)


async def answer_procurement_question(question: str, context_text: str) -> str:
    """Answers a user inquiry strictly using the provided tender or bidder document context.

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

    # Ensure API key is configured
    current_key = os.getenv("GEMINI_API_KEY")
    if current_key:
        genai.configure(api_key=current_key)

    prompt = (
        f"{PROCUREMENT_QA_PROMPT}\n\n"
        f"### Document Context:\n"
        f"{context_text}\n\n"
        f"### Question:\n"
        f"{question}\n\n"
        f"### Answer:"
    )

    candidate_models = ["gemini-1.5-flash", "gemini-3.6-flash", "gemini-2.5-flash"]

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name=model_name)
            response = await model.generate_content_async(prompt)

            if response and response.text:
                return response.text.strip()
            else:
                return "Information not found in the provided documents"

        except Exception as err:
            err_str = str(err)
            if "not found" in err_str.lower() or "no longer available" in err_str.lower() or "404" in err_str:
                logger.warning(
                    "Model %s unavailable (%s). Trying fallback candidate...",
                    model_name,
                    err_str,
                )
                continue
            else:
                logger.error("Error during Gemini Q&A execution: %s", err)
                return "Error processing Q&A request."

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
