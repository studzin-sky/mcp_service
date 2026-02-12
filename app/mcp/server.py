"""
FastAPI-based MCP Protocol Server

Integrates MCP tools into FastAPI app as JSON-RPC endpoints.
Provides both traditional REST and MCP protocol access.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app.mcp import MCPTools, MCPResources
from app.logic.bielik_client import BielikClient
from app.logic.text_analyzer import TextAnalyzer


# ============== MCP Request/Response Schemas ==============

class MCPToolCall(BaseModel):
    """MCP tool call request (JSON-RPC style)"""
    jsonrpc: str = "2.0"
    method: str  # "fill_gaps", "analyze_ad", "validate_fill"
    params: Dict[str, Any]
    id: int = 1


class MCPResourceRequest(BaseModel):
    """MCP resource request"""
    resource: str  # "available_models", "ad_schemas", "supported_domains"


# ============== MCP Server Router ==============

def create_mcp_router(bielik_client: BielikClient) -> APIRouter:
    """Create MCP protocol endpoints"""
    router = APIRouter(prefix="/mcp", tags=["mcp"])

    # Initialize tools and resources
    text_analyzer = TextAnalyzer()
    tools = MCPTools(bielik_client, text_analyzer)
    resources = MCPResources()

    # ============== MCP Tools ==============

    @router.post("/tools/fill_gaps")
    async def fill_gaps_endpoint(
        ad_text: str,
        model: str = "bielik-1.5b-transformer",
        gaps_notation: str = "auto"
    ) -> Dict[str, Any]:
        """
        REST endpoint for gap-filling tool.
        Also accessible via JSON-RPC at /mcp/call with method="fill_gaps"
        """
        return await tools.fill_gaps(ad_text, model, gaps_notation)

    @router.post("/tools/analyze_ad")
    async def analyze_ad_endpoint(ad_text: str) -> Dict[str, Any]:
        """
        REST endpoint for analyzing ad.
        Also accessible via JSON-RPC at /mcp/call with method="analyze_ad"
        """
        return await tools.analyze_ad(ad_text)

    @router.post("/tools/validate_fill")
    async def validate_fill_endpoint(
        original_text: str,
        filled_text: str,
        filled_gaps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        REST endpoint for validating filled text.
        Also accessible via JSON-RPC at /mcp/call with method="validate_fill"
        """
        return await tools.validate_fill(original_text, filled_text, filled_gaps)

    # ============== JSON-RPC Endpoint ==============

    @router.post("/call")
    async def mcp_call(request: MCPToolCall) -> Dict[str, Any]:
        """
        JSON-RPC style tool calls.

        Example:
        {
            "jsonrpc": "2.0",
            "method": "fill_gaps",
            "params": {
                "ad_text": "Piękny [GAP:1] samochód",
                "model": "bielik-1.5b-transformer"
            },
            "id": 1
        }
        """
        try:
            if request.method == "fill_gaps":
                result = await tools.fill_gaps(**request.params)
            elif request.method == "analyze_ad":
                result = await tools.analyze_ad(**request.params)
            elif request.method == "validate_fill":
                result = await tools.validate_fill(**request.params)
            else:
                raise ValueError(f"Unknown method: {request.method}")

            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request.id
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": str(e)
                },
                "id": request.id
            }

    # ============== MCP Resources ==============

    @router.get("/resources/models")
    async def get_available_models() -> Dict[str, Any]:
        """Get list of available Bielik models"""
        return resources.available_models()

    @router.get("/resources/schemas")
    async def get_ad_schemas() -> Dict[str, Any]:
        """Get ad type schemas and patterns"""
        return resources.ad_schemas()

    @router.get("/resources/domains")
    async def get_supported_domains() -> Dict[str, Any]:
        """Get supported content domains"""
        return resources.supported_domains()

    # ============== Health & Metadata ==============

    @router.get("/health")
    async def mcp_health() -> Dict[str, Any]:
        """MCP server health check"""
        return {
            "status": "ok",
            "service": "MCP Protocol Server",
            "tools": ["fill_gaps", "analyze_ad", "validate_fill"],
            "resources": ["available_models", "ad_schemas", "supported_domains"],
            "version": "1.0.0"
        }

    return router
