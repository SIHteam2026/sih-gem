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
import chromadb

logger = logging.getLogger(__name__)

# Determine persistent ChromaDB directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "chroma_db"))

# Initialize persistent Chroma client and gov_rules collection
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
gov_rules_collection = chroma_client.get_or_create_collection(name="gov_rules")


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
