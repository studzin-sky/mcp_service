"""
Pydantic schemas for MCP service requests and responses
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class EnhancementRequestBody(BaseModel):
    """Enhancement request schema"""
    domain: str = Field(..., description="Domain (e.g., 'cars')")
    data: Dict[str, Any] = Field(..., description="Data with description field")
    model: Optional[str] = Field("bielik", description="Model to use (bielik, qwen, gemma, etc.)")
    mcp_rules: Dict[str, Any] = Field(default_factory=dict, description="Optional MCP rules")
    
    class Config:
        example = {
            "domain": "cars",
            "data": {
                "description": "Fiat 500 [GAP:1] z [GAP:2] silnikiem, [GAP:3] przebieg",
                "metadata": {"year": 2020}
            },
            "model": "bielik",
            "mcp_rules": {}
        }


class GapInfo(BaseModel):
    """Single gap information"""
    index: int = Field(..., description="Gap number/index")
    choice: str = Field(..., description="Filled word/phrase")
    case: Optional[str] = Field("nominative", description="Polish grammatical case")
    context: Optional[str] = Field(None, description="Gap context")


class GrammarSuggestion(BaseModel):
    """Grammar correction suggestion"""
    gap_index: int
    original: str
    corrected: str
    case: str
    context: str


class ValidationInfo(BaseModel):
    """Validation results"""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EnhancedDescriptionResponse(BaseModel):
    """Enhancement response schema"""
    description: str = Field(..., description="Enhanced description")
    original: Optional[str] = Field(None, description="Original description")
    gaps: List[GapInfo] = Field(default_factory=list, description="Filled gaps")
    alternatives: Dict[int, List[str]] = Field(default_factory=dict, description="Alternative fills per gap")
    model_used: str = Field(..., description="Model used for enhancement")
    generation_time: float = Field(..., description="Time in seconds")
    validation: Optional[ValidationInfo] = Field(None, description="Validation results")
    grammar_suggestions: Optional[List[GrammarSuggestion]] = Field(None, description="Grammar corrections applied")
    
    class Config:
        example = {
            "description": "Fiat 500 biały z benzynowym silnikiem, 120000 przebieg",
            "original": "Fiat 500 [GAP:1] z [GAP:2] silnikiem, [GAP:3] przebieg",
            "gaps": [
                {"index": 1, "choice": "biały", "case": "nominative", "context": ""},
                {"index": 2, "choice": "benzynowy", "case": "instrumental", "context": ""},
                {"index": 3, "choice": "120000", "case": "accusative", "context": ""}
            ],
            "alternatives": {
                1: ["biały", "czarny", "srebrny"],
                2: ["benzynowy", "dieselowy"],
                3: ["120000", "150000"]
            },
            "model_used": "bielik-1.5b",
            "generation_time": 3.45,
            "validation": {
                "valid": True,
                "errors": [],
                "warnings": []
            },
            "grammar_suggestions": []
        }


class BatchEnhancementRequest(BaseModel):
    """Batch enhancement request"""
    items: List[Dict[str, Any]] = Field(..., description="Items to enhance")
    domain: str = Field(..., description="Domain")
    model: Optional[str] = Field("bielik", description="Model to use")
    parallel: Optional[bool] = Field(False, description="Process in parallel")
    batch_id: Optional[str] = Field(None, description="Batch identifier")


class BatchEnhancementResponse(BaseModel):
    """Batch enhancement response"""
    batch_id: Optional[str]
    results: List[Dict[str, Any]]
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary stats")
