from pydantic import BaseModel, Field
from typing import Dict, Any, List

class InfillItem(BaseModel):
    id: str = Field(..., description="Unique identifier for the item")
    text_with_gaps: str = Field(..., description="Text with [GAP:n] markers")

class InfillOptions(BaseModel):
    language: str = Field(default="pl", description="Language code (pl/en)")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_new_tokens: int = Field(default=300, description="Max tokens to generate")
    top_n_per_gap: int = Field(default=2, description="Number of alternatives per gap")

class EnhancementRequestBody(BaseModel):
    domain: str = Field(..., description="The domain for the enhancement (e.g., 'cars')")
    model: str = Field(..., description="Model to use (e.g., 'bielik-1.5b')")
    items: List[InfillItem] = Field(..., description="Items to process")
    options: InfillOptions = Field(default_factory=InfillOptions, description="Generation options")

class EnhancedDescriptionResponse(BaseModel):
    domain: str
    model: str
    items: List[Dict[str, Any]]
    processing_time_ms: float
    status: str = "success"
