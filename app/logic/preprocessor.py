"""
Preprocessor Module - Data normalization and context extraction

Handles:
1. Text normalization (case, spacing, special chars)
2. Gap detection and analysis  
3. Context extraction around gaps
4. Domain-specific enrichment
5. Metadata preparation for model
"""

import re
from typing import Dict, List, Any, Tuple, Optional


class TextPreprocessor:
    """
    Preprocesses descriptions for enhancement
    """
    
    def __init__(self, domain: str = "cars"):
        self.domain = domain
        self.gap_pattern = r'\[GAP:(\d+)\]|_+'
    
    def preprocess(self, text: str, normalize: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Preprocess text and extract gap information.
        
        Returns:
            (processed_text, gaps_info)
        """
        if normalize:
            text = self._normalize_text(text)
        
        gaps_info = self._extract_gaps(text)
        
        return text, gaps_info
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text: fix spacing, capitalization, special chars.
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.!?])\s+', r'\1 ', text)
        
        # Fix spacing around parentheses
        text = re.sub(r'\s*\(\s*', ' (', text)
        text = re.sub(r'\s*\)\s*', ') ', text)
        
        # Normalize quotes
        text = re.sub(r'['′`]', "'", text)
        text = re.sub(r'[""„"]', '"', text)
        
        return text.strip()
    
    def _extract_gaps(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract gap information from text.
        
        Returns list of:
        {
            "index": 1,
            "position": 45,
            "context_before": "kolor",
            "context_after": "auta",
            "required_case": "locative"
        }
        """
        gaps = []
        
        # Find all gaps - both [GAP:n] and ___ patterns
        for match in re.finditer(r'\[GAP:(\d+)\]', text):
            gap_idx = int(match.group(1))
            pos = match.start()
            gaps.append(self._analyze_gap(text, pos, gap_idx))
        
        # Handle underscores (auto-numbered)
        for match in re.finditer(r'_{2,}', text):
            # Assign auto-number based on position
            auto_idx = len([g for g in gaps if g["position"] < match.start()]) + 1
            pos = match.start()
            gaps.append(self._analyze_gap(text, pos, auto_idx))
        
        return sorted(gaps, key=lambda g: g["position"])
    
    def _analyze_gap(self, text: str, position: int, gap_idx: int) -> Dict[str, Any]:
        """
        Analyze context around a single gap.
        """
        # Get context (30 chars before and after)
        start = max(0, position - 30)
        end = min(len(text), position + 30)
        
        context_before = text[start:position].strip()
        context_after = text[position:end].strip()
        
        # Detect required case
        required_case = self._detect_case(text, position)
        
        # Detect position type (beginning, middle, end)
        position_type = "middle"
        if position < 50:
            position_type = "beginning"
        elif position > len(text) - 50:
            position_type = "end"
        
        # Extract metadata for domain
        metadata = self._extract_metadata(context_before, context_after)
        
        return {
            "index": gap_idx,
            "position": position,
            "context_before": context_before,
            "context_after": context_after,
            "required_case": required_case,
            "position_type": position_type,
            "metadata": metadata
        }
    
    def _detect_case(self, text: str, position: int) -> str:
        """
        Detect required grammatical case based on surrounding context.
        """
        # Get surrounding text
        before = text[max(0, position - 50):position].lower()
        after = text[position:min(len(text), position + 50)].lower()
        context = before + " " + after
        
        # Case indicators
        case_patterns = {
            "locative": [r"w\s+\w+", r"na\s+\w+", r"o\s+\w+", r"przy\s+\w+"],
            "instrumental": [r"z\s+\w+", r"ze\s+\w+", r"przed\s+\w+"],
            "genitive": [r"bez\s+\w+", r"od\s+\w+", r"dla\s+\w+"],
            "dative": [r"do\s+\w+", r"dla\s+\w+"],
            "accusative": [r"ma\s+\w+", r"posiada\s+\w+"],
        }
        
        for case, patterns in case_patterns.items():
            for pattern in patterns:
                if re.search(pattern, context):
                    return case
        
        return "nominative"  # Default
    
    def _extract_metadata(self, context_before: str, context_after: str) -> Dict[str, str]:
        """
        Extract useful metadata from gap context (domain-specific).
        """
        metadata = {}
        
        if self.domain == "cars":
            # Car-specific metadata extraction
            
            # Color context
            if re.search(r'kolor|farb', context_before, re.I):
                metadata["type"] = "color"
                metadata["object"] = "color"
            
            # Engine context
            elif re.search(r'silnik|paliwo|napęd', context_before, re.I):
                metadata["type"] = "engine_feature"
            
            # Body type
            elif re.search(r'sedan|suv|hatchback|combi|van|kabriolet|coupe', context_before, re.I):
                metadata["type"] = "body_type"
            
            # Condition
            elif re.search(r'stan|zadbany|uszkodze|wy|wylegitymowany', context_before, re.I):
                metadata["type"] = "condition"
            
            # Features
            elif re.search(r'wyposażen|opcje|funkcje|system|ekran', context_before, re.I):
                metadata["type"] = "features"
        
        return metadata
    
    def prepare_for_model(self, 
                         text: str, 
                         gaps_info: List[Dict[str, Any]],
                         domain: str = "cars") -> Dict[str, Any]:
        """
        Prepare text and context for language model processing.
        """
        # Build prompt context
        prompt_context = {
            "original_text": text,
            "gaps_count": len(gaps_info),
            "gaps_details": gaps_info,
            "domain": domain,
            "language": "Polish"
        }
        
        # Add domain-specific hints
        if domain == "cars":
            prompt_context["hints"] = {
                "preferred_tenses": ["present", "past_perfect"],
                "tone": "professional, concise",
                "focus": "factual, technical details"
            }
        
        return prompt_context


def preprocess_data(data: Dict[str, Any], domain: str = "cars") -> Dict[str, Any]:
    """
    Main preprocessing function for enhancement requests.
    
    Args:
        data: Request data with description and metadata
        domain: Domain context (cars, products, etc.)
        
    Returns:
        Preprocessed data ready for model
    """
    preprocessor = TextPreprocessor(domain)
    
    description = data.get("description", "")
    
    # Normalize text
    normalized, gaps_info = preprocessor.preprocess(description)
    
    # Prepare for model
    model_context = preprocessor.prepare_for_model(normalized, gaps_info, domain)
    
    return {
        "original_description": description,
        "normalized_description": normalized,
        "gaps": gaps_info,
        "model_context": model_context,
        "domain": domain,
        "metadata": data.get("metadata", {})
    }
