"""Retrieval-Augmented Generation (RAG) Vector Store Service.

Provides vector database indexing and retrieval capabilities for public procurement rulebooks,
General Financial Rules (GFR), and GeM guideline documents using ChromaDB.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List
import uuid

logger = logging.getLogger(__name__)

# Determine persistent ChromaDB directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "chroma_db"))

_in_memory_rules: List[str] = [
    "General Financial Rules (GFR) 2017 Rule 144(xi): Mandatory verification of land border compliance and prior DPIIT registration for foreign bidders.",
    "Public Procurement (Preference to Make in India) Order 2017: Prescribes minimum 50% local content requirement for Class-I local suppliers and statutory CA certification for bids exceeding Rs. 10 Crores.",
    "GeM General Terms and Conditions (GTC) Clause 4(a): Mandates primary seller verification, active GSTIN validation, and valid Manufacturer Authorization Form (MAF) from OEM.",
    "CVC Procurement Guidelines Circular 02/05/2022: Requires transparent rejection grounds and scrutiny of abnormally low commercial bids to ensure delivery assurance.",
]

try:
    import chromadb
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    gov_rules_collection = chroma_client.get_or_create_collection(name="gov_rules")
except Exception as e:
    logger.warning("ChromaDB initialization unavailable (%s). Falling back to in-memory rules store.", e)
    chromadb = None
    gov_rules_collection = None


def _chunk_text(text: str, chunk_size: int = 1000) -> List[str]:
    """Splits text content into 1000-character chunks."""
    if not text or not text.strip():
        return []
    cleaned = text.strip()
    return [
        cleaned[i : i + chunk_size].strip()
        for i in range(0, len(cleaned), chunk_size)
        if cleaned[i : i + chunk_size].strip()
    ]


def _sync_index_rulebook(text_content: str) -> int:
    """Synchronously chunks and indexes text content into ChromaDB."""
    chunks = _chunk_text(text_content, chunk_size=1000)
    if not chunks:
        logger.warning("Empty or whitespace-only rulebook content provided. Nothing indexed.")
        return 0

    if gov_rules_collection is None:
        _in_memory_rules.extend(chunks)
        logger.info("Indexed %d rule chunks into in-memory store", len(chunks))
        return len(chunks)

    ids = [f"rule_{uuid.uuid4().hex}" for _ in chunks]
    metadatas = [
        {"chunk_index": idx, "length": len(chunk)}
        for idx, chunk in enumerate(chunks)
    ]

    gov_rules_collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas,
    )
    logger.info("Indexed %d rule chunks into collection 'gov_rules'", len(chunks))
    return len(chunks)


def _sync_retrieve_clauses(query: str, n_results: int = 3) -> str:
    """Synchronously queries the Chroma collection and formats the legal context string."""
    if not query or not query.strip():
        return "Official Legal Context:\nNo query provided."

    if gov_rules_collection is None:
        matched = [r for r in _in_memory_rules if any(w.lower() in r.lower() for w in query.split() if len(w) > 3)]
        if not matched:
            matched = _in_memory_rules[:n_results]
        formatted = "\n\n".join(f"[Clause {idx + 1}]:\n{doc}" for idx, doc in enumerate(matched[:n_results]))
        return f"Official Legal Context:\n{formatted}"

    total_docs = gov_rules_collection.count()
    if total_docs == 0:
        logger.info("Chroma collection 'gov_rules' is empty. No legal context retrieved.")
        return "Official Legal Context:\nNo indexed government rules found."

    actual_n = min(n_results, total_docs)
    results = gov_rules_collection.query(
        query_texts=[query],
        n_results=actual_n,
    )

    documents = results.get("documents", [])
    if not documents or not documents[0]:
        return "Official Legal Context:\nNo relevant clauses found."

    matched_clauses = documents[0]
    formatted_clauses = "\n\n".join(
        f"[Clause {idx + 1}]:\n{doc}" for idx, doc in enumerate(matched_clauses)
    )
    return f"Official Legal Context:\n{formatted_clauses}"


async def index_rulebook(text_content: str):
    """Chunks the text into 1000-character blocks and inserts them into
    the 'gov_rules' Chroma collection using Chroma's default embedding model.

    Args:
        text_content (str): The raw text of the procurement rulebook or policy document.
    """
    if not text_content or not text_content.strip():
        return

    await asyncio.to_thread(_sync_index_rulebook, text_content)


async def retrieve_relevant_clauses(query: str, n_results: int = 3) -> str:
    """Queries the 'gov_rules' Chroma collection with search text, extracts
    top matching documents, and joins them into a single string labeled 'Official Legal Context'.

    Args:
        query (str): The search prompt, tender requirement, or legal question.
        n_results (int): Number of top matching rule documents to retrieve (default: 3).

    Returns:
        str: Formatted string containing retrieved official legal clauses.
    """
    if not query or not query.strip():
        return "Official Legal Context:\nNo query provided."

    return await asyncio.to_thread(_sync_retrieve_clauses, query, n_results)
