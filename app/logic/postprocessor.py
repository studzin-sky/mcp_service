"""
Postprocessor Module - Clean and format enhanced descriptions

Handles:
1. JSON structure validation and fixing
2. Incomplete response reconstruction
3. Formatting and normalization
4. Alternative suggestion generation
5. Output quality assurance
"""

import re
import json
from typing import Dict, List, Any, Tuple, Optional


class PostProcessor:
    """
    Post-processes raw model output to ensure quality and completeness
    """
    
    def __init__(self):
        self.max_alternatives = 3
    
    def process(self, 
                raw_output: str, 
                original_description: str,
                gaps_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process raw model output and return structured enhancement.
        
        Args:
            raw_output: Raw model output (may be partial or malformed)
            original_description: Original description for reference
            gaps_info: List of gap information
            
        Returns:
            Structured enhancement dict
        """
        # Try to parse JSON
        parsed = self._parse_json(raw_output)
        
        if parsed is None:
            # Fallback: extract what we can
            parsed = self._reconstruct_from_raw(raw_output, original_description, gaps_info)
        
        # Clean and validate
        enhanced = self._clean_enhanced_description(
            parsed.get("enhanced_description", "")
        )
        
        # Extract gaps and alternatives
        gaps = parsed.get("gaps", [])
        alternatives = parsed.get("alternatives", {})
        
        # Ensure gaps are properly structured
        gaps = self._normalize_gaps(gaps)
        
        # Generate missing alternatives
        alternatives = self._ensure_alternatives(alternatives, gaps)
        
        return {
            "original_description": original_description,
            "enhanced_description": enhanced,
            "gaps": gaps,
            "alternatives": alternatives,
            "processing_notes": parsed.get("notes", [])
        }
    
    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Try to extract and parse JSON from text.
        
        Handles:
        - Double-escaped JSON
        - Partial JSON
        - Function call wrappers
        """
        # Try direct parsing first
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try double-escaped JSON
        try:
            unescaped = text.encode().decode('unicode_escape')
            return json.loads(unescaped)
        except:
            pass
        
        # Try extracting from function call format
        func_match = re.search(r'function_name\s*=\s*"([^"]+)"\s*,?\s*result\s*=\s*"?({.*})"?', text, re.DOTALL)
        if func_match:
            try:
                json_str = func_match.group(2)
                # Unescape if needed
                json_str = json_str.replace('\\"', '"').replace('\\n', '\n')
                return json.loads(json_str)
            except:
                pass
        
        return None
    
    def _reconstruct_from_raw(self, 
                             raw_output: str,
                             original_description: str,
                             gaps_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reconstruct structured output from raw text when JSON parsing fails.
        """
        # Try to find enhanced description in raw output
        enhanced = raw_output.strip()
        
        # Extract gaps that were filled
        gaps = []
        alternatives = {}
        
        # Look for gap patterns in original and enhanced
        gap_pattern = r'\[GAP:(\d+)\]'
        original_gaps = re.findall(gap_pattern, original_description)
        enhanced_gaps = re.findall(gap_pattern, enhanced)
        
        for gap_info in gaps_info:
            gap_idx = gap_info.get("index", 0)
            gaps.append({
                "index": gap_idx,
                "choice": gap_info.get("choice", ""),
                "case": gap_info.get("case", "nominative")
            })
        
        return {
            "original_description": original_description,
            "enhanced_description": enhanced,
            "gaps": gaps,
            "alternatives": alternatives,
            "notes": ["Reconstructed from raw output"]
        }
    
    def _clean_enhanced_description(self, text: str) -> str:
        """
        Clean and normalize enhanced description.
        
        Removes:
        - Extra whitespace
        - Invalid characters
        - Incomplete sentences
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove common placeholder patterns
        text = re.sub(r'\[GAP:\d+\]', '', text)
        text = re.sub(r'___+', '', text)
        
        # Clean up double punctuation
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',{2,}', ',', text)
        
        # Ensure proper spacing around punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.,!?;:])\s*\)', r'\1)', text)
        text = re.sub(r'\(\s+', r'(', text)
        
        return text.strip()
    
    def _normalize_gaps(self, gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize gap structure to consistent format.
        """
        normalized = []
        
        for gap in gaps:
            if isinstance(gap, dict):
                normalized.append({
                    "index": gap.get("index", 0),
                    "choice": gap.get("choice", "").strip(),
                    "case": gap.get("case", gap.get("required_case", "nominative")),
                    "context": gap.get("context", "")
                })
        
        return normalized
    
    def _ensure_alternatives(self, 
                            alternatives: Dict[int, List[str]], 
                            gaps: List[Dict[str, Any]]) -> Dict[int, List[str]]:
        """
        Ensure each gap has alternatives, generating defaults if needed.
        """
        result = alternatives.copy() if alternatives else {}
        
        # Ensure all gaps have alternatives
        for gap in gaps:
            gap_idx = gap.get("index", 0)
            
            if gap_idx not in result:
                # Generate default alternatives based on choice
                choice = gap.get("choice", "")
                result[gap_idx] = [choice] if choice else []
            
            # Ensure we have at least one alternative
            if not result[gap_idx]:
                choice = gap.get("choice", "")
                if choice:
                    result[gap_idx] = [choice]
        
        return result
    
    def generate_alternatives(self, gap_choice: str, context: str, count: int = 3) -> List[str]:
        """
        Generate alternative words for a gap fill.
        
        This is a basic implementation. In production, would use language model.
        """
        # For now, return just the original choice
        # In real system, would call model for alternatives
        return [gap_choice] * min(count, 1)  # Return original once
    
    def validate_and_fix(self, 
                        data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate structure and fix common issues.
        
        Returns:
            (fixed_data, issues_found)
        """
        issues = []
        
        # Check required fields
        required = ["original_description", "enhanced_description", "gaps", "alternatives"]
        for field in required:
            if field not in data:
                data[field] = "" if field == "enhanced_description" or field == "original_description" else ([] if field == "gaps" else {})
                issues.append(f"Missing field '{field}', initialized to default")
        
        # Check no gap markers remain
        enhanced = data.get("enhanced_description", "")
        if re.search(r'\[GAP:\d+\]', enhanced):
            issues.append("Warning: Enhanced description still contains [GAP:n] markers")
        
        # Ensure proper types
        if not isinstance(data.get("gaps"), list):
            data["gaps"] = []
            issues.append("Gaps not a list, reset to empty")
        
        if not isinstance(data.get("alternatives"), dict):
            data["alternatives"] = {}
            issues.append("Alternatives not a dict, reset to empty")
        
        return data, issues


def create_final_output(
    original: str,
    enhanced: str,
    gaps: List[Dict[str, Any]],
    alternatives: Dict[int, List[str]],
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create final structured output for enhancement.
    """
    return {
        "original_description": original,
        "enhanced_description": enhanced,
        "gaps": gaps,
        "alternatives": alternatives,
        "stats": {
            "gaps_filled": len(gaps),
            "original_length": len(original),
            "enhanced_length": len(enhanced),
            "expansion_percent": round((len(enhanced) - len(original)) / len(original) * 100, 1) if original else 0
        },
        "metadata": metadata or {}
    }
