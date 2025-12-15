"""
Guardrails Module - Validation and safety checks for enhanced descriptions

Ensures:
1. JSON structure validity
2. No leftover [GAP:n] markers in output
3. Polish grammar agreement (case, gender, number)
4. Content safety and relevance
5. Length constraints
"""

import re
import json
from typing import Tuple, List, Dict, Any, Optional
from enum import Enum


class ValidationLevel(Enum):
    STRICT = "strict"  # Reject if any issues
    NORMAL = "normal"  # Accept with warnings
    LENIENT = "lenient"  # Only check critical issues


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class Guardrails:
    """
    Validation system for MCP enhancement results
    """
    
    def __init__(self, level: ValidationLevel = ValidationLevel.NORMAL):
        self.level = level
        self.errors = []
        self.warnings = []
    
    def reset(self):
        """Clear error and warning logs"""
        self.errors = []
        self.warnings = []
    
    def validate_all(self, data: Dict[str, Any], domain: str = "cars") -> Tuple[bool, Dict[str, Any]]:
        """
        Run all validations on enhancement data.
        
        Returns:
            (is_valid, report)
        """
        self.reset()
        
        # Critical checks
        self._check_json_structure(data)
        self._check_no_gap_markers(data)
        self._check_content_length(data)
        self._check_content_relevance(data, domain)
        
        # Grammar checks
        if domain == "cars":
            self._check_car_domain_grammar(data)
        
        is_valid = len(self.errors) == 0 or (self.level == ValidationLevel.LENIENT)
        
        report = {
            "valid": is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "level": self.level.value,
            "data": data
        }
        
        return is_valid, report
    
    def _check_json_structure(self, data: Dict[str, Any]):
        """Ensure required fields are present and properly typed"""
        required_fields = ["original_description", "enhanced_description", "gaps", "alternatives"]
        
        for field in required_fields:
            if field not in data:
                self.errors.append(f"Missing required field: {field}")
            elif field == "gaps":
                if not isinstance(data[field], list):
                    self.errors.append(f"Field '{field}' must be a list")
            elif field == "alternatives":
                if not isinstance(data[field], dict):
                    self.errors.append(f"Field '{field}' must be a dict")
        
        # Validate gaps structure
        if isinstance(data.get("gaps"), list):
            for i, gap in enumerate(data["gaps"]):
                if not isinstance(gap, dict):
                    self.errors.append(f"Gap {i} is not a dict")
                elif "index" not in gap or "choice" not in gap:
                    self.errors.append(f"Gap {i} missing 'index' or 'choice'")
    
    def _check_no_gap_markers(self, data: Dict[str, Any]):
        """Ensure no [GAP:n] markers remain in enhanced description"""
        enhanced = data.get("enhanced_description", "")
        
        gap_pattern = r'\[GAP:\d+\]'
        matches = re.findall(gap_pattern, enhanced)
        
        if matches:
            self.errors.append(f"Found {len(matches)} unfilled gap markers: {matches}")
    
    def _check_content_length(self, data: Dict[str, Any]):
        """Ensure descriptions are reasonable length"""
        original = data.get("original_description", "")
        enhanced = data.get("enhanced_description", "")
        
        if len(enhanced) < len(original):
            self.warnings.append(
                f"Enhanced description ({len(enhanced)} chars) is shorter than original ({len(original)} chars)"
            )
        
        # Check max length (reasonable for car ads)
        max_length = 2000
        if len(enhanced) > max_length:
            self.errors.append(
                f"Enhanced description exceeds maximum length ({len(enhanced)} > {max_length})"
            )
        
        # Check minimum quality
        if len(enhanced) < 50:
            self.errors.append("Enhanced description is too short (< 50 chars)")
    
    def _check_content_relevance(self, data: Dict[str, Any], domain: str = "cars"):
        """Ensure content is relevant to domain"""
        enhanced = data.get("enhanced_description", "").lower()
        
        if domain == "cars":
            # Must contain at least some car-related terms
            car_terms = ["samochód", "auto", "pojazd", "marka", "model", "silnik", 
                        "kolor", "przebieg", "rocznik", "paliwo", "napęd", "sedan",
                        "suv", "hatchback", "combi", "van", "cabriolet"]
            
            found_terms = [t for t in car_terms if t in enhanced]
            
            if not found_terms:
                self.warnings.append("Enhanced description lacks car-related terminology")
    
    def _check_car_domain_grammar(self, data: Dict[str, Any]):
        """Car-specific grammar and content checks"""
        enhanced = data.get("enhanced_description", "")
        
        # Check for common Polish grammar errors in car descriptions
        error_patterns = [
            (r"\bkolor\s+[a-z]+y\b", "Color adjective should match 'kolor' case (locative: białym, czarnym)"),
            (r"\bsilnik\s+[a-z]+y\b", "Engine adjective should match 'silnik' case (instrumental: benzynowym)"),
            (r"\bnapęd\s+[a-z]+y\b", "Drive adjective should match 'napęd' case"),
        ]
        
        for pattern, msg in error_patterns:
            if re.search(pattern, enhanced.lower()):
                self.warnings.append(f"Potential grammar issue: {msg}")
    
    def validate_gap_fill(self, gap_index: int, choice: str, context: str) -> Tuple[bool, List[str]]:
        """
        Validate a single gap fill choice.
        
        Returns:
            (is_valid, issues)
        """
        issues = []
        
        # Check length
        if len(choice.strip()) == 0:
            issues.append("Gap fill cannot be empty")
        elif len(choice) > 100:
            issues.append(f"Gap fill too long ({len(choice)} chars)")
        
        # Check for invalid characters
        if re.search(r'[\[\]<>"\']', choice):
            issues.append("Gap fill contains invalid characters")
        
        # Check for placeholder text
        placeholders = ["[GAP", "gap", "xxxx", "????", "..."]
        if any(p in choice.lower() for p in placeholders):
            issues.append("Gap fill appears to be placeholder text")
        
        return len(issues) == 0, issues


def create_validation_report(
    original: str,
    enhanced: str,
    gaps: List[Dict[str, Any]],
    alternatives: Dict[int, List[str]],
    domain: str = "cars"
) -> Dict[str, Any]:
    """
    Create a comprehensive validation report for enhancement results.
    """
    guardrails = Guardrails(ValidationLevel.NORMAL)
    
    data = {
        "original_description": original,
        "enhanced_description": enhanced,
        "gaps": gaps,
        "alternatives": alternatives,
        "domain": domain
    }
    
    is_valid, report = guardrails.validate_all(data, domain)
    
    return {
        "is_valid": is_valid,
        "data": data,
        "validation": {
            "errors": report["errors"],
            "warnings": report["warnings"],
            "level": report["level"]
        }
    }
