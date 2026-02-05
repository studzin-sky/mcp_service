# mcp_service/app/logic/postprocessor.py

from typing import List, Dict, Any
from .gap_extractor import extract_gaps

def apply_fills(original_text: str, fills: Dict[int, str]) -> str:
    """
    Apply gap fills to original text.
    
    Args:
        original_text: Original text with [GAP:n] markers
        fills: Dict mapping gap index to fill choice {1: "word", ...}
               
    Returns:
        Text with gaps replaced by fill choices
    """
    if not fills:
        return original_text
        
    gaps = extract_gaps(original_text)
    if not gaps:
        return original_text
    
    # Process from end to start to preserve positions
    result = original_text
    # Sort gaps reversed by position
    sorted_gaps = sorted(gaps, key=lambda g: g.char_position, reverse=True)
    
    for gap in sorted_gaps:
        if gap.index in fills:
            # Clean the fill choice
            fill_text = fills[gap.index]
            # Remove [GAP:n] markers if present in the fill
            import re
            fill_text = re.sub(r'\[GAP:\d+\]', '', fill_text).strip()
            
            # gap.char_position is the start of the marker
            start = gap.char_position
            end = start + len(gap.marker)
            result = result[:start] + fill_text + result[end:]
    
    return result

def format_output(description: str, rules: dict) -> str:
    """
    Formats the final output description based on a set of rules.
    """
    print("MCP: Running postprocessor...")
    
    formatted_description = description.strip()
    
    # Add a closing statement if defined in the rules
    closing_statement = rules.get("closing_statement")
    if closing_statement and not formatted_description.endswith(closing_statement):
        formatted_description = f"{formatted_description}\n\n{closing_statement}"
        
    print("Post-processing complete.")
    return formatted_description
