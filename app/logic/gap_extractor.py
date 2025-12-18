"""Gap extraction and context analysis for infill tasks."""

import re
from typing import List, Dict, Any

class GapContext:
    """Represents a gap with its surrounding context."""
    def __init__(self, index: int, marker: str, text: str, context: str, context_with_marker: str, char_position: int):
        self.index = index
        self.marker = marker
        self.text = text  # Full text with gaps
        self.context = context  # Context with marker replaced by ___
        self.context_with_marker = context_with_marker # Context with original [GAP:n] marker
        self.char_position = char_position
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "marker": self.marker,
            "context": self.context,
            "char_position": self.char_position
        }

def extract_gaps(text: str, context_window: int = 30) -> List[GapContext]:
    """
    Extract all gaps from text with their surrounding context.
    Stop at other gap markers to avoid contamination.
    
    Args:
        text: Text with [GAP:n] markers
        context_window: Characters to include before/after gap (default 30)
    
    Returns:
        List of GapContext objects
    """
    gaps = []
    
    # Find all [GAP:n] patterns
    pattern = r'\[GAP:(\d+)\]'
    for match in re.finditer(pattern, text):
        index = int(match.group(1))
        marker = match.group(0)
        pos = match.start()
        
        # Extract context around gap, stopping at other gaps
        # Find boundaries - start from gap position and go backwards
        start = max(0, pos - context_window)
        # But stop if we hit another [GAP:x] marker
        while start < pos:
            check_text = text[start:pos]
            if re.search(r'\[GAP:\d+\]', check_text):
                # Found another gap, start after it
                gap_match = re.search(r'\[GAP:\d+\]', check_text)
                start = start + gap_match.end()
            else:
                break
        
        # Same for end - go forward from gap end
        end = min(len(text), match.end() + context_window)
        while end > match.end():
            check_text = text[match.end():end]
            if re.search(r'\[GAP:\d+\]', check_text):
                # Found another gap, stop before it
                gap_match = re.search(r'\[GAP:\d+\]', check_text)
                end = match.end() + gap_match.start()
            else:
                break
        
        # Context: replace [GAP:n] with underscore for display
        raw_context = text[start:end]
        context = raw_context.replace(marker, "___")
        context_with_marker = raw_context.strip()
        
        gap = GapContext(
            index=index,
            marker=marker,
            text=text,
            context=context.strip(),
            context_with_marker=context_with_marker,
            char_position=pos
        )
        gaps.append(gap)
    
    return sorted(gaps, key=lambda g: g.index)

def create_optimized_text(gaps: List[GapContext]) -> str:
    """
    Creates an optimized prompt text containing only the contexts around gaps.
    This reduces token usage and focuses the model on the local context.
    
    Args:
        gaps: List of GapContext objects
        
    Returns:
        A single string with all gap contexts separated by newlines.
    """
    lines = []
    for gap in gaps:
        # We present each gap context on a new line
        lines.append(gap.context_with_marker)
    return "\n".join(lines)

def get_gap_for_bielik(text: str, gap_index: int, context_window: int = 40) -> str:
    """
    Get a focused prompt snippet for a single gap.
    
    Args:
        text: Full text with gaps
        gap_index: Gap number to extract
        context_window: Context size
    
    Returns:
        Context string for the gap
    """
    pattern = rf'\[GAP:{gap_index}\]'
    match = re.search(pattern, text)
    
    if not match:
        return ""
    
    start = max(0, match.start() - context_window)
    end = min(len(text), match.end() + context_window)
    
    context = text[start:end].replace(f"[GAP:{gap_index}]", "___")
    return context.strip()

def build_multi_gap_prompt(text: str, gaps: List[GapContext]) -> str:
    """
    Build a prompt showing all gaps with their contexts.
    
    Args:
        text: Full text
        gaps: List of extracted gaps
    
    Returns:
        Formatted prompt showing each gap's context
    """
    prompt_lines = ["Uzupełnij luki w poniższych fragmentach:\n"]
    
    for gap in gaps:
        prompt_lines.append(f"GAP:{gap.index}: {gap.context}")
    
    return "\n".join(prompt_lines)
