"""
Infill Utilities for Batch Gap-Filling

Handles gap detection, JSON parsing from LLM output, and text reconstruction.

Gap Notation Support:
- [GAP:n]: Explicit numbered gaps (preferred)
- ___: Underscores (auto-numbered in scan order)

FUTURE: Chunking Support
-------------------------
For texts exceeding ~2000 tokens (approx 6000 chars), implement per-gap prompting:
1. Split text into chunks preserving gap context (±150 tokens around each gap)
2. Process each gap individually with left/right context
3. Merge results back into full text
4. This avoids context window overflow on smaller models (2k-4k context)

Current implementation assumes texts fit within model context window.
Add chunking when processing long-form content (articles, full listings).
"""

import re
import json
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GapInfo:
    """Information about a detected gap in text."""
    index: int          # 1-based index
    marker: str         # Original marker string
    start: int          # Start position in text
    end: int            # End position in text


def detect_gaps(text: str, notation: str = "auto") -> List[GapInfo]:
    """
    Detect gaps in text and return their positions.
    
    Args:
        text: Input text with gap markers
        notation: "auto", "[GAP:n]", or "___"
        
    Returns:
        List of GapInfo objects sorted by position
        
    Examples:
        >>> detect_gaps("Buy this [GAP:1] car with [GAP:2] features")
        [GapInfo(index=1, marker='[GAP:1]', ...), GapInfo(index=2, marker='[GAP:2]', ...)]
        
        >>> detect_gaps("Buy this ___ car with ___ features")
        [GapInfo(index=1, marker='___', ...), GapInfo(index=2, marker='___', ...)]
    """
    gaps = []
    
    # Pattern for [GAP:n] notation
    gap_tag_pattern = r'\[GAP:(\d+)\]'
    # Pattern for underscore notation (3+ underscores)
    underscore_pattern = r'_{3,}'
    
    if notation == "auto":
        # Try [GAP:n] first, fallback to ___
        gap_matches = list(re.finditer(gap_tag_pattern, text))
        if gap_matches:
            notation = "[GAP:n]"
        else:
            notation = "___"
    
    if notation == "[GAP:n]":
        for match in re.finditer(gap_tag_pattern, text):
            gaps.append(GapInfo(
                index=int(match.group(1)),
                marker=match.group(0),
                start=match.start(),
                end=match.end()
            ))
    else:  # "___"
        for i, match in enumerate(re.finditer(underscore_pattern, text), start=1):
            gaps.append(GapInfo(
                index=i,
                marker=match.group(0),
                start=match.start(),
                end=match.end()
            ))
    
    # Sort by position (should already be, but ensure)
    gaps.sort(key=lambda g: g.start)
    return gaps


def parse_infill_response(raw_output: str) -> Optional[dict]:
    """
    Parse LLM output, supporting both numbered list (preferred) and JSON (legacy).
    
    Expected List Format:
    1. word1
    2. word2
    
    Returns:
        Dict with 'gaps' list and optional 'filled_text'.
    """
    if not raw_output:
        return None
    
    gaps_list = []
    
    # Attempt 1: Parse Numbered List (Regex)
    # Matches "1. word" or "1) word" or just "1 word" at start of line
    list_pattern = r'(?:^|\n)\s*(\d+)[.)]\s*([^\n]+)'
    matches = list(re.finditer(list_pattern, raw_output))
    
    if matches:
        for match in matches:
            index = int(match.group(1))
            choice = match.group(2).strip()
            # Remove any trailing punctuation like periods if they look like sentence enders, 
            # but usually single words are clean.
            gaps_list.append({
                "index": index,
                "choice": choice
            })
        
        return {
            "filled_text": None, # List format doesn't return full text
            "gaps": gaps_list
        }

    # Attempt 2: Parse JSON (Fallback)
    # Try to extract JSON from markdown code blocks
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(json_block_pattern, raw_output)
    text_to_parse = match.group(1) if match else raw_output
    
    # Find JSON object boundaries
    start_idx = text_to_parse.find('{')
    if start_idx != -1:
        # Simple depth counter to find end
        depth = 0
        end_idx = -1
        for i, char in enumerate(text_to_parse[start_idx:], start=start_idx):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        
        if end_idx != -1:
            json_str = text_to_parse[start_idx:end_idx]
            try:
                parsed = json.loads(json_str)
                # Handle nested arguments quirks if present (legacy)
                if 'arguments' in parsed and isinstance(parsed['arguments'], str):
                     try:
                         parsed = json.loads(parsed['arguments'])
                     except: pass
                
                return parsed
            except json.JSONDecodeError:
                pass # Fall through to try repair
    
    # Attempt 3: Repair truncated JSON (grammar output cut off by max_tokens)
    # Extract individual gap items even if JSON is incomplete
    gap_pattern = r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"choice"\s*:\s*"([^"]+)"'
    gap_matches = list(re.finditer(gap_pattern, raw_output))
    
    if gap_matches:
        for match in gap_matches:
            index = int(match.group(1))
            choice = match.group(2).strip()
            gaps_list.append({
                "index": index,
                "choice": choice
            })
        
        return {
            "filled_text": None,
            "gaps": gaps_list
        }
    
    return None


def apply_fills(original_text: str, gaps: List[GapInfo], fills: dict) -> str:
    """
    Apply gap fills to original text.
    
    Uses fills from parsed JSON, replacing markers with chosen words.
    This is a fallback when LLM's 'filled_text' might be corrupted.
    
    Args:
        original_text: Original text with gap markers
        gaps: Detected gaps from detect_gaps()
        fills: Dict mapping gap index to fill choice
               e.g., {1: "excellent", 2: "powerful"}
               
    Returns:
        Text with gaps replaced by fill choices
    """
    if not gaps or not fills:
        return original_text
    
    # Process from end to start to preserve positions
    result = original_text
    for gap in reversed(gaps):
        if gap.index in fills:
            result = result[:gap.start] + fills[gap.index] + result[gap.end:]
    
    return result


def build_fills_dict(gaps_list: List[dict]) -> dict:
    """
    Convert gaps list from JSON to fills dict.
    
    Args:
        gaps_list: List of gap dicts from parsed JSON
                   [{"index": 1, "choice": "word"}, ...]
                   
    Returns:
        Dict mapping index to choice: {1: "word", ...}
    """
    fills = {}
    for gap in gaps_list:
        if 'index' in gap and 'choice' in gap:
            fills[gap['index']] = gap['choice']
    return fills


def normalize_gaps_to_tagged(text: str) -> Tuple[str, List[GapInfo]]:
    """
    Normalize any gap notation to [GAP:n] format.
    
    Useful for standardizing input before processing.
    
    Args:
        text: Text with any gap notation
        
    Returns:
        Tuple of (normalized_text, gaps)
    """
    gaps = detect_gaps(text, "auto")
    
    if not gaps:
        return text, []
    
    # If already [GAP:n], return as-is
    if gaps[0].marker.startswith('[GAP:'):
        return text, gaps
    
    # Convert ___ to [GAP:n]
    result = text
    for gap in reversed(gaps):
        new_marker = f"[GAP:{gap.index}]"
        result = result[:gap.start] + new_marker + result[gap.end:]
    
    # Re-detect with new positions
    return result, detect_gaps(result, "[GAP:n]")
