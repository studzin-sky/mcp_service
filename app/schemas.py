from pydantic import BaseModel, Field
from typing import Dict, Any

class EnhancementRequestBody(BaseModel):
    domain: str = Field(..., description="The domain for the enhancement (e.g., 'cars').")
    data: Dict[str, Any] = Field(..., description="The data to be enhanced.")
    mcp_rules: Dict[str, Any] = Field({}, description="Optional MCP rules to apply.")

class EnhancedDescriptionResponse(BaseModel):
    description: str
    model_used: str
    generation_time: float
