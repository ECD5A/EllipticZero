from __future__ import annotations


def is_extremely_vague_request(seed_text: str) -> bool:
    """Return whether a seed is low-specificity.

    This is advisory only. Novel research ideas can look unfamiliar or short, so
    validation must not reject them before agents and local evidence can review
    the seed in context.
    """

    return not seed_text.strip()


def validate_seed_text(seed_text: str) -> str:
    """Validate and normalize the user-provided research idea.

    The input gate intentionally stays semantic-light: it rejects only empty
    input. Specificity, ambiguity, and novelty are handled inside the bounded
    agent loop and final report instead of being pre-filtered by keyword lists.
    """

    stripped = seed_text.strip()
    if not stripped:
        raise ValueError("Research idea cannot be empty.")
    return stripped
