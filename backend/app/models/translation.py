"""Multilingual Document Translation Models.

Defines Pydantic models for Indian vernacular language detection,
legal/bureaucratic normalization, and English translation results.
"""

from pydantic import BaseModel, Field


class TranslationResult(BaseModel):
    """Model representing multilingual language detection and translation output."""
    detected_language: str = Field(
        ...,
        description="The primary detected natural language (e.g., 'Hindi', 'Bengali', 'Tamil', 'English').",
    )
    is_english: bool = Field(
        ...,
        description="Indicates whether the input document text is already in English.",
    )
    translated_text: str = Field(
        ...,
        description="The accurate English translation preserving technical, legal, and numerical fidelity.",
    )
    translation_confidence: str = Field(
        ...,
        description="Confidence level of the translation: 'HIGH', 'MEDIUM', or 'LOW'.",
    )
