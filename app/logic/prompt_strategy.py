"""
Smart context extraction for gap-filling prompts

Implements efficient prompt generation by extracting only relevant context
around each gap, rather than sending the entire text to the LLM.

This minimizes token usage and prevents OOM while maintaining quality.
"""

from typing import Tuple, List, Dict
from app.logic.infill_utils import GapInfo

# Token estimation: ~1 word = 1.3 tokens, ~1 char = 0.25 tokens
# Conservative estimate: 4 chars = 1 token

def estimate_tokens(text: str) -> int:
    """
    Rough token count estimate for Polish text.
    Conservative: assumes ~4 characters per token.
    """
    return len(text) // 4

def extract_gap_context(
    text: str,
    gap: GapInfo,
    context_tokens: int = 150
) -> Tuple[str, int, int]:
    """
    Extract context around a single gap with token budget.
    
    Args:
        text: Full text with gaps
        gap: GapInfo object (has start, end positions)
        context_tokens: Target tokens to include around gap (≈600 chars)
        
    Returns:
        (context_text, left_idx, right_idx) where indices show original positions
    """
    # Convert token budget to character budget (conservative: 4 chars/token)
    context_chars = context_tokens * 4
    
    # Calculate how many chars to include on each side
    side_chars = context_chars // 2
    
    # Find boundaries
    left_idx = max(0, gap.start - side_chars)
    right_idx = min(len(text), gap.end + side_chars)
    
    # Extract context
    context = text[left_idx:right_idx]
    
    return context, left_idx, right_idx

def build_per_gap_prompts(
    text_with_gaps: str,
    gaps: List[GapInfo],
    attributes: Dict = None,
    context_tokens: int = 150
) -> List[Tuple[str, GapInfo, str]]:
    """
    Build individual prompts for each gap instead of one big prompt.
    
    Args:
        text_with_gaps: Full text with all gaps
        gaps: List of detected gaps
        attributes: Optional car attributes for system context
        context_tokens: Target tokens for context around each gap
        
    Returns:
        List of (prompt, gap, gap_marker) tuples
        
    Example:
        >>> gaps = detect_gaps("Auto [GAP:1] z [GAP:2] silnikiem")
        >>> prompts = build_per_gap_prompts(..., gaps)
        >>> # Now each prompt is focused on ONE gap with surrounding context
        >>> # Much fewer tokens wasted, better for long texts
    """
    prompts = []
    
    for gap in gaps:
        # Extract context around this specific gap
        context, _, _ = extract_gap_context(text_with_gaps, gap, context_tokens)
        
        # Build system message
        system_msg = (
            "Jesteś asystentem sprzedaży samochodów. "
            "Twoim zadaniem jest uzupełnić lukę [GAP:n] w podanym tekście. "
            "Wybierz JEDNO słowo (przymiotnik lub rzeczownik), które najlepiej pasuje do kontekstu. "
            "Odpowiedź: tylko słowo, bez wyjaśnień."
        )
        
        # Build user message with attributes if available
        attr_str = ""
        if attributes:
            attr_list = [f"{k}: {v}" for k, v in attributes.items() if v]
            if attr_list:
                attr_str = "Dane pojazdu: " + ", ".join(attr_list) + "\n\n"
        
        user_msg = f"{attr_str}Tekst:\n{context}\n\nWypełnij lukę - podaj jedno słowo:"
        
        prompt = f"{system_msg}\n\n{user_msg}"
        prompts.append((prompt, gap, gap.marker))
    
    return prompts

def build_batched_prompt(
    text_with_gaps: str,
    gaps: List[GapInfo],
    attributes: Dict = None,
    max_total_tokens: int = 1500
) -> str:
    """
    Build a single prompt for all gaps (original approach, for shorter texts).
    
    Use this when text is short and fits easily in token budget.
    Useful for: short descriptions, product names, etc.
    
    Args:
        text_with_gaps: Full text with gaps
        gaps: List of detected gaps
        attributes: Optional attributes
        max_total_tokens: Max tokens for entire prompt
        
    Returns:
        Single prompt string for batch processing
    """
    system_message = (
        "Jesteś kreatywnym asystentem sprzedaży samochodów. "
        "Uzupełnij luki [GAP:n] w tekście, wybierając jedno słowo dla każdej luki. "
        "Wypisz wynik jako listę: 1. słowo\\n2. słowo\\n..."
    )

    # Build context string from attributes if they exist
    context_str = ""
    if attributes:
        attr_list = [f"{k.capitalize()}: {v}" for k, v in attributes.items() if v]
        if attr_list:
            context_str = "Dane pojazdu:\n" + ", ".join(attr_list) + "\n\n"

    prompt = f"""{system_message}

{context_str}Tekst do uzupełnienia:
{text_with_gaps}

Wypisz listę słów pasujących do luk (1., 2., ...):"""

    return prompt

def choose_strategy(
    text_with_gaps: str,
    gaps: List[GapInfo]
) -> str:
    """
    Automatically choose between batched vs per-gap prompting.
    
    Strategy:
    - Short text (<3000 chars) OR <=2 gaps: use batched (simpler, faster)
    - Long text (>3000 chars) AND >2 gaps: use per-gap (efficient, scalable)
    
    Returns:
        "batched" or "per_gap"
    """
    token_estimate = estimate_tokens(text_with_gaps)
    
    if token_estimate < 750 or len(gaps) <= 2:
        return "batched"
    else:
        return "per_gap"

class PromptStrategy:
    """Smart prompt builder that chooses the best strategy automatically."""
    
    def __init__(self, max_tokens_per_prompt: int = 1500):
        self.max_tokens_per_prompt = max_tokens_per_prompt
    
    def build_prompt(
        self,
        text_with_gaps: str,
        gaps: List[GapInfo],
        attributes: Dict = None
    ) -> Dict:
        """
        Build optimal prompt based on text length and gap count.
        
        Returns:
            {
                "strategy": "batched" or "per_gap",
                "prompts": [prompt_str] or [(prompt_str, gap_info)]
            }
        """
        strategy = choose_strategy(text_with_gaps, gaps)
        
        if strategy == "batched":
            prompt = build_batched_prompt(text_with_gaps, gaps, attributes)
            return {
                "strategy": "batched",
                "prompts": [prompt],
                "gap_count": len(gaps)
            }
        else:
            prompts = build_per_gap_prompts(text_with_gaps, gaps, attributes)
            return {
                "strategy": "per_gap",
                "prompts": prompts,
                "gap_count": len(gaps)
            }
